from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
try:
    from .database import Base
except ImportError:
    from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True) # e.g., EC2, S3, RDS, Lambda
    category = Column(String) # Compute, Storage, Database, etc.

    daily_costs = relationship("DailyCost", back_populates="service")

class DailyCost(Base):
    __tablename__ = "daily_costs"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, index=True)
    cost = Column(Float)
    service_id = Column(Integer, ForeignKey("services.id"))

    service = relationship("Service", back_populates="daily_costs")

class MonitoringMetric(Base):
    __tablename__ = "monitoring_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    instance_id = Column(String, index=True)
    instance_name = Column(String)
    service_type = Column(String) # EC2, RDS, etc.
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    disk_io = Column(Float)
    network_io = Column(Float)
    status = Column(String) # running, stopped, etc.
    zone = Column(String)
    ip_address = Column(String)

class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    impact = Column(String) # e.g. "Save $50/month"
    category = Column(String) # e.g. "Cost", "Performance"
    priority_score = Column(Integer) # 1-5
    status = Column(String, default="Active") # Active, Dismissed
