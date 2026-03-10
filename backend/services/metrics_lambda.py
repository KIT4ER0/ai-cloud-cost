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

def build_lambda_metric_queries_daily(function_name: str):
    """
    Build CloudWatch MetricDataQueries that return DAILY buckets.

    - Duration: DAILY p95 (true daily p95 computed by CloudWatch over the 1-day period)
    - Invocations: DAILY Sum
    - Errors: DAILY Sum
    """
    dims = [{"Name": "FunctionName", "Value": function_name}]

    def q(_id: str, metric: str, stat: str):
        return {
            "Id": _id,
            "Label": f"{function_name}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/Lambda",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,  # ✅ 1 day
                "Stat": stat,     # ✅ supports extended like 'p95'
            },
            "ReturnData": True,
        }

    return [
        q("duration", "Duration", "p95"),       # ✅ TRUE daily p95
        q("invocations", "Invocations", "Sum"), # ✅ daily sum
        q("errors", "Errors", "Sum"),           # ✅ daily sum
    ]




# ─── Lambda Function Discovery ────────────────────────────────────

def list_lambda_functions(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all Lambda functions in the customer's account.
    Returns list of dicts including last_modified for each function.
    """
    from datetime import datetime, timezone as tz
    lam = customer_session.client("lambda", region_name=region)
    functions = []

    paginator = lam.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page["Functions"]:
            # Lambda LastModified is a string like '2024-01-15T10:30:00.000+0000'
            last_mod_str = fn.get("LastModified")
            last_mod_dt = None
            if last_mod_str:
                try:
                    last_mod_dt = datetime.fromisoformat(last_mod_str.replace("+0000", "+00:00"))
                except ValueError:
                    pass

            functions.append({
                "function_name": fn["FunctionName"],
                "function_arn": fn.get("FunctionArn"),
                "runtime": fn.get("Runtime"),
                "memory_mb": fn.get("MemorySize"),
                "timeout_sec": fn.get("Timeout"),
                "last_modified": last_mod_dt,  # datetime (tz-aware) or None
            })

    logger.info(f"Found {len(functions)} Lambda functions in {region}")
    return functions


# ─── High-level: Pull Lambda Metrics ──────────────────────────────

def pull_lambda_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list Lambda functions → build DAILY queries → fetch CloudWatch metrics.
    Uses each function's LastModified as the start of the metric range.
    """
    functions = list_lambda_functions(customer_session, region)

    if not functions:
        logger.info("No Lambda functions found, skipping metric pull")
        return {}

    all_results = {}
    for fn in functions:
        fname = fn["function_name"]
        queries = build_lambda_metric_queries_daily(fname)

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            start_time=fn.get("last_modified"),
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[fname] = {"function": fn, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for {fname} (since {fn.get('last_modified')})")

    logger.info(f"Completed metric pull for {len(all_results)} Lambda functions")
    return all_results


# ─── Save Lambda Metrics to DB ────────────────────────────────────

def save_lambda_metrics(pull_results: dict, account_id: str, region: str, profile_id: int):
    """
    Save pulled Lambda metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

    db = database.SessionLocal()
    try:
        for fname, data in pull_results.items():
            fn = data["function"]
            cw_resp = data["metrics"]

            # 1) Upsert Lambda resource
            resource = db.query(models.LambdaResource).filter_by(
                account_id=account_id, region=region, function_name=fname
            ).first()

            if not resource:
                resource = models.LambdaResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    function_name=fname,
                    function_arn=fn.get("function_arn"),
                    runtime=fn.get("runtime"),
                    memory_mb=fn.get("memory_mb"),
                    timeout_sec=fn.get("timeout_sec"),
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)
            else:
                resource.function_arn = fn.get("function_arn")
                resource.runtime = fn.get("runtime")
                resource.memory_mb = fn.get("memory_mb")
                resource.timeout_sec = fn.get("timeout_sec")
                db.commit()

            if not cw_resp:
                continue

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "lambda_resource_id": resource.lambda_resource_id,
                    "metric_date": metric_date,
                    "duration_p95": values.get("duration"),     # daily p95
                    "invocations": values.get("invocations"),   # daily sum
                    "errors": values.get("errors"),             # daily sum
                })

            if metric_rows:
                stmt = insert(models.LambdaMetric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["lambda_resource_id", "metric_date"],
                    set_={
                        "duration_p95": stmt.excluded.duration_p95,
                        "invocations": stmt.excluded.invocations,
                        "errors": stmt.excluded.errors,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} DAILY metric rows for Lambda {fname}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving Lambda metrics: {e}")
        raise
    finally:
        db.close()


def _upsert_lambda_metric_rows(db, lambda_resource_id: int, daily: dict):
    """Bulk upsert Lambda metric rows from parsed daily data."""
    from .. import models
    from sqlalchemy.dialects.postgresql import insert

    metric_rows = []
    for metric_date, values in daily.items():
        metric_rows.append({
            "lambda_resource_id": lambda_resource_id,
            "metric_date": metric_date,
            "duration_p95": values.get("duration"),
            "invocations": values.get("invocations"),
            "errors": values.get("errors"),
        })

    if not metric_rows:
        return

    stmt = insert(models.LambdaMetric.__table__).values(metric_rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["lambda_resource_id", "metric_date"],
        set_={
            "duration_p95": stmt.excluded.duration_p95,
            "invocations": stmt.excluded.invocations,
            "errors": stmt.excluded.errors,
        }
    )
    db.execute(stmt)
    db.commit()


# ─── Smart Sync: Check DB → Pull only missing → Save ─────────────

def smart_sync_lambda_metrics(
    customer_session: boto3.Session,
    account_id: str,
    region: str,
    profile_id: int,
    timezone_offset_hours: int = 7,
):
    """
    Smart metric sync for Lambda functions with gap detection.

    For each Lambda resource belonging to this profile:
      1. No metrics in DB  → full backfill
      2. Has metrics        → detect gaps + new dates, pull from earliest missing
      3. Already up to date → skip
    """
    from .. import models, database
    from datetime import date, datetime, timedelta, timezone, time

    db = database.SessionLocal()
    try:
        # 1. Discover live Lambda functions & upsert to DB
        logger.info(f"Discovering Lambda functions for profile {profile_id} in {region}...")
        live_functions = list_lambda_functions(customer_session, region)
        logger.info(f"Found {len(live_functions)} Lambda functions in {region}")

        for fn in live_functions:
            fname = fn["function_name"]
            resource = db.query(models.LambdaResource).filter_by(
                account_id=account_id, region=region, function_name=fname
            ).first()
            if not resource:
                resource = models.LambdaResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    function_name=fname,
                    function_arn=fn.get("function_arn"),
                    runtime=fn.get("runtime"),
                    memory_mb=fn.get("memory_mb"),
                    timeout_sec=fn.get("timeout_sec"),
                )
                db.add(resource)
            else:
                resource.function_arn = fn.get("function_arn")
                resource.runtime = fn.get("runtime")
                resource.memory_mb = fn.get("memory_mb")
                resource.timeout_sec = fn.get("timeout_sec")
        db.commit()

        # 2. Get all Lambda resources for this profile
        resources = (
            db.query(models.LambdaResource)
            .filter_by(profile_id=profile_id, region=region)
            .all()
        )

        if not resources:
            logger.info(f"No Lambda resources in DB for profile={profile_id}, region={region}")
            return

        today = date.today()
        yesterday = today - timedelta(days=1)

        for resource in resources:
            fname = resource.function_name

            # ── Get all existing metric dates for gap detection ──
            existing_dates_rows = (
                db.query(models.LambdaMetric.metric_date)
                .filter_by(lambda_resource_id=resource.lambda_resource_id)
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
                    logger.info(f"  ✅ Lambda {fname} up to date (latest: {max_date}), no gaps, skipping")
                    continue

                if gap_dates:
                    pull_from = min(gap_dates)
                else:
                    pull_from = max_date + timedelta(days=1)

                start_dt = datetime.combine(
                    pull_from, time.min, tzinfo=timezone.utc
                )
                logger.info(
                    f"  📦 Lambda {fname} pulling from {pull_from} "
                    f"(gaps: {len(gap_dates)}, latest: {max_date})"
                )
            else:
                start_dt = None
                logger.info(f"  🆕 Lambda {fname} first time, pulling full history")

            # Pull CloudWatch metrics
            queries = build_lambda_metric_queries_daily(fname)
            cw_resp = get_cloudwatch_metric_data(
                customer_session=customer_session,
                region=region,
                metric_data_queries=queries,
                start_time=start_dt,
                timezone_offset_hours=timezone_offset_hours,
            )

            if not cw_resp:
                logger.warning(f"  ⚠️ No CloudWatch response for Lambda {fname}")
                continue

            daily = group_cw_by_date(cw_resp)
            _upsert_lambda_metric_rows(db, resource.lambda_resource_id, daily)
            logger.info(f"  💾 Saved {len(daily)} metric rows for Lambda {fname}")

        logger.info(f"Smart sync completed for {len(resources)} Lambda resources")

    except Exception as e:
        db.rollback()
        logger.error(f"Error in smart sync Lambda metrics: {e}")
        raise
    finally:
        db.close()