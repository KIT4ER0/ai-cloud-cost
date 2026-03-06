import boto3
import logging
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, print_all_datapoints
from .aggregate import group_cw_by_date

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# ──────────────────────────────────────────────────────────────
# ✅ Daily CloudWatch Queries (Period = 86400)
# ──────────────────────────────────────────────────────────────

def build_rds_metric_queries_daily(db_identifier: str):
    """
    Build CloudWatch MetricDataQueries that return DAILY buckets.

    Daily buckets:
    - CPUUtilization: p95 (true daily p95)
    - DatabaseConnections: Maximum (peak connections)
    - FreeableMemory: Minimum (worst case)
    - FreeStorageSpace: Minimum (worst case)
    - DiskQueueDepth: Maximum (peak queue)
    - EBSByteBalancePercent: Minimum (worst burst balance)
    - EBSIOBalancePercent: Minimum (worst burst balance)
    - CPUCreditBalance: Minimum (worst case)
    - CPUCreditUsage: Sum (daily total usage)
    """
    dims = [{"Name": "DBInstanceIdentifier", "Value": db_identifier}]

    def q(_id: str, metric: str, stat: str):
        return {
            "Id": _id,
            "Label": f"{db_identifier}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/RDS",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,  # ✅ 1 day
                "Stat": stat,     # ✅ supports extended like 'p95'
            },
            "ReturnData": True,
        }

    return [
        # ===== Core =====
        q("rds_cpu", "CPUUtilization", "p95"),                # ✅ true daily p95
        q("rds_conn", "DatabaseConnections", "Maximum"),      # ✅ peak
        q("rds_mem_free", "FreeableMemory", "Minimum"),       # ✅ worst
        q("rds_storage_free", "FreeStorageSpace", "Minimum"), # ✅ worst

        # ===== I/O / Storage burst =====
        q("rds_disk_q", "DiskQueueDepth", "Maximum"),              # ✅ peak
        q("rds_ebs_byte_bal", "EBSByteBalancePercent", "Minimum"), # ✅ worst balance
        q("rds_ebs_io_bal", "EBSIOBalancePercent", "Minimum"),     # ✅ worst balance

        # ===== Burstable (t3/t4g) =====
        q("rds_cpu_credit_bal", "CPUCreditBalance", "Minimum"), # ✅ worst case
        q("rds_cpu_credit_use", "CPUCreditUsage", "Sum"),        # ✅ daily total
    ]




# ─── RDS Instance Discovery ───────────────────────────────────────

def list_rds_instances(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all RDS DB instances in the customer's account via DescribeDBInstances.
    Uses paginator to handle accounts with many instances.
    """
    rds = customer_session.client("rds", region_name=region)
    instances = []

    paginator = rds.get_paginator("describe_db_instances")
    for page in paginator.paginate():
        for db in page["DBInstances"]:
            instances.append({
                "db_identifier": db["DBInstanceIdentifier"],
                "engine": db.get("Engine"),
                "instance_class": db.get("DBInstanceClass"),
                "storage_type": db.get("StorageType"),
                "allocated_gb": db.get("AllocatedStorage"),
            })

    logger.info(f"Found {len(instances)} RDS instances in {region}")
    return instances


# ─── High-level: Pull RDS Metrics ─────────────────────────────────

def pull_rds_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    days_back: int = 30,
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list RDS instances → build DAILY queries → fetch CloudWatch metrics.
    """
    instances = list_rds_instances(customer_session, region)

    if not instances:
        logger.info("No RDS instances found, skipping metric pull")
        return {}

    all_results = {}
    for inst in instances:
        db_id = inst["db_identifier"]

        # ✅ Use DAILY queries now
        queries = build_rds_metric_queries_daily(db_id)

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[db_id] = {"instance": inst, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for {db_id} ({inst['engine']})")

    logger.info(f"Completed metric pull for {len(all_results)} RDS instances")
    return all_results


# ─── Save RDS Metrics to DB ───────────────────────────────────────

def save_rds_metrics(pull_results: dict, account_id: str, region: str, profile_id: int):
    """
    Save pulled RDS metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

    db = database.SessionLocal()
    try:
        for db_id, data in pull_results.items():
            inst = data["instance"]
            cw_resp = data["metrics"]

            # 1) Upsert RDS resource
            resource = db.query(models.RDSResource).filter_by(
                account_id=account_id, region=region, db_identifier=db_id
            ).first()

            if not resource:
                resource = models.RDSResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    db_identifier=db_id,
                    engine=inst.get("engine"),
                    instance_class=inst.get("instance_class"),
                    storage_type=inst.get("storage_type"),
                    allocated_gb=inst.get("allocated_gb"),
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)
            else:
                resource.engine = inst.get("engine")
                resource.instance_class = inst.get("instance_class")
                resource.storage_type = inst.get("storage_type")
                resource.allocated_gb = inst.get("allocated_gb")
                db.commit()

            if not cw_resp:
                continue

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "rds_resource_id": resource.rds_resource_id,
                    "metric_date": metric_date,
                    "cpu_utilization": values.get("rds_cpu"),               # daily p95
                    "database_connections": values.get("rds_conn"),         # daily max
                    "freeable_memory": values.get("rds_mem_free"),          # daily min
                    "free_storage_space": values.get("rds_storage_free"),   # daily min
                    "disk_queue_depth": values.get("rds_disk_q"),           # daily max
                    "ebs_byte_balance_pct": values.get("rds_ebs_byte_bal"), # daily min
                    "ebs_io_balance_pct": values.get("rds_ebs_io_bal"),     # daily min
                    "cpu_credit_balance": values.get("rds_cpu_credit_bal"), # daily min
                    "cpu_credit_usage": values.get("rds_cpu_credit_use"),   # daily sum
                })

            if metric_rows:
                stmt = insert(models.RDSMetric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["rds_resource_id", "metric_date"],
                    set_={
                        "cpu_utilization": stmt.excluded.cpu_utilization,
                        "database_connections": stmt.excluded.database_connections,
                        "freeable_memory": stmt.excluded.freeable_memory,
                        "free_storage_space": stmt.excluded.free_storage_space,
                        "disk_queue_depth": stmt.excluded.disk_queue_depth,
                        "ebs_byte_balance_pct": stmt.excluded.ebs_byte_balance_pct,
                        "ebs_io_balance_pct": stmt.excluded.ebs_io_balance_pct,
                        "cpu_credit_balance": stmt.excluded.cpu_credit_balance,
                        "cpu_credit_usage": stmt.excluded.cpu_credit_usage,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} DAILY metric rows for RDS {db_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving RDS metrics: {e}")
        raise
    finally:
        db.close()