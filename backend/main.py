from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

import models, database, auth

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class UserCreate(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class CostSummary(BaseModel):
    total_cost_current_month: float
    forecast_cost_current_month: float
    active_services_count: int
    top_anomalies: List[dict]

class ServiceCost(BaseModel):
    service_name: str
    total_cost: float
    breakdown: dict

class InstanceInfo(BaseModel):
    instance_id: str
    name: str
    type: str
    zone: str
    ip: str
    status: str
    service_type: str

class MetricData(BaseModel):
    timestamp: datetime
    cpu_usage: float
    network_in: float
    network_out: float
    disk_io: float

class RecommendationItem(BaseModel):
    title: str
    impact: str
    priority_score: int
    description: str

# Auth Endpoints
@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    access_token = auth.create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login", response_model=Token)
def login(user: UserCreate, db: Session = Depends(database.get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = auth.create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Dashboard Endpoints
@app.get("/api/summary", response_model=CostSummary)
def get_summary(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Calculate current month cost
    today = datetime.utcnow()
    start_of_month = today.replace(day=1)
    
    total_cost = db.query(func.sum(models.DailyCost.cost)).filter(
        models.DailyCost.date >= start_of_month
    ).scalar() or 0.0

    # Simple forecast: average daily cost * days in month
    # For simplicity in mock, let's just add 10% to current projected
    days_in_month = 30 # Approximation
    current_day = today.day
    if current_day > 0:
        daily_avg = total_cost / current_day
        forecast = daily_avg * days_in_month
    else:
        forecast = 0.0

    active_services = db.query(models.Service).count()

    # Mock anomalies for now, or query from DB if we stored them
    anomalies = [
        {"message": "Instance i-12345 low CPU usage", "severity": "warning"},
        {"message": "Unused S3 bucket 'backup-logs'", "severity": "warning"},
        {"message": "RDS instance idle for 7 days", "severity": "info"}
    ]

    return {
        "total_cost_current_month": round(total_cost, 2),
        "forecast_cost_current_month": round(forecast, 2),
        "active_services_count": active_services,
        "top_anomalies": anomalies
    }

@app.get("/api/costs")
def get_costs(range: str = "1m", db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Range logic: 1w, 1m, 6m, 1y
    today = datetime.utcnow().date()
    if range == "1w":
        start_date = today - timedelta(weeks=1)
    elif range == "6m":
        start_date = today - timedelta(days=180)
    elif range == "1y":
        start_date = today - timedelta(days=365)
    else: # 1m default
        start_date = today - timedelta(days=30)
    
    # Query daily costs joined with service
    results = db.query(
        models.DailyCost.date,
        models.Service.name,
        models.DailyCost.cost
    ).join(models.Service).filter(
        models.DailyCost.date >= start_date
    ).all()

    # Transform for frontend: list of {date, service, cost}
    data = [{"date": r.date, "service": r.name, "cost": r.cost} for r in results]
    return data

@app.get("/api/cost-details/{service_name}")
def get_cost_details(service_name: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Get total cost for this service (all time or last month? Let's say last month for detail)
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)
    
    service = db.query(models.Service).filter(models.Service.name == service_name).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    total_cost = db.query(func.sum(models.DailyCost.cost)).filter(
        models.DailyCost.service_id == service.id,
        models.DailyCost.date >= start_date
    ).scalar() or 0.0

    # Mock breakdown based on service type
    breakdown = {}
    if "EC2" in service_name:
        breakdown = {
            "Compute Hours": round(total_cost * 0.7, 2),
            "EBS Volumes": round(total_cost * 0.2, 2),
            "Data Transfer": round(total_cost * 0.1, 2)
        }
    elif "S3" in service_name:
        breakdown = {
            "Storage": round(total_cost * 0.8, 2),
            "Requests": round(total_cost * 0.15, 2),
            "Data Transfer": round(total_cost * 0.05, 2)
        }
    else:
        breakdown = {"General Usage": total_cost}

    return {
        "service_name": service_name,
        "total_cost": round(total_cost, 2),
        "breakdown": breakdown
    }

@app.get("/api/instances", response_model=List[InstanceInfo])
def get_instances(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Get latest metric for each instance to get info
    # In a real app, we'd have an Instance table. Here we can query distinct instance_ids from metrics
    # For simplicity, let's just query a distinct list of instances from the metrics table (limited to recent)
    
    # Actually, let's just query the most recent metric for each instance_id
    subq = db.query(
        models.MonitoringMetric.instance_id,
        func.max(models.MonitoringMetric.timestamp).label('max_ts')
    ).group_by(models.MonitoringMetric.instance_id).subquery()

    latest_metrics = db.query(models.MonitoringMetric).join(
        subq,
        (models.MonitoringMetric.instance_id == subq.c.instance_id) &
        (models.MonitoringMetric.timestamp == subq.c.max_ts)
    ).all()

    instances = []
    for m in latest_metrics:
        instances.append({
            "instance_id": m.instance_id,
            "name": m.instance_name,
            "type": "t2.medium" if "EC2" in m.service_type else "db.t3.medium", # Mock
            "zone": m.zone,
            "ip": m.ip_address,
            "status": m.status,
            "service_type": m.service_type
        })
    return instances

@app.get("/api/metrics/{instance_id}", response_model=List[MetricData])
def get_metrics(instance_id: str, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Return last 24 hours of metrics
    yesterday = datetime.utcnow() - timedelta(days=1)
    metrics = db.query(models.MonitoringMetric).filter(
        models.MonitoringMetric.instance_id == instance_id,
        models.MonitoringMetric.timestamp >= yesterday
    ).order_by(models.MonitoringMetric.timestamp).all()

    return [
        {
            "timestamp": m.timestamp,
            "cpu_usage": m.cpu_usage,
            "network_in": m.network_io, # Simplified mapping
            "network_out": m.network_io * 0.8, # Mock
            "disk_io": m.disk_io
        }
        for m in metrics
    ]

@app.get("/api/recommendations", response_model=List[RecommendationItem])
def get_recommendations(db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    recs = db.query(models.Recommendation).filter(models.Recommendation.status == "Active").all()
    return [
        {
            "title": r.title,
            "impact": r.impact,
            "priority_score": r.priority_score,
            "description": r.description
        }
        for r in recs
    ]
