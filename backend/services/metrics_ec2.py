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

def build_ec2_metric_queries_daily(instance_id: str):
    """
    Build CloudWatch MetricDataQueries that return DAILY buckets.

    - CPUUtilization: DAILY p95 (true daily p95 computed by CloudWatch over the 1-day period)
    - NetworkIn/Out: DAILY Sum
    - CPUCreditUsage: DAILY Sum (recommended for "usage" metric)
    """
    dims = [{"Name": "InstanceId", "Value": instance_id}]

    def q(_id: str, metric: str, stat: str):
        return {
            "Id": _id,
            "Label": f"{instance_id}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,   # ✅ 1 day
                "Stat": stat,      # ✅ can be 'Sum', 'Average', 'Maximum', 'Minimum', or extended like 'p95'
            },
            "ReturnData": True,
        }

    return [
        q("cpu", "CPUUtilization", "p95"),     # ✅ TRUE daily p95
        q("netin", "NetworkIn", "Sum"),        # ✅ daily sum
        q("netout", "NetworkOut", "Sum"),      # ✅ daily sum
        q("cpu_credit", "CPUCreditUsage", "Sum"),  # ✅ daily sum (better than Average for usage)
    ]




# ─── EC2 Instance Discovery ───────────────────────────────────────

def list_ec2_instances(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all EC2 instances in the customer's account via DescribeInstances.
    Returns list of dicts including launch_time for each instance.
    """
    ec2 = customer_session.client("ec2", region_name=region)
    instances = []

    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate():
        for reservation in page["Reservations"]:
            for i in reservation["Instances"]:
                instances.append({
                    "instance_id": i["InstanceId"],
                    "instance_type": i["InstanceType"],
                    "state": i["State"]["Name"],
                    "launch_time": i.get("LaunchTime"),  # datetime (tz-aware)
                })

    logger.info(f"Found {len(instances)} EC2 instances in {region}")
    return instances


# ─── High-level: Pull EC2 Metrics ─────────────────────────────────

def pull_ec2_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list all EC2 instances → build DAILY queries → fetch CloudWatch metrics.
    Uses each instance's LaunchTime as the start of the metric range.
    """
    instances = list_ec2_instances(customer_session, region)

    if not instances:
        logger.info("No EC2 instances found, skipping metric pull")
        return {}

    all_results = {}
    for inst in instances:
        iid = inst["instance_id"]
        queries = build_ec2_metric_queries_daily(iid)

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            start_time=inst.get("launch_time"),
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[iid] = {"instance": inst, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for {iid} (since {inst.get('launch_time')})")

    logger.info(f"Completed metric pull for {len(all_results)} instances")
    return all_results


# ─── Save EC2 Metrics to DB ───────────────────────────────────────

def save_ec2_metrics(pull_results: dict, account_id: str, region: str, profile_id: int):
    """
    Save pulled EC2 metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

    db = database.SessionLocal()
    try:
        for iid, data in pull_results.items():
            inst = data["instance"]
            cw_resp = data["metrics"]

            # 1) Upsert EC2 resource
            resource = db.query(models.EC2Resource).filter_by(
                account_id=account_id, region=region, instance_id=iid
            ).first()

            if not resource:
                resource = models.EC2Resource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    instance_id=iid,
                    instance_type=inst.get("instance_type"),
                    state=inst.get("state"),
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)
            else:
                resource.instance_type = inst.get("instance_type")
                resource.state = inst.get("state")
                db.commit()

            if not cw_resp:
                continue

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            _upsert_ec2_metric_rows(db, resource.ec2_resource_id, daily)

            logger.info(f"Saved {len(daily)} DAILY metric rows for EC2 {iid}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving EC2 metrics: {e}")
        raise
    finally:
        db.close()


def _upsert_ec2_metric_rows(db, ec2_resource_id: int, daily: dict):
    """Bulk upsert EC2 metric rows from parsed daily data."""
    from .. import models
    from sqlalchemy.dialects.postgresql import insert

    metric_rows = []
    for metric_date, values in daily.items():
        metric_rows.append({
            "ec2_resource_id": ec2_resource_id,
            "metric_date": metric_date,
            "cpu_utilization": values.get("cpu"),
            "network_in": values.get("netin"),
            "network_out": values.get("netout"),
            "cpu_credit_usage": values.get("cpu_credit"),
        })

    if not metric_rows:
        return

    stmt = insert(models.EC2Metric.__table__).values(metric_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ec2_resource_id", "metric_date"],
        set_={
            "cpu_utilization": stmt.excluded.cpu_utilization,
            "network_in": stmt.excluded.network_in,
            "network_out": stmt.excluded.network_out,
            "cpu_credit_usage": stmt.excluded.cpu_credit_usage,
        }
    )
    db.execute(stmt)
    db.commit()


# ─── Smart Sync: Check DB → Pull only missing → Save ─────────────

def smart_sync_ec2_metrics(
    customer_session: boto3.Session,
    account_id: str,
    region: str,
    profile_id: int,
    timezone_offset_hours: int = 7,
):
    """
    Smart metric sync for EC2 instances.

    For each EC2 resource belonging to this profile:
      1. No metrics in DB → pull from launch_time to now (full backfill)
      2. Has metrics but gaps → pull from (latest_date + 1) to now
      3. Already up to date → skip

    Uses AssumeRole session to query CloudWatch.
    """
    from .. import models, database
    from sqlalchemy import func
    from datetime import date, datetime, timedelta, timezone, time

    db = database.SessionLocal()
    try:
        # Get all EC2 resources for this profile
        resources = (
            db.query(models.EC2Resource)
            .filter_by(profile_id=profile_id, region=region)
            .all()
        )

        if not resources:
            logger.info(f"No EC2 resources in DB for profile={profile_id}, region={region}")
            return

        today = date.today()
        yesterday = today - timedelta(days=1)

        for resource in resources:
            iid = resource.instance_id

            # Check latest metric date in DB
            latest_date = (
                db.query(func.max(models.EC2Metric.metric_date))
                .filter_by(ec2_resource_id=resource.ec2_resource_id)
                .scalar()
            )

            if latest_date and latest_date >= yesterday:
                logger.info(f"  ✅ EC2 {iid} up to date (latest: {latest_date}), skipping")
                continue

            # Determine start_time for CloudWatch query
            if latest_date:
                # Case 2: has data but incomplete → pull from next day after latest
                start_dt = datetime.combine(
                    latest_date + timedelta(days=1),
                    time.min,
                    tzinfo=timezone.utc,
                )
                logger.info(f"  📦 EC2 {iid} incomplete (latest: {latest_date}), pulling from {start_dt.date()}")
            else:
                # Case 1: no data at all → pull from creation time (None = use days_back fallback)
                start_dt = None
                logger.info(f"  🆕 EC2 {iid} first time, pulling full history")

            # Pull CloudWatch metrics
            queries = build_ec2_metric_queries_daily(iid)
            cw_resp = get_cloudwatch_metric_data(
                customer_session=customer_session,
                region=region,
                metric_data_queries=queries,
                start_time=start_dt,
                timezone_offset_hours=timezone_offset_hours,
            )

            if not cw_resp:
                logger.warning(f"  ⚠️ No CloudWatch response for EC2 {iid}")
                continue

            # Parse and save
            daily = group_cw_by_date(cw_resp)
            _upsert_ec2_metric_rows(db, resource.ec2_resource_id, daily)
            logger.info(f"  💾 Saved {len(daily)} metric rows for EC2 {iid}")

        logger.info(f"Smart sync completed for {len(resources)} EC2 resources")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in smart sync EC2 metrics: {e}")
        raise
    finally:
        db.close()