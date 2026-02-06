from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List

from .. import database, models, auth, schemas

router = APIRouter(
    prefix="/api",
    tags=["Costs"],
    dependencies=[Depends(auth.get_current_user)]
)

@router.get("/summary", response_model=schemas.CostSummary)
def get_summary(db: Session = Depends(database.get_db)):
    # Calculate current month cost
    today = datetime.utcnow()
    start_of_month = today.replace(day=1)
    
    total_cost = db.query(func.sum(models.DailyCost.cost)).filter(
        models.DailyCost.date >= start_of_month
    ).scalar() or 0.0

    # Simple forecast: average daily cost * days in month
    days_in_month = 30 # Approximation
    current_day = today.day
    if current_day > 0:
        daily_avg = total_cost / current_day
        forecast = daily_avg * days_in_month
    else:
        forecast = 0.0

    active_services = db.query(models.Service).count()

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

@router.get("/costs")
def get_costs(range: str = "1m", db: Session = Depends(database.get_db)):
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
    
    results = db.query(
        models.DailyCost.date,
        models.Service.name,
        models.DailyCost.cost
    ).join(models.Service).filter(
        models.DailyCost.date >= start_date
    ).all()

    data = [{"date": r.date, "service": r.name, "cost": r.cost} for r in results]
    return data

@router.get("/cost-details/{service_name}")
def get_cost_details(service_name: str, db: Session = Depends(database.get_db)):
    today = datetime.utcnow().date()
    start_date = today - timedelta(days=30)
    
    service = db.query(models.Service).filter(models.Service.name == service_name).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    total_cost = db.query(func.sum(models.DailyCost.cost)).filter(
        models.DailyCost.service_id == service.id,
        models.DailyCost.date >= start_date
    ).scalar() or 0.0

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
