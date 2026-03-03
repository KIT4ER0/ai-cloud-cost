"""
Shared aggregation utilities for converting hourly CloudWatch metrics to daily summaries.
Each service's pull script uses these helpers to transform raw CloudWatch response
data into daily-aggregated rows ready for DB insertion.
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import date

logger = logging.getLogger(__name__)


# ─── Aggregation Strategies ───────────────────────────────────────

def _max_val(current: Optional[float], new: float) -> float:
    """Keep the maximum value (useful for Average metrics like CPU)."""
    if current is None:
        return new
    return max(current, new)


def _min_val(current: Optional[float], new: float) -> float:
    """Keep the minimum value (useful for FreeStorageSpace)."""
    if current is None:
        return new
    return min(current, new)


def _sum_val(current: Optional[float], new: float) -> float:
    """Accumulate sum (useful for Sum metrics like NetworkIn, Invocations)."""
    if current is None:
        return new
    return current + new


def _last_val(_current: Optional[float], new: float) -> float:
    """Keep last value (useful for daily S3 metrics that are already 1/day)."""
    return new


# Strategy mapping
STRATEGY = {
    "max": _max_val,
    "min": _min_val,
    "sum": _sum_val,
    "last": _last_val,
}


# ─── Core Aggregation ─────────────────────────────────────────────

def aggregate_hourly_to_daily(
    cw_resp: dict,
    metric_strategies: Dict[str, str],
) -> Dict[date, Dict[str, float]]:
    """
    Aggregate CloudWatch MetricDataResults from hourly to daily.

    Args:
        cw_resp: Raw CloudWatch response from get_cloudwatch_metric_data()
        metric_strategies: Mapping of metric_id -> strategy name.
            Example: {"cpu": "max", "netin": "sum", "netout": "sum"}
            Strategies: "max", "min", "sum", "last"

    Returns:
        Dict keyed by date, each value is a dict of {metric_id: aggregated_value}
        Example: {
            date(2026,3,1): {"cpu": 45.2, "netin": 1234567.0, "netout": 890123.0},
            date(2026,3,2): {"cpu": 32.1, "netin": 987654.0, "netout": 654321.0},
        }
    """
    if not cw_resp:
        return {}

    daily: Dict[date, Dict[str, Optional[float]]] = {}

    for result in cw_resp.get("MetricDataResults", []):
        metric_id = result.get("Id", "")
        timestamps = result.get("Timestamps", [])
        values = result.get("Values", [])

        strategy_name = metric_strategies.get(metric_id, "last")
        strategy_fn = STRATEGY.get(strategy_name, _last_val)

        for ts, val in zip(timestamps, values):
            d = ts.date() if hasattr(ts, "date") else ts
            if d not in daily:
                daily[d] = {}
            daily[d][metric_id] = strategy_fn(daily[d].get(metric_id), val)

    return daily


# ─── Service-Specific Strategies ──────────────────────────────────

EC2_STRATEGIES: Dict[str, str] = {
    "cpu": "max",
    "netin": "sum",
    "netout": "sum",
    "cpu_credit": "max",
}

RDS_STRATEGIES: Dict[str, str] = {
    "rds_cpu": "max",
    "rds_conn": "max",
    "rds_mem_free": "min",
    "rds_storage_free": "min",
    "rds_disk_q": "max",
    "rds_ebs_byte_bal": "min",
    "rds_ebs_io_bal": "min",
    "rds_cpu_credit_bal": "min",
    "rds_cpu_credit_use": "sum",
}

LAMBDA_STRATEGIES: Dict[str, str] = {
    "duration": "max",
    "invocations": "sum",
    "errors": "sum",
}

S3_STRATEGIES: Dict[str, str] = {
    "storage_bytes": "last",
    "num_objects": "last",
}

ALB_STRATEGIES: Dict[str, str] = {
    "request_count": "sum",
    "response_time": "max",
    "http_5xx": "sum",
    "active_conn": "sum",
}
