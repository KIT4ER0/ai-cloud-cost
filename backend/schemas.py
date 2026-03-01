from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# =======================
# Authentication / User
# =======================
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    aws_role_arn: Optional[str] = None
    aws_external_id: Optional[str] = None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# =======================
# Dashboard / Summary
# =======================
class CostSummary(BaseModel):
    total_cost_current_month: float
    forecast_cost_current_month: float
    active_services_count: int
    top_anomalies: List[Dict[str, Any]]

class ServiceCost(BaseModel):
    service_name: str
    total_cost: float
    breakdown: Dict[str, Any]

class KPIItem(BaseModel):
    totalCost: float
    prevTotalCost: float
    topService: Dict[str, Any]
    avgDailyCost: float
    projectedMonthEnd: float

class CostTrendItem(BaseModel):
    date: str
    cost: float

class ServiceCostDistribution(BaseModel):
    name: str
    value: float
    color: str

class CostDriverItem(BaseModel):
    driver: str
    usage: str
    cost: float
    prevCost: float
    change: float
    changePercent: float

class CostAnalysisData(BaseModel):
    summary: KPIItem
    trend: List[CostTrendItem]
    distribution: List[ServiceCostDistribution]
    drivers: Dict[str, List[CostDriverItem]]

# =======================
# Resources & Metrics (Base Helpers)
# =======================
class MetricData(BaseModel):
    timestamp: datetime
    cpu_usage: float
    network_in: float
    network_out: float
    disk_io: float

class EC2ResourceOut(BaseModel):
    ec2_resource_id: int
    account_id: str
    region: str
    instance_id: str
    instance_type: Optional[str]
    state: Optional[str]
    class Config:
        from_attributes = True

class EC2MetricOut(BaseModel):
    metric_date: str
    cpu_p95: Optional[float]
    network_out_gb_sum: Optional[float]
    class Config:
        from_attributes = True

class LambdaResourceOut(BaseModel):
    lambda_resource_id: int
    account_id: str
    region: str
    function_name: str
    function_arn: Optional[str]
    runtime: Optional[str]
    memory_mb: Optional[int]
    timeout_sec: Optional[int]
    class Config:
        from_attributes = True

class LambdaMetricOut(BaseModel):
    metric_date: str
    duration_p95_ms: Optional[float]
    invocations_sum: Optional[float]
    errors_sum: Optional[float]
    class Config:
        from_attributes = True

class RDSResourceOut(BaseModel):
    rds_resource_id: int
    account_id: str
    region: str
    db_identifier: str
    engine: Optional[str]
    instance_class: Optional[str]
    storage_type: Optional[str]
    allocated_gb: Optional[int]
    class Config:
        from_attributes = True

class RDSMetricOut(BaseModel):
    metric_date: str
    cpu_p95: Optional[float]
    db_conn_avg: Optional[float]
    free_storage_gb_min: Optional[float]
    class Config:
        from_attributes = True

class S3ResourceOut(BaseModel):
    s3_resource_id: int
    account_id: str
    region: str
    bucket_name: str
    class Config:
        from_attributes = True

class S3MetricOut(BaseModel):
    metric_date: str
    storage_gb_avg: Optional[float]
    number_of_objects: Optional[float]
    class Config:
        from_attributes = True

class RecommendationItem(BaseModel):
    rec_id: int
    rec_date: date
    account_id: str
    region: str
    service: str
    resource_key: str
    rec_type: str
    details: Dict[str, Any]
    est_saving_usd: Optional[float]
    confidence: Optional[float]
    status: str

    class Config:
        from_attributes = True

class ExternalIdResponse(BaseModel):
    external_id: str
    account_id: int

class AwsConnectRequest(BaseModel):
    role_arn: str
    session_name: Optional[str] = "CostOptimizerAssumedSession"

class AwsConnectResponse(BaseModel):
    aws_account_id: str
    arn: str
    status: str

class AwsAccountOut(BaseModel):
    account_id: int
    user_id: int
    aws_role_arn: str
    external_id: str
    
    class Config:
        from_attributes = True
