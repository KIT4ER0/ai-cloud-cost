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

def build_alb_metric_queries_daily(load_balancer_arn_suffix: str):
    """
    ALB metrics use the LoadBalancer dimension which is the ARN suffix,
    e.g. 'app/my-alb/50dc6c495c0c9188'

    Daily buckets:
    - RequestCount: Sum (daily total requests)
    - TargetResponseTime: p95 (true daily p95)
    - HTTPCode_Target_5XX_Count: Sum
    - ActiveConnectionCount: Maximum (gauge -> peak)
    """
    dims = [{"Name": "LoadBalancer", "Value": load_balancer_arn_suffix}]

    def q(_id: str, metric: str, stat: str):
        return {
            "Id": _id,
            "Label": f"{load_balancer_arn_suffix}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/ApplicationELB",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,  # ✅ 1 day
                "Stat": stat,     # ✅ extended allowed, e.g. 'p95'
            },
            "ReturnData": True,
        }

    return [
        q("request_count", "RequestCount", "Sum"),
        q("response_time", "TargetResponseTime", "p95"),  # ✅ daily p95
        q("http_5xx", "HTTPCode_Target_5XX_Count", "Sum"),
        q("active_conn", "ActiveConnectionCount", "Maximum"),  # ✅ gauge -> max
    ]



# ─── ALB Discovery ────────────────────────────────────────────────

def _extract_alb_arn_suffix(arn: str) -> str:
    """
    Extract the LoadBalancer dimension value from full ARN.
    Full ARN: arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-alb/50dc6c495c0c9188
    Dimension: app/my-alb/50dc6c495c0c9188
    """
    parts = arn.split("loadbalancer/", 1)
    return parts[1] if len(parts) == 2 else arn


def list_alb_load_balancers(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all Application Load Balancers in the customer's account.
    Returns list of dicts including created_time for each ALB.
    """
    elbv2 = customer_session.client("elbv2", region_name=region)
    load_balancers = []

    paginator = elbv2.get_paginator("describe_load_balancers")
    for page in paginator.paginate():
        for lb in page["LoadBalancers"]:
            if lb.get("Type") == "application":
                load_balancers.append({
                    "lb_name": lb["LoadBalancerName"],
                    "lb_arn": lb["LoadBalancerArn"],
                    "lb_arn_suffix": _extract_alb_arn_suffix(lb["LoadBalancerArn"]),
                    "dns_name": lb.get("DNSName"),
                    "scheme": lb.get("Scheme"),
                    "created_time": lb.get("CreatedTime"),  # datetime (tz-aware)
                })

    logger.info(f"Found {len(load_balancers)} ALBs in {region}")
    return load_balancers


# ─── High-level: Pull ALB Metrics ─────────────────────────────────

def pull_alb_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list ALBs → build DAILY queries → fetch CloudWatch metrics.
    Uses each ALB's CreatedTime as the start of the metric range.
    """
    load_balancers = list_alb_load_balancers(customer_session, region)

    if not load_balancers:
        logger.info("No ALBs found, skipping metric pull")
        return {}

    all_results = {}
    for lb in load_balancers:
        lb_name = lb["lb_name"]
        queries = build_alb_metric_queries_daily(lb["lb_arn_suffix"])

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            start_time=lb.get("created_time"),
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[lb_name] = {"load_balancer": lb, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for ALB {lb_name} (since {lb.get('created_time')})")

    logger.info(f"Completed metric pull for {len(all_results)} ALBs")
    return all_results


# ─── Save ALB Metrics to DB ───────────────────────────────────────

def save_alb_metrics(pull_results: dict, account_id: str, region: str, profile_id: int):
    """
    Save pulled ALB metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

    db = database.SessionLocal()
    try:
        for lb_name, data in pull_results.items():
            lb = data["load_balancer"]
            cw_resp = data["metrics"]

            # 1) Upsert ALB resource
            resource = db.query(models.ALBResource).filter_by(
                profile_id=profile_id, account_id=account_id, region=region, lb_name=lb_name
            ).first()

            if not resource:
                resource = models.ALBResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    lb_name=lb_name,
                    lb_arn=lb.get("lb_arn"),
                    dns_name=lb.get("dns_name"),
                    scheme=lb.get("scheme"),
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)
            else:
                resource.lb_arn = lb.get("lb_arn")
                resource.dns_name = lb.get("dns_name")
                resource.scheme = lb.get("scheme")
                db.commit()

            if not cw_resp:
                continue

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "alb_resource_id": resource.alb_resource_id,
                    "metric_date": metric_date,
                    "request_count": values.get("request_count"),
                    "response_time_p95": values.get("response_time"),  # daily p95
                    "http_5xx_count": values.get("http_5xx"),
                    "active_conn_count": values.get("active_conn"),
                })

            if metric_rows:
                stmt = insert(models.ALBMetric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["alb_resource_id", "metric_date"],
                    set_={
                        "request_count": stmt.excluded.request_count,
                        "response_time_p95": stmt.excluded.response_time_p95,
                        "http_5xx_count": stmt.excluded.http_5xx_count,
                        "active_conn_count": stmt.excluded.active_conn_count,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} DAILY metric rows for ALB {lb_name}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving ALB metrics: {e}")
        raise
    finally:
        db.close()


def _upsert_alb_metric_rows(db, alb_resource_id: int, daily: dict):
    """Bulk upsert ALB metric rows from parsed daily data."""
    from .. import models
    from sqlalchemy.dialects.postgresql import insert

    metric_rows = []
    for metric_date, values in daily.items():
        metric_rows.append({
            "alb_resource_id": alb_resource_id,
            "metric_date": metric_date,
            "request_count": values.get("request_count"),
            "response_time_p95": values.get("response_time"),
            "http_5xx_count": values.get("http_5xx"),
            "active_conn_count": values.get("active_conn"),
        })

    if not metric_rows:
        return

    stmt = insert(models.ALBMetric.__table__).values(metric_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["alb_resource_id", "metric_date"],
        set_={
            "request_count": stmt.excluded.request_count,
            "response_time_p95": stmt.excluded.response_time_p95,
            "http_5xx_count": stmt.excluded.http_5xx_count,
            "active_conn_count": stmt.excluded.active_conn_count,
        }
    )
    db.execute(stmt)
    db.commit()


# ─── Smart Sync: Check DB → Pull only missing → Save ─────────────

def smart_sync_alb_metrics(
    customer_session: boto3.Session,
    account_id: str,
    region: str,
    profile_id: int,
    timezone_offset_hours: int = 7,
):
    """
    Smart metric sync for ALBs with gap detection.

    For each ALB resource belonging to this profile:
      1. No metrics in DB  → full backfill
      2. Has metrics        → detect gaps + new dates, pull from earliest missing
      3. Already up to date → skip
    """
    from .. import models, database
    from datetime import date, datetime, timedelta, timezone, time

    db = database.SessionLocal()
    try:
        # 1. Discover live ALBs & upsert to DB
        logger.info(f"Discovering ALBs for profile {profile_id} in {region}...")
        live_albs = list_alb_load_balancers(customer_session, region)
        logger.info(f"Found {len(live_albs)} ALBs in {region}")

        for lb in live_albs:
            lb_name = lb["lb_name"]
            resource = db.query(models.ALBResource).filter_by(
                account_id=account_id, region=region, lb_name=lb_name
            ).first()
            if not resource:
                resource = models.ALBResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    lb_name=lb_name,
                    lb_arn=lb.get("lb_arn"),
                    dns_name=lb.get("dns_name"),
                    scheme=lb.get("scheme"),
                )
                db.add(resource)
            else:
                resource.lb_arn = lb.get("lb_arn")
                resource.dns_name = lb.get("dns_name")
                resource.scheme = lb.get("scheme")
        db.commit()

        # 2. Get all ALB resources for this profile
        resources = (
            db.query(models.ALBResource)
            .filter_by(profile_id=profile_id, region=region)
            .all()
        )

        if not resources:
            logger.info(f"No ALB resources in DB for profile={profile_id}, region={region}")
            return

        today = date.today()
        yesterday = today - timedelta(days=1)

        for resource in resources:
            lb_name = resource.lb_name

            # Need the ARN suffix for CloudWatch queries
            lb_arn_suffix = _extract_alb_arn_suffix(resource.lb_arn) if resource.lb_arn else None
            if not lb_arn_suffix:
                logger.warning(f"  ⚠️ ALB {lb_name} has no ARN, skipping")
                continue

            # ── Get all existing metric dates for gap detection ──
            existing_dates_rows = (
                db.query(models.ALBMetric.metric_date)
                .filter_by(alb_resource_id=resource.alb_resource_id)
                .all()
            )
            existing_dates = {row[0] for row in existing_dates_rows}

            if existing_dates:
                min_date = min(existing_dates)
                max_date = max(existing_dates)

                expected_dates = {
                    min_date + timedelta(days=i)
                    for i in range((yesterday - min_date).days + 1)
                }
                gap_dates = expected_dates - existing_dates

                if max_date >= yesterday and not gap_dates:
                    logger.info(f"  ✅ ALB {lb_name} up to date (latest: {max_date}), no gaps, skipping")
                    continue

                if gap_dates:
                    pull_from = min(gap_dates)
                else:
                    pull_from = max_date + timedelta(days=1)

                start_dt = datetime.combine(
                    pull_from, time.min, tzinfo=timezone.utc
                )
                logger.info(
                    f"  📦 ALB {lb_name} pulling from {pull_from} "
                    f"(gaps: {len(gap_dates)}, latest: {max_date})"
                )
            else:
                start_dt = None
                logger.info(f"  🆕 ALB {lb_name} first time, pulling full history")

            # Pull CloudWatch metrics
            queries = build_alb_metric_queries_daily(lb_arn_suffix)
            cw_resp = get_cloudwatch_metric_data(
                customer_session=customer_session,
                region=region,
                metric_data_queries=queries,
                start_time=start_dt,
                timezone_offset_hours=timezone_offset_hours,
            )

            if not cw_resp:
                logger.warning(f"  ⚠️ No CloudWatch response for ALB {lb_name}")
                continue

            daily = group_cw_by_date(cw_resp)
            _upsert_alb_metric_rows(db, resource.alb_resource_id, daily)
            logger.info(f"  💾 Saved {len(daily)} metric rows for ALB {lb_name}")

        logger.info(f"Smart sync completed for {len(resources)} ALB resources")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in smart sync ALB metrics: {e}")
        raise
    finally:
        db.close()