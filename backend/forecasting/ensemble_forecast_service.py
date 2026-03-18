"""
Ensemble Forecasting Service.

Replaces XGBoost-only approach with a 3-model ensemble:
  1. ETS  (Holt-Winters Exponential Smoothing)  — weight 0.50
  2. SARIMA (1,1,1)(1,1,1,7)                    — weight 0.30
  3. Ridge Regression (trend + calendar)        — weight 0.20

Designed for short history (~90 days) with daily data.
Maintains same input/output contract as xgboost_forecast_service.py
"""
import logging
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sqlalchemy.orm import Session
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .. import models
from .forecast_service import (
    get_available_metrics,
    load_metric_series,
    forecast_metric,
)

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────

FORECAST_RESULT_MODEL_MAP: dict[str, type] = {
    "ec2": models.EC2ForecastResult,
    "rds": models.RDSForecastResult,
    "lambda": models.LambdaForecastResult,
    "s3": models.S3ForecastResult,
    "alb": models.ALBForecastResult,
}

MIN_ROWS_FOR_ENSEMBLE = 21  # ต้องการอย่างน้อย 3 สัปดาห์ (weekly seasonality)

# Ensemble weights — รวมต้องเท่ากับ 1.0
ENSEMBLE_WEIGHTS = {
    "ets": 0.50,
    "sarima": 0.30,
    "ridge": 0.20,
}


# ─── Error Metrics ────────────────────────────────────────────────

def _calculate_error_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict:
    """Calculate MAE, RMSE, and MAPE."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)

    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

    mask = actual != 0
    mape = (
        float(
            np.mean(
                np.abs((actual[mask] - predicted[mask]) / actual[mask])
            )
        )
        * 100
        if np.any(mask)
        else 0.0
    )

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2),
    }


# ─── Individual Model Forecasters ────────────────────────────────

def _forecast_ets(values: np.ndarray, horizon: int) -> np.ndarray:
    """
    Holt-Winters Exponential Smoothing.

    - trend="add"      : จับ linear trend
    - seasonal="add"   : จับ weekly seasonality
    - damped_trend=True: ป้องกัน trend พุ่งเกินจริงใน long horizon
    - seasonal_periods=7: รายวัน → weekly cycle
    """
    try:
        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal="add",
            seasonal_periods=7,
            damped_trend=True,
            initialization_method="estimated",
        ).fit(optimized=True, remove_bias=True)
        result = model.forecast(horizon)
        # Clip ไม่ให้ติดลบ (resource usage ไม่ควรน้อยกว่า 0)
        return np.clip(result, 0, None)
    except Exception as e:
        logger.warning(f"ETS failed: {e}, using mean fallback")
        return np.full(horizon, float(np.mean(values)))


def _forecast_sarima(values: np.ndarray, horizon: int) -> np.ndarray:
    """
    SARIMA(1,1,1)(1,1,1,7)

    - (1,1,1)   : AR(1), differencing, MA(1) — จับ short-term pattern
    - (1,1,1,7) : seasonal AR/MA + weekly differencing
    - ต้องการข้อมูลอย่างน้อย 2 * seasonal_periods = 14 วัน
    """
    try:
        model = SARIMAX(
            values,
            order=(1, 1, 1),
            seasonal_order=(1, 1, 1, 7),
            enforce_stationarity=False,
            enforce_invertibility=False,
            trend="n",
        ).fit(disp=False, maxiter=200)
        result = model.forecast(horizon)
        return np.clip(result, 0, None)
    except Exception as e:
        logger.warning(f"SARIMA failed: {e}, using mean fallback")
        return np.full(horizon, float(np.mean(values)))


def _make_calendar_features(
    indices: np.ndarray,
    dates: list,
) -> np.ndarray:
    """
    สร้าง feature matrix สำหรับ Ridge:
    [linear_trend, dow_sin, dow_cos, month_sin, month_cos, is_weekend]
    """
    t = np.array(indices, dtype=float)
    dow = np.array([d.weekday() for d in dates], dtype=float)
    month = np.array(
        [d.month if hasattr(d, "month") else pd.Timestamp(d).month for d in dates],
        dtype=float,
    )
    return np.column_stack([
        t,
        np.sin(2 * np.pi * dow / 7),
        np.cos(2 * np.pi * dow / 7),
        np.sin(2 * np.pi * month / 12),
        np.cos(2 * np.pi * month / 12),
        (dow >= 5).astype(float),  # is_weekend
    ])


def _forecast_ridge(
    values: np.ndarray,
    horizon: int,
    last_date: pd.Timestamp,
) -> np.ndarray:
    """
    Ridge Regression ด้วย linear trend + cyclic calendar features.

    - Stable มากกับข้อมูลน้อย
    - ไม่ iterative → ไม่มี error propagation
    - alpha=10.0 regularization แรงขึ้นเพื่อ prevent overfit
    """
    try:
        n = len(values)
        train_dates = [
            last_date - pd.Timedelta(days=n - 1 - i) for i in range(n)
        ]
        future_dates = [
            last_date + pd.Timedelta(days=i + 1) for i in range(horizon)
        ]

        X_train = _make_calendar_features(np.arange(n), train_dates)
        X_future = _make_calendar_features(
            np.arange(n, n + horizon), future_dates
        )

        model = Ridge(alpha=10.0)
        model.fit(X_train, values)
        result = model.predict(X_future)
        return np.clip(result, 0, None)
    except Exception as e:
        logger.warning(f"Ridge failed: {e}, using mean fallback")
        return np.full(horizon, float(np.mean(values)))


# ─── Ensemble Combiner ───────────────────────────────────────────

def _ensemble_forecast(
    values: np.ndarray,
    horizon: int,
    last_date: pd.Timestamp,
) -> dict[str, np.ndarray]:
    """
    รัน 3 models แล้ว weighted average

    Returns dict ที่มี key:
        "ensemble", "ets", "sarima", "ridge"
    """
    forecasts = {
        "ets": _forecast_ets(values, horizon),
        "sarima": _forecast_sarima(values, horizon),
        "ridge": _forecast_ridge(values, horizon, last_date),
    }

    ensemble = sum(
        forecasts[name] * weight
        for name, weight in ENSEMBLE_WEIGHTS.items()
    )
    forecasts["ensemble"] = np.clip(ensemble, 0, None)
    return forecasts


# ─── Backtest ────────────────────────────────────────────────────

def _ensemble_backtest(
    all_df: pd.DataFrame,
    test_size: int = 14,
) -> dict:
    """
    Backtest โดย train บน history ก่อน test_size วัน
    แล้ว forecast เทียบกับ actual

    ไม่ใช้ iterative approach → ไม่มี error propagation
    """
    if len(all_df) < test_size + MIN_ROWS_FOR_ENSEMBLE:
        logger.warning("Not enough data for backtest")
        return {}

    train_df = all_df.iloc[:-test_size]
    test_df = all_df.iloc[-test_size:]

    train_values = train_df["value"].to_numpy(dtype=float)
    actual_values = test_df["value"].to_numpy(dtype=float)
    test_dates = pd.to_datetime(test_df["date"]).tolist()

    last_train_date = pd.to_datetime(train_df["date"]).max()

    forecasts = _ensemble_forecast(train_values, test_size, last_train_date)
    predicted_values = forecasts["ensemble"]

    metrics = _calculate_error_metrics(actual_values, predicted_values)
    metrics["training_rows"] = len(train_df)
    metrics["test_rows"] = test_size
    metrics["backtest_dates"] = test_dates
    metrics["backtest_actuals"] = actual_values.tolist()
    metrics["backtest_preds"] = [round(float(p), 4) for p in predicted_values]

    logger.info(
        f"Backtest — MAE: {metrics['mae']}, "
        f"RMSE: {metrics['rmse']}, "
        f"MAPE: {metrics['mape']}%"
    )
    return metrics


# ─── Main Forecast Function ──────────────────────────────────────

def ensemble_forecast_metric(
    db: Session,
    service: str,
    resource_id: int,
    metric_column: str,
    horizon: int = 30,
) -> dict:
    """
    Forecast future values ด้วย Ensemble (ETS + SARIMA + Ridge).

    Drop-in replacement ของ xgboost_forecast_metric()
    — input/output contract เหมือนกันทุกอย่าง

    Returns:
        {
            "metric": str,
            "method": "ensemble",
            "forecast_dates": [date, ...],
            "forecast_values": [float, ...],
            "forecast_by_model": {
                "ets": [...], "sarima": [...], "ridge": [...]
            },
            "backtest_dates": [...] | None,
            "backtest_actuals": [...] | None,
            "backtest_preds": [...] | None,
            "performance_metrics": {...} | None,
        }

    Raises:
        ValueError: ถ้า data น้อยกว่า MIN_ROWS_FOR_ENSEMBLE
    """
    df = load_metric_series(db, service, resource_id, metric_column)

    if len(df) < MIN_ROWS_FOR_ENSEMBLE:
        raise ValueError(
            f"Need at least {MIN_ROWS_FOR_ENSEMBLE} data points for Ensemble, "
            f"got {len(df)} for {service}/{metric_column}"
        )

    # 1. Backtest
    performance_metrics = _ensemble_backtest(df, test_size=14)

    # 2. Forecast บน full history
    values = df["value"].to_numpy(dtype=float)
    last_date = pd.to_datetime(df["date"]).max()

    forecasts = _ensemble_forecast(values, horizon, last_date)

    forecast_dates = [
        (last_date + pd.Timedelta(days=i + 1)).date()
        for i in range(horizon)
    ]

    return {
        "metric": metric_column,
        "method": "ensemble",
        "forecast_dates": forecast_dates,
        "forecast_values": [
            round(float(v), 4) for v in forecasts["ensemble"]
        ],
        # per-model breakdown — ใช้ debug หรือแสดง confidence range ได้
        "forecast_by_model": {
            "ets": [round(float(v), 4) for v in forecasts["ets"]],
            "sarima": [round(float(v), 4) for v in forecasts["sarima"]],
            "ridge": [round(float(v), 4) for v in forecasts["ridge"]],
        },
        "backtest_dates": (
            performance_metrics.get("backtest_dates")
            if performance_metrics else None
        ),
        "backtest_actuals": (
            performance_metrics.get("backtest_actuals")
            if performance_metrics else None
        ),
        "backtest_preds": (
            performance_metrics.get("backtest_preds")
            if performance_metrics else None
        ),
        "performance_metrics": performance_metrics or None,
    }


# ─── Persist ─────────────────────────────────────────────────────

def save_ensemble_forecast(
    db: Session,
    service: str,
    resource_id: int,
    metric: str,
    method: str,
    forecast_dates: list,
    forecast_values: list[float],
    backtest_data: dict | None = None,
):
    """
    Save forecast to per-service result table.
    Interface เหมือน save_xgboost_forecast() ทุกอย่าง
    """
    result_model = FORECAST_RESULT_MODEL_MAP.get(service)
    if not result_model:
        raise ValueError(f"No forecast result table for service: {service}")

    params = {
        "resource_id": resource_id,
        "metric": metric,
        "method": method,
        "forecast_dates": [
            str(d) for d in forecast_dates
        ],
        "forecast_values": forecast_values,
    }
    if backtest_data:
        params.update({
            "backtest_dates": [
                str(d) for d in (backtest_data.get("backtest_dates") or [])
            ],
            "backtest_actuals": backtest_data.get("backtest_actuals"),
            "backtest_preds": backtest_data.get("backtest_preds"),
            "mae": backtest_data.get("mae"),
            "rmse": backtest_data.get("rmse"),
            "mape": backtest_data.get("mape"),
        })

    row = result_model(**params)
    db.add(row)
    db.commit()
    db.refresh(row)
    logger.info(
        f"Saved {method} forecast — {service}/{metric} "
        f"resource_id={resource_id} "
        f"({len(forecast_dates)} values, id={row.id})"
    )
    return row


# ─── Orchestrator ────────────────────────────────────────────────

def run_ensemble_forecast(
    db: Session,
    service: str,
    resource_id: int,
    metric: Optional[str],
    horizon: int = 30,
) -> dict:
    """
    Orchestrator — Drop-in replacement ของ run_xgboost_forecast()

    Priority:
        1. Ensemble (ETS + SARIMA + Ridge)
        2. Baseline moving average (fallback)
        3. Empty result (ถ้า fallback ก็ยังล้มเหลว)

    Returns:
        {
            "service": str,
            "resource_id": int,
            "results": [
                {
                    "metric": str,
                    "method": str,
                    "forecast_dates": [...],
                    "forecast_values": [...],
                    "fallback": bool,
                }
            ]
        }
    """
    if metric:
        available = get_available_metrics(service)
        if metric not in available:
            raise ValueError(
                f"Invalid metric '{metric}' for {service}. "
                f"Available: {available}"
            )
        metrics_to_run = [metric]
    else:
        metrics_to_run = get_available_metrics(service)

    results = []

    for m in metrics_to_run:
        # ── 1. Try Ensemble ───────────────────────────────────────
        try:
            forecast = ensemble_forecast_metric(
                db=db,
                service=service,
                resource_id=resource_id,
                metric_column=m,
                horizon=horizon,
            )
            forecast["fallback"] = False

            save_ensemble_forecast(
                db=db,
                service=service,
                resource_id=resource_id,
                metric=m,
                method="ensemble",
                forecast_dates=forecast["forecast_dates"],
                forecast_values=forecast["forecast_values"],
                backtest_data=forecast.get("performance_metrics"),
            )

            results.append(forecast)
            logger.info(
                f"Ensemble OK — {service}/{m} "
                f"MAPE={forecast['performance_metrics'].get('mape', 'N/A')}%"
                if forecast.get("performance_metrics")
                else f"Ensemble OK — {service}/{m}"
            )

        # ── 2. Fallback: moving average ───────────────────────────
        except Exception as ens_err:
            logger.warning(
                f"Ensemble failed for {service}/{m} "
                f"resource_id={resource_id}: {ens_err}. "
                f"Falling back to moving average."
            )
            try:
                fallback_result = forecast_metric(
                    db=db,
                    service=service,
                    resource_id=resource_id,
                    metric_column=m,
                    horizon=horizon,
                    method="moving_average",
                    window=7,
                    season_length=7,
                )
                fallback = {
                    "metric": m,
                    "method": "moving_average",
                    "forecast_dates": [
                        item["date"] for item in fallback_result["forecast"]
                    ],
                    "forecast_values": [
                        item["forecast"] for item in fallback_result["forecast"]
                    ],
                    "fallback": True,
                }

                save_ensemble_forecast(
                    db=db,
                    service=service,
                    resource_id=resource_id,
                    metric=m,
                    method="moving_average",
                    forecast_dates=fallback["forecast_dates"],
                    forecast_values=fallback["forecast_values"],
                )

                results.append(fallback)

        # ── 3. Both failed ────────────────────────────────────────
            except Exception as base_err:
                logger.error(
                    f"All methods failed for {service}/{m} "
                    f"resource_id={resource_id}: {base_err}"
                )
                results.append({
                    "metric": m,
                    "method": "none",
                    "forecast_dates": [],
                    "forecast_values": [],
                    "fallback": True,
                    "error": str(base_err),
                })

    return {
        "service": service,
        "resource_id": resource_id,
        "results": results,
    }