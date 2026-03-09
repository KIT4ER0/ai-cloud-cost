from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, Text, BigInteger, Numeric, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
try:
    from .database import Base
except ImportError:
    from database import Base
from datetime import datetime


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {"schema": "cloudcost"}

    profile_id = Column(BigInteger, primary_key=True, autoincrement=True)
    supabase_user_id = Column(Text, unique=True, nullable=False, index=True)
    email = Column(Text, index=True)
    aws_role_arn = Column(Text)
    aws_external_id = Column(Text, unique=True)

    # Relationships to resources
    ec2_resources = relationship("EC2Resource", back_populates="profile", cascade="all, delete-orphan")
    lambda_resources = relationship("LambdaResource", back_populates="profile", cascade="all, delete-orphan")
    rds_resources = relationship("RDSResource", back_populates="profile", cascade="all, delete-orphan")
    s3_resources = relationship("S3Resource", back_populates="profile", cascade="all, delete-orphan")
    alb_resources = relationship("ALBResource", back_populates="profile", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="profile", cascade="all, delete-orphan")
    forecast_runs = relationship("ForecastRun", back_populates="profile", cascade="all, delete-orphan")

# =======================
# 1) EC2
# =======================
class EC2Resource(Base):
    __tablename__ = "ec2_resources"
    __table_args__ = (
        UniqueConstraint('account_id', 'region', 'instance_id', name='uq_ec2_resources_unique'),
        {"schema": "cloudcost"}
    )

    ec2_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    instance_id = Column(Text, nullable=False)
    instance_type = Column(Text)
    state = Column(Text)

    profile = relationship("UserProfile", back_populates="ec2_resources")
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
    cpu_utilization = Column(Float)
    network_in = Column(Float)
    network_out = Column(Float)
    cpu_credit_usage = Column(Float)

    resource = relationship("EC2Resource", back_populates="metrics")

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
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    function_name = Column(Text, nullable=False)
    function_arn = Column(Text)
    runtime = Column(Text)
    memory_mb = Column(Integer)
    timeout_sec = Column(Integer)

    profile = relationship("UserProfile", back_populates="lambda_resources")
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
    duration_p95 = Column(Float)
    invocations = Column(Float)
    errors = Column(Float)

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
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    db_identifier = Column(Text, nullable=False)
    engine = Column(Text)
    instance_class = Column(Text)
    storage_type = Column(Text)
    allocated_gb = Column(Integer)

    profile = relationship("UserProfile", back_populates="rds_resources")
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
    cpu_utilization = Column(Float)
    database_connections = Column(Float)
    freeable_memory = Column(Float)
    free_storage_space = Column(Float)
    disk_queue_depth = Column(Float)
    ebs_byte_balance_pct = Column(Float)
    ebs_io_balance_pct = Column(Float)
    cpu_credit_balance = Column(Float)
    cpu_credit_usage = Column(Float)

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
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    bucket_name = Column(Text, nullable=False)

    profile = relationship("UserProfile", back_populates="s3_resources")
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
    bucket_size_bytes = Column(Float)
    number_of_objects = Column(Float)
    get_requests = Column(Float)
    put_requests = Column(Float)
    bytes_downloaded = Column(Float)
    bytes_uploaded = Column(Float)

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
# 5) ALB
# =======================
class ALBResource(Base):
    __tablename__ = "alb_resources"
    __table_args__ = (
        UniqueConstraint('account_id', 'region', 'lb_name', name='uq_alb_resources_unique'),
        {"schema": "cloudcost"}
    )

    alb_resource_id = Column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    lb_name = Column(Text, nullable=False)
    lb_arn = Column(Text)
    dns_name = Column(Text)
    scheme = Column(Text)

    profile = relationship("UserProfile", back_populates="alb_resources")
    metrics = relationship("ALBMetric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("ALBCost", back_populates="resource", cascade="all, delete-orphan")

class ALBMetric(Base):
    __tablename__ = "alb_metrics"
    __table_args__ = (
        UniqueConstraint('alb_resource_id', 'metric_date', name='uq_alb_metrics_unique'),
        {"schema": "cloudcost"}
    )

    alb_metric_id = Column(BigInteger, primary_key=True, autoincrement=True)
    alb_resource_id = Column(BigInteger, ForeignKey("cloudcost.alb_resources.alb_resource_id", ondelete="CASCADE"), nullable=False)
    metric_date = Column(Date, nullable=False, index=True)
    request_count = Column(Float)
    response_time_p95 = Column(Float)
    http_5xx_count = Column(Float)
    active_conn_count = Column(Float)

    resource = relationship("ALBResource", back_populates="metrics")

class ALBCost(Base):
    __tablename__ = "alb_costs"
    __table_args__ = (
        UniqueConstraint('alb_resource_id', 'usage_date', 'usage_type', name='uq_alb_costs_unique'),
        {"schema": "cloudcost"}
    )

    alb_cost_id = Column(BigInteger, primary_key=True, autoincrement=True)
    alb_resource_id = Column(BigInteger, ForeignKey("cloudcost.alb_resources.alb_resource_id", ondelete="CASCADE"), nullable=False)
    usage_date = Column(Date, nullable=False, index=True)
    usage_type = Column(Text, nullable=False, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("ALBResource", back_populates="costs")

# =======================
# Recommendations
# =======================
class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint('rec_date', 'account_id', 'region', 'service', 'resource_key', 'rec_type', name='uq_recommendations_unique'),
        {"schema": "cloudcost"}
    )

    rec_id = Column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    rec_date = Column(Date, nullable=False, index=True)
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    service = Column(Text, nullable=False, index=True)
    resource_key = Column(Text, nullable=False)
    rec_type = Column(Text, nullable=False)
    details = Column(JSONB, nullable=False, default={})
    est_saving_usd = Column(Numeric(14, 6))
    confidence = Column(Float)
    status = Column(Text, nullable=False, default='open', index=True)

    profile = relationship("UserProfile", back_populates="recommendations")

# =======================
# Forecast (Baseline)
# =======================
class ForecastRun(Base):
    __tablename__ = "forecast_runs"
    __table_args__ = {"schema": "cloudcost"}

    run_id = Column(BigInteger, primary_key=True, autoincrement=True)
    profile_id = Column(BigInteger, ForeignKey("cloudcost.user_profiles.profile_id"), nullable=False, index=True)
    service = Column(Text, nullable=False)          # ec2 / rds / lambda / s3 / alb
    resource_id = Column(BigInteger, nullable=False) # e.g. ec2_resource_id
    metric = Column(Text, nullable=False)            # e.g. cpu_utilization
    method = Column(Text, nullable=False)            # naive / moving_average / seasonal_naive
    params = Column(JSONB, nullable=False, default={})
    horizon = Column(Integer, nullable=False)
    train_size = Column(Integer)
    mae = Column(Float)
    rmse = Column(Float)
    mape = Column(Float)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    values = relationship("ForecastValue", back_populates="run", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="forecast_runs")


class ForecastValue(Base):
    __tablename__ = "forecast_values"
    __table_args__ = {"schema": "cloudcost"}

    value_id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey("cloudcost.forecast_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    forecast_date = Column(Date, nullable=False, index=True)
    forecast_value = Column(Float, nullable=False)

    run = relationship("ForecastRun", back_populates="values")
