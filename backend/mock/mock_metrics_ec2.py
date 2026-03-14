import logging
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

def mock_smart_sync_ec2_metrics(db, account_id: str, region: str, profile_id: int):
    """
    Mock function that simulates smart_sync_ec2_metrics.
    Upserts multiple fake EC2Resources and fake EC2Metrics into the database
    over the past 90 days with randomized realistic values.
    """
    from .. import models

    logger.info(f"Running MOCK smart sync for account {account_id} region {region}")
    
    # 4 Mock Instances with varying types
    mock_instances = [
        {"id": "i-mock-web-01", "type": "t3.medium"},
        {"id": "i-mock-db-01", "type": "r6g.large"},
        {"id": "i-mock-worker-01", "type": "c6i.xlarge"},
        {"id": "i-mock-test-01", "type": "t3.micro"},
    ]
    
    launch_time = datetime.now(timezone.utc) - timedelta(days=95)
    
    for inst in mock_instances:
        iid = inst["id"]
        
        # 1. Upsert EC2 Resource
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
            )
            db.add(resource)
            db.flush()
        else:
            resource.state = "running"
            db.flush()
            
        # 2. Upsert EC2 Metrics for the past 90 days
        metric_rows = []
        for days_ago in range(90):
            dt = (datetime.now(timezone.utc) - timedelta(days=days_ago)).date()
            
            # Base load randomizer per instance type roughly
            base_cpu = 10.0 if "t3" in inst["type"] else 40.0
            
            metric_rows.append({
                "ec2_resource_id": resource.ec2_resource_id,
                "metric_date": dt.isoformat(),
                "cpu_utilization": round(random.uniform(base_cpu, base_cpu + 35.0), 2),
                "network_in": random.randint(100000, 2000000),
                "network_out": random.randint(500000, 5000000),
                "hours_running": 24.0,
            })
            
        if metric_rows:
            stmt = insert(models.EC2Metric).values(metric_rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ec2_resource_id", "metric_date"],
                set_={
                    "cpu_utilization": stmt.excluded.cpu_utilization,
                    "network_in": stmt.excluded.network_in,
                    "network_out": stmt.excluded.network_out,
                    "hours_running": stmt.excluded.hours_running,
                }
            )
            db.execute(stmt)
        
        logger.info(f"MOCK sync completed for EC2 {iid} ({inst['type']}) with {len(metric_rows)} metric rows")

    db.commit()
    logger.info("All MOCK EC2 instances synced successfully")
