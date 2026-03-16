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
        q("rds_storage_free", "FreeStorageSpace", "Minimum"), # ✅ worst
        q("rds_data_transfer", "NetworkTransmitThroughput", "Sum"), # approximating data transfer
    ]




# ─── RDS Instance Discovery ───────────────────────────────────────

def list_rds_instances(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all RDS DB instances in the customer's account.
    Returns list of dicts including created_time for each instance.
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
                "created_time": db.get("InstanceCreateTime"),  # datetime (tz-aware)
            })

    logger.info(f"Found {len(instances)} RDS instances in {region}")
    return instances


# ─── High-level: Pull RDS Metrics ─────────────────────────────────

def pull_rds_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list RDS instances → build DAILY queries → fetch CloudWatch metrics.
    Uses each instance's InstanceCreateTime as the start of the metric range.
    """
    instances = list_rds_instances(customer_session, region)

    if not instances:
        logger.info("No RDS instances found, skipping metric pull")
        return {}

    all_results = {}
    for inst in instances:
        db_id = inst["db_identifier"]
        queries = build_rds_metric_queries_daily(db_id)

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            start_time=inst.get("created_time"),
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[db_id] = {"instance": inst, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for {db_id} (since {inst.get('created_time')})")

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
                profile_id=profile_id, account_id=account_id, region=region, db_identifier=db_id
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
                    "free_storage_space": values.get("rds_storage_free"),   # daily min
                    "data_transfer": values.get("rds_data_transfer"),
                })

            if metric_rows:
                stmt = insert(models.RDSMetric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["rds_resource_id", "metric_date"],
                    set_={
                        "cpu_utilization": stmt.excluded.cpu_utilization,
                        "database_connections": stmt.excluded.database_connections,
                        "free_storage_space": stmt.excluded.free_storage_space,
                        "data_transfer": stmt.excluded.data_transfer,
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


def _upsert_rds_metric_rows(db, rds_resource_id: int, daily: dict):
    """Bulk upsert RDS metric rows from parsed daily data."""
    from .. import models
    from sqlalchemy.dialects.postgresql import insert

    metric_rows = []
    for metric_date, values in daily.items():
        metric_rows.append({
            "rds_resource_id": rds_resource_id,
            "metric_date": metric_date,
            "cpu_utilization": values.get("rds_cpu"),
            "database_connections": values.get("rds_conn"),
            "free_storage_space": values.get("rds_storage_free"),
            "data_transfer": values.get("rds_data_transfer"),
        })

    if not metric_rows:
        return

    stmt = insert(models.RDSMetric.__table__).values(metric_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["rds_resource_id", "metric_date"],
        set_={
            "cpu_utilization": stmt.excluded.cpu_utilization,
            "database_connections": stmt.excluded.database_connections,
            "free_storage_space": stmt.excluded.free_storage_space,
            "data_transfer": stmt.excluded.data_transfer,
        }
    )
    db.execute(stmt)
    db.commit()


# ─── Smart Sync: Check DB → Pull only missing → Save ─────────────

def smart_sync_rds_metrics(
    customer_session: boto3.Session,
    account_id: str,
    region: str,
    profile_id: int,
    timezone_offset_hours: int = 7,
):
    """
    Smart metric sync for RDS instances with gap detection.

    For each RDS resource belonging to this profile:
      1. No metrics in DB  → full backfill (pull from created_time to now)
      2. Has metrics        → detect internal gap dates AND new dates:
         - Computes expected range (min_date .. yesterday)
         - Finds missing dates (gaps + trailing)
         - Pulls from the earliest missing date to now
         - Upsert handles de-duplication of existing rows
      3. Already up to date with no gaps → skip

    Uses AssumeRole session to query CloudWatch.
    """
    from .. import models, database
    from datetime import date, datetime, timedelta, timezone, time

    db = database.SessionLocal()
    try:
        # 1. Discover live RDS instances & upsert to DB
        logger.info(f"Discovering RDS instances for profile {profile_id} in {region}...")
        live_instances = list_rds_instances(customer_session, region)
        for inst in live_instances:
            db_id = inst["db_identifier"]
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
            else:
                resource.engine = inst.get("engine")
                resource.instance_class = inst.get("instance_class")
                resource.storage_type = inst.get("storage_type")
                resource.allocated_gb = inst.get("allocated_gb")
        db.commit()

        # 2. Get all RDS resources for this profile
        resources = (
            db.query(models.RDSResource)
            .filter_by(profile_id=profile_id, region=region)
            .all()
        )

        if not resources:
            logger.info(f"No RDS resources in DB for profile={profile_id}, region={region}")
            return

        today = date.today()
        yesterday = today - timedelta(days=1)

        for resource in resources:
            db_id = resource.db_identifier

            # ── Get all existing metric dates for gap detection ──
            existing_dates_rows = (
                db.query(models.RDSMetric.metric_date)
                .filter_by(rds_resource_id=resource.rds_resource_id)
                .all()
            )
            existing_dates = {row[0] for row in existing_dates_rows}

            if existing_dates:
                min_date = min(existing_dates)
                max_date = max(existing_dates)

                # Build the full expected date range: min_date .. yesterday
                expected_dates = {
                    min_date + timedelta(days=i)
                    for i in range((yesterday - min_date).days + 1)
                }
                gap_dates = expected_dates - existing_dates

                if max_date >= yesterday and not gap_dates:
                    logger.info(f"  ✅ RDS {db_id} up to date (latest: {max_date}), no gaps, skipping")
                    continue

                # Determine the earliest date we need to pull from
                if gap_dates:
                    pull_from = min(gap_dates)
                else:
                    pull_from = max_date + timedelta(days=1)

                start_dt = datetime.combine(
                    pull_from, time.min, tzinfo=timezone.utc
                )
                logger.info(
                    f"  📦 RDS {db_id} pulling from {pull_from} "
                    f"(gaps: {len(gap_dates)}, latest: {max_date})"
                )
            else:
                # Case 1: no data at all → pull full history
                start_dt = None
                logger.info(f"  🆕 RDS {db_id} first time, pulling full history")

            # Pull CloudWatch metrics
            queries = build_rds_metric_queries_daily(db_id)
            cw_resp = get_cloudwatch_metric_data(
                customer_session=customer_session,
                region=region,
                metric_data_queries=queries,
                start_time=start_dt,
                timezone_offset_hours=timezone_offset_hours,
            )

            if not cw_resp:
                logger.warning(f"  ⚠️ No CloudWatch response for RDS {db_id}")
                continue

            # Parse and save (upsert handles duplicates safely)
            daily = group_cw_by_date(cw_resp)
            _upsert_rds_metric_rows(db, resource.rds_resource_id, daily)
            logger.info(f"  💾 Saved {len(daily)} metric rows for RDS {db_id}")

        logger.info(f"Smart sync completed for {len(resources)} RDS resources")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in smart sync RDS metrics: {e}")
        raise
    finally:
        db.close()