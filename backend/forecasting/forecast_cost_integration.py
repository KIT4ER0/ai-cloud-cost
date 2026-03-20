"""
Forecast Cost Integration

Integrates cost calculation with forecast results.
Fetches resource information and calculates costs based on forecasted usage.
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from datetime import date

from . import forecast_pricing
from .. import models

logger = logging.getLogger(__name__)


def get_ec2_resource_info(db: Session, resource_id: int) -> Dict:
    """Get EC2 resource information for cost calculation."""
    resource = db.query(models.EC2Resource).filter_by(ec2_resource_id=resource_id).first()
    if not resource:
        logger.warning(f"EC2 resource {resource_id} not found")
        return {}
    
    # Get EBS volume info
    ebs_volume = db.query(models.EC2EBSVolume).filter_by(ec2_resource_id=resource_id).first()
    
    return {
        "instance_type": resource.instance_type,
        "has_public_ip": resource.has_public_ip or False,
        "ebs_type": ebs_volume.volume_type if ebs_volume else "gp3",
        "ebs_size_gb": ebs_volume.size_gb if ebs_volume else 50,
        "ebs_iops": ebs_volume.iops if ebs_volume else 3000,
    }


def get_rds_resource_info(db: Session, resource_id: int) -> Dict:
    """Get RDS resource information for cost calculation."""
    resource = db.query(models.RDSResource).filter_by(rds_resource_id=resource_id).first()
    if not resource:
        logger.warning(f"RDS resource {resource_id} not found")
        return {}
    
    return {
        "instance_class": resource.instance_class,
        "storage_type": resource.storage_type or "gp3",
        "allocated_gb": resource.allocated_gb or 100,
        "multi_az": resource.multi_az or False,
    }


def get_lambda_resource_info(db: Session, resource_id: int) -> Dict:
    """Get Lambda resource information for cost calculation."""
    resource = db.query(models.LambdaResource).filter_by(lambda_resource_id=resource_id).first()
    if not resource:
        logger.warning(f"Lambda resource {resource_id} not found")
        return {}
    
    return {
        "memory_mb": resource.memory_mb or 128,
    }


def get_s3_resource_info(db: Session, resource_id: int) -> Dict:
    """Get S3 resource information for cost calculation."""
    resource = db.query(models.S3Resource).filter_by(s3_resource_id=resource_id).first()
    if not resource:
        logger.warning(f"S3 resource {resource_id} not found")
        return {}
    
    return {
        "storage_class": resource.storage_class or "Standard",
    }


def get_alb_resource_info(db: Session, resource_id: int) -> Dict:
    """Get ALB resource information for cost calculation."""
    resource = db.query(models.ALBResource).filter_by(alb_resource_id=resource_id).first()
    if not resource:
        logger.warning(f"ALB resource {resource_id} not found")
        return {}
    
    return {
        "lb_type": resource.lb_type or "ALB",
    }


def calculate_forecast_costs(
    db: Session,
    service: str,
    resource_id: int,
    forecast_dates: List[date],
    all_forecast_results: List[Dict]
) -> tuple[Optional[List[float]], Optional[Dict]]:
    """
    Calculate forecast costs based on predicted metrics.
    
    Args:
        db: Database session
        service: Service name (ec2, rds, lambda, s3, alb)
        resource_id: Resource ID
        forecast_dates: List of forecast dates
        all_forecast_results: List of forecast result dicts with metric and forecast_values
    
    Returns:
        (forecast_costs, cost_breakdown) or (None, None) if calculation fails
    """
    # Get resource information
    resource_info_funcs = {
        "ec2": get_ec2_resource_info,
        "rds": get_rds_resource_info,
        "lambda": get_lambda_resource_info,
        "s3": get_s3_resource_info,
        "alb": get_alb_resource_info,
    }
    
    get_resource_info = resource_info_funcs.get(service)
    if not get_resource_info:
        logger.warning(f"No resource info function for service: {service}")
        return None, None
    
    resource_info = get_resource_info(db, resource_id)
    if not resource_info:
        logger.warning(f"Could not get resource info for {service} resource {resource_id}")
        return None, None
    
    # Build forecast metrics dict
    forecast_metrics = {}
    for result in all_forecast_results:
        metric_name = result.get("metric")
        forecast_values = result.get("forecast_values", [])
        if metric_name and forecast_values:
            forecast_metrics[metric_name] = forecast_values
    
    if not forecast_metrics:
        logger.warning(f"No forecast metrics available for cost calculation")
        return None, None
    
    # Calculate costs based on service type
    try:
        if service == "ec2":
            total_costs, cost_breakdown = forecast_pricing.calculate_ec2_forecast_cost(
                resource_info, forecast_dates, forecast_metrics
            )
        elif service == "rds":
            total_costs, cost_breakdown = forecast_pricing.calculate_rds_forecast_cost(
                resource_info, forecast_dates, forecast_metrics
            )
        elif service == "lambda":
            total_costs, cost_breakdown = forecast_pricing.calculate_lambda_forecast_cost(
                resource_info, forecast_dates, forecast_metrics
            )
        elif service == "s3":
            total_costs, cost_breakdown = forecast_pricing.calculate_s3_forecast_cost(
                resource_info, forecast_dates, forecast_metrics
            )
        elif service == "alb":
            total_costs, cost_breakdown = forecast_pricing.calculate_alb_forecast_cost(
                resource_info, forecast_dates, forecast_metrics
            )
        else:
            logger.warning(f"Unsupported service for cost calculation: {service}")
            return None, None
        
        logger.info(
            f"Calculated forecast costs for {service} resource {resource_id}: "
            f"{len(total_costs)} days, total=${sum(total_costs):.2f}"
        )
        
        return total_costs, cost_breakdown
        
    except Exception as e:
        logger.error(f"Error calculating forecast costs for {service} resource {resource_id}: {e}")
        return None, None


def add_costs_to_forecast_result(
    forecast_result: Dict,
    forecast_costs: Optional[List[float]],
    cost_breakdown: Optional[Dict]
) -> Dict:
    """
    Add cost information to forecast result dict.
    
    Args:
        forecast_result: Original forecast result dict
        forecast_costs: List of total daily costs
        cost_breakdown: Dict of cost breakdown by type
    
    Returns:
        Updated forecast result dict with cost information
    """
    result = forecast_result.copy()
    
    if forecast_costs:
        result["forecast_costs"] = forecast_costs
        result["total_forecast_cost"] = round(sum(forecast_costs), 2)
        result["avg_daily_cost"] = round(sum(forecast_costs) / len(forecast_costs), 2) if forecast_costs else 0
    
    if cost_breakdown:
        result["cost_breakdown"] = cost_breakdown
        
        # Calculate breakdown totals
        breakdown_totals = {}
        for cost_type, costs in cost_breakdown.items():
            breakdown_totals[cost_type] = round(sum(costs), 2)
        result["cost_breakdown_totals"] = breakdown_totals
    
    return result
