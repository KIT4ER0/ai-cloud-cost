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

# =======================
# Resources & Metrics (Base Helpers)
# =======================
class MetricData(BaseModel):
    timestamp: datetime
    cpu_usage: float
    network_in: float
    network_out: float
    disk_io: float

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
