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
                })

    logger.info(f"Found {len(load_balancers)} ALBs in {region}")
    return load_balancers


# ─── High-level: Pull ALB Metrics ─────────────────────────────────

def pull_alb_metrics(
    customer_session: boto3.Session,
    region: str = "us-east-1",
    days_back: int = 30,
    timezone_offset_hours: int = 0,
) -> dict:
    """
    End-to-end: list ALBs → build DAILY queries → fetch CloudWatch metrics.
    """
    load_balancers = list_alb_load_balancers(customer_session, region)

    if not load_balancers:
        logger.info("No ALBs found, skipping metric pull")
        return {}

    all_results = {}
    for lb in load_balancers:
        lb_name = lb["lb_name"]

        # ✅ Use DAILY queries now
        queries = build_alb_metric_queries_daily(lb["lb_arn_suffix"])

        metrics = get_cloudwatch_metric_data(
            customer_session=customer_session,
            region=region,
            metric_data_queries=queries,
            days_back=days_back,
            timezone_offset_hours=timezone_offset_hours,
        )

        all_results[lb_name] = {"load_balancer": lb, "metrics": metrics}
        logger.info(f"Fetched DAILY metrics for ALB {lb_name}")

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