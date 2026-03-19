"""
Forecast Pricing Calculator

Calculate forecasted costs based on predicted usage metrics and AWS pricing.
Supports EC2, RDS, Lambda, S3, and ALB services.
"""

import logging
from typing import Dict, List, Tuple
import numpy as np
from datetime import date

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# AWS Pricing Constants (ap-southeast-1)
# ──────────────────────────────────────────────

# EC2 Instance Pricing ($/hour)
EC2_INSTANCE_PRICING = {
    "t3.nano": 0.0058,
    "t3.micro": 0.0116,
    "t3.small": 0.0232,
    "t3.medium": 0.0464,
    "t3.large": 0.0928,
    "t3.xlarge": 0.1856,
    "t3.2xlarge": 0.3712,
    "t3a.nano": 0.0052,
    "t3a.micro": 0.0104,
    "t3a.small": 0.0208,
    "t3a.medium": 0.0416,
    "t3a.large": 0.0832,
    "m5.large": 0.107,
    "m5.xlarge": 0.214,
    "m5.2xlarge": 0.428,
    "m5.4xlarge": 0.856,
    "c5.large": 0.094,
    "c5.xlarge": 0.188,
    "c5.2xlarge": 0.376,
    "c6i.large": 0.096,
    "c6i.xlarge": 0.192,
    "c6i.2xlarge": 0.384,
    "r5.large": 0.140,
    "r5.xlarge": 0.280,
    "r5.2xlarge": 0.560,
    "r6g.medium": 0.0605,
    "r6g.large": 0.121,
    "r6g.xlarge": 0.242,
}

# EBS Volume Pricing ($/GB/month)
EBS_VOLUME_PRICING = {
    "gp3": 0.096,
    "gp2": 0.114,
    "io1": 0.138,
    "io2": 0.138,
    "st1": 0.051,
    "sc1": 0.029,
}

# EBS IOPS Pricing ($/IOPS/month)
EBS_IOPS_PRICING = {
    "io1": 0.072,
    "io2": 0.072,
    "gp3": 0.006,  # Above 3000 IOPS
}

# Network Pricing
NETWORK_EGRESS_PRICE_PER_GB = 0.09  # $/GB (first 10TB/month)
NETWORK_CROSS_AZ_PRICE_PER_GB = 0.01  # $/GB
PUBLIC_IPV4_PRICE_PER_HR = 0.005  # $/hour
EBS_SNAPSHOT_PRICE_PER_GB = 0.053  # $/GB/month

# RDS Instance Pricing ($/hour) - PostgreSQL
RDS_INSTANCE_PRICING = {
    "db.t3.micro": 0.018,
    "db.t3.small": 0.036,
    "db.t3.medium": 0.073,
    "db.t3.large": 0.146,
    "db.t3.xlarge": 0.292,
    "db.t3.2xlarge": 0.584,
    "db.t4g.micro": 0.016,
    "db.t4g.small": 0.032,
    "db.t4g.medium": 0.065,
    "db.t4g.large": 0.130,
    "db.m5.large": 0.192,
    "db.m5.xlarge": 0.384,
    "db.m5.2xlarge": 0.768,
    "db.r5.large": 0.280,
    "db.r5.xlarge": 0.560,
    "db.r5.2xlarge": 1.120,
}

# RDS Storage Pricing ($/GB/month)
RDS_STORAGE_PRICING = {
    "gp2": 0.138,
    "gp3": 0.138,
    "io1": 0.138,
    "magnetic": 0.115,
}

# Lambda Pricing
LAMBDA_REQUEST_PRICE = 0.0000002  # $/request
LAMBDA_DURATION_PRICE_PER_GB_SEC = 0.0000166667  # $/GB-second

# S3 Pricing ($/GB/month)
S3_STORAGE_PRICING = {
    "Standard": 0.025,  # First 50TB
    "Standard-IA": 0.0138,
    "One Zone-IA": 0.011,
    "Glacier": 0.005,
    "Glacier Deep Archive": 0.002,
}

# S3 Request Pricing
S3_GET_REQUEST_PRICE = 0.00000044  # $/1000 requests
S3_PUT_REQUEST_PRICE = 0.0000055  # $/1000 requests

# ALB Pricing
ALB_HOUR_PRICE = 0.0252  # $/hour
ALB_LCU_PRICE = 0.008  # $/LCU-hour
NLB_HOUR_PRICE = 0.0252  # $/hour
NLB_NLCU_PRICE = 0.006  # $/NLCU-hour


# ──────────────────────────────────────────────
# EC2 Cost Calculation
# ──────────────────────────────────────────────

def calculate_ec2_forecast_cost(
    resource_info: Dict,
    forecast_dates: List[date],
    forecast_metrics: Dict[str, List[float]]
) -> Tuple[List[float], Dict[str, List[float]]]:
    """
    Calculate EC2 forecast costs based on predicted metrics.
    
    Args:
        resource_info: EC2 resource information (instance_type, ebs_type, etc.)
        forecast_dates: List of forecast dates
        forecast_metrics: Dict of metric_name -> forecasted values
            Expected keys: cpu_utilization, network_egress_gb, hours_running
    
    Returns:
        (total_daily_costs, cost_breakdown)
        - total_daily_costs: List of total costs per day
        - cost_breakdown: Dict of cost_type -> List of costs per day
    """
    instance_type = resource_info.get("instance_type", "t3.medium")
    hourly_price = EC2_INSTANCE_PRICING.get(instance_type, 0.0464)
    
    # EBS information
    ebs_type = resource_info.get("ebs_type", "gp3")
    ebs_size_gb = resource_info.get("ebs_size_gb", 50)
    ebs_iops = resource_info.get("ebs_iops", 3000)
    
    # Network information
    has_public_ip = resource_info.get("has_public_ip", False)
    
    # Get forecasted metrics
    hours_running = forecast_metrics.get("hours_running", [24.0] * len(forecast_dates))
    network_egress_gb = forecast_metrics.get("network_egress_gb", [0.0] * len(forecast_dates))
    
    # Initialize cost breakdown
    compute_costs = []
    ebs_costs = []
    network_costs = []
    ip_costs = []
    total_costs = []
    
    for i, forecast_date in enumerate(forecast_dates):
        # Compute cost
        hours = hours_running[i] if i < len(hours_running) else 24.0
        compute_cost = hourly_price * hours
        
        # EBS cost (daily portion of monthly cost)
        ebs_volume_cost = (EBS_VOLUME_PRICING.get(ebs_type, 0.096) * ebs_size_gb) / 30
        
        # EBS IOPS cost (if applicable)
        ebs_iops_cost = 0
        if ebs_type in ["io1", "io2"]:
            ebs_iops_cost = (EBS_IOPS_PRICING.get(ebs_type, 0) * ebs_iops) / 30
        elif ebs_type == "gp3" and ebs_iops > 3000:
            extra_iops = ebs_iops - 3000
            ebs_iops_cost = (EBS_IOPS_PRICING.get("gp3", 0) * extra_iops) / 30
        
        ebs_cost = ebs_volume_cost + ebs_iops_cost
        
        # Network cost
        egress_gb = network_egress_gb[i] if i < len(network_egress_gb) else 0.0
        network_cost = egress_gb * NETWORK_EGRESS_PRICE_PER_GB
        
        # Public IP cost
        ip_cost = 0
        if has_public_ip:
            ip_cost = PUBLIC_IPV4_PRICE_PER_HR * hours
        
        # Total
        total_cost = compute_cost + ebs_cost + network_cost + ip_cost
        
        compute_costs.append(round(compute_cost, 6))
        ebs_costs.append(round(ebs_cost, 6))
        network_costs.append(round(network_cost, 6))
        ip_costs.append(round(ip_cost, 6))
        total_costs.append(round(total_cost, 6))
    
    cost_breakdown = {
        "compute": compute_costs,
        "ebs": ebs_costs,
        "network": network_costs,
        "public_ip": ip_costs,
    }
    
    return total_costs, cost_breakdown


# ──────────────────────────────────────────────
# RDS Cost Calculation
# ──────────────────────────────────────────────

def calculate_rds_forecast_cost(
    resource_info: Dict,
    forecast_dates: List[date],
    forecast_metrics: Dict[str, List[float]]
) -> Tuple[List[float], Dict[str, List[float]]]:
    """
    Calculate RDS forecast costs based on predicted metrics.
    
    Args:
        resource_info: RDS resource information
        forecast_dates: List of forecast dates
        forecast_metrics: Dict of metric_name -> forecasted values
    
    Returns:
        (total_daily_costs, cost_breakdown)
    """
    instance_class = resource_info.get("instance_class", "db.t3.medium")
    hourly_price = RDS_INSTANCE_PRICING.get(instance_class, 0.073)
    
    # Storage information
    storage_type = resource_info.get("storage_type", "gp3")
    allocated_gb = resource_info.get("allocated_gb", 100)
    
    # Multi-AZ factor (doubles compute cost)
    multi_az = resource_info.get("multi_az", False)
    multi_az_factor = 2.0 if multi_az else 1.0
    
    # Get forecasted metrics for utilization-based pricing
    cpu_utilization = forecast_metrics.get("cpu_utilization", [50.0] * len(forecast_dates))
    database_connections = forecast_metrics.get("database_connections", [10.0] * len(forecast_dates))
    
    # Initialize cost breakdown
    compute_costs = []
    storage_costs = []
    total_costs = []
    
    for i, forecast_date in enumerate(forecast_dates):
        # Get utilization metrics for this day
        cpu_util = cpu_utilization[i] if i < len(cpu_utilization) else 50.0
        connections = database_connections[i] if i < len(database_connections) else 10.0
        
        # RDS instances are always running and billed per hour, regardless of connections
        # However, we can apply a modest utilization discount for consistently low usage
        # This represents potential savings from rightsizing or serverless options
        
        if cpu_util > 70:
            utilization_factor = 1.0  # Full price for high utilization
        elif cpu_util > 30:
            utilization_factor = 0.95  # 5% discount for medium utilization
        else:
            utilization_factor = 0.90  # 10% discount for low utilization (rightsizing opportunity)
        
        # Compute cost with Multi-AZ and modest utilization adjustment
        effective_hourly_price = hourly_price * multi_az_factor * utilization_factor
        compute_cost = effective_hourly_price * 24
        
        # Storage cost (daily portion of monthly cost)
        storage_cost = (RDS_STORAGE_PRICING.get(storage_type, 0.138) * allocated_gb) / 30
        
        # Total
        total_cost = compute_cost + storage_cost
        
        compute_costs.append(round(compute_cost, 6))
        storage_costs.append(round(storage_cost, 6))
        total_costs.append(round(total_cost, 6))
    
    cost_breakdown = {
        "compute": compute_costs,
        "storage": storage_costs,
    }
    
    return total_costs, cost_breakdown


# ──────────────────────────────────────────────
# Lambda Cost Calculation
# ──────────────────────────────────────────────

def calculate_lambda_forecast_cost(
    resource_info: Dict,
    forecast_dates: List[date],
    forecast_metrics: Dict[str, List[float]]
) -> Tuple[List[float], Dict[str, List[float]]]:
    """
    Calculate Lambda forecast costs based on predicted metrics.
    
    Args:
        resource_info: Lambda resource information
        forecast_dates: List of forecast dates
        forecast_metrics: Dict of metric_name -> forecasted values
            Expected keys: invocations, duration_avg
    
    Returns:
        (total_daily_costs, cost_breakdown)
    """
    memory_mb = resource_info.get("memory_mb", 128)
    memory_gb = memory_mb / 1024.0
    
    # Get forecasted metrics
    invocations = forecast_metrics.get("invocations", [0.0] * len(forecast_dates))
    duration_avg_ms = forecast_metrics.get("duration_avg", [100.0] * len(forecast_dates))
    
    # Initialize cost breakdown
    request_costs = []
    duration_costs = []
    total_costs = []
    
    for i, forecast_date in enumerate(forecast_dates):
        # Request cost
        inv_count = invocations[i] if i < len(invocations) else 0.0
        request_cost = inv_count * LAMBDA_REQUEST_PRICE
        
        # Duration cost (GB-seconds)
        duration_ms = duration_avg_ms[i] if i < len(duration_avg_ms) else 100.0
        duration_sec = duration_ms / 1000.0
        gb_seconds = inv_count * memory_gb * duration_sec
        duration_cost = gb_seconds * LAMBDA_DURATION_PRICE_PER_GB_SEC
        
        # Total
        total_cost = request_cost + duration_cost
        
        request_costs.append(round(request_cost, 6))
        duration_costs.append(round(duration_cost, 6))
        total_costs.append(round(total_cost, 6))
    
    cost_breakdown = {
        "requests": request_costs,
        "duration": duration_costs,
    }
    
    return total_costs, cost_breakdown


# ──────────────────────────────────────────────
# S3 Cost Calculation
# ──────────────────────────────────────────────

def calculate_s3_forecast_cost(
    resource_info: Dict,
    forecast_dates: List[date],
    forecast_metrics: Dict[str, List[float]]
) -> Tuple[List[float], Dict[str, List[float]]]:
    """
    Calculate S3 forecast costs based on predicted metrics.
    
    Args:
        resource_info: S3 resource information
        forecast_dates: List of forecast dates
        forecast_metrics: Dict of metric_name -> forecasted values
            Expected keys: bucket_size_bytes, get_requests, put_requests
    
    Returns:
        (total_daily_costs, cost_breakdown)
    """
    storage_class = resource_info.get("storage_class", "Standard")
    storage_price_per_gb = S3_STORAGE_PRICING.get(storage_class, 0.025)
    
    # Get forecasted metrics
    bucket_size_bytes = forecast_metrics.get("bucket_size_bytes", [0.0] * len(forecast_dates))
    get_requests = forecast_metrics.get("get_requests", [0.0] * len(forecast_dates))
    put_requests = forecast_metrics.get("put_requests", [0.0] * len(forecast_dates))
    
    # Initialize cost breakdown
    storage_costs = []
    request_costs = []
    total_costs = []
    
    for i, forecast_date in enumerate(forecast_dates):
        # Storage cost (daily portion of monthly cost)
        size_bytes = bucket_size_bytes[i] if i < len(bucket_size_bytes) else 0.0
        size_gb = size_bytes / (1024 ** 3)
        storage_cost = (storage_price_per_gb * size_gb) / 30
        
        # Request cost
        get_req = get_requests[i] if i < len(get_requests) else 0.0
        put_req = put_requests[i] if i < len(put_requests) else 0.0
        request_cost = (get_req / 1000) * S3_GET_REQUEST_PRICE + (put_req / 1000) * S3_PUT_REQUEST_PRICE
        
        # Total
        total_cost = storage_cost + request_cost
        
        storage_costs.append(round(storage_cost, 6))
        request_costs.append(round(request_cost, 6))
        total_costs.append(round(total_cost, 6))
    
    cost_breakdown = {
        "storage": storage_costs,
        "requests": request_costs,
    }
    
    return total_costs, cost_breakdown


# ──────────────────────────────────────────────
# ALB Cost Calculation
# ──────────────────────────────────────────────

def calculate_alb_forecast_cost(
    resource_info: Dict,
    forecast_dates: List[date],
    forecast_metrics: Dict[str, List[float]]
) -> Tuple[List[float], Dict[str, List[float]]]:
    """
    Calculate ALB/NLB forecast costs based on predicted metrics.
    
    Args:
        resource_info: ALB resource information
        forecast_dates: List of forecast dates
        forecast_metrics: Dict of metric_name -> forecasted values
            Expected keys: request_count, processed_bytes, new_conn_count
    
    Returns:
        (total_daily_costs, cost_breakdown)
    """
    lb_type = resource_info.get("lb_type", "ALB")
    
    # Get forecasted metrics
    request_count = forecast_metrics.get("request_count", [0.0] * len(forecast_dates))
    processed_bytes = forecast_metrics.get("processed_bytes", [0.0] * len(forecast_dates))
    new_conn_count = forecast_metrics.get("new_conn_count", [0.0] * len(forecast_dates))
    
    # Initialize cost breakdown
    hourly_costs = []
    lcu_costs = []
    total_costs = []
    
    for i, forecast_date in enumerate(forecast_dates):
        # Hourly cost (24 hours)
        if lb_type == "NLB":
            hourly_cost = NLB_HOUR_PRICE * 24
        else:
            hourly_cost = ALB_HOUR_PRICE * 24
        
        # LCU/NLCU cost calculation
        # LCU dimensions: new connections, active connections, processed bytes, rule evaluations
        # Simplified: use max of (requests/25, processed_gb/1, new_conns/3000)
        requests = request_count[i] if i < len(request_count) else 0.0
        proc_bytes = processed_bytes[i] if i < len(processed_bytes) else 0.0
        new_conns = new_conn_count[i] if i < len(new_conn_count) else 0.0
        
        proc_gb = proc_bytes / (1024 ** 3)
        
        # Calculate LCU (simplified)
        lcu_from_requests = requests / 25
        lcu_from_bytes = proc_gb / 1.0
        lcu_from_conns = new_conns / 3000
        
        lcu_hours = max(lcu_from_requests, lcu_from_bytes, lcu_from_conns)
        
        if lb_type == "NLB":
            lcu_cost = lcu_hours * NLB_NLCU_PRICE
        else:
            lcu_cost = lcu_hours * ALB_LCU_PRICE
        
        # Total
        total_cost = hourly_cost + lcu_cost
        
        hourly_costs.append(round(hourly_cost, 6))
        lcu_costs.append(round(lcu_cost, 6))
        total_costs.append(round(total_cost, 6))
    
    cost_breakdown = {
        "hourly": hourly_costs,
        "lcu": lcu_costs,
    }
    
    return total_costs, cost_breakdown
