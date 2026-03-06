import boto3
import logging
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, print_all_datapoints
from .aggregate import group_cw_by_date

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def build_s3_metric_queries_daily(bucket_name: str, request_filter_id: str = "EntireBucket"):
    """
    S3 has 2 families of metrics with different dimensions:

    1) Storage metrics (daily, once/day):
       Namespace: AWS/S3
       Dimensions: BucketName, StorageType
       Metrics: BucketSizeBytes, NumberOfObjects
       Stat: Average
       Period: 86400

    2) Request metrics (must be enabled in S3):
       Namespace: AWS/S3
       Dimensions: BucketName, FilterId
       Metrics: GetRequests, PutRequests, BytesDownloaded, BytesUploaded
       Stat: Sum
       Period: 86400

    request_filter_id:
      - Common value is "EntireBucket" when enabling request metrics for whole bucket
      - If you configured a different filter id, pass it here
    """
    # Storage metrics dims
    storage_dims = [
        {"Name": "BucketName", "Value": bucket_name},
        {"Name": "StorageType", "Value": "StandardStorage"},
    ]

    # Request metrics dims
    request_dims = [
        {"Name": "BucketName", "Value": bucket_name},
        {"Name": "FilterId", "Value": request_filter_id},
    ]

    def q(_id: str, metric: str, stat: str, dims):
        return {
            "Id": _id,
            "Label": f"{bucket_name}:{metric}:{stat}:daily",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/S3",
                    "MetricName": metric,
                    "Dimensions": dims,
                },
                "Period": 86400,  # ✅ daily
                "Stat": stat,
            },
            "ReturnData": True,
        }

    return [
        # ===== Storage (daily snapshot-ish) =====
        q("storage_bytes", "BucketSizeBytes", "Average", storage_dims),
        q("num_objects", "NumberOfObjects", "Average", storage_dims),

        # ===== Requests (must enable S3 Request Metrics) =====
        q("get_requests", "GetRequests", "Sum", request_dims),
        q("put_requests", "PutRequests", "Sum", request_dims),
        q("bytes_downloaded", "BytesDownloaded", "Sum", request_dims),
        q("bytes_uploaded", "BytesUploaded", "Sum", request_dims),
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
    request_filter_id: str = "EntireBucket",
) -> dict:
    """
    End-to-end: list S3 buckets → build DAILY queries → fetch CloudWatch metrics.
    """
    buckets = list_s3_buckets(customer_session, region)

    if not buckets:
        logger.info("No S3 buckets found in region, skipping metric pull")
        return {}

    all_results = {}
    for bkt in buckets:
        bname = bkt["bucket_name"]

        queries = build_s3_metric_queries_daily(bname, request_filter_id=request_filter_id)

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[bname] = {"bucket": bkt, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for bucket {bname}")

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

            # 2) Parse daily CloudWatch results
            daily = group_cw_by_date(cw_resp)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "s3_resource_id": resource.s3_resource_id,
                    "metric_date": metric_date,

                    "bucket_size_bytes": values.get("storage_bytes"),
                    "number_of_objects": values.get("num_objects"),

                    # ✅ new request metrics
                    "get_requests": values.get("get_requests"),
                    "put_requests": values.get("put_requests"),
                    "bytes_downloaded": values.get("bytes_downloaded"),
                    "bytes_uploaded": values.get("bytes_uploaded"),
                })

            if metric_rows:
                stmt = insert(models.S3Metric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["s3_resource_id", "metric_date"],
                    set_={
                        "bucket_size_bytes": stmt.excluded.bucket_size_bytes,
                        "number_of_objects": stmt.excluded.number_of_objects,
                        "get_requests": stmt.excluded.get_requests,
                        "put_requests": stmt.excluded.put_requests,
                        "bytes_downloaded": stmt.excluded.bytes_downloaded,
                        "bytes_uploaded": stmt.excluded.bytes_uploaded,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} DAILY metric rows for S3 {bname}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving S3 metrics: {e}")
        raise
    finally:
        db.close()