from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import os
import boto3

from .. import schemas, database, models
from ..auth import get_current_user
from ..services.sync import sync_aws_costs, sync_aws_metrics
from ..services.pull_data_metric import (
    list_ec2_instances,
    pull_ec2_metrics,
)

router = APIRouter(
    prefix="/sync",
    tags=["sync"],
    responses={404: {"description": "Not found"}},
)

@router.post("/cost", status_code=status.HTTP_202_ACCEPTED)
async def trigger_cost_sync(
    background_tasks: BackgroundTasks,
    days_back: int = 90,
    current_user: models.User = Depends(get_current_user)
):
    """
    Trigger AWS Cost Explorer sync in the background.
    """
        
    background_tasks.add_task(sync_aws_costs, days_back)
    return {"message": "Cost sync started in background", "days_back": days_back}

@router.post("/metrics", status_code=status.HTTP_202_ACCEPTED)
async def trigger_metric_sync(
    background_tasks: BackgroundTasks,
    hours_back: int = 24,
    current_user: models.User = Depends(get_current_user)
):
    """
    Trigger AWS CloudWatch Metrics sync in the background.
    """
        
    background_tasks.add_task(sync_aws_metrics, hours_back)
    return {"message": "Metric sync started in background", "hours_back": hours_back}


# ─── Pull EC2 Metrics (via AssumeRole) ─────────────────────────────

@router.get("/ec2-metrics")
def test_pull_ec2_metrics(
    region: str = "us-east-1",
    days_back: int = 7,
    current_user: models.User = Depends(get_current_user),
):
    """
    List EC2 instances and pull CloudWatch metrics
    using AssumeRole with the current user's stored role_arn.
    """
    if not current_user.aws_role_arn:
        raise HTTPException(
            status_code=400,
            detail="No AWS role linked. Connect your AWS account first via /api/aws/connect.",
        )
    if not current_user.aws_external_id:
        raise HTTPException(status_code=400, detail="No external_id found for current user.")

    # AssumeRole to get customer session
    from ..services.aws_sts import get_assumed_session

    try:
        session = get_assumed_session(
            role_arn=current_user.aws_role_arn,
            session_name=f"metric-pull-{current_user.user_id}",
            external_id=current_user.aws_external_id,
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=500, detail=f"AssumeRole failed: {e}")

    # Step 1: List instances
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

    # Step 2: Pull metrics
    try:
        results = pull_ec2_metrics(
            customer_session=session,
            region=region,
            days_back=days_back,
            timezone_offset_hours=7,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pull metrics: {e}")

    # Step 3: Format response (convert datetimes to strings)
    formatted = {}
    for iid, data in results.items():
        metrics = data.get("metrics")
        if metrics:
            for r in metrics.get("MetricDataResults", []):
                r["Timestamps"] = [t.isoformat() for t in r.get("Timestamps", [])]
            metrics["StartTimeUTC"] = str(metrics.get("StartTimeUTC"))
            metrics["EndTimeUTC"] = str(metrics.get("EndTimeUTC"))
        formatted[iid] = data

    return {
        "status": "ok",
        "region": region,
        "days_back": days_back,
        "instance_count": len(instances),
        "instances": instances,
        "metrics": formatted,
    }

