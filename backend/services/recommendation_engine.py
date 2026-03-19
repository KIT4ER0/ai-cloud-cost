import os
import yaml
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from .. import models

RULES_FILE_PATH = os.path.join(os.path.dirname(__file__), "rules.yml")

class RecommendationEngine:
    def __init__(self, db: Session, profile_id: int):
        self.db = db
        self.profile_id = profile_id
        self.rules = self._load_rules()
        self.today = date.today()

    def _load_rules(self):
        try:
            with open(RULES_FILE_PATH, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                return data.get('rules', {})
        except Exception as e:
            print(f"Error loading rules.yml: {e}")
            return {}

    def run_all(self):
        if not self.rules:
            print("No rules loaded. Skipping engine run.")
            return

        self._evaluate_ec2()
        self._evaluate_s3()
        self._evaluate_rds()
        self._evaluate_lambda()
        self._evaluate_alb()
        
        self.db.commit()
        print("Recommendation Engine finished successfully.")

    def _sanitize(self, details: dict) -> dict:
        """แปลง Decimal และ float ทุกตัวใน dict ให้เป็น float ปกติก่อนส่งเข้า JSONB"""
        from decimal import Decimal
        return {k: float(v) if isinstance(v, (Decimal, float)) else v for k, v in details.items()}

    def _create_or_update_rec(self, account_id, region, service, resource_key, rec_type, details, confidence, est_saving_usd=0.0):
        details = self._sanitize(details)
        existing = self.db.query(models.Recommendation).filter(
            models.Recommendation.profile_id == self.profile_id,
            models.Recommendation.account_id == account_id,
            models.Recommendation.region == region,
            models.Recommendation.service == service,
            models.Recommendation.resource_key == resource_key,
            models.Recommendation.rec_type == rec_type,
            models.Recommendation.status == "open"
        ).first()

        if existing:
            existing.details = details
            existing.confidence = confidence
            existing.est_saving_usd = est_saving_usd
        else:
            rec = models.Recommendation(
                profile_id=self.profile_id,
                rec_date=self.today,
                account_id=account_id,
                region=region,
                service=service,
                resource_key=resource_key,
                rec_type=rec_type,
                details=details,
                confidence=confidence,
                status="open"
            )
            self.db.add(rec)

    def _evaluate_ec2(self):
        seven_days_ago = self.today - timedelta(days=7)
        
        # 1. EC2_RIGHTSIZE_CPU_LOW
        rule = self.rules.get('EC2_RIGHTSIZE_CPU_LOW', {})
        if rule.get('enabled'):
            t_val = rule.get('cpu_p99_7d_lt', 20)
            subq = self.db.query(
                models.EC2Metric.ec2_resource_id,
                func.max(models.EC2Metric.cpu_p99).label('max_cpu')
            ).filter(models.EC2Metric.metric_date >= seven_days_ago).group_by(models.EC2Metric.ec2_resource_id).subquery()
            
            resources = self.db.query(models.EC2Resource, subq.c.max_cpu).join(
                subq, models.EC2Resource.ec2_resource_id == subq.c.ec2_resource_id
            ).filter(subq.c.max_cpu < t_val).all()
            
            for res, val in resources:
                # ลด size ครึ่งนึง คร่าวๆ ประหยัด 50% ของราคา On-Demand. แต่ถ้าไม่มีข้อมูล สมมติเซฟ $20/mo
                est_save = (res.on_demand_price_hr * 730 * 0.5) if hasattr(res, 'on_demand_price_hr') and res.on_demand_price_hr else 20.0
                self._create_or_update_rec(res.account_id, res.region, "EC2", res.instance_id, "EC2_RIGHTSIZE_CPU_LOW", {"max_cpu_p99": val}, rule.get('confidence', 0.85), est_save)

        # 2. EC2_IDLE_STOPPED
        rule = self.rules.get('EC2_IDLE_STOPPED', {})
        if rule.get('enabled'):
            subq = self.db.query(
                models.EC2Metric.ec2_resource_id,
                func.sum(models.EC2Metric.hours_running).label('total_hours')
            ).filter(models.EC2Metric.metric_date >= seven_days_ago).group_by(models.EC2Metric.ec2_resource_id).subquery()
            
            resources = self.db.query(models.EC2Resource, subq.c.total_hours).join(
                subq, models.EC2Resource.ec2_resource_id == subq.c.ec2_resource_id
            ).filter(subq.c.total_hours == 0).all()
            
            for res, val in resources:
                est_save = (res.on_demand_price_hr * 730) if hasattr(res, 'on_demand_price_hr') and res.on_demand_price_hr else 30.0
                self._create_or_update_rec(res.account_id, res.region, "EC2", res.instance_id, "EC2_IDLE_STOPPED", {"running_hours_7d": val}, rule.get('confidence', 0.95), est_save)

        # 3. EC2_EIP_UNASSOCIATED
        rule = self.rules.get('EC2_EIP_UNASSOCIATED', {})
        if rule.get('enabled'):
            t_val = rule.get('hours_idle_7d_gt', 24)
            subq = self.db.query(
                models.EC2EIPCost.eip_id,
                func.sum(models.EC2EIPCost.hours_idle).label('total_idle')
            ).filter(models.EC2EIPCost.usage_date >= seven_days_ago).group_by(models.EC2EIPCost.eip_id).subquery()
            
            eips = self.db.query(models.EC2ElasticIP, subq.c.total_idle).join(
                subq, models.EC2ElasticIP.eip_id == subq.c.eip_id
            ).filter(subq.c.total_idle > t_val, models.EC2ElasticIP.profile_id == self.profile_id).all()
            
            for res, val in eips:
                # EIP ไม่ได้ผูกเครื่อง เสียเงิน $0.005/h ประมาณ $3.60/เดือน
                est_save = 3.60
                self._create_or_update_rec(res.account_id, res.region, "EC2_EIP", res.public_ip, "EC2_EIP_UNASSOCIATED", {"idle_hours_7d": val}, rule.get('confidence', 0.95), est_save)

        # 4. EC2_EBS_UNATTACHED
        rule = self.rules.get('EC2_EBS_UNATTACHED', {})
        if rule.get('enabled'):
            # This requires access to account/region. EBS volume model has resource_id relation.
            volumes = self.db.query(models.EC2EBSVolume, models.EC2Resource).join(
                models.EC2Resource, models.EC2EBSVolume.ec2_resource_id == models.EC2Resource.ec2_resource_id
            ).filter(models.EC2EBSVolume.state == "available").all()
            
            for vol, res in volumes:
                # เผื่อ gp2/gp3 ราคา 0.08 - 0.10 ต่อ GB
                est_save = vol.size_gb * 0.08 if vol.size_gb else 5.0
                self._create_or_update_rec(res.account_id, res.region, "EBS", str(vol.ebs_volume_id), "EC2_EBS_UNATTACHED", {"state": vol.state}, rule.get('confidence', 0.95), est_save)

        # 5. EC2_EBS_SNAPSHOT_OLD
        rule = self.rules.get('EC2_EBS_SNAPSHOT_OLD', {})
        if rule.get('enabled'):
            t_val = rule.get('age_days_gt', 30)
            snaps = self.db.query(models.EC2EBSSnapshot, models.EC2Resource).join(
                models.EC2Resource, models.EC2EBSSnapshot.ec2_resource_id == models.EC2Resource.ec2_resource_id
            ).filter(models.EC2EBSSnapshot.age_days > t_val).all()
            
            for snap, res in snaps:
                # EBS Snapshot เก็บราคา ~ $0.05 ต่อ GB
                est_save = snap.size_gb * 0.05 if snap.size_gb else 1.0
                self._create_or_update_rec(res.account_id, res.region, "EBS_SNAPSHOT", str(snap.ebs_snapshot_id), "EC2_EBS_SNAPSHOT_OLD", {"age_days": snap.age_days}, rule.get('confidence', 0.9), est_save)

        # Data Transfer Rules based on EC2 Metrics
        thirty_days_ago = self.today - timedelta(days=30)
        
        # DT_CROSS_AZ_WASTE
        rule = self.rules.get('DT_CROSS_AZ_WASTE', {})
        if rule.get('enabled'):
            t_val = rule.get('network_cross_az_gb_30d_gt', 100)
            subq = self.db.query(
                models.EC2Metric.ec2_resource_id,
                func.sum(models.EC2Metric.network_cross_az_gb).label('total_az')
            ).filter(models.EC2Metric.metric_date >= thirty_days_ago).group_by(models.EC2Metric.ec2_resource_id).subquery()
            
            resources = self.db.query(models.EC2Resource, subq.c.total_az).join(
                subq, models.EC2Resource.ec2_resource_id == subq.c.ec2_resource_id
            ).filter(subq.c.total_az > t_val).all()
            
            for res, val in resources:
                # ข้าม AZ ปกติ ~$0.01 ต่อ GB
                est_save = val * 0.01 if val else 0
                self._create_or_update_rec(res.account_id, res.region, "EC2_DT", res.instance_id, "DT_CROSS_AZ_WASTE", {"cross_az_gb_30d": val}, rule.get('confidence', 0.85), est_save)

        # DT_HIGH_INTERNET_EGRESS
        rule = self.rules.get('DT_HIGH_INTERNET_EGRESS', {})
        if rule.get('enabled'):
            t_val = rule.get('network_egress_gb_30d_gt', 500)
            subq = self.db.query(
                models.EC2Metric.ec2_resource_id,
                func.sum(models.EC2Metric.network_egress_gb).label('total_egress')
            ).filter(models.EC2Metric.metric_date >= thirty_days_ago).group_by(models.EC2Metric.ec2_resource_id).subquery()
            
            resources = self.db.query(models.EC2Resource, subq.c.total_egress).join(
                subq, models.EC2Resource.ec2_resource_id == subq.c.ec2_resource_id
            ).filter(subq.c.total_egress > t_val).all()
            
            for res, val in resources:
                # ปกติ Data egress = ~$0.09 ถ้าใช้ CDN อาจเหลือ $0.02 ประหยัด $0.07/GB
                est_save = val * 0.07 if val else 0
                self._create_or_update_rec(res.account_id, res.region, "EC2_DT", res.instance_id, "DT_HIGH_INTERNET_EGRESS", {"egress_gb_30d": val}, rule.get('confidence', 0.8), est_save)

    def _evaluate_s3(self):
        thirty_days_ago = self.today - timedelta(days=30)
        
        # 4. S3_EMPTY_BUCKET
        rule = self.rules.get('S3_EMPTY_BUCKET', {})
        if rule.get('enabled'):
            # We look at the latest metric for each bucket
            subq = self.db.query(
                models.S3Metric.s3_resource_id,
                func.max(models.S3Metric.metric_date).label('latest')
            ).group_by(models.S3Metric.s3_resource_id).subquery()
            
            metrics = self.db.query(models.S3Metric, models.S3Resource).join(
                models.S3Resource, models.S3Metric.s3_resource_id == models.S3Resource.s3_resource_id
            ).join(
                subq, (models.S3Metric.s3_resource_id == subq.c.s3_resource_id) & (models.S3Metric.metric_date == subq.c.latest)
            ).filter(models.S3Metric.bucket_size_bytes == 0, models.S3Metric.number_of_objects == 0).all()
            
            for m, res in metrics:
                self._create_or_update_rec(res.account_id, res.region, "S3", res.bucket_name, "S3_EMPTY_BUCKET", {"size_bytes": 0, "objects": 0}, rule.get('confidence', 0.95), 0.0)

        # S3_LIFECYCLE_COLD
        rule = self.rules.get('S3_LIFECYCLE_COLD', {})
        if rule.get('enabled'):
            req_0 = rule.get('get_requests_30d_eq', 0)
            down_0 = rule.get('bytes_downloaded_30d_eq', 0)
            min_size = rule.get('bucket_size_bytes_gt', 104857600)
            subq = self.db.query(
                models.S3Metric.s3_resource_id,
                func.sum(models.S3Metric.get_requests).label('sum_get'),
                func.sum(models.S3Metric.bytes_downloaded).label('sum_down'),
                func.max(models.S3Metric.bucket_size_bytes).label('max_size')
            ).filter(models.S3Metric.metric_date >= thirty_days_ago).group_by(models.S3Metric.s3_resource_id).subquery()
            
            resources = self.db.query(models.S3Resource, subq.c.max_size).join(
                subq, models.S3Resource.s3_resource_id == subq.c.s3_resource_id
            ).filter(subq.c.sum_get == req_0, subq.c.sum_down == down_0, subq.c.max_size > min_size).all()
            for res, sz in resources:
                # ย้ายลง IA หรือ Glacier ลดราคาได้ราว 40-60% สมมติ Storage Standard S3 = $0.023/GB, Glacier = $0.004/GB -> Save ~$0.019/GB
                gb_size = sz / (1024**3) if sz else 0
                est_save = gb_size * 0.019
                self._create_or_update_rec(res.account_id, res.region, "S3", res.bucket_name, "S3_LIFECYCLE_COLD", {"max_size": sz}, rule.get('confidence', 0.9), est_save)

        # S3_ARCHIVE_PATTERN
        rule = self.rules.get('S3_ARCHIVE_PATTERN', {})
        if rule.get('enabled'):
            fourteen_days_ago = self.today - timedelta(days=14)
            gt_puts = rule.get('put_requests_14d_gt', 50)
            eq_gets = rule.get('get_requests_14d_eq', 0)
            subq = self.db.query(
                models.S3Metric.s3_resource_id,
                func.sum(models.S3Metric.put_requests).label('sum_put'),
                func.sum(models.S3Metric.get_requests).label('sum_get')
            ).filter(models.S3Metric.metric_date >= fourteen_days_ago).group_by(models.S3Metric.s3_resource_id).subquery()
            resources = self.db.query(models.S3Resource, subq.c.sum_put).join(
                subq, models.S3Resource.s3_resource_id == subq.c.s3_resource_id
            ).filter(subq.c.sum_put > gt_puts, subq.c.sum_get == eq_gets).all()
            for res, puts in resources:
                est_save = 10.0 # ยากที่จะคำนวณแบบจำเพาะเจาะจง ให้ค่ากลางไว้
                self._create_or_update_rec(res.account_id, res.region, "S3", res.bucket_name, "S3_ARCHIVE_PATTERN", {"puts_14d": puts}, rule.get('confidence', 0.85), est_save)

        # S3_HUGE_ABANDONED
        rule = self.rules.get('S3_HUGE_ABANDONED', {})
        if rule.get('enabled'):
            min_size = rule.get('bucket_size_bytes_gt', 10737418240)
            eq_puts = rule.get('put_requests_30d_eq', 0)
            eq_gets = rule.get('get_requests_30d_eq', 0)
            subq = self.db.query(
                models.S3Metric.s3_resource_id,
                func.sum(models.S3Metric.put_requests).label('sum_put'),
                func.sum(models.S3Metric.get_requests).label('sum_get'),
                func.max(models.S3Metric.bucket_size_bytes).label('max_size')
            ).filter(models.S3Metric.metric_date >= thirty_days_ago).group_by(models.S3Metric.s3_resource_id).subquery()
            resources = self.db.query(models.S3Resource, subq.c.max_size).join(
                subq, models.S3Resource.s3_resource_id == subq.c.s3_resource_id
            ).filter(subq.c.sum_put == eq_puts, subq.c.sum_get == eq_gets, subq.c.max_size > min_size).all()
            for res, sz in resources:
                gb_size = sz / (1024**3) if sz else 0
                est_save = gb_size * 0.023 # ประหยัดทั้งเนื้อที่ Storage Standard = 0.023
                self._create_or_update_rec(res.account_id, res.region, "S3", res.bucket_name, "S3_HUGE_ABANDONED", {"max_size": sz}, rule.get('confidence', 0.95), est_save)

    def _evaluate_rds(self):
        seven_days_ago = self.today - timedelta(days=7)
        
        # RDS_RIGHTSIZE_CPU_LOW
        rule = self.rules.get('RDS_RIGHTSIZE_CPU_LOW', {})
        if rule.get('enabled'):
            t_val = rule.get('cpu_utilization_7d_lt', 20)
            subq = self.db.query(
                models.RDSMetric.rds_resource_id,
                func.max(models.RDSMetric.cpu_utilization).label('max_cpu')
            ).filter(models.RDSMetric.metric_date >= seven_days_ago).group_by(models.RDSMetric.rds_resource_id).subquery()
            
            resources = self.db.query(models.RDSResource, subq.c.max_cpu).join(
                subq, models.RDSResource.rds_resource_id == subq.c.rds_resource_id
            ).filter(subq.c.max_cpu < t_val).all()
            
            for res, val in resources:
                est_save = 30.0 # ลด size 1 step (e.g. 2xlarge -> xlarge) จะเซฟประมาณครึ่งนึง แต่เราตีกลมๆ
                self._create_or_update_rec(res.account_id, res.region, "RDS", res.db_identifier, "RDS_RIGHTSIZE_CPU_LOW", {"max_cpu": val}, rule.get('confidence', 0.85), est_save)

        # RDS_IDLE_STOP
        rule = self.rules.get('RDS_IDLE_STOP', {})
        if rule.get('enabled'):
            db_lt = rule.get('db_connections_7d_lt', 5)
            cpu_lt = rule.get('cpu_utilization_7d_lt', 5)
            subq = self.db.query(
                models.RDSMetric.rds_resource_id,
                func.sum(models.RDSMetric.database_connections).label('sum_conn'),
                func.max(models.RDSMetric.cpu_utilization).label('max_cpu')
            ).filter(models.RDSMetric.metric_date >= seven_days_ago).group_by(models.RDSMetric.rds_resource_id).subquery()
            
            resources = self.db.query(models.RDSResource, subq.c.sum_conn).join(
                subq, models.RDSResource.rds_resource_id == subq.c.rds_resource_id
            ).filter(subq.c.sum_conn < db_lt, subq.c.max_cpu < cpu_lt).all()
            
            for res, conn_count in resources:
                est_save = 40.0 # Stop ทิ้งไว้เซฟได้เยอะ
                self._create_or_update_rec(res.account_id, res.region, "RDS", res.db_identifier, "RDS_IDLE_STOP", {"conns_7d": conn_count}, rule.get('confidence', 0.95), est_save)

        # RDS_HIGH_SNAPSHOT_COST
        rule = self.rules.get('RDS_HIGH_SNAPSHOT_COST', {})
        if rule.get('enabled'):
            size_gt = rule.get('snapshot_storage_gb_gt', 100)
            subq = self.db.query(
                models.RDSMetric.rds_resource_id,
                func.max(models.RDSMetric.snapshot_storage_gb).label('max_snap')
            ).filter(models.RDSMetric.metric_date >= seven_days_ago).group_by(models.RDSMetric.rds_resource_id).subquery()
            
            resources = self.db.query(models.RDSResource, subq.c.max_snap).join(
                subq, models.RDSResource.rds_resource_id == subq.c.rds_resource_id
            ).filter(subq.c.max_snap > size_gt).all()
            
            for res, snap_sz in resources:
                # RDS Snapshot ประมาณ $0.095 ต่อ GB-month นอกพื้นที่แถม
                est_save = snap_sz * 0.095 if snap_sz else 5.0
                self._create_or_update_rec(res.account_id, res.region, "RDS", res.db_identifier, "RDS_HIGH_SNAPSHOT_COST", {"snap_gb": snap_sz}, rule.get('confidence', 0.8), est_save)

        # RDS_MEMORY_BOTTLENECK
        rule = self.rules.get('RDS_MEMORY_BOTTLENECK', {})
        if rule.get('enabled'):
            swap_gt = rule.get('swap_usage_bytes_gt', 536870912)
            free_lt = rule.get('freeable_memory_lt', 268435456)
            subq = self.db.query(
                models.RDSMetric.rds_resource_id,
                func.max(models.RDSMetric.swap_usage).label('max_swap'),
                func.min(models.RDSMetric.freeable_memory).label('min_free')
            ).filter(models.RDSMetric.metric_date >= seven_days_ago).group_by(models.RDSMetric.rds_resource_id).subquery()
            
            resources = self.db.query(models.RDSResource, subq.c.max_swap, subq.c.min_free).join(
                subq, models.RDSResource.rds_resource_id == subq.c.rds_resource_id
            ).filter(subq.c.max_swap > swap_gt, subq.c.min_free < free_lt).all()
            
            for res, s_val, f_val in resources:
                self._create_or_update_rec(res.account_id, res.region, "RDS", res.db_identifier, "RDS_MEMORY_BOTTLENECK", {"max_swap": s_val, "min_free": f_val}, rule.get('confidence', 0.85), 0.0) # อันนี้อาจเสียค่าใช้จ่ายเพิ่ม (Upsize)

    def _evaluate_lambda(self):
        rule = self.rules.get('LAMBDA_UNUSED_CLEANUP', {})
        if rule.get('enabled'):
            thirty_days_ago = self.today - timedelta(days=30)
            subq = self.db.query(
                models.LambdaMetric.lambda_resource_id,
                func.sum(models.LambdaMetric.invocations).label('total_invokes')
            ).filter(models.LambdaMetric.metric_date >= thirty_days_ago).group_by(models.LambdaMetric.lambda_resource_id).subquery()
            
            resources = self.db.query(models.LambdaResource, subq.c.total_invokes).join(
                subq, models.LambdaResource.lambda_resource_id == subq.c.lambda_resource_id
            ).filter(subq.c.total_invokes == 0).all()
            
            for res, val in resources:
                self._create_or_update_rec(res.account_id, res.region, "Lambda", res.function_name, "LAMBDA_UNUSED_CLEANUP", {"invocations_30d": val}, rule.get('confidence', 0.95), 0.0)

        # LAMBDA_OPTIMIZE_DURATION
        rule = self.rules.get('LAMBDA_OPTIMIZE_DURATION', {})
        if rule.get('enabled'):
            dur_gt = rule.get('duration_p95_ms_gt', 500)
            invs_gt = rule.get('invocations_14d_gt', 10000)
            fourteen_days_ago = self.today - timedelta(days=14)
            
            subq = self.db.query(
                models.LambdaMetric.lambda_resource_id,
                func.max(models.LambdaMetric.duration_p95).label('max_p95'),
                func.sum(models.LambdaMetric.invocations).label('sum_invs')
            ).filter(models.LambdaMetric.metric_date >= fourteen_days_ago).group_by(models.LambdaMetric.lambda_resource_id).subquery()
            
            resources = self.db.query(models.LambdaResource, subq.c.max_p95, subq.c.sum_invs).join(
                subq, models.LambdaResource.lambda_resource_id == subq.c.lambda_resource_id
            ).filter(subq.c.max_p95 > dur_gt, subq.c.sum_invs > invs_gt).all()
            
            for res, dur, invs in resources:
                # สมมติถ้าลดช้าได้ครึ่งนึง -> (dur/2 * invs / 1000) * ราคา compute ตีคร่าวๆ
                est_save = 15.0
                self._create_or_update_rec(res.account_id, res.region, "Lambda", res.function_name, "LAMBDA_OPTIMIZE_DURATION", {"max_p95": dur, "invocations_14d": invs}, rule.get('confidence', 0.85), est_save)

        # LAMBDA_HIGH_ERROR_WASTE
        rule = self.rules.get('LAMBDA_HIGH_ERROR_WASTE', {})
        if rule.get('enabled'):
            seven_days_ago = self.today - timedelta(days=7)
            err_gt = rule.get('errors_7d_gt', 100)
            
            subq = self.db.query(
                models.LambdaMetric.lambda_resource_id,
                func.sum(models.LambdaMetric.errors).label('sum_err')
            ).filter(models.LambdaMetric.metric_date >= seven_days_ago).group_by(models.LambdaMetric.lambda_resource_id).subquery()
            
            resources = self.db.query(models.LambdaResource, subq.c.sum_err).join(
                subq, models.LambdaResource.lambda_resource_id == subq.c.lambda_resource_id
            ).filter(subq.c.sum_err > err_gt).all()
            
            for res, e_val in resources:
                est_save = 5.0 # Error = ของเสียที่เสียเงินฟรี ๆ
                self._create_or_update_rec(res.account_id, res.region, "Lambda", res.function_name, "LAMBDA_HIGH_ERROR_WASTE", {"errors_7d": e_val}, rule.get('confidence', 0.9), est_save)

    def _evaluate_alb(self):
        seven_days_ago = self.today - timedelta(days=7)
        
        # ALB_IDLE_DELETE
        rule = self.rules.get('ALB_IDLE_DELETE', {})
        if rule.get('enabled'):
            req_val = rule.get('request_count_7d_lt', 100)
            conn_val = rule.get('active_conn_count_7d_lt', 5)
            
            subq = self.db.query(
                models.ALBMetric.alb_resource_id,
                func.sum(models.ALBMetric.request_count).label('sum_req'),
                func.sum(models.ALBMetric.active_conn_count).label('sum_conn')
            ).filter(models.ALBMetric.metric_date >= seven_days_ago).group_by(models.ALBMetric.alb_resource_id).subquery()
            
            resources = self.db.query(models.ALBResource, subq.c.sum_req, subq.c.sum_conn).join(
                subq, models.ALBResource.alb_resource_id == subq.c.alb_resource_id
            ).filter(subq.c.sum_req < req_val, subq.c.sum_conn < conn_val).all()
            
            for res, r_val, c_val in resources:
                # ALB idle ราคาตั้งต้น $0.0225 * 730ชม = $16.4/เดือน
                est_save = 16.4
                self._create_or_update_rec(res.account_id, res.region, "ALB", res.alb_name, "ALB_IDLE_DELETE", {"req_count": r_val, "conn_count": c_val}, rule.get('confidence', 0.95), est_save)

        # ALB_HIGH_5XX_ERRORS
        rule = self.rules.get('ALB_HIGH_5XX_ERRORS', {})
        if rule.get('enabled'):
            t_val = rule.get('http_5xx_count_7d_gt', 100)
            subq = self.db.query(
                models.ALBMetric.alb_resource_id,
                func.sum(models.ALBMetric.http_5xx_count).label('sum_5xx')
            ).filter(models.ALBMetric.metric_date >= seven_days_ago).group_by(models.ALBMetric.alb_resource_id).subquery()
            
            resources = self.db.query(models.ALBResource, subq.c.sum_5xx).join(
                subq, models.ALBResource.alb_resource_id == subq.c.alb_resource_id
            ).filter(subq.c.sum_5xx > t_val).all()
            
            for res, val in resources:
                self._create_or_update_rec(res.account_id, res.region, "ALB", res.alb_name, "ALB_HIGH_5XX_ERRORS", {"http_5xx": val}, rule.get('confidence', 0.9), 0.0)

        # CLB_MIGRATE_TO_ALB
        rule = self.rules.get('CLB_MIGRATE_TO_ALB', {})
        if rule.get('enabled'):
            lb_type = rule.get('lb_type', 'classic')
            resources = self.db.query(models.ALBResource).filter(models.ALBResource.alb_type == lb_type).all()
            for res in resources:
                est_save = 5.0 # CLB โดยปกติแพงกว่า ALB/NLB ขึ้นกับทราฟฟิก (สมมติประหยัด $5)
                self._create_or_update_rec(res.account_id, res.region, "ALB", res.alb_name, "CLB_MIGRATE_TO_ALB", {"type": res.alb_type}, rule.get('confidence', 0.9), est_save)
