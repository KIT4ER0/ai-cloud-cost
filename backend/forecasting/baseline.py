from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd
import numpy as np


BaselineMethod = Literal["naive", "moving_average", "seasonal_naive"]


@dataclass
class BaselineConfig:
    method: BaselineMethod
    window: int = 7          # for moving_average
    season_length: int = 7   # for seasonal_naive
    min_train_size: int = 7


class BaselineForecaster:
    def __init__(self, config: BaselineConfig):
        self.config = config

    def validate_input(self, df: pd.DataFrame) -> pd.DataFrame:
        required_cols = {"date", "value"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        out = df.copy()
        out["date"] = pd.to_datetime(out["date"])
        out = out.sort_values("date").reset_index(drop=True)

        if out["value"].isna().any():
            raise ValueError("Column 'value' contains NaN. Clean missing values first.")

        if len(out) < self.config.min_train_size:
            raise ValueError(
                f"Not enough rows to forecast. Need at least {self.config.min_train_size}, got {len(out)}"
            )

        return out

    def fit_predict_in_sample(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create one-step-ahead predictions on historical data.
        Useful for evaluating baseline error on known actuals.
        """
        df = self.validate_input(df)
        method = self.config.method

        result = df.copy()
        result["prediction"] = np.nan

        if method == "naive":
            result["prediction"] = result["value"].shift(1)

        elif method == "moving_average":
            window = self.config.window
            result["prediction"] = result["value"].shift(1).rolling(window=window).mean()

        elif method == "seasonal_naive":
            season = self.config.season_length
            result["prediction"] = result["value"].shift(season)

        else:
            raise ValueError(f"Unsupported method: {method}")

        return result

    def forecast_future(self, df: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """
        Forecast future dates.
        Returns a DataFrame with columns: date, forecast
        """
        if horizon <= 0:
            raise ValueError("horizon must be > 0")

        df = self.validate_input(df)
        method = self.config.method

        last_date = df["date"].max()
        future_dates = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=horizon,
            freq="D"
        )

        history = df["value"].tolist()
        forecasts = []

        for step in range(horizon):
            if method == "naive":
                pred = history[-1]

            elif method == "moving_average":
                window = self.config.window
                if len(history) < window:
                    pred = float(np.mean(history))
                else:
                    pred = float(np.mean(history[-window:]))

            elif method == "seasonal_naive":
                season = self.config.season_length
                if len(history) < season:
                    raise ValueError(
                        f"Not enough history for seasonal_naive. Need at least {season} rows."
                    )
                pred = history[-season]

            else:
                raise ValueError(f"Unsupported method: {method}")

            forecasts.append(pred)
            history.append(pred)

        return pd.DataFrame({
            "date": future_dates,
            "forecast": forecasts
        })


def calculate_regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict:
    """
    Compute common forecast error metrics.
    Rows with NaN in prediction are dropped automatically.
    """
    eval_df = pd.DataFrame({
        "actual": actual,
        "predicted": predicted
    }).dropna()

    if eval_df.empty:
        return {
            "n": 0,
            "mae": None,
            "rmse": None,
            "mape": None,
        }

    y_true = eval_df["actual"].astype(float).to_numpy()
    y_pred = eval_df["predicted"].astype(float).to_numpy()

    mae = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))

    # avoid divide-by-zero for MAPE
    non_zero_mask = y_true != 0
    if np.any(non_zero_mask):
        mape = float(
            np.mean(np.abs((y_true[non_zero_mask] - y_pred[non_zero_mask]) / y_true[non_zero_mask])) * 100
        )
    else:
        mape = None

    return {
        "n": int(len(eval_df)),
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
    }


def train_test_split_time_series(df: pd.DataFrame, test_size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split time series without shuffling.
    """
    if test_size <= 0:
        raise ValueError("test_size must be > 0")
    if len(df) <= test_size:
        raise ValueError("test_size must be smaller than dataset length")

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    train_df = df.iloc[:-test_size].copy()
    test_df = df.iloc[-test_size:].copy()
    return train_df, test_df


def backtest_baseline(
    df: pd.DataFrame,
    config: BaselineConfig,
    test_size: int
) -> tuple[pd.DataFrame, dict]:
    """
    Evaluate a baseline model on the last `test_size` points.
    Returns:
      1) DataFrame with actual/prediction
      2) metrics dict
    """
    train_df, test_df = train_test_split_time_series(df, test_size=test_size)

    model = BaselineForecaster(config)

    # use full history up to each point via in-sample one-step prediction
    full_pred = model.fit_predict_in_sample(df)

    eval_df = full_pred[["date", "value", "prediction"]].tail(test_size).copy()
    eval_df.rename(columns={"value": "actual"}, inplace=True)

    metrics = calculate_regression_metrics(eval_df["actual"], eval_df["prediction"])
    return eval_df, metrics