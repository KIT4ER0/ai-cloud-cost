from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from .. import database, models, auth, schemas

router = APIRouter(
    prefix="/api/monitoring",
    tags=["Monitoring"],
    dependencies=[Depends(auth.get_current_user)]
)

# ---- EC2 ----

@router.get("/ec2", response_model=List[schemas.EC2ResourceOut])
def get_ec2_resources(db: Session = Depends(database.get_db)):
    return db.query(models.EC2Resource).all()

@router.get("/ec2/{resource_id}/metrics", response_model=List[schemas.EC2MetricOut])
def get_ec2_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.EC2Metric).filter(
        models.EC2Metric.ec2_resource_id == resource_id
    ).order_by(models.EC2Metric.metric_date).all()
    return [
        schemas.EC2MetricOut(
            metric_date=str(r.metric_date),
            cpu_p95=r.cpu_p95,
            network_out_gb_sum=r.network_out_gb_sum,
        ) for r in rows
    ]

# ---- Lambda ----

@router.get("/lambda", response_model=List[schemas.LambdaResourceOut])
def get_lambda_resources(db: Session = Depends(database.get_db)):
    return db.query(models.LambdaResource).all()

@router.get("/lambda/{resource_id}/metrics", response_model=List[schemas.LambdaMetricOut])
def get_lambda_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.LambdaMetric).filter(
        models.LambdaMetric.lambda_resource_id == resource_id
    ).order_by(models.LambdaMetric.metric_date).all()
    return [
        schemas.LambdaMetricOut(
            metric_date=str(r.metric_date),
            duration_p95_ms=r.duration_p95_ms,
            invocations_sum=r.invocations_sum,
            errors_sum=r.errors_sum,
        ) for r in rows
    ]

# ---- RDS ----

@router.get("/rds", response_model=List[schemas.RDSResourceOut])
def get_rds_resources(db: Session = Depends(database.get_db)):
    return db.query(models.RDSResource).all()

@router.get("/rds/{resource_id}/metrics", response_model=List[schemas.RDSMetricOut])
def get_rds_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.RDSMetric).filter(
        models.RDSMetric.rds_resource_id == resource_id
    ).order_by(models.RDSMetric.metric_date).all()
    return [
        schemas.RDSMetricOut(
            metric_date=str(r.metric_date),
            cpu_p95=r.cpu_p95,
            db_conn_avg=r.db_conn_avg,
            free_storage_gb_min=r.free_storage_gb_min,
        ) for r in rows
    ]

# ---- S3 ----

@router.get("/s3", response_model=List[schemas.S3ResourceOut])
def get_s3_resources(db: Session = Depends(database.get_db)):
    return db.query(models.S3Resource).all()

@router.get("/s3/{resource_id}/metrics", response_model=List[schemas.S3MetricOut])
def get_s3_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.S3Metric).filter(
        models.S3Metric.s3_resource_id == resource_id
    ).order_by(models.S3Metric.metric_date).all()
    return [
        schemas.S3MetricOut(
            metric_date=str(r.metric_date),
            storage_gb_avg=r.storage_gb_avg,
            number_of_objects=r.number_of_objects,
        ) for r in rows
    ]
