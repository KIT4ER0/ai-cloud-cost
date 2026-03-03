import logging
import json
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import text

# App imports
from .. import models, database
from .aws_sts import boto_client, get_account_id

logger = logging.getLogger(__name__)

# ==============================================================================
# Helper: Upsert Utils
# ==============================================================================

def _upsert_resource(db: Session, model_cls, unique_filters: Dict, defaults: Dict) -> int:
    """
    Get existing resource ID or create new one.
    Returns the primary key ID.
    """
    obj = db.query(model_cls).filter_by(**unique_filters).first()
    if obj:
        return getattr(obj, f"{model_cls.__tablename__[:-1]}_id")
    
    # Create new
    new_obj = model_cls(**unique_filters, **defaults)
    db.add(new_obj)
    db.commit()
    db.refresh(new_obj)
    return getattr(new_obj, f"{model_cls.__tablename__[:-1]}_id")

def _bulk_upsert(db: Session, model_cls, rows: List[Dict], index_elements: List[str]):
    """
    Bulk upsert using PostgreSQL ON CONFLICT.
    """
    if not rows:
        return

    table = model_cls.__table__
    stmt = insert(table).values(rows)
    
    # Prepare update dict (exclude PK and index elements)
    update_cols = {c.name: c for c in stmt.excluded if c.name not in index_elements}
    
    if update_cols:
        stmt = stmt.on_conflict_do_update(
            index_elements=index_elements,
            set_=update_cols
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=index_elements)

    db.execute(stmt)
    db.commit()

# ==============================================================================
# 1. AWS Cost Explorer Sync
# ==============================================================================

def sync_aws_costs(days_back: int = 90):
    """
    Fetch daily costs (Grouped by SERVICE, USAGE_TYPE) and upsert to DB.
    Since CE doesn't give Resource IDs for daily granularity easily, 
    we link to a dummy 'AGGREGATED' resource per service/region.
    """
    db = database.SessionLocal()
    logger.info(f"🚀 Starting AWS Cost Explorer Sync (Days Back: {days_back})...")
    try:
        ce = boto_client("ce")
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        logger.info(f"📅 Fetching cost data from {start_date} to {end_date}")
        
        # We process in chunks of time if needed, but for simplicity let's do 1 call per granularity
        # Note: CE is expensive if called too often.
        
        # 1. Fetch Data
        results = []
        next_token = None
        
        while True:
            params = {
                "TimePeriod": {"Start": str(start_date), "End": str(end_date)},
                "Granularity": "DAILY",
                "Metrics": ["UnblendedCost"],
                "GroupBy": [
                    {"Type": "DIMENSION", "Key": "SERVICE"},
                    {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                    # {"Type": "DIMENSION", "Key": "REGION"} # Optional: might make result too big, but better for accuracy
                ]
            }
            if next_token:
                params["NextPageToken"] = next_token
                
            resp = ce.get_cost_and_usage(**params)
            results.extend(resp.get("ResultsByTime", []))
            next_token = resp.get("NextPageToken")
            if not next_token:
                break
        
        # 2. Process Results
        account_id = get_account_id()
        
        # Buffers for bulk insert
        ec2_costs = []
        s3_costs = []
        rds_costs = []
        lambda_costs = []
        
        # Cache for Resource IDs: {(Service, Region): ResourceID}
        # We assume Region='global' if not specified in CE (CE doesn't return Region in GroupBy unless requested)
        # To simplify, we'll assume a default region for aggregated costs or "us-east-1"
        default_region = "us-east-1" 
        
        resource_cache = {}

        for day_data in results:
            usage_date = day_data["TimePeriod"]["Start"]
            for group in day_data["Groups"]:
                # keys: [Service, UsageType]
                service_name = group["Keys"][0]
                usage_type = group["Keys"][1]
                amount = float(group["Metrics"]["UnblendedCost"]["Amount"])
                
                if amount == 0:
                    continue

                # Map Service Name to our Tables
                if service_name in ("Amazon Elastic Compute Cloud - Compute", "EC2 - Other"):
                    target_list = ec2_costs
                    model_res = models.EC2Resource
                    model_cost = models.EC2Cost
                    res_key_field = "instance_id"
                elif service_name == "Amazon Simple Storage Service":
                    target_list = s3_costs
                    model_res = models.S3Resource
                    model_cost = models.S3Cost
                    res_key_field = "bucket_name"
                elif service_name == "Amazon Relational Database Service":
                    target_list = rds_costs
                    model_res = models.RDSResource
                    model_cost = models.RDSCost
                    res_key_field = "db_identifier"
                elif service_name == "AWS Lambda":
                    target_list = lambda_costs
                    model_res = models.LambdaResource
                    model_cost = models.LambdaCost
                    res_key_field = "function_name"
                else:
                    continue # Skip other services for now

                # Get Aggregated Resource ID
                cache_key = (service_name, default_region)
                if cache_key not in resource_cache:
                    # Upsert "AGGREGATED" resource
                    filters = {
                        "account_id": account_id,
                        "region": default_region,
                        res_key_field: "AGGREGATED"
                    }
                    defaults = {"state": "active"} if model_res == models.EC2Resource else {}
                    rid = _upsert_resource(db, model_res, filters, defaults)
                    resource_cache[cache_key] = rid
                
                rid = resource_cache[cache_key]
                
                # Add Cost Row
                # Mapping: ec2_resource_id / s3_resource_id ...
                fk_field = f"{model_res.__tablename__[:-1]}_id"
                
                target_list.append({
                    fk_field: rid,
                    "usage_date": usage_date,
                    "usage_type": usage_type,
                    "amount_usd": amount,
                    "currency_src": "USD"
                })
        
        # 3. Bulk Insert
        if ec2_costs:
            _bulk_upsert(db, models.EC2Cost, ec2_costs, ["ec2_resource_id", "usage_date", "usage_type"])
        if s3_costs:
            _bulk_upsert(db, models.S3Cost, s3_costs, ["s3_resource_id", "usage_date", "usage_type"])
        if rds_costs:
            _bulk_upsert(db, models.RDSCost, rds_costs, ["rds_resource_id", "usage_date", "usage_type"])
        if lambda_costs:
            _bulk_upsert(db, models.LambdaCost, lambda_costs, ["lambda_resource_id", "usage_date", "usage_type"])
            
        logger.info(f" synced costs for {len(results)} days.")
        
    except Exception as e:
        logger.error(f"Error syncing costs: {e}")
        raise
    finally:
        db.close()

# ==============================================================================
# 2. AWS CloudWatch Metrics Sync
# ==============================================================================

def sync_aws_metrics(hours_back: int = 24):
    """
    Fetch CloudWatch metrics for EC2, RDS, S3, Lambda.
    Upserts real Resource records and then Metrics.
    """
    db = database.SessionLocal()
    cw = boto_client("cloudwatch")
    account_id = get_account_id()
    region = boto_client("s3").meta.region_name or "us-east-1" # Hack to get region
    
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours_back)
    
    logger.info(f"🚀 Starting AWS CloudWatch Metrics Sync (Hours Back: {hours_back})...")
    logger.info(f"⏰ Fetching metrics from {start_time} to {end_time} for region: {region}")
    
    try:
        # --- EC2 ---
        logger.info("  -> Syncing EC2 Metrics...")
        _sync_ec2_metrics(db, cw, account_id, region, start_time, end_time)
        logger.info("  ✅ EC2 Metrics Synced!")
        
        # --- S3 (List buckets from env or generic) ---
        # For demo simplicity, skipping listing all buckets unless we call S3 ListBuckets
        # _sync_s3_metrics(...)
        
        # --- RDS ---
        # _sync_rds_metrics(...)
        
        # --- Lambda ---
        # _sync_lambda_metrics(...)
        
    except Exception as e:
        logger.error(f"Error syncing metrics: {e}")
        raise
    finally:
        db.close()

def _sync_ec2_metrics(db: Session, cw, account_id, region, start_time, end_time):
    # 1. List Instances (Real world: use EC2 DescribeInstances)
    ec2_client = boto_client("ec2")
    instances = []
    paginator = ec2_client.get_paginator('describe_instances')
    for page in paginator.paginate(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
        for r in page['Reservations']:
            for i in r['Instances']:
                instances.append({
                    'id': i['InstanceId'],
                    'type': i['InstanceType'],
                    'state': i['State']['Name']
                })
    
    metric_rows = []
    
    for inst in instances:
        # Upsert Resource
        pk = _upsert_resource(
            db, 
            models.EC2Resource, 
            {"account_id": account_id, "region": region, "instance_id": inst['id']},
            {"instance_type": inst['type'], "state": inst['state']}
        )
        
        # Get Metrics (CPU)
        resp = cw.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': inst['id']}],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=['Maximum'] # p95 needs specialized call, use Max for simple demo
        )
        
        daily_metrics = {}
        for point in resp['Datapoints']:
            d_key = point['Timestamp'].date()
            val = point['Maximum']
            if d_key not in daily_metrics:
                daily_metrics[d_key] = val
            else:
                daily_metrics[d_key] = max(daily_metrics[d_key], val)
                
        for d_key, max_val in daily_metrics.items():
            metric_rows.append({
                "ec2_resource_id": pk,
                "metric_date": d_key,
                "cpu_utilization": max_val,
            })
    if metric_rows:
        _bulk_upsert(db, models.EC2Metric, metric_rows, ["ec2_resource_id", "metric_date"])
