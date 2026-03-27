"""
Forecasting service: bridges DB metrics with BaselineForecaster.

Provides functions to:
  1. Load metric time-series from DB for any resource type + metric column
  2. Run forecast and return structured results
  3. Run backtest and return evaluation metrics
"""
import logging
from datetime import date
from typing import Optional, List, Dict

import pandas as pd
from sqlalchemy.orm import Session

from ..database import SessionLocal
from .. import models
from .baseline import BaselineConfig, BaselineForecaster, backtest_baseline

logger = logging.getLogger(__name__)


# ─── Metric column mappings per service ──────────────────────────

SERVICE_METRIC_MAP: dict[str, dict] = {
    "ec2": {
        "model": models.EC2Metric,
        "resource_model": models.EC2Resource,
        "resource_id_col": "ec2_resource_id",
        "resource_lookup": "instance_id",
        "metrics": ["network_out", "hours_running", "cpu_utilization"],
    },
    "rds": {
        "model": models.RDSMetric,
        "resource_model": models.RDSResource,
        "resource_id_col": "rds_resource_id",
        "resource_lookup": "db_identifier",
        "metrics": [
            "running_hours", "free_storage_space",
            "backup_retention_storage_gb", "snapshot_storage_gb",
            "data_transfer", "read_iops", "write_iops",
            "cpu_utilization", "database_connections",
            "freeable_memory", "swap_usage",
            "read_latency", "write_latency",
        ],
    },
    "lambda": {
        "model": models.LambdaMetric,
        "resource_model": models.LambdaResource,
        "resource_id_col": "lambda_resource_id",
        "resource_lookup": "function_name",
        "metrics": ["duration_avg", "duration_p95", "invocations", "errors"],
    },
    "s3": {
        "model": models.S3Metric,
        "resource_model": models.S3Resource,
        "resource_id_col": "s3_resource_id",
        "resource_lookup": "bucket_name",
        "metrics": ["bucket_size_bytes", "number_of_objects"],
    },
    "alb": {
        "model": models.ALBMetric,
        "resource_model": models.ALBResource,
        "resource_id_col": "alb_resource_id",
        "resource_lookup": "lb_name",
        "metrics": ["request_count", "processed_bytes", "new_conn_count", "response_time_p95", "http_5xx_count", "active_conn_count"],
    },
}


def get_available_metrics(service: str) -> list[str]:
    """Return list of forecastable metric columns for a service."""
    cfg = SERVICE_METRIC_MAP.get(service)
    if not cfg:
        raise ValueError(f"Unknown service: {service}. Available: {list(SERVICE_METRIC_MAP.keys())}")
    return cfg["metrics"]


def load_metric_series(
    db: Session,
    service: str,
    resource_id: int,
    metric_column: str,
    days_back: Optional[int] = None,
) -> pd.DataFrame:
    """
    Load a single metric column as a time series from DB.
    Returns DataFrame with columns: date, value
    """
    cfg = SERVICE_METRIC_MAP.get(service)
    if not cfg:
        raise ValueError(f"Unknown service: {service}")
    if metric_column not in cfg["metrics"]:
        raise ValueError(f"Invalid metric '{metric_column}' for {service}. Available: {cfg['metrics']}")

    metric_model = cfg["model"]
    resource_id_col = cfg["resource_id_col"]

    query = db.query(
        metric_model.metric_date,
        getattr(metric_model, metric_column),
    ).filter(getattr(metric_model, resource_id_col) == resource_id)

    if days_back:
        from datetime import date, timedelta
        start_date = date.today() - timedelta(days=days_back)
        query = query.filter(metric_model.metric_date >= start_date)

    rows = query.order_by(metric_model.metric_date).all()

    if not rows:
        return pd.DataFrame(columns=["date", "value"])

    df = pd.DataFrame(rows, columns=["date", "value"])
    df = df.dropna(subset=["value"])
    return df


def forecast_metric(
    db: Session,
    service: str,
    resource_id: int,
    metric_column: str,
    horizon: int = 30,
    method: str = "moving_average",
    window: int = 7,
    season_length: int = 7,
) -> dict:
    """
    Forecast future values for a specific metric.

    Returns:
        {
            "resource_id": int,
            "service": str,
            "metric": str,
            "method": str,
            "history": [{"date": ..., "value": ...}, ...],
            "forecast": [{"date": ..., "forecast": ...}, ...],
        }
    """
    df = load_metric_series(db, service, resource_id, metric_column)

    if df.empty:
        raise ValueError(f"No metric data found for {service} resource_id={resource_id}, metric={metric_column}")

    config = BaselineConfig(
        method=method,
        window=window,
        season_length=season_length,
        min_train_size=max(window, 3),
    )
    model = BaselineForecaster(config)
    forecast_df = model.forecast_future(df, horizon=horizon)

    return {
        "resource_id": resource_id,
        "service": service,
        "metric": metric_column,
        "method": method,
        "history": [
            {"date": str(row["date"]), "value": float(row["value"])}
            for _, row in df.iterrows()
        ],
        "forecast": [
            {"date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
             "forecast": round(float(row["forecast"]), 4)}
            for _, row in forecast_df.iterrows()
        ],
    }


def backtest_metric(
    db: Session,
    service: str,
    resource_id: int,
    metric_column: str,
    test_size: int = 7,
    method: str = "moving_average",
    window: int = 7,
    season_length: int = 7,
) -> dict:
    """
    Evaluate forecast accuracy on held-out data.

    Returns:
        {
            "metrics": {"n", "mae", "rmse", "mape"},
            "evaluation": [{"date", "actual", "prediction"}, ...],
        }
    """
    df = load_metric_series(db, service, resource_id, metric_column)

    if df.empty:
        raise ValueError(f"No metric data found for {service} resource_id={resource_id}, metric={metric_column}")

    config = BaselineConfig(
        method=method,
        window=window,
        season_length=season_length,
        min_train_size=max(window, 3),
    )

    eval_df, metrics = backtest_baseline(df, config, test_size=test_size)

    return {
        "resource_id": resource_id,
        "service": service,
        "metric": metric_column,
        "method": method,
        "test_size": test_size,
        "metrics": metrics,
        "evaluation": [
            {
                "date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
                "actual": round(float(row["actual"]), 4) if pd.notna(row["actual"]) else None,
                "prediction": round(float(row["prediction"]), 4) if pd.notna(row["prediction"]) else None,
            }
            for _, row in eval_df.iterrows()
        ],
    }


# ─── Persist forecast results to DB ──────────────────────────────

def save_forecast_run(
    db: Session,
    profile_id: int,
    service: str,
    resource_id: int,
    metric: str,
    method: str,
    params: dict,
    horizon: int,
    train_size: int,
    forecast_data: list[dict],
    backtest_metrics: dict | None = None,
) -> models.ForecastRun:
    """
    Save a forecast run and its values to the database.

    Args:
        forecast_data: list of {"date": str, "forecast": float}
        backtest_metrics: optional {"mae", "rmse", "mape"} from backtest
    """
    run = models.ForecastRun(
        profile_id=profile_id,
        service=service,
        resource_id=resource_id,
        metric=metric,
        method=method,
        params=params,
        horizon=horizon,
        train_size=train_size,
        mae=backtest_metrics.get("mae") if backtest_metrics else None,
        rmse=backtest_metrics.get("rmse") if backtest_metrics else None,
        mape=backtest_metrics.get("mape") if backtest_metrics else None,
    )
    db.add(run)
    db.flush()  # get run_id

    for item in forecast_data:
        val = models.ForecastValue(
            run_id=run.run_id,
            forecast_date=item["date"],
            forecast_value=item["forecast"],
        )
        db.add(val)

    db.commit()
    db.refresh(run)
    logger.info(f"Saved forecast run_id={run.run_id} ({service}/{metric}, {len(forecast_data)} values)")
    return run


def get_forecast_runs(
    db: Session,
    profile_id: int,
    service: str | None = None,
    resource_id: int | None = None,
) -> list[models.ForecastRun]:
    """Get forecast runs for a profile, optionally filtered by service/resource."""
    query = db.query(models.ForecastRun).filter_by(profile_id=profile_id)
    if service:
        query = query.filter_by(service=service)
    if resource_id:
        query = query.filter_by(resource_id=resource_id)
    return query.order_by(models.ForecastRun.created_at.desc()).all()


def get_forecast_run_by_id(db: Session, run_id: int) -> models.ForecastRun | None:
    """Get a single forecast run with its values."""
    return db.query(models.ForecastRun).filter_by(run_id=run_id).first()
