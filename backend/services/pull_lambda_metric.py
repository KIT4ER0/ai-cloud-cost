import boto3
import logging
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, print_all_datapoints
from .aggregate import aggregate_hourly_to_daily, LAMBDA_STRATEGIES

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def build_lambda_metric_queries_hourly(function_name: str):
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
                "Period": 3600,
                "Stat": stat,
            },
            "ReturnData": True,
        }

    return [
        q("duration", "Duration", "p95"),
        q("invocations", "Invocations", "Sum"),
        q("errors", "Errors", "Sum"),
    ]


# ─── Lambda Function Discovery ────────────────────────────────────

def list_lambda_functions(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all Lambda functions in the customer's account via ListFunctions.
    """
    lam = customer_session.client("lambda", region_name=region)
    functions = []

    paginator = lam.get_paginator("list_functions")
    for page in paginator.paginate():
        for fn in page["Functions"]:
            functions.append({
                "function_name": fn["FunctionName"],
                "function_arn": fn.get("FunctionArn"),
                "runtime": fn.get("Runtime"),
                "memory_mb": fn.get("MemorySize"),
                "timeout_sec": fn.get("Timeout"),
            })

    logger.info(f"Found {len(functions)} Lambda functions in {region}")
    return functions


# ─── High-level: Pull Lambda Metrics ──────────────────────────────

def pull_lambda_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    days_back: int = 30,
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list Lambda functions → build queries → fetch CloudWatch metrics.
    """
    functions = list_lambda_functions(customer_session, region)

    if not functions:
        logger.info("No Lambda functions found, skipping metric pull")
        return {}

    all_results = {}
    for fn in functions:
        fname = fn["function_name"]
        queries = build_lambda_metric_queries_hourly(fname)
        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )
        all_results[fname] = {"function": fn, "metrics": metrics}
        logger.info(f"Fetched metrics for {fname} ({fn['runtime']})")

    logger.info(f"Completed metric pull for {len(all_results)} Lambda functions")
    return all_results


# ─── Save Lambda Metrics to DB ────────────────────────────────────

def save_lambda_metrics(pull_results: dict, account_id: str, region: str):
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

            # 2) Aggregate hourly → daily
            daily = aggregate_hourly_to_daily(cw_resp, LAMBDA_STRATEGIES)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "lambda_resource_id": resource.lambda_resource_id,
                    "metric_date": metric_date,
                    "duration_p95": values.get("duration"),
                    "invocations": values.get("invocations"),
                    "errors": values.get("errors"),
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

            logger.info(f"Saved {len(metric_rows)} metric rows for Lambda {fname}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving Lambda metrics: {e}")
        raise
    finally:
        db.close()
