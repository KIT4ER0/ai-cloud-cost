from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from .. import schemas, database, models
from ..auth import get_current_user
from ..services.sync import sync_aws_costs, sync_aws_metrics

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
