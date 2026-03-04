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
    
    # 1. Create User (Admin)
    admin_email = "admin@example.com"
    if not db.query(models.User).filter(models.User.email == admin_email).first():
        hashed_pw = auth.get_password_hash("admin123")
        user = models.User(
            email=admin_email, 
            password_hash=hashed_pw,
            display_name="Administrator",
            role="admin",
            is_active=True
        )
        db.add(user)
        print(f"Created admin user: {admin_email}")

    # 2. Create Resources & Related Data
    # For simplicity, we just create entries directly. Use try/except or checks.
    
    # --- EC2 ---
    ec2_instances = [
        {"id": "i-0a1b2c3d4e", "network": 50.0, "type": "t3.micro", "state": "running"},
        {"id": "i-5f6g7h8i9j", "network": 120.0, "type": "m5.large", "state": "running"}
    ]
    
    for inst in ec2_instances:
        # Check if exists
        curr = db.query(models.EC2Resource).filter_by(instance_id=inst["id"]).first()
        if not curr:
            curr = models.EC2Resource(
                profile_id=1,
                account_id="123456789012",
                region="us-east-1",
                instance_id=inst["id"],
                instance_type=inst["type"],
                state=inst["state"]
            )
            db.add(curr)
            db.commit() # commit to get ID
            db.refresh(curr)
            
        # Add Metrics (Last 3 days)
        start_date = datetime.utcnow().date() - timedelta(days=3)
        for i in range(4):
            d = start_date + timedelta(days=i)
            # Check dup
            if not db.query(models.EC2Metric).filter_by(ec2_resource_id=curr.ec2_resource_id, metric_date=d).first():
                m = models.EC2Metric(
                    ec2_resource_id=curr.ec2_resource_id,
                    metric_date=d,
                    cpu_p95=random.uniform(10, 90),
                    network_out_gb_sum=inst["network"] * random.uniform(0.8, 1.2)
                )
                db.add(m)
        
        # Add Costs (Last 3 days)
        for i in range(4):
            d = start_date + timedelta(days=i)
            if not db.query(models.EC2Cost).filter_by(ec2_resource_id=curr.ec2_resource_id, usage_date=d).first():
                c = models.EC2Cost(
                    ec2_resource_id=curr.ec2_resource_id,
                    usage_date=d,
                    usage_type="BoxUsage",
                    amount_usd=random.uniform(0.5, 5.0),
                    currency_src="USD"
                )
                db.add(c)

    print("Seeded EC2 data")

    # --- S3 ---
    buckets = ["logs-archive", "app-assets"]
    for b in buckets:
        curr = db.query(models.S3Resource).filter_by(bucket_name=b).first()
        if not curr:
            curr = models.S3Resource(
                profile_id=1,
                account_id="123456789012",
                region="us-east-1",
                bucket_name=b
            )
            db.add(curr)
            db.commit()
            db.refresh(curr)
        
        start_date = datetime.utcnow().date() - timedelta(days=3)
        for i in range(4):
            d = start_date + timedelta(days=i)
            if not db.query(models.S3Cost).filter_by(s3_resource_id=curr.s3_resource_id, usage_date=d).first():
                c = models.S3Cost(
                    s3_resource_id=curr.s3_resource_id,
                    usage_date=d,
                    usage_type="Storage",
                    amount_usd=random.uniform(0.1, 1.0)
                )
                db.add(c)

    print("Seeded S3 data")

    # 5. Recommendations
    if db.query(models.Recommendation).count() == 0:
        recs = [
            models.Recommendation(
                profile_id=1,
                rec_date=datetime.utcnow().date(),
                account_id="123456789012",
                region="us-east-1",
                service="EC2",
                resource_key="i-0a1b2c3d4e",
                rec_type="RIGHTSIZE",
                details={"reason": "Low CPU usage"},
                est_saving_usd=50.0,
                confidence=0.9,
                status="open"
            )
        ]
        db.add_all(recs)
        print("Generated recommendations")

    db.commit()
    db.close()
    print("Seeding complete!")

if __name__ == "__main__":
    seed_data()
