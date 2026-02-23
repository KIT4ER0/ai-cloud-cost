from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
try:
    from .database import Base
except ImportError:
    from database import Base
from datetime import datetime


class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, autoincrement=True)
    email = Column(Text, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    aws_role_arn = Column(Text)
    aws_external_id = Column(Text, unique=True)


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

class EC2Metric(Base):
    __tablename__ = "ec2_metrics"
    __table_args__ = (
        UniqueConstraint('ec2_resource_id', 'metric_date', name='uq_ec2_metrics_unique'),
        {"schema": "cloudcost"}
    )



    ec2_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    instance_id = Column(Text, nullable=False)
    instance_type = Column(Text)
    state = Column(Text)

    metrics = relationship("EC2Metric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("EC2Cost", back_populates="resource", cascade="all, delete-orphan")

class EC2Metric(Base):
    __tablename__ = "ec2_metrics"
    __table_args__ = (
        UniqueConstraint('ec2_resource_id', 'metric_date', name='uq_ec2_metrics_unique'),
        {"schema": "cloudcost"}
    )


    ec2_metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ec2_resource_id = Column(BigInteger, ForeignKey("cloudcost.ec2_resources.ec2_resource_id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, index=True)
    cpu_p95 = Column(Float)
    network_out_gb_sum = Column(Float)


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

class EC2Cost(Base):
    __tablename__ = "ec2_costs"
    __table_args__ = (
        UniqueConstraint('ec2_resource_id', 'usage_date', 'usage_type', name='uq_ec2_costs_unique'),
        {"schema": "cloudcost"}
    )

    ec2_cost_id = Column(BigInteger, primary_key=True, autoincrement=True)
    ec2_resource_id = Column(BigInteger, ForeignKey("cloudcost.ec2_resources.ec2_resource_id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False, index=True)
    usage_type = Column(Text, nullable=False, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("EC2Resource", back_populates="costs")

# =======================
# 2) Lambda
# =======================
class LambdaResource(Base):
    __tablename__ = "lambda_resources"
    __table_args__ = (
        UniqueConstraint('account_id', 'region', 'function_name', name='uq_lambda_resources_unique'),
        {"schema": "cloudcost"}
    )

    lambda_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    function_name = Column(Text, nullable=False)
    function_arn = Column(Text)
    runtime = Column(Text)
    memory_mb = Column(Integer)
    timeout_sec = Column(Integer)

    metrics = relationship("LambdaMetric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("LambdaCost", back_populates="resource", cascade="all, delete-orphan")

class LambdaMetric(Base):
    __tablename__ = "lambda_metrics"
    __table_args__ = (
        UniqueConstraint('lambda_resource_id', 'metric_date', name='uq_lambda_metrics_unique'),
        {"schema": "cloudcost"}
    )

    lambda_metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    lambda_resource_id = Column(BigInteger, ForeignKey("cloudcost.lambda_resources.lambda_resource_id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, index=True)
    duration_p95_ms = Column(Float)
    invocations_sum = Column(Float)
    errors_sum = Column(Float)

    resource = relationship("LambdaResource", back_populates="metrics")

class LambdaCost(Base):
    __tablename__ = "lambda_costs"
    __table_args__ = (
        UniqueConstraint('lambda_resource_id', 'usage_date', 'usage_type', name='uq_lambda_costs_unique'),
        {"schema": "cloudcost"}
    )

    lambda_cost_id = Column(BigInteger, primary_key=True, autoincrement=True)
    lambda_resource_id = Column(BigInteger, ForeignKey("cloudcost.lambda_resources.lambda_resource_id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False, index=True)
    usage_type = Column(Text, nullable=False, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("LambdaResource", back_populates="costs")

# =======================
# 3) RDS
# =======================
class RDSResource(Base):
    __tablename__ = "rds_resources"
    __table_args__ = (
        UniqueConstraint('account_id', 'region', 'db_identifier', name='uq_rds_resources_unique'),
        {"schema": "cloudcost"}
    )

    rds_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    db_identifier = Column(Text, nullable=False)
    engine = Column(Text)
    instance_class = Column(Text)
    storage_type = Column(Text)
    allocated_gb = Column(Integer)

    metrics = relationship("RDSMetric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("RDSCost", back_populates="resource", cascade="all, delete-orphan")

class RDSMetric(Base):
    __tablename__ = "rds_metrics"
    __table_args__ = (
        UniqueConstraint('rds_resource_id', 'metric_date', name='uq_rds_metrics_unique'),
        {"schema": "cloudcost"}
    )

    rds_metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    rds_resource_id = Column(BigInteger, ForeignKey("cloudcost.rds_resources.rds_resource_id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, index=True)
    cpu_p95 = Column(Float)
    db_conn_avg = Column(Float)
    free_storage_gb_min = Column(Float)

    resource = relationship("RDSResource", back_populates="metrics")

class RDSCost(Base):
    __tablename__ = "rds_costs"
    __table_args__ = (
        UniqueConstraint('rds_resource_id', 'usage_date', 'usage_type', name='uq_rds_costs_unique'),
        {"schema": "cloudcost"}
    )

    rds_cost_id = Column(BigInteger, primary_key=True, autoincrement=True)
    rds_resource_id = Column(BigInteger, ForeignKey("cloudcost.rds_resources.rds_resource_id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False, index=True)
    usage_type = Column(Text, nullable=False, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("RDSResource", back_populates="costs")

# =======================
# 4) S3
# =======================
class S3Resource(Base):
    __tablename__ = "s3_resources"
    __table_args__ = (
        UniqueConstraint('account_id', 'region', 'bucket_name', name='uq_s3_resources_unique'),
        {"schema": "cloudcost"}
    )

    s3_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    bucket_name = Column(Text, nullable=False)

    metrics = relationship("S3Metric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("S3Cost", back_populates="resource", cascade="all, delete-orphan")

class S3Metric(Base):
    __tablename__ = "s3_metrics"
    __table_args__ = (
        UniqueConstraint('s3_resource_id', 'metric_date', name='uq_s3_metrics_unique'),
        {"schema": "cloudcost"}
    )

    s3_metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    s3_resource_id = Column(BigInteger, ForeignKey("cloudcost.s3_resources.s3_resource_id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, index=True)
    storage_gb_avg = Column(Float)
    number_of_objects = Column(Float)

    resource = relationship("S3Resource", back_populates="metrics")

class S3Cost(Base):
    __tablename__ = "s3_costs"
    __table_args__ = (
        UniqueConstraint('s3_resource_id', 'usage_date', 'usage_type', name='uq_s3_costs_unique'),
        {"schema": "cloudcost"}
    )

    s3_cost_id = Column(BigInteger, primary_key=True, autoincrement=True)
    s3_resource_id = Column(BigInteger, ForeignKey("cloudcost.s3_resources.s3_resource_id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False, index=True)
    usage_type = Column(Text, nullable=False, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("S3Resource", back_populates="costs")

# =======================
# Recommendations
# =======================
class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String)
    impact = Column(String) # e.g. "Save $50/month"
    category = Column(String) # e.g. "Cost", "Performance"
    priority_score = Column(Integer) # 1-5
    status = Column(String, default="Active") # Active, Dismissed
