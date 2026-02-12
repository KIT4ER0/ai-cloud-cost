from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: str
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

# ---- Monitoring: per-service resource schemas ----

class EC2ResourceOut(BaseModel):
    ec2_resource_id: int
    account_id: str
    region: str
    instance_id: str
    instance_type: Optional[str] = None
    state: Optional[str] = None
    class Config:
        from_attributes = True

class LambdaResourceOut(BaseModel):
    lambda_resource_id: int
    account_id: str
    region: str
    function_name: str
    function_arn: Optional[str] = None
    runtime: Optional[str] = None
    memory_mb: Optional[int] = None
    timeout_sec: Optional[int] = None
    class Config:
        from_attributes = True

class RDSResourceOut(BaseModel):
    rds_resource_id: int
    account_id: str
    region: str
    db_identifier: str
    engine: Optional[str] = None
    instance_class: Optional[str] = None
    storage_type: Optional[str] = None
    allocated_gb: Optional[int] = None
    class Config:
        from_attributes = True

class S3ResourceOut(BaseModel):
    s3_resource_id: int
    account_id: str
    region: str
    bucket_name: str
    class Config:
        from_attributes = True

# ---- Monitoring: per-service metric schemas ----

class EC2MetricOut(BaseModel):
    metric_date: str
    cpu_p95: Optional[float] = None
    network_out_gb_sum: Optional[float] = None
    class Config:
        from_attributes = True

class LambdaMetricOut(BaseModel):
    metric_date: str
    duration_p95_ms: Optional[float] = None
    invocations_sum: Optional[float] = None
    errors_sum: Optional[float] = None
    class Config:
        from_attributes = True

class RDSMetricOut(BaseModel):
    metric_date: str
    cpu_p95: Optional[float] = None
    db_conn_avg: Optional[float] = None
    free_storage_gb_min: Optional[float] = None
    class Config:
        from_attributes = True

class S3MetricOut(BaseModel):
    metric_date: str
    storage_gb_avg: Optional[float] = None
    number_of_objects: Optional[float] = None
    class Config:
        from_attributes = True

