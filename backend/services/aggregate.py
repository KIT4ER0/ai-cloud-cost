"""
Shared utilities for parsing CloudWatch daily metric responses.

Since all services now request daily buckets (Period=86400),
CloudWatch returns exactly 1 datapoint per day per metric.
This module provides a simple parser to group those results by date.
"""
import logging
from datetime import date

logger = logging.getLogger(__name__)


# ─── Core: Parse Daily CloudWatch Response ────────────────────────

def group_cw_by_date(
    cw_resp: dict,
) -> dict[date, dict[str, float]]:
    """
    Parse a CloudWatch MetricDataResults response (daily Period=86400)
    into a dict keyed by date.

    Since CloudWatch returns 1 value per day, this simply groups
    timestamps by their date and maps metric IDs to their values.

    Args:
        cw_resp: Raw CloudWatch response from get_cloudwatch_metric_data()

    Returns:
        Dict keyed by date, each value is a dict of {metric_id: value}
        Example: {
            date(2026,3,1): {"cpu": 45.2, "netin": 1234567.0},
            date(2026,3,2): {"cpu": 32.1, "netin": 987654.0},
        }
    """
    if not cw_resp:
        return {}

    daily: Dict[date, Dict[str, float]] = {}

    for result in cw_resp.get("MetricDataResults", []):
        metric_id = result.get("Id", "")
        timestamps = result.get("Timestamps", [])
        values = result.get("Values", [])

        for ts, val in zip(timestamps, values):
            d = ts.date() if hasattr(ts, "date") else ts
            if d not in daily:
                daily[d] = {}
            daily[d][metric_id] = val

    return daily
