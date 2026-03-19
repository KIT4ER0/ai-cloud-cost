"""
Forecast API router.

Provides endpoints to:
  - GET  /forecast/metrics          → list available services and metrics
  - POST /forecast/predict          → generate + save forecast
  - POST /forecast/backtest         → evaluate model accuracy
  - GET  /forecast/runs             → list saved forecast runs
  - GET  /forecast/runs/{run_id}    → get specific forecast run with values
  - POST /forecast/ensemble         → run ensemble forecast (single resource)
  - POST /forecast/multi-ensemble   → run ensemble forecast (multi resource)
"""
import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..database import get_db
from ..auth import get_current_user
from ..models import UserProfile
from ..schemas import (
    ForecastRunOut,
    EnsembleForecastRequest,
    EnsembleForecastResponse,
    MultiEnsembleForecastRequest,
    MultiEnsembleForecastResponse,
    MultiEnsembleForecastResult,
)
from .. import models
from .forecast_service import (
    SERVICE_METRIC_MAP,
    get_available_metrics,
    forecast_metric,
    backtest_metric,
    save_forecast_run,
    get_forecast_runs,
    get_forecast_run_by_id,
)
from .ensemble_forecast_service import run_ensemble_forecast, FORECAST_RESULT_MODEL_MAP

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
    t0 = time.time()
    logger.info(
        "predict_start",
        extra={"service": req.service, "resource_id": req.resource_id,
               "metric": req.metric, "horizon": req.horizon,
               "user": current_user.profile_id}
    )
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
        elapsed = round(time.time() - t0, 2)
        logger.info(
            f"predict_ok in {elapsed}s",
            extra={"service": req.service, "resource_id": req.resource_id,
                   "elapsed_s": elapsed}
        )
        return result

    except ValueError as e:
        logger.warning(
            f"predict_error: {e}",
            extra={"service": req.service, "resource_id": req.resource_id}
        )
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"predict_unexpected: {e}",
            extra={"service": req.service, "resource_id": req.resource_id},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Internal forecast error: {type(e).__name__}")


@router.post("/backtest")
def run_backtest(
    req: BacktestRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Evaluate forecast accuracy on held-out historical data."""
    t0 = time.time()
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
        elapsed = round(time.time() - t0, 2)
        logger.info(f"backtest_ok in {elapsed}s — {req.service}/{req.metric}")
        return result
    except ValueError as e:
        logger.warning(f"backtest_error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"backtest_unexpected: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal backtest error: {type(e).__name__}")


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


# ─── Resource listing for forecast ────────────────────────────────

_RESOURCE_MODEL_MAP = {
    "ec2": (models.EC2Resource, "ec2_resource_id", "instance_id", "instance_type"),
    "rds": (models.RDSResource, "rds_resource_id", "db_identifier", "instance_class"),
    "lambda": (models.LambdaResource, "lambda_resource_id", "function_name", "runtime"),
    "s3": (models.S3Resource, "s3_resource_id", "bucket_name", "storage_class"),
    "alb": (models.ALBResource, "alb_resource_id", "lb_name", "lb_type"),
}


@router.get("/resources")
def list_forecast_resources(
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    List all available resources per service for forecast.
    Returns resources with their IDs, names, types.
    """
    result = {}
    for service, (model, id_col, name_col, type_col) in _RESOURCE_MODEL_MAP.items():
        rows = db.query(model).filter(
            model.profile_id == current_user.profile_id
        ).all()
        resources = []
        for r in rows:
            resources.append({
                "id": getattr(r, id_col),
                "name": getattr(r, name_col, None),
                "type": getattr(r, type_col, None),
            })
        result[service] = {
            "metrics": SERVICE_METRIC_MAP.get(service, {}).get("metrics", []),
            "resources": resources,
        }
    return result


@router.get("/results/{service}/{resource_id}")
def get_forecast_results(
    service: str,
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Get the latest saved forecast results (with costs) for a resource.
    Returns all metrics' forecast results from the DB.
    """
    result_model = FORECAST_RESULT_MODEL_MAP.get(service)
    if not result_model:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

    # Verify resource belongs to current user
    resource_cfg = _RESOURCE_MODEL_MAP.get(service)
    if resource_cfg:
        res_model, id_col, _, _ = resource_cfg
        resource = db.query(res_model).filter(
            getattr(res_model, id_col) == resource_id,
            res_model.profile_id == current_user.profile_id
        ).first()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")

    # Get all latest forecast results for this resource (one per metric)
    from sqlalchemy import func
    subq = (
        db.query(
            result_model.metric,
            func.max(result_model.created_at).label("latest")
        )
        .filter(result_model.resource_id == resource_id)
        .group_by(result_model.metric)
        .subquery()
    )

    rows = (
        db.query(result_model)
        .join(subq, (
            (result_model.metric == subq.c.metric) &
            (result_model.created_at == subq.c.latest)
        ))
        .filter(result_model.resource_id == resource_id)
        .all()
    )

    results = []
    for row in rows:
        item = {
            "metric": row.metric,
            "method": row.method,
            "forecast_dates": [str(d) for d in row.forecast_dates] if row.forecast_dates else [],
            "forecast_values": row.forecast_values or [],
            "mae": row.mae,
            "rmse": row.rmse,
            "mape": row.mape,
            "created_at": str(row.created_at) if row.created_at else None,
        }
        # Add cost data if available
        if row.forecast_costs:
            item["forecast_costs"] = row.forecast_costs
            item["total_forecast_cost"] = round(sum(row.forecast_costs), 2)
            item["avg_daily_cost"] = round(sum(row.forecast_costs) / len(row.forecast_costs), 2)
        if row.cost_breakdown:
            item["cost_breakdown"] = row.cost_breakdown
            # Calculate totals per cost type
            item["cost_breakdown_totals"] = {
                k: round(sum(v), 2) for k, v in row.cost_breakdown.items()
                if isinstance(v, list)
            }
        # Add backtest data if available
        if row.backtest_dates:
            item["backtest_dates"] = [str(d) for d in row.backtest_dates]
            item["backtest_actuals"] = row.backtest_actuals
            item["backtest_preds"] = row.backtest_preds
        results.append(item)

    return {
        "service": service,
        "resource_id": resource_id,
        "results": results,
    }


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
    t0 = time.time()
    logger.info(
        f"ensemble_start — {req.service}/{req.resource_id} horizon={req.horizon}"
    )
    try:
        result = run_ensemble_forecast(
            db=db,
            service=req.service,
            resource_id=req.resource_id,
            metric=req.metric,
            horizon=req.horizon,
        )
        elapsed = round(time.time() - t0, 2)
        n_results = len(result.get("results", []))
        fallbacks = sum(1 for r in result.get("results", []) if r.get("fallback"))
        logger.info(
            f"ensemble_ok in {elapsed}s — {req.service}/{req.resource_id} "
            f"{n_results} metrics, {fallbacks} fallbacks"
        )
        return result
    except ValueError as e:
        logger.warning(f"ensemble_value_error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            f"ensemble_unexpected: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ensemble forecast failed: {type(e).__name__}: {e}",
        )


@router.post("/multi-ensemble", response_model=MultiEnsembleForecastResponse)
def run_multi_ensemble(
    req: MultiEnsembleForecastRequest,
    db: Session = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Run Ensemble forecast for multiple resources in one call.

    - Iterates over each resource in `req.resources`
    - Runs the full ensemble pipeline per resource
    - Collects results; individual failures do NOT block others
    """
    t0 = time.time()
    n_resources = len(req.resources)
    logger.info(
        f"multi_ensemble_start — {n_resources} resources, horizon={req.horizon}"
    )

    forecasts: list[MultiEnsembleForecastResult] = []
    successful = 0
    failed_count = 0

    for idx, item in enumerate(req.resources, 1):
        item_t0 = time.time()

        # Resolve resource name for the response
        resource_name: str | None = None
        res_cfg = _RESOURCE_MODEL_MAP.get(item.service)
        if res_cfg:
            res_model, id_col, name_col, _ = res_cfg
            row = db.query(res_model).filter(
                getattr(res_model, id_col) == item.resource_id,
                res_model.profile_id == current_user.profile_id,
            ).first()
            if row:
                resource_name = getattr(row, name_col, None)
            else:
                logger.warning(
                    f"multi_ensemble [{idx}/{n_resources}] "
                    f"{item.service}/{item.resource_id}: resource not found"
                )
                forecasts.append(MultiEnsembleForecastResult(
                    service=item.service,
                    resource_id=item.resource_id,
                    resource_name=None,
                    results=[],
                    error="Resource not found or access denied",
                ))
                failed_count += 1
                continue

        try:
            result = run_ensemble_forecast(
                db=db,
                service=item.service,
                resource_id=item.resource_id,
                metric=None,  # forecast all metrics
                horizon=req.horizon,
            )
            item_elapsed = round(time.time() - item_t0, 2)
            n_metrics = len(result.get("results", []))
            logger.info(
                f"multi_ensemble [{idx}/{n_resources}] "
                f"{item.service}/{item.resource_id} OK in {item_elapsed}s "
                f"({n_metrics} metrics)"
            )
            forecasts.append(MultiEnsembleForecastResult(
                service=item.service,
                resource_id=item.resource_id,
                resource_name=resource_name,
                results=result["results"],
                error=None,
            ))
            successful += 1
        except Exception as e:
            item_elapsed = round(time.time() - item_t0, 2)
            logger.warning(
                f"multi_ensemble [{idx}/{n_resources}] "
                f"{item.service}/{item.resource_id} FAILED in {item_elapsed}s: {e}"
            )
            forecasts.append(MultiEnsembleForecastResult(
                service=item.service,
                resource_id=item.resource_id,
                resource_name=resource_name,
                results=[],
                error=str(e),
            ))
            failed_count += 1

    total_elapsed = round(time.time() - t0, 2)
    logger.info(
        f"multi_ensemble_done in {total_elapsed}s — "
        f"{successful}/{n_resources} OK, {failed_count} failed"
    )

    return MultiEnsembleForecastResponse(
        total_resources=n_resources,
        successful=successful,
        failed=failed_count,
        forecasts=forecasts,
    )
