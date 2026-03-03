import boto3
import logging
from datetime import datetime, timedelta, timezone
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
    days_back: int = 30,
    max_datapoints: int = 10000,
    align_to_day: bool = True,
    timezone_offset_hours: int = 0,
):
    cw = customer_session.client("cloudwatch", region_name=region)

    tz = timezone(timedelta(hours=timezone_offset_hours))
    now = datetime.now(tz)

    if align_to_day:
        end_time = datetime(now.year, now.month, now.day, tzinfo=tz) + timedelta(days=1)
        start_time = end_time - timedelta(days=days_back)
    else:
        end_time = now
        start_time = now - timedelta(days=days_back)

    start_time_utc = start_time.astimezone(timezone.utc)
    end_time_utc = end_time.astimezone(timezone.utc)

    try:
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

    except ClientError as e:
        logger.error(f"[FAILED] CloudWatch error: {e.response['Error']['Message']}")
        return None



def build_ec2_metric_queries_hourly(instance_id: str):
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
                "Period": 3600,
                "Stat": stat,
            },
            "ReturnData": True,
        }

    return [
        q("cpu", "CPUUtilization", "Average"),
        q("netin", "NetworkIn", "Sum"),
        q("netout", "NetworkOut", "Sum"),
    ]


# ─── EC2 Instance Discovery ───────────────────────────────────────

def list_ec2_instances(
    customer_session: boto3.Session,
    region: str = "us-east-1",
) -> list[dict]:
    """
    List all running EC2 instances in the customer's account via DescribeInstances.
    Uses paginator to handle accounts with many instances.

    Returns list of dicts: [{"instance_id", "instance_type", "state"}, ...]
    """
    ec2 = customer_session.client("ec2", region_name=region)
    instances = []

    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
    ):
        for reservation in page["Reservations"]:
            for i in reservation["Instances"]:
                instances.append({
                    "instance_id": i["InstanceId"],
                    "instance_type": i["InstanceType"],
                    "state": i["State"]["Name"],
                })

    logger.info(f"Found {len(instances)} running EC2 instances in {region}")
    return instances


# ─── High-level: Pull EC2 Metrics ─────────────────────────────────

def pull_ec2_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    days_back: int = 30,
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list EC2 instances → build queries → fetch CloudWatch metrics.

    Returns dict keyed by instance_id:
    {
        "i-0abc...": {"instance": {...}, "metrics": {...}},
        ...
    }
    """
    instances = list_ec2_instances(customer_session, region)

    if not instances:
        logger.info("No running EC2 instances found, skipping metric pull")
        return {}

    all_results = {}
    for inst in instances:
        iid = inst["instance_id"]
        queries = build_ec2_metric_queries_hourly(iid)
        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )
        all_results[iid] = {"instance": inst, "metrics": metrics}
        logger.info(f"Fetched metrics for {iid} ({inst['instance_type']})")

    logger.info(f"Completed metric pull for {len(all_results)} instances")
    return all_results
