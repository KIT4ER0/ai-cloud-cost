from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import List

from .. import database, models, auth, schemas

router = APIRouter(
    prefix="/api",
    tags=["Monitoring"],
    dependencies=[Depends(auth.get_current_user)]
)

@router.get("/instances", response_model=List[schemas.InstanceInfo])
def get_instances(db: Session = Depends(database.get_db)):
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

@router.get("/metrics/{instance_id}", response_model=List[schemas.MetricData])
def get_metrics(instance_id: str, db: Session = Depends(database.get_db)):
    yesterday = datetime.utcnow() - timedelta(days=1)
    metrics = db.query(models.MonitoringMetric).filter(
        models.MonitoringMetric.instance_id == instance_id,
        models.MonitoringMetric.timestamp >= yesterday
    ).order_by(models.MonitoringMetric.timestamp).all()

    return [
        {
            "timestamp": m.timestamp,
            "cpu_usage": m.cpu_usage,
            "network_in": m.network_io,
            "network_out": m.network_io * 0.8,
            "disk_io": m.disk_io
        }
        for m in metrics
    ]
