"""
Test script for ensemble forecast improvements.

Validates:
  1. Adaptive backtest-driven weights (inverse-MAPE)
  2. Enhanced log transform with basic_stats in volatility_info
  3. Seasonal period detection passed to ETS/SARIMA
  4. Adaptive MAPE threshold
"""
import numpy as np
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.forecasting.ensemble_forecast_service import (
    get_adaptive_ensemble_weights,
    enhanced_log_transform,
    inverse_enhanced_transform,
    detect_seasonality,
    get_adaptive_mape_threshold,
    _detect_volatility_pattern,
    _forecast_ets,
    _forecast_sarima,
    _forecast_ridge,
    _ensemble_forecast,
    _calculate_error_metrics,
)

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 1. Backtest-driven adaptive weights ===")

# When backtest MAPEs are provided, weights should be inverse-MAPE
mapes = {"ets": 10.0, "sarima": 20.0, "ridge": 40.0}
w = get_adaptive_ensemble_weights("stable", backtest_mapes=mapes)
check("ETS gets highest weight (lowest MAPE)",
      w["ets"] > w["sarima"] > w["ridge"],
      f"got {w}")
check("Weights sum to ~1.0",
      abs(sum(w.values()) - 1.0) < 0.01,
      f"sum={sum(w.values())}")

# When MAPEs are None, fall back to volatility-based
w2 = get_adaptive_ensemble_weights("extreme", backtest_mapes=None)
check("Extreme volatility: ridge gets highest default weight",
      w2["ridge"] >= w2["ets"] and w2["ridge"] >= w2["sarima"],
      f"got {w2}")

w3 = get_adaptive_ensemble_weights("stable", backtest_mapes=None)
check("Stable volatility: ETS gets highest default weight",
      w3["ets"] >= w3["sarima"] and w3["ets"] >= w3["ridge"],
      f"got {w3}")

# Edge case: only 1 valid MAPE → should fall back to volatility-based
w4 = get_adaptive_ensemble_weights("low", backtest_mapes={"ets": 5.0, "sarima": 0.0, "ridge": 0.0})
check("Only 1 valid MAPE → fallback to volatility defaults",
      abs(sum(w4.values()) - 1.0) < 0.01,
      f"got {w4}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 2. Volatility detection with basic_stats ===")

np.random.seed(42)
stable_data = np.random.normal(100, 5, 90)   # CV ~ 0.05
volatile_data = np.random.normal(100, 120, 90)  # CV ~ 1.2

vi_stable = _detect_volatility_pattern(stable_data)
check("Stable data: basic_stats key exists",
      "basic_stats" in vi_stable,
      f"keys={list(vi_stable.keys())}")
check("Stable data: basic_stats.cv present",
      "cv" in vi_stable.get("basic_stats", {}),
      f"basic_stats={vi_stable.get('basic_stats')}")
check("Stable data: volatility_level is stable or low",
      vi_stable["classification"]["volatility_level"] in ("stable", "low"),
      f"got {vi_stable['classification']['volatility_level']}")

vi_volatile = _detect_volatility_pattern(np.abs(volatile_data))
check("Volatile data: volatility_level is high or extreme",
      vi_volatile["classification"]["volatility_level"] in ("high", "extreme"),
      f"got {vi_volatile['classification']['volatility_level']}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 3. Enhanced log transform ===")

# High CV → should transform
high_cv_info = {"basic_stats": {"cv": 1.6}, "classification": {"volatility_level": "extreme"}}
transformed, was_t, t_type = enhanced_log_transform(np.array([1.0, 100.0, 1000.0]), high_cv_info)
check("Extreme CV → transform applied", was_t, f"was_transformed={was_t}")
check("Extreme CV → sqrt_log transform", t_type == "sqrt_log", f"type={t_type}")

# Inverse transform roundtrip
original = np.array([10.0, 50.0, 200.0, 500.0])
for cv_val, expected_type in [(1.6, "sqrt_log"), (0.9, "log"), (0.6, "boxcox_approx")]:
    info = {"basic_stats": {"cv": cv_val}, "classification": {"volatility_level": "high"}}
    t_vals, _, tt = enhanced_log_transform(original, info)
    recovered = inverse_enhanced_transform(t_vals, tt)
    max_err = np.max(np.abs(original - recovered))
    check(f"Roundtrip ({tt}): max error < 1.0",
          max_err < 1.0,
          f"max_err={max_err:.4f}")

# Low CV → no transform
low_cv_info = {"basic_stats": {"cv": 0.2}, "classification": {"volatility_level": "stable"}}
_, was_t_low, t_low = enhanced_log_transform(np.array([10.0, 11.0, 12.0]), low_cv_info)
check("Low CV → no transform", not was_t_low, f"was_transformed={was_t_low}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 4. Seasonal detection ===")

np.random.seed(123)
t = np.arange(200)
weekly_signal = 50 + 10 * np.sin(2 * np.pi * t / 7) + np.random.normal(0, 2, 200)
has_s, periods = detect_seasonality(weekly_signal)
check("Weekly signal detected as seasonal", has_s, f"has_seasonality={has_s}")
check("Period close to 7",
      any(abs(p - 7) <= 2 for p in periods) if periods else False,
      f"periods={periods}")

flat_signal = np.ones(200) * 50 + np.random.normal(0, 0.5, 200)
has_s2, periods2 = detect_seasonality(flat_signal)
check("Flat signal: no strong seasonality", not has_s2, f"has_seasonality={has_s2}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 5. ETS/SARIMA accept seasonal_period param ===")

np.random.seed(0)
data = 100 + 10 * np.sin(2 * np.pi * np.arange(90) / 7) + np.random.normal(0, 3, 90)

ets_7 = _forecast_ets(data, horizon=14, seasonal_period=7)
check("ETS with period=7 returns correct length",
      len(ets_7) == 14, f"len={len(ets_7)}")
check("ETS with period=7 returns positive values",
      np.all(ets_7 >= 0), f"min={np.min(ets_7)}")

sarima_7 = _forecast_sarima(data, horizon=14, seasonal_period=7)
check("SARIMA with period=7 returns correct length",
      len(sarima_7) == 14, f"len={len(sarima_7)}")
check("SARIMA with period=7 returns positive values",
      np.all(sarima_7 >= 0), f"min={np.min(sarima_7)}")


# ─────────────────────────────────────────────────────────────────
print("\n=== 6. Adaptive MAPE thresholds ===")

for level, expected_min in [("stable", 25), ("low", 35), ("moderate", 45), ("high", 55), ("extreme", 65)]:
    t_val = get_adaptive_mape_threshold(level)
    check(f"Threshold for {level} >= {expected_min}",
          t_val >= expected_min, f"threshold={t_val}")

check("Higher volatility → higher threshold",
      get_adaptive_mape_threshold("extreme") > get_adaptive_mape_threshold("stable"),
      "not monotonically increasing")


# ─────────────────────────────────────────────────────────────────
print("\n=== 7. Full ensemble_forecast with backtest_mapes ===")

import pandas as pd
np.random.seed(42)
data = 100 + 10 * np.sin(2 * np.pi * np.arange(90) / 7) + np.random.normal(0, 3, 90)
last_dt = pd.Timestamp("2025-03-01")

vol_info = _detect_volatility_pattern(data)
vol_info["seasonality"] = {"has_seasonality": True, "seasonal_periods": [7], "best_period": 7}

mapes_for_test = {"ets": 8.0, "sarima": 15.0, "ridge": 25.0}

result = _ensemble_forecast(
    data, horizon=30, last_date=last_dt,
    volatility_info=vol_info,
    use_enhanced_transform=False,
    seasonal_period=7,
    backtest_mapes=mapes_for_test,
)
check("Ensemble forecast returns all keys",
      all(k in result for k in ("ensemble", "ets", "sarima", "ridge", "weights_used")),
      f"keys={list(result.keys())}")
check("Ensemble uses backtest-driven weights (ETS highest)",
      result["weights_used"]["ets"] > result["weights_used"]["ridge"],
      f"weights={result['weights_used']}")
check("Ensemble forecast length = 30",
      len(result["ensemble"]) == 30,
      f"len={len(result['ensemble'])}")
check("All ensemble values >= 0",
      np.all(result["ensemble"] >= 0),
      f"min={np.min(result['ensemble'])}")


# ─────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"WARNING: {failed} test(s) failed")
print(f"{'='*60}\n")

sys.exit(0 if failed == 0 else 1)
