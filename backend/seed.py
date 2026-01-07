from database import SessionLocal, engine, Base
import models
import auth
from datetime import datetime, timedelta
import random

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

def seed_data():
    print("Seeding data...")
    
    # 1. Create User
    if not db.query(models.User).filter(models.User.username == "admin").first():
        hashed_pw = auth.get_password_hash("admin")
        user = models.User(username="admin", hashed_password=hashed_pw)
        db.add(user)
        print("Created admin user")

    # 2. Create Services
    service_names = ["EC2", "S3", "RDS", "Lambda"]
    services = {}
    for name in service_names:
        s = db.query(models.Service).filter(models.Service.name == name).first()
        if not s:
            s = models.Service(name=name, category="Infrastructure" if name in ["EC2", "Lambda"] else "Storage/DB")
            db.add(s)
            db.commit()
            db.refresh(s)
        services[name] = s
    
    # 3. Generate Daily Costs (6 months)
    # Trend: Start low, increase by random % each month
    start_date = datetime.utcnow().date() - timedelta(days=180)
    current_date = start_date
    end_date = datetime.utcnow().date()

    # Base costs
    base_costs = {
        "EC2": 50.0,
        "S3": 10.0,
        "RDS": 30.0,
        "Lambda": 5.0
    }

    while current_date <= end_date:
        # Add slight random fluctuation and trend
        days_passed = (current_date - start_date).days
        trend_factor = 1 + (days_passed / 365.0) * 0.5 # 50% increase over a year

        for name, service in services.items():
            # Check if exists
            exists = db.query(models.DailyCost).filter(
                models.DailyCost.date == current_date,
                models.DailyCost.service_id == service.id
            ).first()
            
            if not exists:
                daily_base = base_costs[name] * trend_factor
                fluctuation = random.uniform(0.8, 1.2)
                cost = daily_base * fluctuation
                
                dc = models.DailyCost(date=current_date, cost=cost, service_id=service.id)
                db.add(dc)
        
        current_date += timedelta(days=1)
    
    print("Generated daily costs")

    # 4. Monitoring Metrics (Last 3 days for 4 instances)
    instances = [
        {"id": "i-0a1b2c3d4e", "name": "Web-Server-1", "type": "EC2", "zone": "us-east-1a", "ip": "10.0.0.1"},
        {"id": "i-5f6g7h8i9j", "name": "Worker-Node-1", "type": "EC2", "zone": "us-east-1b", "ip": "10.0.0.2"},
        {"id": "db-prod-01", "name": "Prod-DB", "type": "RDS", "zone": "us-east-1a", "ip": "10.0.1.1"},
        {"id": "func-process-data", "name": "Data-Processor", "type": "Lambda", "zone": "us-east-1", "ip": "-"},
        {"id": "bucket-logs", "name": "Log-Archive", "type": "S3", "zone": "Global", "ip": "-"}
    ]

    metric_start = datetime.utcnow() - timedelta(days=3)
    metric_now = metric_start
    
    while metric_now <= datetime.utcnow():
        for inst in instances:
            # Random metrics
            cpu = random.uniform(10, 80)
            if inst["name"] == "Worker-Node-1" and random.random() > 0.8:
                cpu = random.uniform(85, 99) # Spike
            
            mem = random.uniform(20, 60)
            disk = random.uniform(100, 5000)
            net = random.uniform(1000, 10000)

            m = models.MonitoringMetric(
                timestamp=metric_now,
                instance_id=inst["id"],
                instance_name=inst["name"],
                service_type=inst["type"],
                cpu_usage=cpu,
                memory_usage=mem,
                disk_io=disk,
                network_io=net,
                status="running",
                zone=inst["zone"],
                ip_address=inst["ip"]
            )
            db.add(m)
        
        metric_now += timedelta(minutes=30) # Every 30 mins
    
    print("Generated monitoring metrics")

    # 5. Recommendations
    if db.query(models.Recommendation).count() == 0:
        recs = [
            models.Recommendation(
                title="Instance shows sustained low CPU",
                description="Instance i-12345 has < 5% CPU for 7 days. Consider downsizing.",
                impact="Save $50/month",
                category="Cost",
                priority_score=3,
                status="Active"
            ),
            models.Recommendation(
                title="Object data in STANDARD storage not accessed",
                description="3TB of data in bucket 'logs-archive' not accessed for 90 days.",
                impact="Save $120/month",
                category="Cost",
                priority_score=2,
                status="Active"
            ),
            models.Recommendation(
                title="RDS instance shows low CPU",
                description="DB instance db-prod-01 is over-provisioned.",
                impact="Save $80/month",
                category="Cost",
                priority_score=3,
                status="Active"
            )
        ]
        db.add_all(recs)
        print("Generated recommendations")

    db.commit()
    db.close()
    print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
