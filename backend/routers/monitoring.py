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
def get_ec2_resources(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.EC2Resource).filter(
        models.EC2Resource.profile_id == current_user.profile_id
    ).all()

@router.get("/ec2/{resource_id}/metrics", response_model=List[schemas.EC2MetricOut])
def get_ec2_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.EC2Metric).filter(
        models.EC2Metric.ec2_resource_id == resource_id
    ).order_by(models.EC2Metric.metric_date).all()
    return [
        schemas.EC2MetricOut(
            metric_date=str(r.metric_date),
            cpu_utilization=r.cpu_utilization,
            network_in=r.network_in,
            network_out=r.network_out,
            cpu_credit_usage=r.cpu_credit_usage,
        ) for r in rows
    ]

# ---- Lambda ----

@router.get("/lambda", response_model=List[schemas.LambdaResourceOut])
def get_lambda_resources(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.LambdaResource).filter(
        models.LambdaResource.profile_id == current_user.profile_id
    ).all()

@router.get("/lambda/{resource_id}/metrics", response_model=List[schemas.LambdaMetricOut])
def get_lambda_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.LambdaMetric).filter(
        models.LambdaMetric.lambda_resource_id == resource_id
    ).order_by(models.LambdaMetric.metric_date).all()
    return [
        schemas.LambdaMetricOut(
            metric_date=str(r.metric_date),
            duration_p95=r.duration_p95,
            invocations=r.invocations,
            errors=r.errors,
        ) for r in rows
    ]

# ---- RDS ----

@router.get("/rds", response_model=List[schemas.RDSResourceOut])
def get_rds_resources(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.RDSResource).filter(
        models.RDSResource.profile_id == current_user.profile_id
    ).all()

@router.get("/rds/{resource_id}/metrics", response_model=List[schemas.RDSMetricOut])
def get_rds_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.RDSMetric).filter(
        models.RDSMetric.rds_resource_id == resource_id
    ).order_by(models.RDSMetric.metric_date).all()
    return [
        schemas.RDSMetricOut(
            metric_date=str(r.metric_date),
            cpu_utilization=r.cpu_utilization,
            database_connections=r.database_connections,
            freeable_memory=r.freeable_memory,
            free_storage_space=r.free_storage_space,
            disk_queue_depth=r.disk_queue_depth,
            ebs_byte_balance_pct=r.ebs_byte_balance_pct,
            ebs_io_balance_pct=r.ebs_io_balance_pct,
            cpu_credit_balance=r.cpu_credit_balance,
            cpu_credit_usage=r.cpu_credit_usage,
        ) for r in rows
    ]

# ---- S3 ----

@router.get("/s3", response_model=List[schemas.S3ResourceOut])
def get_s3_resources(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.S3Resource).filter(
        models.S3Resource.profile_id == current_user.profile_id
    ).all()

@router.get("/s3/{resource_id}/metrics", response_model=List[schemas.S3MetricOut])
def get_s3_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.S3Metric).filter(
        models.S3Metric.s3_resource_id == resource_id
    ).order_by(models.S3Metric.metric_date).all()
    return [
        schemas.S3MetricOut(
            metric_date=str(r.metric_date),
            bucket_size_bytes=r.bucket_size_bytes,
            number_of_objects=r.number_of_objects,
            get_requests=r.get_requests,
            put_requests=r.put_requests,
            bytes_downloaded=r.bytes_downloaded,
            bytes_uploaded=r.bytes_uploaded,
        ) for r in rows
    ]

# ---- ALB ----

@router.get("/alb", response_model=List[schemas.ALBResourceOut])
def get_alb_resources(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.ALBResource).filter(
        models.ALBResource.profile_id == current_user.profile_id
    ).all()

@router.get("/alb/{resource_id}/metrics", response_model=List[schemas.ALBMetricOut])
def get_alb_metrics(resource_id: int, db: Session = Depends(database.get_db)):
    rows = db.query(models.ALBMetric).filter(
        models.ALBMetric.alb_resource_id == resource_id
    ).order_by(models.ALBMetric.metric_date).all()
    return [
        schemas.ALBMetricOut(
            metric_date=str(r.metric_date),
            request_count=r.request_count,
            response_time_p95=r.response_time_p95,
            http_5xx_count=r.http_5xx_count,
            active_conn_count=r.active_conn_count,
        ) for r in rows
    ]
