from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, date

# =======================
# Authentication / User
# =======================
class UserProfileResponse(BaseModel):
    profile_id: int
    supabase_user_id: str
    email: Optional[str] = None
    aws_role_arn: Optional[str] = None
    aws_external_id: Optional[str] = None

    class Config:
        from_attributes = True

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
# Resources & Metrics
# =======================

# --- EC2 ---
class EC2ResourceOut(BaseModel):
    ec2_resource_id: int
    profile_id: int
    account_id: str
    region: str
    instance_id: str
    instance_type: Optional[str] = None
    state: Optional[str] = None
    class Config:
        from_attributes = True

class EC2MetricOut(BaseModel):
    metric_date: str
    cpu_utilization: Optional[float] = None
    network_in: Optional[float] = None
    network_out: Optional[float] = None
    cpu_credit_usage: Optional[float] = None
    class Config:
        from_attributes = True

# --- Lambda ---
class LambdaResourceOut(BaseModel):
    lambda_resource_id: int
    profile_id: int
    account_id: str
    region: str
    function_name: str
    function_arn: Optional[str] = None
    runtime: Optional[str] = None
    memory_mb: Optional[int] = None
    timeout_sec: Optional[int] = None
    class Config:
        from_attributes = True

class LambdaMetricOut(BaseModel):
    metric_date: str
    duration_p95: Optional[float] = None
    invocations: Optional[float] = None
    errors: Optional[float] = None
    class Config:
        from_attributes = True

# --- RDS ---
class RDSResourceOut(BaseModel):
    rds_resource_id: int
    profile_id: int
    account_id: str
    region: str
    db_identifier: str
    engine: Optional[str] = None
    instance_class: Optional[str] = None
    storage_type: Optional[str] = None
    allocated_gb: Optional[int] = None
    class Config:
        from_attributes = True

class RDSMetricOut(BaseModel):
    metric_date: str
    cpu_utilization: Optional[float] = None
    database_connections: Optional[float] = None
    freeable_memory: Optional[float] = None
    free_storage_space: Optional[float] = None
    disk_queue_depth: Optional[float] = None
    ebs_byte_balance_pct: Optional[float] = None
    ebs_io_balance_pct: Optional[float] = None
    cpu_credit_balance: Optional[float] = None
    cpu_credit_usage: Optional[float] = None
    class Config:
        from_attributes = True

# --- S3 ---
class S3ResourceOut(BaseModel):
    s3_resource_id: int
    profile_id: int
    account_id: str
    region: str
    bucket_name: str
    class Config:
        from_attributes = True

class S3MetricOut(BaseModel):
    metric_date: str
    bucket_size_bytes: Optional[float] = None
    number_of_objects: Optional[float] = None
    get_requests: Optional[float] = None
    put_requests: Optional[float] = None
    bytes_downloaded: Optional[float] = None
    bytes_uploaded: Optional[float] = None
    class Config:
        from_attributes = True

# --- ALB ---
class ALBResourceOut(BaseModel):
    alb_resource_id: int
    profile_id: int
    account_id: str
    region: str
    lb_name: str
    lb_arn: Optional[str] = None
    dns_name: Optional[str] = None
    scheme: Optional[str] = None
    class Config:
        from_attributes = True

class ALBMetricOut(BaseModel):
    metric_date: str
    request_count: Optional[float] = None
    response_time_p95: Optional[float] = None
    http_5xx_count: Optional[float] = None
    active_conn_count: Optional[float] = None
    class Config:
        from_attributes = True

# =======================
# Recommendations
# =======================
class RecommendationItem(BaseModel):
    rec_id: int
    profile_id: int
    rec_date: date
    account_id: str
    region: str
    service: str
    resource_key: str
    rec_type: str
    details: Dict[str, Any]
    est_saving_usd: Optional[float] = None
    confidence: Optional[float] = None
    status: str

    class Config:
        from_attributes = True

# =======================
# AWS Connection
# =======================
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
