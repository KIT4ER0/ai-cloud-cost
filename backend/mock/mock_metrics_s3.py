import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# Realistic cost rates (us-east-1)
STORAGE_COST_PER_GB = 0.023
GET_COST_PER_1000 = 0.0004
PUT_COST_PER_1000 = 0.005
TRANSFER_COST_PER_GB = 0.09

def _calculate_storage_cost(bucket_size_bytes: int) -> float:
    gb = bucket_size_bytes / (1024 ** 3)
    return round(gb * STORAGE_COST_PER_GB, 6)

def _calculate_request_cost(get_requests: int, put_requests: int) -> float:
    get_cost = (get_requests / 1000) * GET_COST_PER_1000
    put_cost = (put_requests / 1000) * PUT_COST_PER_1000
    return round(get_cost + put_cost, 6)

def _calculate_transfer_cost(bytes_downloaded: int) -> float:
    gb = bytes_downloaded / (1024 ** 3)
    return round(gb * TRANSFER_COST_PER_GB, 6)

def mock_smart_sync_s3_metrics(db, account_id: str, region: str, profile_id: int):
    """
    Mock function that simulates smart_sync_s3_metrics.
    Upserts multiple fake S3Resources, S3Metrics, and S3Costs into the database
    over the past 180 days with randomized realistic values.
    """
    from .. import models

    logger.info(f"Running MOCK smart sync for account {account_id} region {region}")

    mock_buckets = [
        {"name": "mock-webapp-assets-" + account_id[-4:]},
        {"name": "mock-database-backups-" + account_id[-4:]},
        {"name": "mock-user-uploads-" + account_id[-4:]},
        {"name": "mock-logs-archive-" + account_id[-4:]},
    ]

    try:
        for bkt in mock_buckets:
            bucket_name = bkt["name"]

            # 1. Upsert S3Resource
            resource = db.query(models.S3Resource).filter_by(
                account_id=account_id, region=region, bucket_name=bucket_name
            ).first()

            if not resource:
                resource = models.S3Resource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    bucket_name=bucket_name,
                    storage_class="Standard",
                    bucket_arn=f"arn:aws:s3:::{bucket_name}",
                    is_versioning_enabled=random.choice([True, False]),
                    tags={"Environment": "Mock", "Project": "CloudCost"},
                )
                db.add(resource)
                db.flush()

            # 2. Upsert S3Metrics + S3Costs for the past 180 days
            metric_rows = []
            cost_rows = []

            # Initialize with realistic starting values
            current_size = random.randint(50_000_000, 200_000_000)  # 50-200MB start
            current_objects = random.randint(500, 2000)

            for days_ago in reversed(range(180)):
                dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
                dt_iso = dt.isoformat()

                # More realistic gradual growth (smaller increments)
                size_growth = random.randint(0, 10_000_000)  # 0-10MB per day
                object_growth = random.randint(0, 20)  # 0-20 objects per day
                
                # Weekend patterns (less activity)
                if dt.weekday() >= 5:
                    size_growth = int(size_growth * 0.3)  # 70% less on weekends
                    object_growth = int(object_growth * 0.3)

                current_size += size_growth
                current_objects += object_growth

                # More realistic request patterns with daily variations
                base_get = random.randint(500, 2000)
                base_put = random.randint(50, 200)
                
                # Apply daily/weekly patterns
                if dt.weekday() >= 5:  # Weekend
                    get_requests = int(base_get * random.uniform(0.3, 0.7))
                    put_requests = int(base_put * random.uniform(0.2, 0.6))
                else:  # Weekday
                    get_requests = int(base_get * random.uniform(0.8, 1.5))
                    put_requests = int(base_put * random.uniform(0.7, 1.3))
                
                # Realistic data transfer ranges
                bytes_downloaded = get_requests * random.randint(1000, 50000)  # 1-50KB per request

                metric_rows.append({
                    "s3_resource_id": resource.s3_resource_id,
                    "metric_date": dt_iso,
                    "bucket_size_bytes": current_size,
                    "number_of_objects": current_objects,
                    "get_requests": get_requests,
                    "put_requests": put_requests,
                    "bytes_downloaded": bytes_downloaded,
                    "bytes_uploaded": put_requests * random.randint(2000, 100000),  # 2-100KB per put
                    "delete_requests": random.randint(0, 10),  # Fewer deletes
                    "list_requests": random.randint(20, 100),  # Moderate list operations
                })

                storage_cost = _calculate_storage_cost(current_size)
                request_cost = _calculate_request_cost(get_requests, put_requests)
                transfer_cost = _calculate_transfer_cost(bytes_downloaded)
                total_cost = round(storage_cost + request_cost + transfer_cost, 6)

                cost_rows.extend([
                    {
                        "s3_resource_id": resource.s3_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "TimedStorage-ByteHrs",
                        "amount_usd": storage_cost,
                        "currency_src": "USD",
                    },
                    {
                        "s3_resource_id": resource.s3_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "Requests-Tier1-Tier2",
                        "amount_usd": request_cost,
                        "currency_src": "USD",
                    },
                    {
                        "s3_resource_id": resource.s3_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "DataTransfer-Out-Bytes",
                        "amount_usd": transfer_cost,
                        "currency_src": "USD",
                    },
                    {
                        "s3_resource_id": resource.s3_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": "total",
                        "amount_usd": total_cost,
                        "currency_src": "USD",
                    },
                ])

            # Upsert metrics
            if metric_rows:
                stmt = insert(models.S3Metric).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["s3_resource_id", "metric_date"],
                    set_={
                        "bucket_size_bytes": stmt.excluded.bucket_size_bytes,
                        "number_of_objects": stmt.excluded.number_of_objects,
                        "get_requests": stmt.excluded.get_requests,
                        "put_requests": stmt.excluded.put_requests,
                        "bytes_downloaded": stmt.excluded.bytes_downloaded,
                        "bytes_uploaded": stmt.excluded.bytes_uploaded,
                        "delete_requests": stmt.excluded.delete_requests,
                        "list_requests": stmt.excluded.list_requests,
                    },
                )
                db.execute(stmt)

            # Upsert costs
            if cost_rows:
                stmt = insert(models.S3Cost).values(cost_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["s3_resource_id", "usage_date", "usage_type"],
                    set_={
                        "amount_usd": stmt.excluded.amount_usd,
                        "currency_src": stmt.excluded.currency_src,
                    },
                )
                db.execute(stmt)

            logger.info(
                f"MOCK sync completed for {bucket_name} — "
                f"{len(metric_rows)} metric rows, {len(cost_rows)} cost rows"
            )

        db.commit()
        logger.info("All MOCK S3 buckets synced successfully")

    except Exception as e:
        db.rollback()
        logger.error(f"MOCK sync failed: {e}")
        raise