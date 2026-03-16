from fastapi import APIRouter, Depends, HTTPException
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
    print(f"DEBUG: get_ec2_resources called for profile_id={current_user.profile_id}")
    resources = db.query(models.EC2Resource).filter(
        models.EC2Resource.profile_id == current_user.profile_id,
        models.EC2Resource.instance_id != 'AGGREGATED'
    ).all()
    print(f"DEBUG: found {len(resources)} resources")
    return resources

@router.get("/ec2/{resource_id}/metrics", response_model=List[schemas.EC2MetricOut])
def get_ec2_metrics(
    resource_id: int,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    resource = db.query(models.EC2Resource).filter_by(
        ec2_resource_id=resource_id, profile_id=current_user.profile_id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    rows = db.query(models.EC2Metric).filter(
        models.EC2Metric.ec2_resource_id == resource_id
    ).order_by(models.EC2Metric.metric_date).all()
    return [
        schemas.EC2MetricOut(
            metric_date=str(r.metric_date),
            cpu_utilization=r.cpu_utilization,
            cpu_max=r.cpu_max,
            cpu_p99=r.cpu_p99,
            network_in=r.network_in,
            network_out=r.network_out,
            network_egress_gb=r.network_egress_gb,
            network_cross_az_gb=r.network_cross_az_gb,
            hours_running=r.hours_running,
        ) for r in rows
    ]

@router.get("/ec2/eips", response_model=List[schemas.EC2ElasticIPOut])
def get_ec2_eips(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    eips = db.query(models.EC2ElasticIP).filter(
        models.EC2ElasticIP.profile_id == current_user.profile_id
    ).all()
    
    results = []
    for eip in eips:
        # Get the latest daily cost for this EIP
        latest_cost = db.query(models.EC2EIPCost).filter(
            models.EC2EIPCost.eip_id == eip.eip_id,
            models.EC2EIPCost.usage_type == "total"
        ).order_by(models.EC2EIPCost.usage_date.desc()).first()
        
        eip_out = schemas.EC2ElasticIPOut.from_orm(eip)
        eip_out.current_cost_usd = float(latest_cost.amount_usd) if latest_cost else 0.0
        results.append(eip_out)
        
    return results

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
def get_lambda_metrics(
    resource_id: int,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    resource = db.query(models.LambdaResource).filter_by(
        lambda_resource_id=resource_id, profile_id=current_user.profile_id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
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
def get_rds_metrics(
    resource_id: int,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    resource = db.query(models.RDSResource).filter_by(
        rds_resource_id=resource_id, profile_id=current_user.profile_id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    rows = db.query(models.RDSMetric).filter(
        models.RDSMetric.rds_resource_id == resource_id
    ).order_by(models.RDSMetric.metric_date).all()
    return [
        schemas.RDSMetricOut(
            metric_date=str(r.metric_date),
            cpu_utilization=r.cpu_utilization,
            database_connections=r.database_connections,
            free_storage_space=r.free_storage_space,
            data_transfer=r.data_transfer,
            freeable_memory=r.freeable_memory,
            swap_usage=r.swap_usage,
            read_iops=r.read_iops,
            write_iops=r.write_iops,
            read_latency=r.read_latency,
            write_latency=r.write_latency,
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
def get_s3_metrics(
    resource_id: int,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    resource = db.query(models.S3Resource).filter_by(
        s3_resource_id=resource_id, profile_id=current_user.profile_id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
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
def get_alb_metrics(
    resource_id: int,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    resource = db.query(models.ALBResource).filter_by(
        alb_resource_id=resource_id, profile_id=current_user.profile_id
    ).first()
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
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
