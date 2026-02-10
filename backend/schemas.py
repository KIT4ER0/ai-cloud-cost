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
