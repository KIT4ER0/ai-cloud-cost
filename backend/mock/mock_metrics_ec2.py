import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Pricing Constants (ap-southeast-1, Linux)
# ──────────────────────────────────────────────

INSTANCE_PRICING = {
    "t3.medium":  0.0464,
    "r6g.large":  0.1210,
    "c6i.xlarge": 0.1920,
    "t3.micro":   0.0116,
}

EBS_VOLUME_PRICE_PER_GB = {
    "gp3": 0.096,
    "gp2": 0.114,
    "io1": 0.138,
    "st1": 0.051,
    "sc1": 0.029,
}

EBS_IOPS_PRICE = {
    "io1": 0.072,  # $/IOPS/month
    "io2": 0.072,
    "gp3": 0.0,
    "gp2": 0.0,
    "st1": 0.0,
    "sc1": 0.0,
}

EBS_SNAPSHOT_PRICE_PER_GB  = 0.053   # $/GB/month
NETWORK_EGRESS_PRICE_PER_GB = 0.09   # $/GB
NETWORK_CROSS_AZ_PRICE_PER_GB = 0.01 # $/GB
PUBLIC_IPV4_PRICE_PER_HR    = 0.005
ELASTIC_IP_IDLE_PRICE_PER_HR = 0.005

# ──────────────────────────────────────────────
# Mock Instance Profiles
# ──────────────────────────────────────────────

MOCK_INSTANCES = [
    {
        "id": "i-mock-web-01",
        "type": "t3.medium",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "production",
        "usage_pattern": "24x7",
        "cpu_base": 5.0,
        "cpu_range": 10.0,
        # EBS
        "ebs_volume_id": "vol-mock-web-01",
        "ebs_type": "gp3",
        "ebs_size_gb": 50,
        "ebs_iops": 3000,
        "ebs_throughput_mbps": 125,
        "snapshot_id": "snap-mock-web-01",
        "snapshot_gb": 30,
        # Network
        "egress_gb_per_day": 5.0,
        "cross_az_gb_per_day": 1.0,
        # IP
        "has_public_ip": True,
        "eip": {
            "allocation_id": "eipalloc-mock-web-01",
            "public_ip": "54.251.10.11",
            "is_idle": False,
        },
    },
    {
        "id": "i-mock-db-01",
        "type": "r6g.large",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "production",
        "usage_pattern": "24x7",
        "cpu_base": 55.0,
        "cpu_range": 30.0,
        # EBS — io1 คิด IOPS แยก
        "ebs_volume_id": "vol-mock-db-01",
        "ebs_type": "io1",
        "ebs_size_gb": 200,
        "ebs_iops": 5000,
        "ebs_throughput_mbps": None,
        "snapshot_id": "snap-mock-db-01",
        "snapshot_gb": 150,
        # Network
        "egress_gb_per_day": 2.0,
        "cross_az_gb_per_day": 5.0,
        # IP
        "has_public_ip": False,
        "eip": None,
    },
    {
        "id": "i-mock-worker-01",
        "type": "c6i.xlarge",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "staging",
        "usage_pattern": "business_hours",
        "cpu_base": 10.0,
        "cpu_range": 70.0,
        # EBS
        "ebs_volume_id": "vol-mock-worker-01",
        "ebs_type": "gp3",
        "ebs_size_gb": 100,
        "ebs_iops": 3000,
        "ebs_throughput_mbps": 125,
        "snapshot_id": "snap-mock-worker-01",
        "snapshot_gb": 50,
        # Network
        "egress_gb_per_day": 10.0,
        "cross_az_gb_per_day": 2.0,
        # IP
        "has_public_ip": True,
        "eip": {
            "allocation_id": "eipalloc-mock-worker-01",
            "public_ip": "54.251.10.22",
            "is_idle": False,
        },
    },
    {
        "id": "i-mock-test-01",
        "type": "t3.micro",
        "platform": "Linux",
        "purchase_option": "OnDemand",
        "environment": "dev",
        "usage_pattern": "business_hours",
        "cpu_base": 1.0,
        "cpu_range": 4.0,
        # EBS
        "ebs_volume_id": "vol-mock-test-01",
        "ebs_type": "gp2",
        "ebs_size_gb": 20,
        "ebs_iops": 0,
        "ebs_throughput_mbps": None,
        "snapshot_id": None,
        "snapshot_gb": 0,
        # Network
        "egress_gb_per_day": 0.5,
        "cross_az_gb_per_day": 0.0,
        # IP — มี idle EIP ที่ไม่ได้ใช้
        "has_public_ip": False,
        "eip": {
            "allocation_id": "eipalloc-mock-test-01",
            "public_ip": "54.251.10.33",
            "is_idle": True,   # ← จะโดน charge $0.005/hr
        },
    },
]

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _simulate_cpu(
    base: float, range_: float, date, usage_pattern: str
) -> tuple[float, float, float]:
    is_weekend = date.weekday() >= 5
    if usage_pattern == "business_hours" and is_weekend:
        base = base * 0.1
    cpu_avg = round(random.uniform(base, base + range_ * 0.5), 2)
    cpu_max = round(min(cpu_avg + random.uniform(range_ * 0.3, range_), 99.0), 2)
    cpu_p99 = round(min(cpu_avg + random.uniform(range_ * 0.2, range_ * 0.7), 99.0), 2)
    return cpu_avg, cpu_max, cpu_p99


def _hours_running(usage_pattern: str, date) -> float:
    if usage_pattern == "24x7":
        return 24.0
    return 8.0 if date.weekday() < 5 else 0.0


def _build_cost_rows(resource_id: int, inst: dict, days: int = 90) -> list[dict]:
    rows = []
    hourly_price = INSTANCE_PRICING.get(inst["type"], 0.05)
    ebs_type = inst["ebs_type"]

    ebs_daily        = EBS_VOLUME_PRICE_PER_GB[ebs_type] * inst["ebs_size_gb"] / 30
    ebs_iops_daily   = EBS_IOPS_PRICE.get(ebs_type, 0.0) * inst["ebs_iops"] / 30
    snapshot_daily   = EBS_SNAPSHOT_PRICE_PER_GB * inst["snapshot_gb"] / 30

    for days_ago in range(days):
        dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
        hours = _hours_running(inst["usage_pattern"], dt)
        is_active = hours > 0

        def row(usage_type: str, amount: float) -> dict:
            return {
                "ec2_resource_id": resource_id,
                "usage_date": dt.isoformat(),
                "usage_type": usage_type,
                "amount_usd": round(amount, 6),
                "currency_src": "USD",
            }

        # Compute
        rows.append(row("compute", hourly_price * hours))

        # EBS Volume
        rows.append(row("ebs_volume", ebs_daily))

        # EBS IOPS (io1/io2 เท่านั้น)
        if ebs_iops_daily > 0:
            rows.append(row("ebs_iops", ebs_iops_daily))

        # EBS Snapshot
        if snapshot_daily > 0:
            rows.append(row("ebs_snapshot", snapshot_daily))

        # Network (เฉพาะวันที่ทำงาน)
        if is_active:
            egress_gb = inst["egress_gb_per_day"] * random.uniform(0.7, 1.3)
            rows.append(row("network_egress", egress_gb * NETWORK_EGRESS_PRICE_PER_GB))

            if inst["cross_az_gb_per_day"] > 0:
                cross_gb = inst["cross_az_gb_per_day"] * random.uniform(0.5, 1.5)
                rows.append(row("network_cross_az", cross_gb * NETWORK_CROSS_AZ_PRICE_PER_GB))

        # Public IPv4
        if inst["has_public_ip"]:
            rows.append(row("public_ipv4", PUBLIC_IPV4_PRICE_PER_HR * 24))

    return rows


def _build_eip_cost_rows(eip_id: int, days: int = 90) -> list[dict]:
    rows = []
    for days_ago in range(days):
        dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
        rows.append({
            "eip_id": eip_id,
            "usage_date": dt.isoformat(),
            "hours_idle": 24.0,
            "amount_usd": round(ELASTIC_IP_IDLE_PRICE_PER_HR * 24, 6),
            "currency_src": "USD",
        })
    return rows

# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def mock_smart_sync_ec2_metrics(
    db, account_id: str, region: str, profile_id: int
):
    from .. import models

    logger.info(f"Running MOCK smart sync for account={account_id} region={region}")

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
                has_public_ip=inst["has_public_ip"],
            )
            db.add(resource)
            db.flush()
        else:
            resource.state = "running"
            resource.has_public_ip = inst["has_public_ip"]
            db.flush()

        # ── 2. Upsert EBS Volume ─────────────────────────────────────────────
        ebs_volume = db.query(models.EC2EBSVolume).filter_by(
            volume_id=inst["ebs_volume_id"]
        ).first()

        if not ebs_volume:
            ebs_volume = models.EC2EBSVolume(
                ec2_resource_id=resource.ec2_resource_id,
                volume_id=inst["ebs_volume_id"],
                volume_type=inst["ebs_type"],
                size_gb=inst["ebs_size_gb"],
                iops=inst["ebs_iops"] or None,
                throughput_mbps=inst["ebs_throughput_mbps"],
                state="in-use",
            )
            db.add(ebs_volume)
            db.flush()

        # ── 3. Upsert EBS Snapshot ───────────────────────────────────────────
        if inst["snapshot_id"]:
            snapshot = db.query(models.EC2EBSSnapshot).filter_by(
                snapshot_id=inst["snapshot_id"]
            ).first()

            if not snapshot:
                snapshot_date = (datetime.now(timezone.utc) - timedelta(days=30)).date()
                db.add(models.EC2EBSSnapshot(
                    ebs_volume_id=ebs_volume.ebs_volume_id,
                    ec2_resource_id=resource.ec2_resource_id,
                    snapshot_id=inst["snapshot_id"],
                    size_gb=inst["snapshot_gb"],
                    snapshot_date=snapshot_date,
                    age_days=30,
                ))
                db.flush()

        # ── 4. Upsert Elastic IP ─────────────────────────────────────────────
        eip_record = None
        if inst["eip"]:
            eip_data = inst["eip"]
            eip_record = db.query(models.EC2ElasticIP).filter_by(
                allocation_id=eip_data["allocation_id"]
            ).first()

            if not eip_record:
                eip_record = models.EC2ElasticIP(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    allocation_id=eip_data["allocation_id"],
                    public_ip=eip_data["public_ip"],
                    ec2_resource_id=resource.ec2_resource_id if not eip_data["is_idle"] else None,
                    association_id=str(resource.ec2_resource_id) if not eip_data["is_idle"] else None,
                    is_idle=eip_data["is_idle"],
                    idle_since=datetime.now(timezone.utc) - timedelta(days=90)
                    if eip_data["is_idle"] else None,
                )
                db.add(eip_record)
                db.flush()
            else:
                eip_record.ec2_resource_id = resource.ec2_resource_id if not eip_data["is_idle"] else None
                eip_record.association_id = str(resource.ec2_resource_id) if not eip_data["is_idle"] else None
                eip_record.is_idle = eip_data["is_idle"]
                db.flush()

        # ── 5. Upsert EC2Metrics (90 วัน) ───────────────────────────────────
        metric_rows = []
        for days_ago in range(90):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
            cpu_avg, cpu_max, cpu_p99 = _simulate_cpu(
                inst["cpu_base"], inst["cpu_range"], dt, inst["usage_pattern"]
            )
            hours = _hours_running(inst["usage_pattern"], dt)
            is_active = hours > 0

            metric_rows.append({
                "ec2_resource_id": resource.ec2_resource_id,
                "metric_date": dt.isoformat(),
                "cpu_utilization": cpu_avg,
                "cpu_max": cpu_max,
                "cpu_p99": cpu_p99,
                "network_in": random.randint(100_000, 2_000_000) if is_active else 0,
                "network_out": random.randint(500_000, 5_000_000) if is_active else 0,
                "network_egress_gb": round(inst["egress_gb_per_day"] * random.uniform(0.7, 1.3), 4) if is_active else 0,
                "network_cross_az_gb": round(inst["cross_az_gb_per_day"] * random.uniform(0.5, 1.5), 4) if is_active else 0,
                "hours_running": hours,
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
                    "network_egress_gb": stmt.excluded.network_egress_gb,
                    "network_cross_az_gb": stmt.excluded.network_cross_az_gb,
                    "hours_running": stmt.excluded.hours_running,
                },
            )
            db.execute(stmt)

        # ── 6. Upsert EC2Costs (90 วัน) ─────────────────────────────────────
        cost_rows = _build_cost_rows(resource.ec2_resource_id, inst)
        if cost_rows:
            stmt = insert(models.EC2Cost).values(cost_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ec2_resource_id", "usage_date", "usage_type"],
                set_={"amount_usd": stmt.excluded.amount_usd},
            )
            db.execute(stmt)

        # ── 7. Upsert EIP Costs (เฉพาะ idle) ────────────────────────────────
        if eip_record and inst["eip"]["is_idle"]:
            eip_cost_rows = _build_eip_cost_rows(eip_record.eip_id)
            if eip_cost_rows:
                stmt = insert(models.EC2EIPCost).values(eip_cost_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["eip_id", "usage_date"],
                    set_={
                        "hours_idle": stmt.excluded.hours_idle,
                        "amount_usd": stmt.excluded.amount_usd,
                    },
                )
                db.execute(stmt)

        logger.info(
            f"MOCK sync done: {iid} ({inst['type']}) | "
            f"metrics={len(metric_rows)} | "
            f"costs={len(cost_rows)} | "
            f"eip={'idle' if inst['eip'] and inst['eip']['is_idle'] else 'ok' if inst['eip'] else 'none'}"
        )

    db.commit()
    logger.info("All MOCK EC2 instances synced successfully")