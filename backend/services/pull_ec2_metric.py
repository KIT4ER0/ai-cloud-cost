import boto3
import logging
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from .cloudwatch_utils import get_cloudwatch_metric_data, print_all_datapoints
from .aggregate import aggregate_hourly_to_daily, EC2_STRATEGIES

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)



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
        q("cpu_credit", "CPUCreditUsage", "Average"),
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


# ─── Save EC2 Metrics to DB ───────────────────────────────────────

def save_ec2_metrics(pull_results: dict, account_id: str, region: str):
    """
    Save pulled EC2 metrics to the database.
    Upserts resources and bulk-upserts metric rows.
    """
    from .. import models, database
    from sqlalchemy.dialects.postgresql import insert

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
                    account_id=account_id,
                    region=region,
                    instance_id=iid,
                    instance_type=inst.get("instance_type"),
                    state=inst.get("state"),
                )
                db.add(resource)
                db.commit()
                db.refresh(resource)
            else:
                resource.instance_type = inst.get("instance_type")
                resource.state = inst.get("state")
                db.commit()

            if not cw_resp:
                continue

            # 2) Aggregate hourly → daily
            daily = aggregate_hourly_to_daily(cw_resp, EC2_STRATEGIES)

            # 3) Bulk upsert metrics
            metric_rows = []
            for metric_date, values in daily.items():
                metric_rows.append({
                    "ec2_resource_id": resource.ec2_resource_id,
                    "metric_date": metric_date,
                    "cpu_utilization": values.get("cpu"),
                    "network_in": values.get("netin"),
                    "network_out": values.get("netout"),
                    "cpu_credit_usage": values.get("cpu_credit"),
                })

            if metric_rows:
                stmt = insert(models.EC2Metric.__table__).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ec2_resource_id", "metric_date"],
                    set_={
                        "cpu_utilization": stmt.excluded.cpu_utilization,
                        "network_in": stmt.excluded.network_in,
                        "network_out": stmt.excluded.network_out,
                        "cpu_credit_usage": stmt.excluded.cpu_credit_usage,
                    }
                )
                db.execute(stmt)
                db.commit()

            logger.info(f"Saved {len(metric_rows)} metric rows for EC2 {iid}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving EC2 metrics: {e}")
        raise
    finally:
        db.close()
