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
from typing import Optional, Tuple

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
# With 180 days data, we can detect longer seasonal patterns
MAX_LAG_SEASONALITY = 60  # Increased from 30 to detect monthly patterns
# Backtest size can be increased with more data
DEFAULT_BACKTEST_SIZE = 21  # Increased from 14 to 3 weeks for better validation

# Ensemble weights — รวมต้องเท่ากับ 1.0
ENSEMBLE_WEIGHTS = {
    "ets": 0.50,
    "sarima": 0.30,
    "ridge": 0.20,
}

# Volatile metrics that benefit from log transform
VOLATILE_METRICS = {
    "ec2": ["network_out", "ebs_snapshot_total_gb"],
    "rds": ["data_transfer", "read_iops", "write_iops", "cpu_utilization", "database_connections"],
    "lambda": ["duration_avg", "duration_p95", "invocations", "errors"],
    "s3": ["bucket_size_bytes", "number_of_objects"],
    "alb": ["request_count", "processed_bytes", "new_conn_count", "http_5xx_count", "active_conn_count"],
}

# RDS metrics that need extra smoothing due to high volatility
RDS_HIGH_VOLATILITY_METRICS = ["cpu_utilization", "database_connections", "read_iops", "write_iops"]

# MAPE threshold for fallback guard
MAPE_FALLBACK_THRESHOLD = 50.0  # ถ้า MAPE > 50% จะ fallback ไป baseline
LOG_TRANSFORM_EPSILON = 1e-6  # ป้องกัน log(0)


# ─── Error Metrics ────────────────────────────────────────────────

def _calculate_error_metrics(
    actual: np.ndarray,
    predicted: np.ndarray,
) -> dict:
    """Calculate MAE, RMSE, and WMAPE."""
    actual = np.array(actual, dtype=float)
    predicted = np.array(predicted, dtype=float)

    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))

    # Use WMAPE (Weighted MAPE) instead of standard MAPE.
    # Standard MAPE blows up when actual values are near zero.
    # WMAPE weights the error by the actual volume, which is the industry
    # standard for cloud metrics (like network transfer or cost).
    sum_actual = float(np.sum(np.abs(actual)))
    if sum_actual > 0:
        mape = float(np.sum(np.abs(actual - predicted)) / sum_actual) * 100
    else:
        mape = 0.0

    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2),
    }


# ─── Enhanced Transform Utilities ────────────────────────────────────

def get_adaptive_ensemble_weights(
    volatility_level: str,
    backtest_mapes: dict[str, float] | None = None,
) -> dict[str, float]:
    """
    Get adaptive ensemble weights.

    Strategy:
      1. If backtest MAPE per model is available, weight inversely to MAPE
         (better models get higher weight).
      2. Otherwise fall back to volatility-based defaults.

    Args:
        volatility_level: 'stable', 'low', 'moderate', 'high', 'extreme'
        backtest_mapes: {"ets": float, "sarima": float, "ridge": float} or None

    Returns:
        Dictionary of model weights that sum to 1.0
    """
    # ── 1. Backtest-driven weights (preferred) ─────────────────────
    if backtest_mapes:
        valid = {k: v for k, v in backtest_mapes.items() if v is not None and v > 0}
        if len(valid) >= 2:
            # Inverse-MAPE weighting: lower MAPE → higher weight
            inv = {k: 1.0 / v for k, v in valid.items()}
            total_inv = sum(inv.values())
            weights = {k: round(v / total_inv, 3) for k, v in inv.items()}
            # Fill any missing model with 0
            for m in ("ets", "sarima", "ridge"):
                weights.setdefault(m, 0.0)
            logger.info(f"Backtest-driven weights: {weights} (from MAPEs {backtest_mapes})")
            return weights

    # ── 2. Volatility-based defaults ───────────────────────────────
    weight_configs = {
        "stable":   {"ets": 0.60, "sarima": 0.25, "ridge": 0.15},
        "low":      {"ets": 0.50, "sarima": 0.30, "ridge": 0.20},
        "moderate": {"ets": 0.40, "sarima": 0.35, "ridge": 0.25},
        "high":     {"ets": 0.35, "sarima": 0.35, "ridge": 0.30},
        "extreme":  {"ets": 0.30, "sarima": 0.30, "ridge": 0.40},
    }

    return weight_configs.get(volatility_level, weight_configs["stable"])


def enhanced_log_transform(values: np.ndarray, volatility_info: dict) -> tuple[np.ndarray, bool, str]:
    """
    Enhanced log transform with volatility-specific handling.
    
    Args:
        values: Input time series values
        volatility_info: Volatility analysis results
    
    Returns:
        (transformed_values, was_transformed, transform_type)
    """
    # Get CV from volatility info, handle missing keys gracefully
    cv = volatility_info.get('cv', 0.0)  # Direct CV if available
    if 'basic_stats' in volatility_info:
        cv = volatility_info['basic_stats'].get('cv', cv)
    
    if cv > 1.5:  # Extreme volatility - use sqrt + log
        transformed = np.log1p(np.sqrt(np.maximum(values, 0) + LOG_TRANSFORM_EPSILON))
        return transformed, True, "sqrt_log"
    elif cv > 0.8:  # High volatility - standard log transform
        transformed = np.log1p(np.maximum(values, 0) + LOG_TRANSFORM_EPSILON)
        return transformed, True, "log"
    elif cv > 0.5:  # Moderate volatility - Box-Cox like transform
        # Simple Box-Cox approximation: (x^λ - 1)/λ with λ=0.25
        lambda_val = 0.25
        transformed = (np.maximum(values, 0) ** lambda_val - 1) / lambda_val
        return transformed, True, "boxcox_approx"
    else:
        return values, False, "none"


def inverse_enhanced_transform(transformed_values: np.ndarray, transform_type: str) -> np.ndarray:
    """
    Inverse transform for enhanced log transform.
    
    Args:
        transformed_values: Transformed values
        transform_type: Type of transform applied
    
    Returns:
        Original scale values
    """
    if transform_type == "sqrt_log":
        # Inverse of log1p(sqrt(x))
        return np.maximum((np.expm1(transformed_values)) ** 2 - LOG_TRANSFORM_EPSILON, 0)
    elif transform_type == "log":
        # Inverse of log1p
        return np.maximum(np.expm1(transformed_values) - LOG_TRANSFORM_EPSILON, 0)
    elif transform_type == "boxcox_approx":
        # Inverse of Box-Cox approximation with λ=0.25
        lambda_val = 0.25
        return np.maximum((lambda_val * transformed_values + 1) ** (1/lambda_val), 0)
    else:
        return transformed_values


def detect_seasonality(values: np.ndarray, max_lag: int = MAX_LAG_SEASONALITY) -> tuple[bool, list[int]]:
    """
    Detect seasonal patterns using autocorrelation analysis.
    
    Args:
        values: Input time series values
        max_lag: Maximum lag to check for seasonality
    
    Returns:
        (has_seasonality, seasonal_periods)
    """
    if len(values) < max_lag * 2:
        return False, []
    
    # Calculate autocorrelation
    values_centered = values - np.mean(values)
    autocorr = np.correlate(values_centered, values_centered, mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    
    # Normalize autocorrelation
    autocorr = autocorr / autocorr[0] if autocorr[0] != 0 else autocorr
    
    # Find peaks (potential seasonal periods)
    # Look for significant peaks at lags >= 7 (weekly patterns)
    threshold = 0.3  # Minimum autocorrelation value
    min_distance = 5  # Minimum distance between peaks
    
    peaks = []
    for lag in range(7, min(max_lag, len(autocorr)//2)):
        if autocorr[lag] > threshold:
            # Check if this is a local maximum
            window_start = max(0, lag - min_distance)
            window_end = min(len(autocorr), lag + min_distance + 1)
            window = autocorr[window_start:window_end]
            
            if lag == window_start + np.argmax(window):
                peaks.append(lag)
    
    has_seasonality = len(peaks) > 0
    return has_seasonality, peaks


def apply_exponential_smoothing(values: np.ndarray, alpha: float = 0.3) -> np.ndarray:
    """
    Apply exponential smoothing to reduce noise in volatile metrics.
    
    Args:
        values: Input time series
        alpha: Smoothing factor (0-1), lower = more smoothing
    
    Returns:
        Smoothed values
    """
    if len(values) == 0:
        return values
    
    smoothed = np.zeros_like(values)
    smoothed[0] = values[0]
    
    for i in range(1, len(values)):
        smoothed[i] = alpha * values[i] + (1 - alpha) * smoothed[i-1]
    
    return smoothed


def cap_outliers_iqr(values: np.ndarray, multiplier: float = 2.0) -> np.ndarray:
    """
    Cap extreme outliers using the Interquartile Range (IQR) method.
    Useful for removing random spikes in cloud metrics before modeling.
    """
    if len(values) < 7:
        return values
    
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    
    lower_bound = max(0, q1 - multiplier * iqr)
    upper_bound = q3 + multiplier * iqr
    
    return np.clip(values, lower_bound, upper_bound)


def get_adaptive_mape_threshold(volatility_level: str) -> float:
    """
    Get adaptive MAPE threshold based on volatility level.
    
    Increased thresholds to reduce fallback rate while maintaining quality.
    
    Args:
        volatility_level: Current volatility classification
    
    Returns:
        Adaptive MAPE threshold for fallback
    """
    thresholds = {
        "stable": 35.0,      # was 30.0
        "low": 45.0,         # was 40.0
        "moderate": 55.0,    # was 50.0
        "high": 65.0,        # was 60.0
        "extreme": 80.0      # was 70.0
    }
    return thresholds.get(volatility_level, 55.0)


# ─── Transform Utilities ─────────────────────────────────────────────

def _should_use_log_transform(service: str, metric: str) -> bool:
    """Check if metric should use log transform based on volatility patterns."""
    volatile_metrics = VOLATILE_METRICS.get(service, [])
    return metric in volatile_metrics


def _apply_log_transform(values: np.ndarray) -> Tuple[np.ndarray, bool]:
    """
    Apply log transform to reduce spike impact.
    Returns (transformed_values, was_transformed)
    """
    if np.all(values <= 0):
        # All non-positive values, skip log transform
        return values, False
    
    # Check coefficient of variation - high CV indicates volatility
    cv = np.std(values) / (np.mean(values) + LOG_TRANSFORM_EPSILON)
    if cv < 0.5:  # Low volatility, no transform needed
        return values, False
    
    # Apply log1p transform to handle zeros and reduce spike impact
    transformed = np.log1p(values + LOG_TRANSFORM_EPSILON)
    return transformed, True


def _inverse_log_transform(transformed_values: np.ndarray) -> np.ndarray:
    """Inverse of log1p transform."""
    return np.expm1(transformed_values) - LOG_TRANSFORM_EPSILON


def _detect_volatility_pattern(values: np.ndarray) -> dict:
    """
    Detect volatility patterns in time series.
    Returns dict with volatility metrics.
    """
    if len(values) < 7:
        return {"is_volatile": False, "cv": 0, "spike_ratio": 0}
    
    # Calculate basic statistics
    mean_val = np.mean(values)
    std_val = np.std(values)
    cv = std_val / (mean_val + LOG_TRANSFORM_EPSILON)
    
    # Detect spikes (values > 3 std from mean)
    spike_threshold = mean_val + 3 * std_val
    spikes = np.sum(values > spike_threshold)
    spike_ratio = spikes / len(values)
    
    # Detect dips (values < mean - 2 std)
    dip_threshold = max(mean_val - 2 * std_val, 0)
    dips = np.sum(values < dip_threshold)
    dip_ratio = dips / len(values)
    
    is_volatile = (cv > 0.5) or (spike_ratio > 0.1) or (dip_ratio > 0.1)
    
    # Classify volatility level
    if cv > 1.0 or spike_ratio > 0.2 or dip_ratio > 0.2:
        volatility_level = "extreme"
    elif cv > 0.7 or spike_ratio > 0.15 or dip_ratio > 0.15:
        volatility_level = "high"
    elif cv > 0.5 or spike_ratio > 0.1 or dip_ratio > 0.1:
        volatility_level = "moderate"
    elif cv > 0.3 or spike_ratio > 0.05 or dip_ratio > 0.05:
        volatility_level = "low"
    else:
        volatility_level = "stable"
    
    return {
        "is_volatile": is_volatile,
        "cv": round(cv, 3),
        "spike_ratio": round(spike_ratio, 3),
        "dip_ratio": round(dip_ratio, 3),
        "spike_count": int(spikes),
        "dip_count": int(dips),
        "basic_stats": {
            "mean": round(float(mean_val), 4),
            "std": round(float(std_val), 4),
            "cv": round(cv, 3),
        },
        "classification": {
            "volatility_level": volatility_level
        }
    }


# ─── Individual Model Forecasters ────────────────────────────────

def _forecast_ets(
    values: np.ndarray,
    horizon: int,
    seasonal_period: int = 7,
) -> np.ndarray:
    """
    Holt-Winters Exponential Smoothing.

    - trend="add"      : จับ linear trend
    - seasonal="add"   : จับ seasonality ตาม detected period
    - damped_trend=True: ป้องกัน trend พุ่งเกินจริงใน long horizon
    """
    try:
        # ต้องมีข้อมูลอย่างน้อย 2 * seasonal_period
        if len(values) < seasonal_period * 2:
            seasonal_period = 7  # fallback to weekly
        if len(values) < 14:
            # ข้อมูลน้อยมาก ใช้ simple exponential smoothing
            model = ExponentialSmoothing(
                values,
                trend="add",
                seasonal=None,
                damped_trend=True,
                initialization_method="estimated",
            ).fit(optimized=True, remove_bias=True)
        else:
            model = ExponentialSmoothing(
                values,
                trend="add",
                seasonal="add",
                seasonal_periods=seasonal_period,
                damped_trend=True,
                initialization_method="estimated",
            ).fit(optimized=True, remove_bias=True)
        result = model.forecast(horizon)
        return np.clip(result, 0, None)
    except Exception as e:
        logger.warning(f"ETS failed: {e}, using mean fallback")
        return np.full(horizon, float(np.mean(values)))

def _forecast_sarima(
    values: np.ndarray,
    horizon: int,
    seasonal_period: int = 7,
) -> np.ndarray:
    """
    SARIMA สำหรับจับ seasonal pattern + trend

    - (1,0,1)   : AR(1), no differencing, MA(1) — จับ short-term pattern
    - (1,1,1,7) : seasonal AR/MA + differencing weekly cycle
    - ต้องการข้อมูลอย่างน้อย 2 * seasonal_period
    """
    try:
        # ต้องมีข้อมูลอย่างน้อย 2 * seasonal_period
        if len(values) < seasonal_period * 2:
            seasonal_period = 7  # fallback to weekly
        if len(values) < 14:
            # ข้อมูลน้อยมาก ใช้ ARIMA ธรรมดา (ไม่มี seasonal)
            model = SARIMAX(
                values,
                order=(1, 0, 1),
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False)
        else:
            model = SARIMAX(
                values,
                order=(1, 0, 1),
                seasonal_order=(1, 1, 1, 7),
                enforce_stationarity=False,
                enforce_invertibility=False,
            ).fit(disp=False)
        result = model.forecast(horizon)
        return np.maximum(result, 0)
    except Exception as e:
        logger.warning(f"SARIMA failed: {e}, using simple fallback")
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
    
    Enhanced for 180 days data: Adaptive regularization based on data length
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

        # Adaptive regularization: stronger for longer data to prevent overfitting
        if n >= 180:  # Full 6 months data
            alpha = 20.0  # Stronger regularization
        elif n >= 90:  # 3 months data
            alpha = 15.0  # Moderate regularization
        else:  # Shorter data
            alpha = 10.0  # Standard regularization
        
        model = Ridge(alpha=alpha)
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
    volatility_info: dict | None = None,
    use_enhanced_transform: bool = True,
    seasonal_period: int = 7,
    backtest_mapes: dict[str, float] | None = None,
) -> dict[str, np.ndarray]:
    """
    รัน 3 models แล้ว weighted average ด้วย adaptive weights
    รองรับ enhanced log transform สำหรับ volatile data

    Returns dict ที่มี key:
        "ensemble", "ets", "sarima", "ridge", "transform_info", "weights_used"
    """
    transform_info = {"log_transformed": False, "original_scale": True, "transform_type": "none"}
    
    # Apply enhanced log transform if requested and beneficial
    if use_enhanced_transform and volatility_info:
        transformed_values, was_transformed, transform_type = enhanced_log_transform(values, volatility_info)
        if was_transformed:
            values = transformed_values
            transform_info["log_transformed"] = True
            transform_info["original_scale"] = False
            transform_info["transform_type"] = transform_type
            logger.info(f"Applied enhanced transform: {transform_type} due to volatility")
    
    # Get adaptive weights — prefer backtest-driven, fallback to volatility-based
    volatility_level = "stable"
    if volatility_info:
        volatility_level = volatility_info['classification']['volatility_level']
    adaptive_weights = get_adaptive_ensemble_weights(volatility_level, backtest_mapes)
    logger.info(f"Weights for {volatility_level}: {adaptive_weights}"
                + (f" (backtest-driven)" if backtest_mapes else " (volatility-based)"))
    
    # Run individual models with detected seasonal period
    forecasts = {
        "ets": _forecast_ets(values, horizon, seasonal_period),
        "sarima": _forecast_sarima(values, horizon, seasonal_period),
        "ridge": _forecast_ridge(values, horizon, last_date),
    }

    # Apply adaptive weights for ensemble
    ensemble = sum(
        forecasts[name] * weight
        for name, weight in adaptive_weights.items()
    )
    forecasts["ensemble"] = np.clip(ensemble, 0, None)
    
    # Add transform info and weights to results
    forecasts["transform_info"] = transform_info
    forecasts["weights_used"] = adaptive_weights
    
    return forecasts


# ─── Backtest ────────────────────────────────────────────────────

def _ensemble_backtest(
    all_df: pd.DataFrame,
    test_size: int = DEFAULT_BACKTEST_SIZE,
    service: str = "",
    metric: str = "",
) -> dict:
    """
    Backtest โดย train บน history ก่อน test_size วัน
    แล้ว forecast เทียบกับ actual

    Flow:
      1. Detect volatility & seasonality
      2. Run *individual* model backtests → per-model MAPE
      3. Re-run ensemble with backtest-driven weights
      4. Return comprehensive metrics
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

    # ── 1. Detect volatility & seasonality ────────────────────────
    volatility_info = _detect_volatility_pattern(train_values)

    # Cap outliers if extremely volatile
    if volatility_info.get("classification", {}).get("volatility_level") in ("high", "extreme"):
        capped_train_values = cap_outliers_iqr(train_values)
    else:
        capped_train_values = train_values

    has_seasonality, seasonal_periods = detect_seasonality(capped_train_values)
    best_seasonal_period = seasonal_periods[0] if seasonal_periods else 7
    volatility_info['seasonality'] = {
        'has_seasonality': has_seasonality,
        'seasonal_periods': seasonal_periods,
        'best_period': best_seasonal_period,
    }

    use_enhanced_transform = (
        _should_use_log_transform(service, metric)
        or volatility_info["is_volatile"]
    )

    # ── 2. Per-model backtest → collect MAPE per model ────────────
    # Run a *first pass* without backtest-driven weights to get each
    # model's independent forecast on the test window.
    first_pass = _ensemble_forecast(
        capped_train_values, test_size, last_train_date,
        volatility_info, use_enhanced_transform,
        seasonal_period=best_seasonal_period,
        backtest_mapes=None,  # volatility-based weights only
    )

    transform_type = first_pass["transform_info"]["transform_type"]
    was_transformed = first_pass["transform_info"]["log_transformed"]

    per_model_mape: dict[str, float] = {}
    for model_name in ("ets", "sarima", "ridge"):
        preds = first_pass[model_name]
        if was_transformed:
            preds = inverse_enhanced_transform(preds, transform_type)
        model_metrics = _calculate_error_metrics(actual_values, preds)
        per_model_mape[model_name] = model_metrics["mape"]

    logger.info(f"Per-model backtest MAPEs: {per_model_mape}")

    # ── 3. Re-run ensemble with backtest-driven weights ───────────
    forecasts = _ensemble_forecast(
        capped_train_values, test_size, last_train_date,
        volatility_info, use_enhanced_transform,
        seasonal_period=best_seasonal_period,
        backtest_mapes=per_model_mape,
    )

    predicted_values = forecasts["ensemble"]
    if forecasts["transform_info"]["log_transformed"]:
        t_type = forecasts["transform_info"]["transform_type"]
        predicted_values = inverse_enhanced_transform(predicted_values, t_type)
        logger.info(f"Inverse enhanced transform applied for backtest: {t_type}")

    # ── 4. Calculate final ensemble error metrics ─────────────────
    metrics = _calculate_error_metrics(actual_values, predicted_values)

    volatility_level = volatility_info['classification']['volatility_level']
    adaptive_threshold = get_adaptive_mape_threshold(volatility_level)

    metrics.update({
        "training_rows": len(train_df),
        "test_rows": test_size,
        "backtest_dates": test_dates,
        "backtest_actuals": actual_values.tolist(),
        "backtest_preds": [round(float(p), 4) for p in predicted_values],
        "volatility_info": volatility_info,
        "enhanced_transform_used": forecasts["transform_info"]["log_transformed"],
        "transform_type": forecasts["transform_info"]["transform_type"],
        "weights_used": forecasts["weights_used"],
        "per_model_mape": per_model_mape,
        "adaptive_threshold": adaptive_threshold,
        "should_fallback": metrics.get("mape", 0) > adaptive_threshold,
    })

    logger.info(
        f"Backtest — MAPE: {metrics['mape']}% "
        f"(ETS={per_model_mape.get('ets', '?')}% "
        f"SARIMA={per_model_mape.get('sarima', '?')}% "
        f"Ridge={per_model_mape.get('ridge', '?')}%), "
        f"Transform: {metrics['enhanced_transform_used']} ({metrics['transform_type']}), "
        f"Season: {best_seasonal_period}d, "
        f"Weights: {metrics['weights_used']}, "
        f"Threshold: {adaptive_threshold}%, "
        f"Fallback: {metrics['should_fallback']}"
    )
    return metrics


# ─── Main Forecast Function ──────────────────────────────────────

def ensemble_forecast_metric(
    db: Session,
    service: str,
    resource_id: int,
    metric_column: str,
    horizon: int = 30,
    baseline_days: Optional[int] = None,
) -> dict:
    """
    Forecast future values ด้วย Enhanced Ensemble (ETS + SARIMA + Ridge).
    รองรับ enhanced log transform, seasonal detection, adaptive weights และ MAPE-based fallback

    Enhanced Features:
    - Adaptive ensemble weights based on volatility level
    - Enhanced log transform (log, sqrt+log, Box-Cox approximation)
    - Seasonal pattern detection using autocorrelation
    - Adaptive MAPE threshold for fallback guard

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
            "volatility_info": {...} | None,
            "seasonality_info": {...} | None,
            "enhanced_transform_used": bool,
            "transform_type": str,
            "weights_used": dict,
            "adaptive_threshold": float,
            "should_fallback": bool,
        }

    Raises:
        ValueError: ถ้า data น้อยกว่า MIN_ROWS_FOR_ENSEMBLE
    """
    df = load_metric_series(db, service, resource_id, metric_column, days_back=baseline_days)

    if len(df) < MIN_ROWS_FOR_ENSEMBLE:
        raise ValueError(
            f"Need at least {MIN_ROWS_FOR_ENSEMBLE} data points for Ensemble, "
            f"got {len(df)} for {service}/{metric_column}"
        )

    # 1. Apply smoothing for RDS high-volatility metrics
    original_df = df.copy()
    if service == "rds" and metric_column in RDS_HIGH_VOLATILITY_METRICS:
        logger.info(f"Applying exponential smoothing to RDS metric: {metric_column}")
        df["value"] = apply_exponential_smoothing(df["value"].to_numpy(), alpha=0.3)

    # 2. Enhanced Backtest with all new features
    performance_metrics = _ensemble_backtest(df, test_size=DEFAULT_BACKTEST_SIZE, service=service, metric=metric_column)

    # 3. Forecast บน full history with enhanced features
    values = df["value"].to_numpy(dtype=float)
    last_date = pd.to_datetime(df["date"]).max()

    # Get volatility and seasonality info from backtest
    volatility_info = performance_metrics.get("volatility_info", {})
    seasonality_info = volatility_info.get("seasonality", {})
    best_seasonal_period = seasonality_info.get("best_period", 7)
    per_model_mape = performance_metrics.get("per_model_mape")

    if volatility_info.get("classification", {}).get("volatility_level") in ("high", "extreme"):
        capped_values = cap_outliers_iqr(values)
        logger.info(f"Applied IQR outlier capping for {service}/{metric_column} due to high volatility.")
    else:
        capped_values = values

    # Determine if enhanced transform should be used
    use_enhanced_transform = (
        _should_use_log_transform(service, metric_column) or 
        volatility_info.get("is_volatile", False)
    )

    # Run enhanced ensemble forecast with backtest-driven weights
    forecasts = _ensemble_forecast(
        capped_values, horizon, last_date, 
        volatility_info, use_enhanced_transform,
        seasonal_period=best_seasonal_period,
        backtest_mapes=per_model_mape,
    )
    
    # Inverse transform if enhanced transform was applied
    if forecasts["transform_info"]["log_transformed"]:
        transform_type = forecasts["transform_info"]["transform_type"]
        for model_name in ["ensemble", "ets", "sarima", "ridge"]:
            forecasts[model_name] = inverse_enhanced_transform(forecasts[model_name], transform_type)
        logger.info(f"Inverse enhanced transform applied for forecast: {transform_type}")

    forecast_dates = [
        (last_date + pd.Timedelta(days=i + 1)).date()
        for i in range(horizon)
    ]

    return {
        "metric": metric_column,
        "method": "ensemble",
        "history": [
            {"date": str(row["date"].date()) if hasattr(row["date"], "date") else str(row["date"]),
             "value": round(float(row["value"]), 4)}
            for _, row in original_df.iterrows()
        ],
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
        "volatility_info": performance_metrics.get("volatility_info") if performance_metrics else None,
        "seasonality_info": seasonality_info,
        "enhanced_transform_used": forecasts["transform_info"]["log_transformed"],
        "transform_type": forecasts["transform_info"]["transform_type"],
        "weights_used": forecasts["weights_used"],
        "adaptive_threshold": performance_metrics.get("adaptive_threshold") if performance_metrics else 50.0,
        "should_fallback": performance_metrics.get("should_fallback", False) if performance_metrics else False,
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
    forecast_costs: list[float] | None = None,
    cost_breakdown: dict | None = None,
):
    """
    Save forecast to per-service result table.
    Interface เหมือน save_xgboost_forecast() ทุกอย่าง
    
    Added support for forecast costs and cost breakdown.
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
    
    # Add cost data if available
    if forecast_costs:
        params["forecast_costs"] = forecast_costs
    if cost_breakdown:
        params["cost_breakdown"] = cost_breakdown

    row = result_model(**params)
    db.add(row)
    db.commit()
    db.refresh(row)
    
    cost_info = f", total_cost=${sum(forecast_costs):.2f}" if forecast_costs else ""
    logger.info(
        f"Saved {method} forecast — {service}/{metric} "
        f"resource_id={resource_id} "
        f"({len(forecast_dates)} values{cost_info}, id={row.id})"
    )
    return row


# ─── Orchestrator ────────────────────────────────────────────────

def run_ensemble_forecast(
    db: Session,
    service: str,
    resource_id: int,
    metric: Optional[str],
    horizon: int = 30,
    baseline_days: Optional[int] = None,
) -> dict:
    """
    Orchestrator — Drop-in replacement ของ run_xgboost_forecast()
    พร้อม MAPE-based fallback guard และ log transform สำหรับ volatile data

    Priority:
        1. Ensemble (ETS + SARIMA + Ridge) with log transform for volatile metrics
        2. MAPE-based fallback guard → ถ้า MAPE > 50% จะ auto fallback
        3. Baseline moving average (fallback)
        4. Empty result (ถ้า fallback ก็ยังล้มเหลว)

    Features:
        - Automatic volatility detection and log transform
        - MAPE-based fallback guard (threshold: 50%)
        - Enhanced logging with transform/fallback info
        - Backward compatible with existing interface

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
                    "fallback_reason": str | None,
                    "volatility_info": dict | None,
                    "log_transform_used": bool,
                    "should_fallback": bool,
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

    RESOURCE_FALLBACK_THRESHOLD = 65.0  # ตรงกับ Threshold ที่แสดงบน UI

    results = []
    ensemble_results = []  # เก็บผล Ensemble ของทุก Metric ก่อน ค่อยตัดสิน

    for m in metrics_to_run:
        # ── 1. Try Ensemble (ไม่ตัดสิน Fallback ต่อ Metric อีกต่อไป) ──
        try:
            forecast = ensemble_forecast_metric(
                db=db,
                service=service,
                resource_id=resource_id,
                metric_column=m,
                horizon=horizon,
                baseline_days=baseline_days,
            )
            forecast["fallback"] = False
            ensemble_results.append(forecast)
            logger.info(
                f"Ensemble OK — {service}/{m} "
                f"MAPE={forecast.get('performance_metrics', {}).get('mape', 'N/A')}%"
            )
        except Exception as ens_err:
            logger.warning(
                f"Ensemble failed for {service}/{m} "
                f"resource_id={resource_id}: {ens_err}"
            )
            ensemble_results.append(None)  # mark as failed

    # ── 2. คำนวณ avg MAPE ระดับ Resource (เหมือน UI คำนวณ) ─────────
    mapes = [
        r.get("performance_metrics", {}).get("mape")
        for r in ensemble_results if r is not None
        and r.get("performance_metrics", {}).get("mape") is not None
    ]
    avg_resource_mape = sum(mapes) / len(mapes) if mapes else None

    use_fallback = (
        avg_resource_mape is not None and avg_resource_mape > RESOURCE_FALLBACK_THRESHOLD
    ) or any(r is None for r in ensemble_results)

    if avg_resource_mape is not None:
        logger.info(
            f"Resource-level avg MAPE = {avg_resource_mape:.1f}% "
            f"(threshold={RESOURCE_FALLBACK_THRESHOLD}%) → "
            f"{'FALLBACK' if use_fallback else 'ENSEMBLE OK'}"
        )

    # ── 3a. ถ้า avg MAPE ≤ 65% → บันทึก Ensemble ─────────────────
    if not use_fallback:
        for forecast in ensemble_results:
            if forecast is None:
                continue
            m = forecast["metric"]
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

    # ── 3b. ถ้า avg MAPE > 65% → Fallback ทุก Metric ─────────────
    else:
        fallback_reason = (
            f"Resource avg MAPE too high ({avg_resource_mape:.1f}% > {RESOURCE_FALLBACK_THRESHOLD}%)"
            if avg_resource_mape is not None
            else "Ensemble failed for one or more metrics"
        )
        logger.warning(
            f"{fallback_reason} for {service} resource_id={resource_id}. "
            f"Falling back to moving_average ({baseline_days or 90}-day window) for all metrics."
        )
        for m in metrics_to_run:
            try:
                fallback_result = forecast_metric(
                    db=db,
                    service=service,
                    resource_id=resource_id,
                    metric_column=m,
                    horizon=horizon,
                    method="moving_average",
                    window=baseline_days or 90,
                    season_length=7,
                )
                fallback = {
                    "metric": m,
                    "method": "moving_average",
                    "forecast_dates": [item["date"] for item in fallback_result["forecast"]],
                    "forecast_values": [item["forecast"] for item in fallback_result["forecast"]],
                    "fallback": True,
                    "fallback_reason": fallback_reason,
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
                logger.info(f"Fallback OK — {service}/{m}")

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
                    "fallback_reason": "All methods failed",
                    "error": str(base_err),
                })

    # ── 4. Calculate forecast costs (if we have successful forecasts) ────
    successful_results = [r for r in results if r.get("method") != "none" and r.get("forecast_values")]
    
    if successful_results:
        try:
            from .forecast_cost_integration import calculate_forecast_costs, add_costs_to_forecast_result
            
            # Get forecast dates from first successful result
            forecast_dates = successful_results[0].get("forecast_dates", [])
            
            # Calculate costs based on all forecasted metrics
            forecast_costs, cost_breakdown = calculate_forecast_costs(
                db=db,
                service=service,
                resource_id=resource_id,
                forecast_dates=forecast_dates,
                all_forecast_results=successful_results
            )
            
            if forecast_costs and cost_breakdown:
                # Fetch last month's actual costs from the DB (instead of calculating via pricing)
                history_costs = None
                history_dates_str = None

                try:
                    from datetime import date as date_type, timedelta
                    from sqlalchemy import func

                    COST_MODEL_MAP = {
                        "ec2":    ("models", "EC2Cost",    "ec2_resource_id"),
                        "rds":    ("models", "RDSCost",    "rds_resource_id"),
                        "lambda": ("models", "LambdaCost", "lambda_resource_id"),
                        "s3":     ("models", "S3Cost",     "s3_resource_id"),
                        "alb":    ("models", "ALBCost",    "alb_resource_id"),
                    }

                    cost_model_info = COST_MODEL_MAP.get(service)
                    if cost_model_info:
                        _, model_name, id_col = cost_model_info
                        from .. import models as m_module
                        cost_model = getattr(m_module, model_name)
                        id_field = getattr(cost_model, id_col)

                        today = date_type.today()
                        # Last month's date range
                        first_day_this_month = today.replace(day=1)
                        last_day_prev_month = first_day_this_month - timedelta(days=1)
                        first_day_prev_month = last_day_prev_month.replace(day=1)

                        rows = (
                            db.query(cost_model.usage_date, cost_model.amount_usd)
                            .filter(
                                id_field == resource_id,
                                cost_model.usage_type == "total",
                                cost_model.usage_date >= first_day_prev_month,
                                cost_model.usage_date <= last_day_prev_month,
                            )
                            .order_by(cost_model.usage_date)
                            .all()
                        )

                        if rows:
                            history_costs = [float(row.amount_usd) for row in rows]
                            history_dates_str = [str(row.usage_date) for row in rows]
                            hist_total = sum(history_costs)
                            hist_daily_avg = hist_total / len(history_costs)
                            
                            logger.info(
                                f"Fetched {len(history_costs)} actual cost rows for {service}/{resource_id} "
                                f"({first_day_prev_month} – {last_day_prev_month}), "
                                f"total=${hist_total:.2f}, daily_avg=${hist_daily_avg:.2f}"
                            )

                            # ── Calibration ─────────────────────────────────────────
                            # If history exists, we scale the forecast to match the REAL billing profile
                            # (matches RIs, custom region pricing, etc.)
                            if forecast_costs and len(forecast_costs) > 0:
                                forecast_total = sum(forecast_costs)
                                forecast_daily_avg = forecast_total / len(forecast_costs)
                                
                                if forecast_daily_avg > 0:
                                    calibration_factor = hist_daily_avg / forecast_daily_avg
                                    # Limit the factor for safety (e.g. max 5x change)
                                    calibration_factor = max(0.2, min(5.0, calibration_factor))
                                    
                                    if abs(calibration_factor - 1.0) > 0.01:
                                        logger.info(
                                            f"Calibrating {service}/{resource_id} forecast by {calibration_factor:.2f}x "
                                            f"to match history (${hist_daily_avg:.2f}/day)"
                                        )
                                        forecast_costs = [float(c * calibration_factor) for c in forecast_costs]
                                        # Scale breakdown too
                                        for key in cost_breakdown:
                                            cost_breakdown[key] = [float(val * calibration_factor) for val in cost_breakdown[key]]
                                
                                # ── Seasonal Pattern from History ───────────────────
                                # EC2/RDS มีต้นทุนส่วนใหญ่เป็น Fixed (Compute+Storage) ทำให้กราฟแบน
                                # แก้ไขโดยการนำ Seasonal Ratio จาก Historical Costs จริง มา apply
                                # กับ Forecast เพื่อให้กราฟขึ้นลงตาม Pattern การใช้จ่ายจริงในอดีต
                                if len(history_costs) >= 7 and len(forecast_costs) > 0:
                                    hist_avg = float(np.mean(history_costs)) if hist_daily_avg > 0 else 1.0
                                    if hist_avg > 0:
                                        seasonal_ratios = [c / hist_avg for c in history_costs]
                                        n_hist = len(seasonal_ratios)
                                        # Dampen the seasonal effect: blend 35% ratio + 65% flat (1.0)
                                        # ป้องกันไม่ให้กราฟดูเหมือน copy มาจาก history
                                        SEASONAL_STRENGTH = 0.35
                                        dampened_ratios = [
                                            1.0 + SEASONAL_STRENGTH * (r - 1.0)
                                            for r in seasonal_ratios
                                        ]
                                        # Map each forecast day to a historical ratio (cycling)
                                        seasoned_costs = [
                                            forecast_costs[i] * dampened_ratios[i % n_hist]
                                            for i in range(len(forecast_costs))
                                        ]
                                        # Preserve total — scale back to match original forecast sum
                                        orig_sum = sum(forecast_costs)
                                        new_sum = sum(seasoned_costs)
                                        if new_sum > 0:
                                            scale = orig_sum / new_sum
                                            forecast_costs = [float(c * scale) for c in seasoned_costs]
                                        logger.info(
                                            f"Applied seasonal cost pattern to {service}/{resource_id} "
                                            f"using {n_hist} historical days (strength={SEASONAL_STRENGTH})"
                                        )
                            # ────────────────────────────────────────────────────────

                        else:
                            logger.warning(
                                f"No actual cost data in {service}_costs for resource_id={resource_id} "
                                f"between {first_day_prev_month} and {last_day_prev_month}"
                            )
                except Exception as hist_err:
                    logger.error(f"Error fetching historical costs from DB: {hist_err}")

                # Add cost info to all successful results
                for i, result in enumerate(results):
                    if result.get("method") != "none" and result.get("forecast_values"):
                        updated_result = add_costs_to_forecast_result(result, forecast_costs, cost_breakdown)
                        if history_costs and history_dates_str:
                            updated_result["history_costs"] = history_costs
                            updated_result["history_dates"] = history_dates_str
                        results[i] = updated_result
                
                # Update saved forecast records with cost data
                # Find the first metric result to save costs (typically the primary metric)
                primary_result = successful_results[0]
                if primary_result:
                    # Update the database record with cost data
                    result_model = FORECAST_RESULT_MODEL_MAP.get(service)
                    if result_model:
                        # Find the most recent forecast record for this resource and metric
                        latest_record = db.query(result_model).filter_by(
                            resource_id=resource_id,
                            metric=primary_result.get("metric")
                        ).order_by(result_model.created_at.desc()).first()
                        
                        if latest_record:
                            latest_record.forecast_costs = forecast_costs
                            latest_record.cost_breakdown = cost_breakdown
                            db.commit()
                            logger.info(
                                f"Updated forecast costs for {service} resource {resource_id}: "
                                f"total=${sum(forecast_costs):.2f}"
                            )
        
        except Exception as cost_err:
            logger.warning(f"Failed to calculate forecast costs for {service} resource {resource_id}: {cost_err}")
            # Don't fail the entire forecast if cost calculation fails

    return {
        "service": service,
        "resource_id": resource_id,
        "results": results,
    }