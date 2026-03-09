import logging
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

# App imports
from .. import models, database
from .aws_sts import boto_client, get_account_id

logger = logging.getLogger(__name__)

# ==============================================================================
# Helper: Upsert Utils
# ==============================================================================

def _upsert_resource(db: Session, model_cls, unique_filters: Dict, defaults: Dict) -> int:
    """
    Get existing resource ID or create new one.
    Returns the primary key ID.
    Note: unique_filters should include profile_id.
    """
    obj = db.query(model_cls).filter_by(**unique_filters).first()
    if obj:
        return getattr(obj, f"{model_cls.__tablename__[:-1]}_id")
    
    # Create new
    new_obj = model_cls(**unique_filters, **defaults)
    db.add(new_obj)
    db.commit()
    db.refresh(new_obj)
    return getattr(new_obj, f"{model_cls.__tablename__[:-1]}_id")

def _bulk_upsert(db: Session, model_cls, rows: List[Dict], index_elements: List[str]):
    """
    Bulk upsert using PostgreSQL ON CONFLICT.
    """
    if not rows:
        return

    table = model_cls.__table__
    stmt = insert(table).values(rows)
    
    # Prepare update dict (exclude PK and index elements)
    update_cols = {c.name: c for c in stmt.excluded if c.name not in index_elements}
    
    if update_cols:
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_=update_cols
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)

    db.execute(stmt)
    db.commit()

# ==============================================================================
# 1. AWS Cost & Usage Report (CUR via Athena) Sync
# ==============================================================================

def sync_aws_costs(profile_id: int, days_back: int = 90):
    """
    Fetch daily costs via Athena querying the CUR and upsert to DB.
    """
    db = database.SessionLocal()
    logger.info(f"🚀 Starting AWS CUR Sync (Days Back: {days_back})...")
    try:
        # Load necessary AWS Clients
        athena_client = boto_client("athena")
        s3_client = boto_client("s3")
        account_id = get_account_id()
        region = s3_client.meta.region_name or "us-east-1"
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        start_date_str = str(start_date)
        end_date_str = str(end_date)
        
        from .cur_service import query_athena_cur_data
        
        # 1. Fetch Data from Athena CUR
        results = query_athena_cur_data(athena_client, start_date_str, end_date_str)
        
        # Buffers for bulk insert
        ec2_costs = []
        alb_costs = []
        s3_costs = []
        rds_costs = []
        lambda_costs = []
        
        # Cache for Resource IDs: {(service_model, resource_key): local_id}
        resource_cache = {}

        for row in results:
            usage_date = row["usage_date"]
            service_name = row["service_name"]
            usage_type = row["usage_type"]
            resource_id_raw = row["resource_id"]
            amount = row["cost"]
            
            if amount == 0:
                continue

            # Default models
            model_res = None
            model_cost = None
            res_key_field = None
            target_list = None
            
            # Map Service Name and Usage Type to our Tables
            if service_name == "AmazonEC2":
                if 'LoadBalancer' in usage_type or 'LCU' in usage_type:
                    target_list = alb_costs
                    model_res = models.ALBResource
                    model_cost = models.ALBCost
                    res_key_field = "lb_name" 
                    # Extract LB Name from ARN (approximate)
                    resource_key = resource_id_raw.split('/')[-1] if '/' in resource_id_raw else resource_id_raw
                else: 
                     # This will catch BoxUsage, EBS, and DataTransfer
                    target_list = ec2_costs
                    model_res = models.EC2Resource
                    model_cost = models.EC2Cost
                    res_key_field = "instance_id"
                    # EC2 instances usually start with 'i-', Volumes with 'vol-'
                    # For Data Transfer, it might be an instance ID or aggregated.
                    resource_key = resource_id_raw
                    
            elif service_name == "AWSELB":
                 # Classic ELB
                 target_list = alb_costs
                 model_res = models.ALBResource
                 model_cost = models.ALBCost
                 res_key_field = "lb_name"
                 resource_key = resource_id_raw.split('/')[-1] if '/' in resource_id_raw else resource_id_raw
                 
            elif service_name == "AmazonS3":
                target_list = s3_costs
                model_res = models.S3Resource
                model_cost = models.S3Cost
                res_key_field = "bucket_name"
                resource_key = resource_id_raw
                
            elif service_name == "AmazonRDS":
                target_list = rds_costs
                model_res = models.RDSResource
                model_cost = models.RDSCost
                res_key_field = "db_identifier"
                # RDS ARNs end with the DB identifier
                resource_key = resource_id_raw.split(':')[-1] if ':' in resource_id_raw else resource_id_raw
                
            elif service_name == "AWSLambda":
                target_list = lambda_costs
                model_res = models.LambdaResource
                model_cost = models.LambdaCost
                res_key_field = "function_name"
                # Lambda ARNs end with the function name
                resource_key = resource_id_raw.split(':')[-1] if ':' in resource_id_raw else resource_id_raw
                
            else:
                continue # Skip unmapped services

            if not model_res: continue
            
            # 2. Get or Create Resource ID in local DB
            cache_key = (model_res.__name__, resource_key)
            if cache_key not in resource_cache:
                filters = {
                    "profile_id": profile_id,
                    "account_id": account_id,
                    "region": region,
                    res_key_field: resource_key
                }
                
                # Add default states for models that need them
                defaults = {}
                if model_res == models.EC2Resource: defaults["state"] = "active"
                
                local_rid = _upsert_resource(db, model_res, filters, defaults)
                resource_cache[cache_key] = local_rid
            
            local_rid = resource_cache[cache_key]
            
            # 3. Add Cost Row
            fk_field = f"{model_res.__tablename__[:-1]}_id"
            target_list.append({
                fk_field: local_rid,
                "usage_date": usage_date,
                "usage_type": usage_type,
                "amount_usd": amount,
                "currency_src": "USD"
            })
        
        # 4. Bulk Insert
        if ec2_costs:
            _bulk_upsert(db, models.EC2Cost, ec2_costs, ["ec2_resource_id", "usage_date", "usage_type"])
            logger.info(f" -> Upserted {len(ec2_costs)} EC2 cost rows")
        if s3_costs:
            _bulk_upsert(db, models.S3Cost, s3_costs, ["s3_resource_id", "usage_date", "usage_type"])
            logger.info(f" -> Upserted {len(s3_costs)} S3 cost rows")
        if rds_costs:
            _bulk_upsert(db, models.RDSCost, rds_costs, ["rds_resource_id", "usage_date", "usage_type"])
            logger.info(f" -> Upserted {len(rds_costs)} RDS cost rows")
        if lambda_costs:
            _bulk_upsert(db, models.LambdaCost, lambda_costs, ["lambda_resource_id", "usage_date", "usage_type"])
            logger.info(f" -> Upserted {len(lambda_costs)} Lambda cost rows")
        if alb_costs:
            _bulk_upsert(db, models.ALBCost, alb_costs, ["alb_resource_id", "usage_date", "usage_type"])
            logger.info(f" -> Upserted {len(alb_costs)} ALB cost rows")
            
        logger.info(f"✅ Successfully synced CUR data from Athena for {start_date_str} to {end_date_str}")
        
    except Exception as e:
        logger.error(f"Error syncing costs through Athena CUR: {e}")
        raise
    finally:
        db.close()


# ==============================================================================
# 2. AWS CloudWatch Metrics Sync
# ==============================================================================

def sync_aws_metrics(profile_id: int, hours_back: int = 24):
    """
    Fetch CloudWatch metrics for EC2, RDS, S3, Lambda, ALB.
    Upserts real Resource records and then Metrics using AssumeRole.
    """
    db = database.SessionLocal()
    try:
        user = db.query(models.UserProfile).filter_by(profile_id=profile_id).first()
        if not user or not user.aws_role_arn:
            logger.error(f"Cannot sync metrics: User {profile_id} has no aws_role_arn configured")
            return

        from .aws_sts import get_assumed_session
        session = get_assumed_session(
            role_arn=user.aws_role_arn,
            session_name=f"sync-metrics-{profile_id}",
            external_id=user.aws_external_id,
        )

        from .metrics_ec2 import smart_sync_ec2_metrics
        from .metrics_rds import pull_rds_metrics, save_rds_metrics
        from .metrics_lambda import pull_lambda_metrics, save_lambda_metrics
        from .metrics_s3 import pull_s3_metrics, save_s3_metrics
        from .metrics_alb import pull_alb_metrics, save_alb_metrics
        # Hack to get region from local boto3
        region = boto_client("s3").meta.region_name or "us-east-1"
        account_id = get_account_id()

        logger.info(f"🚀 Starting AWS CloudWatch Metrics Sync for Profile {profile_id}...")
        
        # --- EC2 ---
        logger.info("  -> Syncing EC2 Metrics...")
        smart_sync_ec2_metrics(
            customer_session=session,
            account_id=account_id,
            region=region,
            profile_id=profile_id
        )
        logger.info("  ✅ EC2 Metrics Synced!")

        # --- RDS ---
        try:
            logger.info("  -> Syncing RDS Metrics...")
            rds_results = pull_rds_metrics(customer_session=session, region=region)
            save_rds_metrics(rds_results, account_id=account_id, region=region, profile_id=profile_id)
            logger.info(f"  ✅ RDS Metrics Synced! ({len(rds_results)} instances)")
        except Exception as e:
            logger.warning(f"  ⚠️ RDS Metrics sync skipped: {e}")

        # --- Lambda ---
        try:
            logger.info("  -> Syncing Lambda Metrics...")
            lambda_results = pull_lambda_metrics(customer_session=session, region=region)
            save_lambda_metrics(lambda_results, account_id=account_id, region=region, profile_id=profile_id)
            logger.info(f"  ✅ Lambda Metrics Synced! ({len(lambda_results)} functions)")
        except Exception as e:
            logger.warning(f"  ⚠️ Lambda Metrics sync skipped: {e}")

        # --- S3 ---
        try:
            logger.info("  -> Syncing S3 Metrics...")
            s3_results = pull_s3_metrics(customer_session=session, region=region)
            save_s3_metrics(s3_results, account_id=account_id, region=region, profile_id=profile_id)
            logger.info(f"  ✅ S3 Metrics Synced! ({len(s3_results)} buckets)")
        except Exception as e:
            logger.warning(f"  ⚠️ S3 Metrics sync skipped: {e}")

        # --- ALB ---
        try:
            logger.info("  -> Syncing ALB Metrics...")
            alb_results = pull_alb_metrics(customer_session=session, region=region)
            save_alb_metrics(alb_results, account_id=account_id, region=region, profile_id=profile_id)
            logger.info(f"  ✅ ALB Metrics Synced! ({len(alb_results)} load balancers)")
        except Exception as e:
            logger.warning(f"  ⚠️ ALB Metrics sync skipped: {e}")

        logger.info(f"🎉 All metrics synced for Profile {profile_id}!")
        
    except Exception as e:
        logger.error(f"Error syncing metrics: {e}")
        raise
    finally:
        db.close()

def _sync_ec2_metrics(db: Session, cw, account_id, region, start_time, end_time, profile_id: int):
    # 1. List Instances (Real world: use EC2 DescribeInstances)
    ec2_client = boto_client("ec2")
    instances = []
    paginator = ec2_client.get_paginator('describe_instances')
    for page in paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
        for r in page['Reservations']:
            for i in r['Instances']:
                instances.append({
                    'id': i['InstanceId'],
                    'type': i['InstanceType'],
                    'state': i['State']['Name']
                })
    
    metric_rows = []
    
    for inst in instances:
        # Upsert Resource
        pk = _upsert_resource(
            db, 
            models.EC2Resource, 
            {"profile_id": profile_id, "account_id": account_id, "region": region, "instance_id": inst['id']},
            {"instance_type": inst['type'], "state": inst['state']}
        )
        
        # Get Metrics (CPU)
        resp = cw.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': inst['id']}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Maximum'] # p95 needs specialized call, use Max for simple demo
        )
        
        daily_metrics = {}
        for point in resp['Datapoints']:
            d_key = point['Timestamp'].date()
            val = point['Maximum']
            if d_key not in daily_metrics:
                daily_metrics[d_key] = val
            else:
                daily_metrics[d_key] = max(daily_metrics[d_key], val)
                
        for d_key, max_val in daily_metrics.items():
            metric_rows.append({
                "ec2_resource_id": pk,
                "metric_date": d_key,
                "cpu_utilization": max_val,
            })
    if metric_rows:
        _bulk_upsert(db, models.EC2Metric, metric_rows, ["ec2_resource_id", "metric_date"])
