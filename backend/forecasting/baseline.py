"""
Baseline forecasting models.

Provides:
  - BaselineConfig: configuration dataclass for baseline models
  - BaselineForecaster: simple forecast methods (moving_average, seasonal_naive, drift)
  - backtest_baseline: rolling-origin backtest evaluation
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

ForecastMethod = Literal["moving_average", "seasonal_naive", "drift"]


@dataclass
class BaselineConfig:
    """Configuration for a baseline forecaster."""
    method: ForecastMethod = "moving_average"
    window: int = 7                  # look-back window for moving_average / drift
    season_length: int = 7           # period for seasonal_naive
    min_train_size: int = 3          # minimum rows required to fit


class BaselineForecaster:
    """
    Simple baseline forecasters:

    - moving_average : mean of last `window` observations
    - seasonal_naive : repeat last observed season (lag = season_length)
    - drift          : linear extrapolation from first to last observation
    """

    def __init__(self, config: Optional[BaselineConfig] = None) -> None:
        self.config = config or BaselineConfig()

    # ── Internal helpers ──────────────────────────────────────────

    def _moving_average(self, values: np.ndarray, h: int) -> np.ndarray:
        w = min(self.config.window, len(values))
        last_mean = float(np.mean(values[-w:]))
        return np.full(h, last_mean)

    def _seasonal_naive(self, values: np.ndarray, h: int) -> np.ndarray:
        s = self.config.season_length
        preds = []
        n = len(values)
        for i in range(h):
            idx = n - s + (i % s)
            if idx < 0:
                idx = n - 1
            preds.append(float(values[idx]))
        return np.array(preds)

    def _drift(self, values: np.ndarray, h: int) -> np.ndarray:
        n = len(values)
        if n < 2:
            return np.full(h, values[-1])
        slope = (values[-1] - values[0]) / (n - 1)
        last = float(values[-1])
        return np.array([last + slope * (i + 1) for i in range(h)])

    def _predict(self, values: np.ndarray, h: int) -> np.ndarray:
        m = self.config.method
        if m == "moving_average":
            return self._moving_average(values, h)
        elif m == "seasonal_naive":
            return self._seasonal_naive(values, h)
        elif m == "drift":
            return self._drift(values, h)
        else:
            raise ValueError(f"Unknown forecast method: {m}")

    # ── Public API ────────────────────────────────────────────────

    def forecast_future(self, df: pd.DataFrame, horizon: int = 30) -> pd.DataFrame:
        """
        Produce future forecasts beyond the last date in df.

        Args:
            df: DataFrame with columns ['date', 'value']
            horizon: number of future steps to forecast

        Returns:
            DataFrame with columns ['date', 'forecast']
        """
        if df.empty or len(df) < self.config.min_train_size:
            raise ValueError(
                f"Not enough data to forecast (got {len(df)}, need {self.config.min_train_size})"
            )

        df = df.copy().sort_values("date").reset_index(drop=True)
        values = df["value"].to_numpy(dtype=float)

        preds = self._predict(values, horizon)

        # Build future date index
        last_date = pd.Timestamp(df["date"].iloc[-1])
        future_dates = [last_date + pd.Timedelta(days=i + 1) for i in range(horizon)]

        return pd.DataFrame({"date": future_dates, "forecast": preds})

    def predict_in_sample(self, df: pd.DataFrame, start: int = 0) -> pd.DataFrame:
        """
        Predict for each position from `start` to end of df (one-step ahead simulation).

        Returns:
            DataFrame with columns ['date', 'actual', 'prediction']
        """
        df = df.copy().sort_values("date").reset_index(drop=True)
        dates, actuals, preds = [], [], []

        for i in range(start, len(df)):
            train = df["value"].iloc[:i].to_numpy(dtype=float)
            if len(train) < self.config.min_train_size:
                continue
            pred = float(self._predict(train, 1)[0])
            dates.append(df["date"].iloc[i])
            actuals.append(float(df["value"].iloc[i]))
            preds.append(pred)

        return pd.DataFrame({"date": dates, "actual": actuals, "prediction": preds})


# ── Backtest ──────────────────────────────────────────────────────

def backtest_baseline(
    df: pd.DataFrame,
    config: BaselineConfig,
    test_size: int = 7,
) -> tuple[pd.DataFrame, dict]:
    """
    Rolling-origin backtest on the last `test_size` observations.

    Args:
        df: DataFrame with columns ['date', 'value']
        config: BaselineConfig
        test_size: number of held-out test points

    Returns:
        (eval_df, metrics_dict)
        eval_df has columns: ['date', 'actual', 'prediction']
        metrics_dict has keys: ['n', 'mae', 'rmse', 'mape']
    """
    df = df.copy().sort_values("date").reset_index(drop=True)
    n = len(df)

    if n < config.min_train_size + test_size:
        raise ValueError(
            f"Not enough data for backtest: need at least "
            f"{config.min_train_size + test_size} rows, got {n}"
        )

    model = BaselineForecaster(config)
    train_end = n - test_size
    eval_df = model.predict_in_sample(df, start=train_end)

    # Compute metrics
    actuals = eval_df["actual"].to_numpy(dtype=float)
    predictions = eval_df["prediction"].to_numpy(dtype=float)

    mae = float(np.mean(np.abs(actuals - predictions)))
    rmse = float(math.sqrt(np.mean((actuals - predictions) ** 2)))

    # MAPE — guard against zeros
    nonzero = actuals != 0
    if nonzero.any():
        mape = float(np.mean(np.abs((actuals[nonzero] - predictions[nonzero]) / actuals[nonzero])) * 100)
    else:
        mape = None

    metrics = {
        "n": len(eval_df),
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(mape, 2) if mape is not None else None,
    }

    return eval_df, metrics
