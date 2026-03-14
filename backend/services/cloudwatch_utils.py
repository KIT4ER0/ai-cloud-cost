import boto3
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
import time as time_module
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def print_all_datapoints(cw_resp, timezone_offset_hours: int = 0):
    if not cw_resp:
        print("No CloudWatch response")
        return

    tz = timezone(timedelta(hours=timezone_offset_hours))
    results = cw_resp.get("MetricDataResults", [])
    print(f"MetricDataResults count: {len(results)}")
    print("StartTimeUTC:", cw_resp.get("StartTimeUTC"))
    print("EndTimeUTC  :", cw_resp.get("EndTimeUTC"))

    for r in results:
        _id = r.get("Id")
        label = r.get("Label")
        status = r.get("StatusCode")
        ts = r.get("Timestamps", [])
        vals = r.get("Values", [])

        print("\n" + "=" * 80)
        print(f"Id: {_id}")
        if label:
            print(f"Label: {label}")
        print(f"StatusCode: {status}")
        print(f"Total points: {len(vals)}")

        pairs = sorted(zip(ts, vals), key=lambda x: x[0])
        for t, v in pairs:
            print(f"{t.astimezone(tz).isoformat()}  {v}")

def get_cloudwatch_metric_data(
    customer_session: boto3.Session,
    region: str,
    metric_data_queries: list,
    days_back: int = 60,
    max_datapoints: int = 10000,
    align_to_day: bool = True,
    timezone_offset_hours: int = 0,
    start_time: Optional[datetime] = None,
):
    """
    Fetch CloudWatch metric data with pagination.

    Args:
        start_time: If provided, use this as the start time directly
                    (overrides days_back). Must be timezone-aware.
        days_back:  Fallback — used only when start_time is not provided.
    """
    cw = customer_session.client("cloudwatch", region_name=region)

    tz = timezone(timedelta(hours=timezone_offset_hours))
    now = datetime.now(tz)

    if align_to_day:
        end_time = datetime(now.year, now.month, now.day, tzinfo=tz) + timedelta(days=1)
    else:
        end_time = now

    if start_time is not None:
        # Use the provided start_time directly
        computed_start = start_time
    else:
        # Fallback to days_back
        computed_start = end_time - timedelta(days=days_back)

    start_time_utc = computed_start.astimezone(timezone.utc)
    end_time_utc = end_time.astimezone(timezone.utc)

    logger.info("[START] Calling CloudWatch get_metric_data (BATCH, paginated)")
    all_results_by_id = {}
    next_token = None
    page = 0

    while True:
        page += 1
        kwargs = dict(
            MetricDataQueries=metric_data_queries,
            StartTime=start_time_utc,
            EndTime=end_time_utc,
            ScanBy="TimestampAscending",
            MaxDatapoints=max_datapoints,
        )
        if next_token:
            kwargs["NextToken"] = next_token

        resp = cw.get_metric_data(**kwargs)
        logger.info(f"[PAGE {page}] fetched")

        for r in resp.get("MetricDataResults", []):
            _id = r.get("Id")
            if _id not in all_results_by_id:
                all_results_by_id[_id] = {
                    "Id": _id,
                    "Label": r.get("Label"),
                    "StatusCode": r.get("StatusCode"),
                    "Timestamps": [],
                    "Values": [],
                }
            all_results_by_id[_id]["Timestamps"].extend(r.get("Timestamps", []))
            all_results_by_id[_id]["Values"].extend(r.get("Values", []))

        next_token = resp.get("NextToken")
        if not next_token:
            return {
                "MetricDataResults": list(all_results_by_id.values()),
                "Messages": resp.get("Messages", []),
                "StartTimeUTC": start_time_utc,
                "EndTimeUTC": end_time_utc,
            }

def fetch_cw_with_retry(customer_session, region, queries, start_time, timezone_offset_hours, max_retries=3):
    """Helper to fetch CloudWatch metrics with exponential backoff on Throttling."""
    import time as time_module
    for attempt in range(max_retries):
        try:
            return get_cloudwatch_metric_data(
                customer_session=customer_session,
                region=region,
                metric_data_queries=queries,
                start_time=start_time,
                timezone_offset_hours=timezone_offset_hours,
            )
        except ClientError as ce:
            if ce.response['Error']['Code'] == 'Throttling':
                logger.warning(f"Throttled by CloudWatch, retrying attempt {attempt+1}/{max_retries}")
                time_module.sleep(2 ** attempt)
            else:
                raise
                
    logger.error("Max retries reached for CloudWatch fetch")
    raise RuntimeError("CloudWatch fetch failed after max retries")
