import boto3
import logging
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, print_all_datapoints
from .aggregate import aggregate_hourly_to_daily, S3_STRATEGIES

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def build_s3_metric_queries_daily(bucket_name: str):
    """
    S3 metrics are reported once per day with StorageType dimension.
    Period must be 86400 (1 day).
    """
    dims = [
        {"Name": "BucketName", "Value": bucket_name},
        {"Name": "StorageType", "Value": "StandardStorage"},
    ]

    def q(_id: str, metric: str, stat: str):
        return {
            "Id": _id,
            "Label": f"{bucket_name}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/S3",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,
                "Stat": stat,
            },
            "ReturnData": True,
        }

    return [
        q("storage_bytes", "BucketSizeBytes", "Average"),
        q("num_objects", "NumberOfObjects", "Average"),
    ]


# ─── S3 Bucket Discovery ──────────────────────────────────────────

def list_s3_buckets(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all S3 buckets in the customer's account, filtering by region.
    """
    s3 = customer_session.client("s3", region_name=region)
    buckets = []

    try:
        response = s3.list_buckets()
        for b in response.get("Buckets", []):
            bucket_name = b["Name"]
            try:
                loc = s3.get_bucket_location(Bucket=bucket_name)
                bucket_region = loc.get("LocationConstraint") or "us-east-1"
                if bucket_region == region:
                    buckets.append({
                        "bucket_name": bucket_name,
                        "region": bucket_region,
                    })
            except ClientError as e:
                logger.warning(f"Cannot get location for bucket {bucket_name}: {e}")
                continue
    except ClientError as e:
        logger.error(f"Failed to list S3 buckets: {e}")
        return []

    logger.info(f"Found {len(buckets)} S3 buckets in {region}")
    return buckets


# ─── High-level: Pull S3 Metrics ──────────────────────────────────

def pull_s3_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    days_back: int = 30,
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list S3 buckets → build queries → fetch CloudWatch metrics.
    """
    buckets = list_s3_buckets(customer_session, region)

    if not buckets:
        logger.info("No S3 buckets found in region, skipping metric pull")
        return {}

    all_results = {}
    for bkt in buckets:
        bname = bkt["bucket_name"]
        queries = build_s3_metric_queries_daily(bname)
        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )
        all_results[bname] = {"bucket": bkt, "metrics": metrics}
        logger.info(f"Fetched metrics for bucket {bname}")

    logger.info(f"Completed metric pull for {len(all_results)} S3 buckets")
    return all_results


# ─── Save S3 Metrics to DB ────────────────────────────────────────

def save_s3_metrics(pull_results: dict, account_id: str, region: str, profile_id: int):
    """
    Save pulled S3 metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

    db = database.SessionLocal()
    try:
        for bname, data in pull_results.items():
            bkt = data["bucket"]
            cw_resp = data["metrics"]

            # 1) Upsert S3 resource
            resource = db.query(models.S3Resource).filter_by(
                account_id=account_id, region=region, bucket_name=bname
            ).first()

            if not resource:
                resource = models.S3Resource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    bucket_name=bname,
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)

            if not cw_resp:
                continue

            # 2) Aggregate daily (S3 Period=86400)
            daily = aggregate_hourly_to_daily(cw_resp, S3_STRATEGIES)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "s3_resource_id": resource.s3_resource_id,
                    "metric_date": metric_date,
                    "bucket_size_bytes": values.get("storage_bytes"),
                    "number_of_objects": values.get("num_objects"),
                })

            if metric_rows:
                stmt = insert(models.S3Metric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["s3_resource_id", "metric_date"],
                    set_={
                        "bucket_size_bytes": stmt.excluded.bucket_size_bytes,
                        "number_of_objects": stmt.excluded.number_of_objects,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} metric rows for S3 {bname}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving S3 metrics: {e}")
        raise
    finally:
        db.close()
