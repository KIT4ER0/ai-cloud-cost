"""
Forecast API router.

Provides endpoints to:
  - GET  /forecast/metrics          → list available services and metrics
  - POST /forecast/predict          → generate + save forecast
  - POST /forecast/backtest         → evaluate model accuracy
  - GET  /forecast/runs             → list saved forecast runs
  - GET  /forecast/runs/{run_id}    → get specific forecast run with values
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from ..models import UserProfile
from ..schemas import (
    ForecastRunOut,
    EnsembleForecastRequest,
    EnsembleForecastResponse
)
from .forecast_service import (
    SERVICE_METRIC_MAP,
    get_available_metrics,
    forecast_metric,
    backtest_metric,
    save_forecast_run,
    get_forecast_runs,
    get_forecast_run_by_id,
)
from .ensemble_forecast_service import run_ensemble_forecast

router = APIRouter(prefix="/forecast", tags=["Forecast"])


# ─── Request Schemas ─────────────────────────────────────────────

class ForecastRequest(BaseModel):
    service: str
    resource_id: int
    metric: str
    horizon: int = 30
    method: str = "moving_average"
    window: int = 7
    season_length: int = 7


class BacktestRequest(BaseModel):
    service: str
    resource_id: int
    metric: str
    test_size: int = 7
    method: str = "moving_average"
    window: int = 7
    season_length: int = 7


# ─── Endpoints ───────────────────────────────────────────────────

@router.get("/metrics")
def list_forecastable_metrics(
    current_user: UserProfile = Depends(get_current_user),
):
    """List all services and their forecastable metric columns."""
    return {
        service: cfg["metrics"]
        for service, cfg in SERVICE_METRIC_MAP.items()
    }


@router.post("/predict")
def predict_forecast(
    req: ForecastRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Generate forecast and save to DB."""
    try:
        result = forecast_metric(
            db=db,
            service=req.service,
            resource_id=req.resource_id,
            metric_column=req.metric,
            horizon=req.horizon,
            method=req.method,
            window=req.window,
            season_length=req.season_length,
        )

        # Save forecast run to DB
        run = save_forecast_run(
            db=db,
            profile_id=current_user.profile_id,
            service=req.service,
            resource_id=req.resource_id,
            metric=req.metric,
            method=req.method,
            params={"window": req.window, "season_length": req.season_length},
            horizon=req.horizon,
            train_size=len(result["history"]),
            forecast_data=result["forecast"],
        )

        result["run_id"] = run.run_id
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/backtest")
def run_backtest(
    req: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Evaluate forecast accuracy on held-out historical data."""
    try:
        result = backtest_metric(
            db=db,
            service=req.service,
            resource_id=req.resource_id,
            metric_column=req.metric,
            test_size=req.test_size,
            method=req.method,
            window=req.window,
            season_length=req.season_length,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/runs", response_model=List[ForecastRunOut])
def list_forecast_runs(
    service: Optional[str] = Query(None),
    resource_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """List saved forecast runs for the current user."""
    runs = get_forecast_runs(
        db=db,
        profile_id=current_user.profile_id,
        service=service,
        resource_id=resource_id,
    )
    return runs


@router.get("/runs/{run_id}", response_model=ForecastRunOut)
def get_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Get a specific forecast run with all forecast values."""
    run = get_forecast_run_by_id(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Forecast run not found")
    if run.profile_id != current_user.profile_id:
        raise HTTPException(status_code=403, detail="Access denied")
    return run


# ─── Ensemble Forecast Endpoint ───────────────────────────────────

@router.post("/ensemble", response_model=EnsembleForecastResponse)
def run_ensemble(
    req: EnsembleForecastRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Run Ensemble forecast for a resource (ETS + SARIMA + Ridge).

    - If `metric` is provided, forecasts only that metric.
    - If `metric` is omitted, forecasts all available metrics for the service.
    - Falls back to baseline (moving_average) if Ensemble fails.
    - Results are saved to the per-service forecast_results table.
    """
    try:
        # Replaces XGBoost logic with the new 3-model ensemble
        result = run_ensemble_forecast(
            db=db,
            service=req.service,
            resource_id=req.resource_id,
            metric=req.metric,
            horizon=req.horizon,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
