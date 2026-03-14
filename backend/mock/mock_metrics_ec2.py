import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# ราคา On-Demand ap-southeast-1 (Linux) $/hr
INSTANCE_PRICING = {
    "t3.medium":  0.0464,
    "r6g.large":  0.1210,
    "c6i.xlarge": 0.1920,
    "t3.micro":   0.0116,
}

MOCK_INSTANCES = [
    {
        "id": "i-mock-web-01",
        "type": "t3.medium",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "production",
        "usage_pattern": "24x7",
        # CPU ต่ำ → ควรแนะนำ Downsize
        "cpu_base": 5.0,
        "cpu_range": 10.0,
    },
    {
        "id": "i-mock-db-01",
        "type": "r6g.large",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "production",
        "usage_pattern": "24x7",
        # CPU ปานกลาง-สูง → ควรแนะนำ Reserved
        "cpu_base": 55.0,
        "cpu_range": 30.0,
    },
    {
        "id": "i-mock-worker-01",
        "type": "c6i.xlarge",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "staging",
        "usage_pattern": "business_hours",
        # CPU สูงเฉพาะเวลากลางวัน
        "cpu_base": 10.0,
        "cpu_range": 70.0,
    },
    {
        "id": "i-mock-test-01",
        "type": "t3.micro",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "dev",
        "usage_pattern": "business_hours",
        # CPU ต่ำมาก → ควรแนะนำ Stop
        "cpu_base": 1.0,
        "cpu_range": 4.0,
    },
]


def _simulate_cpu(base: float, range_: float, date, usage_pattern: str) -> tuple[float, float, float]:
    """
    Return (cpu_avg, cpu_max, cpu_p99) จำลองตาม usage_pattern
    - business_hours: weekday สูง / weekend ต่ำ
    - 24x7: สม่ำเสมอ
    """
    is_weekend = date.weekday() >= 5

    if usage_pattern == "business_hours" and is_weekend:
        base = base * 0.1  # weekend แทบไม่ใช้งาน

    cpu_avg = round(random.uniform(base, base + range_ * 0.5), 2)
    cpu_max = round(min(cpu_avg + random.uniform(range_ * 0.3, range_), 99.0), 2)
    cpu_p99 = round(min(cpu_avg + random.uniform(range_ * 0.2, range_ * 0.7), 99.0), 2)

    return cpu_avg, cpu_max, cpu_p99


def mock_smart_sync_ec2_metrics(db, account_id: str, region: str, profile_id: int):
    from .. import models

    logger.info(f"Running MOCK smart sync for account {account_id} region {region}")

    launch_time = datetime.now(timezone.utc) - timedelta(days=95)

    for inst in MOCK_INSTANCES:
        iid = inst["id"]
        hourly_price = INSTANCE_PRICING.get(inst["type"], 0.05)

        # ── 1. Upsert EC2Resource ────────────────────────────────────────────
        resource = db.query(models.EC2Resource).filter_by(
            account_id=account_id, region=region, instance_id=iid
        ).first()

        if not resource:
            resource = models.EC2Resource(
                profile_id=profile_id,
                account_id=account_id,
                region=region,
                instance_id=iid,
                instance_type=inst["type"],
                state="running",
                launch_time=launch_time,
                platform=inst["platform"],
                purchase_option=inst["purchase_option"],
                on_demand_price_hr=hourly_price,
                environment=inst["environment"],
                usage_pattern=inst["usage_pattern"],
            )
            db.add(resource)
            db.flush()
        else:
            resource.state = "running"
            db.flush()

        # ── 2. Upsert EC2Metrics (90 วัน) ───────────────────────────────────
        metric_rows = []
        for days_ago in range(90):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
            cpu_avg, cpu_max, cpu_p99 = _simulate_cpu(
                inst["cpu_base"], inst["cpu_range"], dt, inst["usage_pattern"]
            )

            metric_rows.append({
                "ec2_resource_id": resource.ec2_resource_id,
                "metric_date": dt.isoformat(),
                "cpu_utilization": cpu_avg,
                "cpu_max": cpu_max,
                "cpu_p99": cpu_p99,
                "network_in": random.randint(100_000, 2_000_000),
                "network_out": random.randint(500_000, 5_000_000),
                "hours_running": 24.0 if inst["usage_pattern"] == "24x7"
                                 else (8.0 if dt.weekday() < 5 else 0.0),
            })

        if metric_rows:
            stmt = insert(models.EC2Metric).values(metric_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ec2_resource_id", "metric_date"],
                set_={
                    "cpu_utilization": stmt.excluded.cpu_utilization,
                    "cpu_max": stmt.excluded.cpu_max,
                    "cpu_p99": stmt.excluded.cpu_p99,
                    "network_in": stmt.excluded.network_in,
                    "network_out": stmt.excluded.network_out,
                    "hours_running": stmt.excluded.hours_running,
                },
            )
            db.execute(stmt)

        # ── 3. Upsert EC2Costs (90 วัน) ─────────────────────────────────────
        cost_rows = []
        for days_ago in range(90):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()

            # hours_running ตาม usage_pattern
            if inst["usage_pattern"] == "24x7":
                hours = 24.0
            elif dt.weekday() < 5:  # weekday
                hours = 8.0
            else:
                hours = 0.0

            daily_cost = round(hourly_price * hours, 6)

            cost_rows.append({
                "ec2_resource_id": resource.ec2_resource_id,
                "usage_date": dt.isoformat(),
                "usage_type": "total",
                "amount_usd": daily_cost,
                "currency_src": "USD",
            })

        if cost_rows:
            stmt = insert(models.EC2Cost).values(cost_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ec2_resource_id", "usage_date", "usage_type"],
                set_={"amount_usd": stmt.excluded.amount_usd},
            )
            db.execute(stmt)

        logger.info(
            f"MOCK sync done: {iid} ({inst['type']}) | "
            f"metrics={len(metric_rows)} | costs={len(cost_rows)}"
        )

    db.commit()
    logger.info("All MOCK EC2 instances synced successfully")