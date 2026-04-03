import logging
import random
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

ENGINES = {
    "mysql": ["8.0.32", "8.0.28", "5.7.44"],
    "postgres": ["15.4", "14.9", "13.12"],
    "mariadb": ["10.11.5", "10.6.14"],
}

INSTANCE_CLASSES = [
    "db.t3.micro",
    "db.t3.small",
    "db.t3.medium",
    "db.r6g.large",
    "db.r6g.xlarge",
]

STORAGE_TYPES = ["gp2", "gp3", "io1"]
ENVIRONMENTS = ["production", "staging", "dev", "test"]
TEAMS = ["backend", "frontend", "data", "devops"]
STATUSES = ["available", "stopped", "deleting"]
PRICING_MODELS = ["on-demand", "reserved"]
PAYMENT_OPTIONS = ["no-upfront", "partial-upfront", "all-upfront"]
USAGE_TYPES = ["compute", "storage", "io", "backup", "data_transfer"]

SCENARIOS = [
    "idle",              # CPU ต่ำมาก, connections น้อย
    "over_provisioned",  # CPU/memory ต่ำ แต่ใช้ instance ใหญ่
    "on_demand_candidate",  # รันต่อเนื่องนาน ควรเปลี่ยนเป็น RI
]

def random_date_within(days_ago_max: int, days_ago_min: int = 0):
    offset = random.randint(days_ago_min, days_ago_max)
    return (datetime.now(timezone.utc) - timedelta(days=offset)).date()

def mock_smart_sync_rds_metrics(db, account_id: str, region: str, profile_id: int):
    """
    Mock function that simulates smart sync for RDS metrics.
    Upserts multiple fake RDSResources, RDSMetrics, RDSCosts, and RDSReservedInstances.
    """
    from .. import models

    logger.info(f"Running MOCK RDS smart sync for account {account_id} region {region}")

    try:
        # We will create 2 mock instances
        instances = []
        for i in range(2):
            engine_name = random.choice(list(ENGINES.keys()))
            engine_version = random.choice(ENGINES[engine_name])
            scenario = SCENARIOS[i % len(SCENARIOS)]
            environment = random.choice(ENVIRONMENTS)

            if scenario == "over_provisioned":
                instance_class = random.choice(["db.r6g.large", "db.r6g.xlarge"])
            else:
                instance_class = random.choice(INSTANCE_CLASSES)

            if scenario == "on_demand_candidate":
                pricing_model = "on-demand"
            else:
                pricing_model = random.choice(PRICING_MODELS)

            allocated_gb = random.choice([100, 200, 500, 1000])
            db_identifier = f"mock-db-{environment}-{engine_name[:3]}-{i+1:02d}-{account_id[-4:]}"

            # 1. Upsert RDSResource
            resource = db.query(models.RDSResource).filter_by(
                account_id=account_id,
                region=region,
                db_identifier=db_identifier,
            ).first()

            if not resource:
                resource = models.RDSResource(
                    profile_id=profile_id,
                    account_id=account_id,
                    region=region,
                    db_identifier=db_identifier,
                    engine=engine_name,
                    engine_version=engine_version,
                    instance_class=instance_class,
                    storage_type=random.choice(STORAGE_TYPES),
                    allocated_gb=allocated_gb,
                    multi_az=random.choice([True, False]),
                    environment=environment,
                    status=random.choices(STATUSES, weights=[80, 15, 5], k=1)[0],
                    pricing_model=pricing_model,
                    team=random.choice(TEAMS),
                    created_date=random_date_within(730, 180),
                )
                db.add(resource)
                db.flush()
            
            instances.append((resource, scenario))

        # 2. Upsert RDSMetrics + RDSCosts
        base_costs = {
            "compute": {
                "idle": (50, 100),
                "over_provisioned": (200, 400),
                "on_demand_candidate": (150, 300),
            },
            "storage": (10, 50),
            "io": (1, 20),
            "backup": (1, 10),
            "data_transfer": (0.5, 5),
        }

        for resource, scenario in instances:
            metric_rows = []
            cost_rows = []

            for day_offset in range(180):
                metric_date = (datetime.now(timezone.utc) - timedelta(days=day_offset)).date()
                dt_iso = metric_date.isoformat()

                if scenario == "idle":
                    # Idle database with very low, consistent values
                    base_cpu = random.uniform(0.5, 2.0)
                    cpu = round(base_cpu + random.uniform(-0.2, 0.2), 2)
                    cpu = max(0.1, min(cpu, 5.0))
                    connections = random.randint(0, 3)
                    read_iops = round(random.uniform(0, 5), 2)
                    write_iops = round(random.uniform(0, 2), 2)
                elif scenario == "over_provisioned":
                    # Over-provisioned with moderate but consistent usage
                    base_cpu = random.uniform(8.0, 15.0)
                    cpu = round(base_cpu + random.uniform(-2.0, 2.0), 2)
                    cpu = max(5.0, min(cpu, 25.0))
                    connections = random.randint(10, 25)
                    read_iops = round(random.uniform(20, 60), 2)
                    write_iops = round(random.uniform(10, 30), 2)
                else:
                    # Production usage with realistic patterns
                    base_cpu = random.uniform(35.0, 60.0)
                    cpu = round(base_cpu + random.uniform(-5.0, 5.0), 2)
                    cpu = max(25.0, min(cpu, 75.0))
                    connections = random.randint(40, 120)
                    read_iops = round(random.uniform(150, 400), 2)
                    write_iops = round(random.uniform(80, 200), 2)

                allocated_bytes = resource.allocated_gb * 1024**3 if resource.allocated_gb else 500 * 1024**3
                used_ratio = random.uniform(0.1, 0.6)
                free_storage = int(allocated_bytes * (1 - used_ratio))
                freeable_memory = random.randint(512, 8192) * 1024**2
                swap_usage = random.randint(0, 256) * 1024**2
                data_transfer = random.randint(100, 5000) * 1024**2
                read_latency = round(random.uniform(0.001, 0.05), 4)
                write_latency = round(random.uniform(0.001, 0.05), 4)

                backup_retention = round(resource.allocated_gb * random.uniform(0.01, 0.05), 2)
                snapshot_storage = round(resource.allocated_gb * random.uniform(0.05, 0.15), 2)
                running_hours = 24.0

                metric_rows.append({
                    "rds_resource_id": resource.rds_resource_id,
                    "metric_date": dt_iso,
                    "running_hours": running_hours,
                    "cpu_utilization": cpu,
                    "database_connections": connections,
                    "free_storage_space": free_storage,
                    "backup_retention_storage_gb": backup_retention,
                    "snapshot_storage_gb": snapshot_storage,
                    "data_transfer": data_transfer,
                    "freeable_memory": freeable_memory,
                    "swap_usage": swap_usage,
                    "read_iops": read_iops,
                    "write_iops": write_iops,
                    "read_latency": read_latency,
                    "write_latency": write_latency,
                })

                daily_total = Decimal("0")
                for usage_type in USAGE_TYPES:
                    if usage_type == "compute":
                        low, high = base_costs["compute"][scenario]
                    else:
                        low, high = base_costs[usage_type]

                    amount = Decimal(str(round(random.uniform(low / 30, high / 30), 6)))
                    daily_total += amount

                    cost_rows.append({
                        "rds_resource_id": resource.rds_resource_id,
                        "usage_date": dt_iso,
                        "usage_type": usage_type,
                        "amount_usd": amount,
                        "currency_src": "USD",
                    })

                cost_rows.append({
                    "rds_resource_id": resource.rds_resource_id,
                    "usage_date": dt_iso,
                    "usage_type": "total",
                    "amount_usd": daily_total,
                    "currency_src": "USD",
                })

            if metric_rows:
                stmt = insert(models.RDSMetric).values(metric_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["rds_resource_id", "metric_date"],
                    set_={
                        "running_hours": stmt.excluded.running_hours,
                        "cpu_utilization": stmt.excluded.cpu_utilization,
                        "database_connections": stmt.excluded.database_connections,
                        "free_storage_space": stmt.excluded.free_storage_space,
                        "backup_retention_storage_gb": stmt.excluded.backup_retention_storage_gb,
                        "snapshot_storage_gb": stmt.excluded.snapshot_storage_gb,
                        "data_transfer": stmt.excluded.data_transfer,
                        "freeable_memory": stmt.excluded.freeable_memory,
                        "swap_usage": stmt.excluded.swap_usage,
                        "read_iops": stmt.excluded.read_iops,
                        "write_iops": stmt.excluded.write_iops,
                        "read_latency": stmt.excluded.read_latency,
                        "write_latency": stmt.excluded.write_latency,
                    },
                )
                db.execute(stmt)

            if cost_rows:
                stmt = insert(models.RDSCost).values(cost_rows)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["rds_resource_id", "usage_date", "usage_type"],
                    set_={
                        "amount_usd": stmt.excluded.amount_usd,
                        "currency_src": stmt.excluded.currency_src,
                    },
                )
                db.execute(stmt)

        # 3. Create Reserved Instances for any instances marked as 'reserved'
        for resource, scenario in instances:
            if resource.pricing_model != "reserved":
                continue

            ri_instance_id = f"ri-{random.randint(100000, 999999):06x}-{account_id[-4:]}"
            
            # Use profile_id to create distinct instances 
            existing_ri = db.query(models.RDSReservedInstance).filter_by(
                rds_resource_id=resource.rds_resource_id
            ).first()

            if not existing_ri:
                term_years = random.choice([1, 3])
                start_date = random_date_within(365, 30)
                end_date = start_date + timedelta(days=365 * term_years)
                hourly_rate = round(random.uniform(0.05, 0.50), 6)
                upfront_cost = round(hourly_rate * 8760 * term_years * random.uniform(0.3, 0.6), 2)

                ri_resource = models.RDSReservedInstance(
                    profile_id=profile_id,
                    account_id=account_id,
                    ri_instance_id=ri_instance_id,
                    region=region,
                    instance_class=resource.instance_class,
                    engine=resource.engine,
                    multi_az=resource.multi_az,
                    term_years=term_years,
                    payment_option=random.choice(PAYMENT_OPTIONS),
                    start_date=start_date,
                    end_date=end_date,
                    hourly_rate=Decimal(str(hourly_rate)),
                    upfront_cost=Decimal(str(upfront_cost)),
                    rds_resource_id=resource.rds_resource_id,
                )
                db.add(ri_resource)

        db.commit()
        logger.info(f"All MOCK RDS instances synced successfully for profile {profile_id}")

    except Exception as e:
        db.rollback()
        logger.error(f"MOCK RDS sync failed: {e}")
        raise