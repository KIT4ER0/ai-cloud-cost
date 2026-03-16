import boto3
import logging
import time as time_module
from datetime import date, datetime, timedelta, timezone, time
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, fetch_cw_with_retry
from .aggregate import group_cw_by_date
from .. import models, database
from sqlalchemy.dialects.postgresql import insert


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
    ]




def compute_hours_running(metric_date, launch_time) -> float:
    """Calculate hours running for the given day based on launch time."""
    
    if not launch_time:
        return 24.0
    
    # If launched on a future date (shouldn't happen with CW, but safe)
    if launch_time.date() > metric_date:
        return 0.0
        
    # If launched on this exact metric date
    if launch_time.date() == metric_date:
        eod = datetime.combine(metric_date, time(23, 59, 59), tzinfo=timezone.utc)
        hours = (eod - launch_time).total_seconds() / 3600.0
        return max(0.0, min(24.0, hours))
        
    return 24.0

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
                state_name = i["State"]["Name"]
                if state_name in ("terminated", "shutting-down"):
                    continue
                
                instances.append({
                    "instance_id": i["InstanceId"],
                    "instance_type": i["InstanceType"],
                    "state": state_name,
                    "launch_time": i.get("LaunchTime"),  # datetime (tz-aware)
                })

    logger.info(f"Found {len(instances)} active EC2 instances in {region}")
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
                    launch_time=inst.get("launch_time"),
                )
                db.add(resource)
                db.flush()
            else:
                resource.instance_type = inst.get("instance_type")
                resource.state = inst.get("state")
                db.flush()

            if not cw_resp:
                continue

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            _upsert_ec2_metric_rows(db, resource.ec2_resource_id, daily, inst.get("launch_time"))

            logger.info(f"Saved {len(daily)} DAILY metric rows for EC2 {iid}")
            
        # Commit all instances together
        db.commit()

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving EC2 metrics: {e}")
        raise
    finally:
        db.close()


def _upsert_ec2_metric_rows(db, ec2_resource_id: int, daily: dict, launch_time=None):
    """Bulk upsert EC2 metric rows from parsed daily data."""

    metric_rows = []
    for metric_date, values in daily.items():
        hours = compute_hours_running(metric_date, launch_time)
        
        metric_rows.append({
            "ec2_resource_id": ec2_resource_id,
            "metric_date": metric_date,
            "cpu_utilization": values.get("cpu"),
            "network_in": values.get("netin"),
            "network_out": values.get("netout"),
            "hours_running": hours,
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
            "hours_running": stmt.excluded.hours_running,
        }
    )
    db.execute(stmt)
    # Removing db.commit() here so the caller handles transactions


# ─── Smart Sync: Check DB → Pull only missing → Save ─────────────

def smart_sync_ec2_metrics(
    customer_session: boto3.Session,
    account_id: str,
    region: str,
    profile_id: int,
    timezone_offset_hours: int = 7,
):
    """
    Smart metric sync for EC2 instances with gap detection.

    For each EC2 resource belonging to this profile:
      1. No metrics in DB  → full backfill (pull from launch_time to now)
      2. Has metrics        → detect internal gap dates AND new dates:
         - Computes expected range (min_date .. yesterday)
         - Finds missing dates (gaps + trailing)
         - Pulls from the earliest missing date to now
         - Upsert handles de-duplication of existing rows
      3. Already up to date with no gaps → skip

    Uses AssumeRole session to query CloudWatch.
    """


    db = database.SessionLocal()
    try:
        # 1. Discover live instances & upsert to DB
        logger.info(f"Discovering EC2 instances for profile {profile_id} in {region}...")
        live_instances = list_ec2_instances(customer_session, region)
        for inst in live_instances:
            iid = inst["instance_id"]
            resource = db.query(models.EC2Resource).filter_by(
                profile_id=profile_id, account_id=account_id, region=region, instance_id=iid
            ).first()
            if not resource:
                resource = models.EC2Resource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    instance_id=iid,
                    instance_type=inst.get("instance_type"),
                    state=inst.get("state"),
                    launch_time=inst.get("launch_time"),
                )
                db.add(resource)
            else:
                resource.instance_type = inst.get("instance_type")
                resource.state = inst.get("state")
        db.commit()

        # 2. Get all EC2 resources for this profile
        resources = (
            db.query(models.EC2Resource)
            .filter_by(profile_id=profile_id, region=region)
            .filter(models.EC2Resource.instance_id != 'AGGREGATED')
            .all()
        )

        if not resources:
            logger.info(f"No EC2 resources in DB for profile={profile_id}, region={region}")
            return

        today = date.today()
        yesterday = today - timedelta(days=1)

        for resource in resources:
            iid = resource.instance_id

            # Grab the launch instance from live_instances
            live_inst = next((i for i in live_instances if i["instance_id"] == iid), None)
            resource_launch_time = live_inst.get("launch_time") if live_inst else resource.launch_time
            
            try:
                # ── Get all existing metric dates for gap detection ──
                existing_dates_rows = (
                    db.query(models.EC2Metric.metric_date)
                    .filter_by(ec2_resource_id=resource.ec2_resource_id)
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
                        # Fully up to date with no internal gaps
                        logger.info(f" EC2 {iid} up to date (latest: {max_date}), no gaps, skipping")
                        continue

                    # Determine the earliest date we need to pull from
                    # Could be an internal gap or the day after max_date
                    if gap_dates:
                        pull_from = min(gap_dates)
                    else:
                        pull_from = max_date + timedelta(days=1)

                    start_dt = datetime.combine(
                        pull_from, time.min, tzinfo=timezone.utc
                    )
                    logger.info(
                        f"EC2 {iid} pulling from {pull_from} "
                        f"(gaps: {len(gap_dates)}, latest: {max_date})"
                    )
                else:
                    # Case 1: no data at all → pull full history based on launch time
                    start_dt = resource_launch_time
                    logger.info(f"EC2 {iid} first time, pulling full history since {start_dt}")

                # Pull CloudWatch metrics with basic retry
                queries = build_ec2_metric_queries_daily(iid)
                
                cw_resp = fetch_cw_with_retry(
                    customer_session=customer_session,
                    region=region,
                    queries=queries,
                    start_time=start_dt,
                    timezone_offset_hours=timezone_offset_hours,
                    max_retries=3
                )

                if cw_resp is None:
                    logger.error(f"EC2 {iid} CloudWatch pull failed after 3 retries, skipping")
                    continue

                # Parse and save (upsert handles duplicates safely)
                daily = group_cw_by_date(cw_resp)
                _upsert_ec2_metric_rows(db, resource.ec2_resource_id, daily, resource_launch_time)
                logger.info(f"Saved {len(daily)} metric rows for EC2 {iid}")
                
            except Exception as metric_err:
                logger.error(f"Failed syncing EC2 {iid}: {metric_err}")
                continue  # Skip to next instance instead of crashing whole job

        db.commit()
        logger.info(f"Smart sync completed for {len(resources)} EC2 resources")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in smart sync EC2 metrics: {e}")
        raise
    finally:
        db.close()