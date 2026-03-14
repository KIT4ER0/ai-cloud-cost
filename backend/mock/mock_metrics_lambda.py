import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# Realistic cost rates (us-east-1)
REQUEST_COST_PER_1M = 0.20
DURATION_COST_PER_GB_SECOND = 0.0000166667
PROVISIONED_CONCURRENCY_COST_PER_GB_SECOND = 0.0000097222

RUNTIME_OPTIONS = [
    "python3.11",
    "python3.12",
    "nodejs20.x",
    "nodejs18.x",
    "java21",
    "go1.x",
]

MEMORY_OPTIONS = [128, 256, 512, 1024, 2048, 3008]  # MB


def _calculate_request_cost(invocations: int) -> float:
    return round((invocations / 1_000_000) * REQUEST_COST_PER_1M, 6)


def _calculate_duration_cost(memory_mb: int, avg_duration_ms: float, invocations: int) -> float:
    gb = memory_mb / 1024
    seconds = avg_duration_ms / 1000
    gb_seconds = gb * seconds * invocations
    return round(gb_seconds * DURATION_COST_PER_GB_SECOND, 6)


def mock_smart_sync_lambda_metrics(db, account_id: str, region: str, profile_id: int):
    """
    Mock function that simulates smart_sync_lambda_metrics.
    Upserts multiple fake LambdaResources, LambdaMetrics, and LambdaCosts
    into the database over the past 90 days with randomized realistic values.
    """
    from .. import models

    logger.info(f"Running MOCK Lambda smart sync for account {account_id} region {region}")

    mock_functions = [
        {
            "name": f"mock-api-handler-{account_id[-4:]}",
            "memory_mb": 512,
            "runtime": "python3.11",
            "description": "Handles API Gateway requests",
        },
        {
            "name": f"mock-image-processor-{account_id[-4:]}",
            "memory_mb": 2048,
            "runtime": "nodejs20.x",
            "description": "Processes uploaded images",
        },
        {
            "name": f"mock-scheduled-job-{account_id[-4:]}",
            "memory_mb": 256,
            "runtime": "python3.12",
            "description": "Runs nightly batch jobs",
        },
        {
            "name": f"mock-event-consumer-{account_id[-4:]}",
            "memory_mb": 1024,
            "runtime": "nodejs18.x",
            "description": "Consumes SQS/Kinesis events",
        },
    ]

    try:
        for fn in mock_functions:
            function_name = fn["name"]
            memory_mb = fn["memory_mb"]
            function_arn = (
                f"arn:aws:lambda:{region}:{account_id}:function:{function_name}"
            )

            # 1. Upsert LambdaResource
            resource = db.query(models.LambdaResource).filter_by(
                account_id=account_id,
                region=region,
                function_name=function_name,
            ).first()

            if not resource:
                resource = models.LambdaResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    function_name=function_name,
                    function_arn=function_arn,
                    runtime=fn["runtime"],
                    memory_size=memory_mb,
                    timeout=random.choice([30, 60, 120, 300, 900]),
                    description=fn["description"],
                    last_modified=datetime.now(timezone.utc),
                    tags={"Environment": "Mock", "Project": "CloudCost"},
                )
                db.add(resource)
                db.flush()

            # 2. Upsert LambdaMetrics + LambdaCosts for the past 90 days
            metric_rows = []
            cost_rows = []

            for days_ago in reversed(range(90)):
                dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
                dt_iso = dt.isoformat()

                invocations = random.randint(1_000, 500_000)
                errors = random.randint(0, int(invocations * 0.05))  # up to 5% error rate
                throttles = random.randint(0, int(invocations * 0.01))  # up to 1% throttle
                avg_duration_ms = random.uniform(50, 5000)
                max_duration_ms = avg_duration_ms * random.uniform(1.2, 3.0)
                min_duration_ms = avg_duration_ms * random.uniform(0.3, 0.9)
                concurrent_executions = random.randint(1, 200)
                cold_starts = random.randint(0, int(invocations * 0.02))  # up to 2% cold start

                metric_rows.append({
                    "lambda_resource_id": resource.lambda_resource_id,
                    "metric_date": dt_iso,
                    "invocations": invocations,
                    "errors": errors,
                    "throttles": throttles,
                    "avg_duration_ms": round(avg_duration_ms, 3),
                    "max_duration_ms": round(max_duration_ms, 3),
                    "min_duration_ms": round(min_duration_ms, 3),
                    "concurrent_executions": concurrent_executions,
                    "cold_starts": cold_starts,
                })

                request_cost = _calculate_request_cost(invocations)
                duration_cost = _calculate_duration_cost(memory_mb, avg_duration_ms, invocations)
                total_cost = round(request_cost + duration_cost, 6)

                cost_rows.extend([
                    {
                        "lambda_resource_id": resource.lambda_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "Lambda-GB-Second",
                        "amount_usd": duration_cost,
                        "currency_src": "USD",
                    },
                    {
                        "lambda_resource_id": resource.lambda_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "Lambda-Request",
                        "amount_usd": request_cost,
                        "currency_src": "USD",
                    },
                    {
                        "lambda_resource_id": resource.lambda_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "total",
                        "amount_usd": total_cost,
                        "currency_src": "USD",
                    },
                ])

            # Upsert metrics
            if metric_rows:
                stmt = insert(models.LambdaMetric).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["lambda_resource_id", "metric_date"],
                    set_={
                        "invocations": stmt.excluded.invocations,
                        "errors": stmt.excluded.errors,
                        "throttles": stmt.excluded.throttles,
                        "avg_duration_ms": stmt.excluded.avg_duration_ms,
                        "max_duration_ms": stmt.excluded.max_duration_ms,
                        "min_duration_ms": stmt.excluded.min_duration_ms,
                        "concurrent_executions": stmt.excluded.concurrent_executions,
                        "cold_starts": stmt.excluded.cold_starts,
                    },
                )
                db.execute(stmt)

            # Upsert costs
            if cost_rows:
                stmt = insert(models.LambdaCost).values(cost_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["lambda_resource_id", "usage_date", "usage_type"],
                    set_={
                        "amount_usd": stmt.excluded.amount_usd,
                        "currency_src": stmt.excluded.currency_src,
                    },
                )
                db.execute(stmt)

            logger.info(
                f"MOCK Lambda sync completed for {function_name} — "
                f"{len(metric_rows)} metric rows, {len(cost_rows)} cost rows"
            )

        db.commit()
        logger.info("All MOCK Lambda functions synced successfully")

    except Exception as e:
        db.rollback()
        logger.error(f"MOCK Lambda sync failed: {e}")
        raise