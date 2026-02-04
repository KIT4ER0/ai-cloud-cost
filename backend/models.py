from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, Boolean, Text, BigInteger, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
try:
    from .database import Base
except ImportError:
    from database import Base
from datetime import datetime

# =======================
# Authentication (Keep existing User model)
# =======================
class User(Base):
    __tablename__ = "users"
    # users table likely resides in public schema or default search path
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)

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
    account_id = Column(String(12), nullable=False)
    region = Column(Text, nullable=False)
    instance_id = Column(Text, nullable=False)
    instance_type = Column(Text)
    state = Column(Text)

    metrics = relationship("EC2Metric", back_populates="resource", cascade="all, delete-orphan")
    costs = relationship("EC2Cost", back_populates="resource", cascade="all, delete-orphan")

class EC2Metric(Base):
    __tablename__ = "ec2_metrics"
    __table_args__ = {"schema": "cloudcost"}

    ec2_resource_id = Column(BigInteger, ForeignKey("cloudcost.ec2_resources.ec2_resource_id", ondelete="CASCADE"), primary_key=True)
    metric_date = Column(Date, primary_key=True, index=True)
    cpu_p95 = Column(Float)
    network_out_gb_sum = Column(Float)

    resource = relationship("EC2Resource", back_populates="metrics")

class EC2Cost(Base):
    __tablename__ = "ec2_costs"
    __table_args__ = {"schema": "cloudcost"}

    ec2_resource_id = Column(BigInteger, ForeignKey("cloudcost.ec2_resources.ec2_resource_id", ondelete="CASCADE"), primary_key=True)
    usage_date = Column(Date, primary_key=True, index=True)
    usage_type = Column(Text, primary_key=True, default='total')
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
    __table_args__ = {"schema": "cloudcost"}

    lambda_resource_id = Column(BigInteger, ForeignKey("cloudcost.lambda_resources.lambda_resource_id", ondelete="CASCADE"), primary_key=True)
    metric_date = Column(Date, primary_key=True, index=True)
    duration_p95_ms = Column(Float)
    invocations_sum = Column(Float)
    errors_sum = Column(Float)

    resource = relationship("LambdaResource", back_populates="metrics")

class LambdaCost(Base):
    __tablename__ = "lambda_costs"
    __table_args__ = {"schema": "cloudcost"}

    lambda_resource_id = Column(BigInteger, ForeignKey("cloudcost.lambda_resources.lambda_resource_id", ondelete="CASCADE"), primary_key=True)
    usage_date = Column(Date, primary_key=True, index=True)
    usage_type = Column(Text, primary_key=True, default='total')
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
    __table_args__ = {"schema": "cloudcost"}

    rds_resource_id = Column(BigInteger, ForeignKey("cloudcost.rds_resources.rds_resource_id", ondelete="CASCADE"), primary_key=True)
    metric_date = Column(Date, primary_key=True, index=True)
    cpu_p95 = Column(Float)
    db_conn_avg = Column(Float)
    free_storage_gb_min = Column(Float)

    resource = relationship("RDSResource", back_populates="metrics")

class RDSCost(Base):
    __tablename__ = "rds_costs"
    __table_args__ = {"schema": "cloudcost"}

    rds_resource_id = Column(BigInteger, ForeignKey("cloudcost.rds_resources.rds_resource_id", ondelete="CASCADE"), primary_key=True)
    usage_date = Column(Date, primary_key=True, index=True)
    usage_type = Column(Text, primary_key=True, default='total')
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
    __table_args__ = {"schema": "cloudcost"}

    s3_resource_id = Column(BigInteger, ForeignKey("cloudcost.s3_resources.s3_resource_id", ondelete="CASCADE"), primary_key=True)
    metric_date = Column(Date, primary_key=True, index=True)
    storage_gb_avg = Column(Float)
    number_of_objects = Column(Float)

    resource = relationship("S3Resource", back_populates="metrics")

class S3Cost(Base):
    __tablename__ = "s3_costs"
    __table_args__ = {"schema": "cloudcost"}

    s3_resource_id = Column(BigInteger, ForeignKey("cloudcost.s3_resources.s3_resource_id", ondelete="CASCADE"), primary_key=True)
    usage_date = Column(Date, primary_key=True, index=True)
    usage_type = Column(Text, primary_key=True, default='total')
    amount_usd = Column(Numeric(14, 6), nullable=False, default=0)
    currency_src = Column(Text, nullable=False, default='USD')

    resource = relationship("S3Resource", back_populates="costs")

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
