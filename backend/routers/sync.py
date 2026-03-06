from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import os
import boto3

from .. import schemas, database, models
from ..auth import get_current_user
from ..services.sync import sync_aws_costs, sync_aws_metrics
from ..services.metrics_ec2 import list_ec2_instances, pull_ec2_metrics
from ..services.metrics_rds import list_rds_instances, pull_rds_metrics

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    responses={404: {"description": "Not found"}},
)

@router.post("/cost", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cost_sync(
    background_tasks: BackgroundTasks,
    days_back: int = 90,
    current_user: models.UserProfile = Depends(get_current_user)
):
    """Trigger AWS Cost Explorer sync in the background."""
    background_tasks.add_task(sync_aws_costs, current_user.profile_id, days_back)
    return {"message": "Cost sync started in background", "days_back": days_back}

@router.post("/metrics", status_code=status.HTTP_202_ACCEPTED)
async def trigger_metric_sync(
    background_tasks: BackgroundTasks,
    hours_back: int = 24,
    current_user: models.UserProfile = Depends(get_current_user)
):
    """Trigger AWS CloudWatch Metrics sync in the background."""
    background_tasks.add_task(sync_aws_metrics, current_user.profile_id, hours_back)
    return {"message": "Metric sync started in background", "hours_back": hours_back}


# ─── Helper: AssumeRole Session ────────────────────────────────────

def _get_customer_session(current_user: models.UserProfile):
    """Validate user has AWS linked and return assumed session."""
    if not current_user.aws_role_arn:
        raise HTTPException(
            status_code=400,
            detail="No AWS role linked. Connect your AWS account first via /api/aws/connect.",
        )
    if not current_user.aws_external_id:
        raise HTTPException(status_code=400, detail="No external_id found for current user.")

    from ..services.aws_sts import get_assumed_session

    try:
        return get_assumed_session(
            role_arn=current_user.aws_role_arn,
            session_name=f"metric-pull-{current_user.profile_id}",
            external_id=current_user.aws_external_id,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AssumeRole failed: {e}")


def _format_cw_response(results: dict) -> dict:
    """Convert datetime objects in CloudWatch response to strings."""
    formatted = {}
    for key, data in results.items():
        metrics = data.get("metrics")
        if metrics:
            for r in metrics.get("MetricDataResults", []):
                r["Timestamps"] = [t.isoformat() for t in r.get("Timestamps", [])]
            metrics["StartTimeUTC"] = str(metrics.get("StartTimeUTC"))
            metrics["EndTimeUTC"] = str(metrics.get("EndTimeUTC"))
        formatted[key] = data
    return formatted


# ─── Pull EC2 Metrics (via AssumeRole) ─────────────────────────────

@router.get("/ec2-metrics")
def test_pull_ec2_metrics(
    region: str = "us-east-1",
    days_back: int = 30,
    current_user: models.UserProfile = Depends(get_current_user),
):
    """
    List EC2 instances and pull CloudWatch metrics
    using AssumeRole with the current user's stored role_arn.
    """
    session = _get_customer_session(current_user)

    try:
        instances = list_ec2_instances(session, region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list EC2 instances: {e}")

    if not instances:
        return {
            "status": "no_instances",
            "message": f"No running EC2 instances found in {region}",
            "instances": [],
            "metrics": {},
        }

    try:
        results = pull_ec2_metrics(
            customer_session=session,
            region=region,
            days_back=days_back,
            timezone_offset_hours=7,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull EC2 metrics: {e}")

    return {
        "status": "ok",
        "region": region,
        "days_back": days_back,
        "instance_count": len(instances),
        "instances": instances,
        "metrics": _format_cw_response(results),
    }


# ─── Pull RDS Metrics (via AssumeRole) ─────────────────────────────

@router.get("/rds-metrics")
def test_pull_rds_metrics(
    region: str = "us-east-1",
    days_back: int = 30,
    current_user: models.UserProfile = Depends(get_current_user),
):
    """
    List RDS instances and pull CloudWatch metrics
    using AssumeRole with the current user's stored role_arn.
    """
    session = _get_customer_session(current_user)

    try:
        instances = list_rds_instances(session, region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list RDS instances: {e}")

    if not instances:
        return {
            "status": "no_instances",
            "message": f"No RDS instances found in {region}",
            "instances": [],
            "metrics": {},
        }

    try:
        results = pull_rds_metrics(
            customer_session=session,
            region=region,
            days_back=days_back,
            timezone_offset_hours=7,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull RDS metrics: {e}")

    return {
        "status": "ok",
        "region": region,
        "days_back": days_back,
        "instance_count": len(instances),
        "instances": instances,
        "metrics": _format_cw_response(results),
    }
