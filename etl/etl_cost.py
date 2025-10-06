# etl/etl_cost.py
"""
ETL: AWS Cost Explorer -> raw.costs (LEAN)
- GroupBy เฉพาะ 2 มิติ: SERVICE + USAGE_TYPE
- รองรับหลาย ACCOUNT/REGION ผ่าน Filter (วนทีละค่า)
- Auto-detect AWS Account ID ผ่าน STS ถ้าไม่กำหนด
- Validate LINKED_ACCOUNT ต้อง 12 หลัก (ไม่ตรง -> ตัดออกจาก Filter อัตโนมัติ)
- Idempotent upsert ด้วย PK: (usage_date, account_id, region, service, usage_type)
"""

from __future__ import annotations

import os
import re
import json
import hashlib
import argparse
from typing import Iterable, List, Optional, Dict

from etl.common import (
    boto_client,
    ce_get_cost_and_usage,
    upsert_many_costs,
    daterange_days_back,
)

# ---------------------------
# Utilities
# ---------------------------

def h(*parts) -> str:
    """Stable hash for source row tracking"""
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()

def env_list(name: str) -> List[str]:
    """Read comma-separated list from env; return [] if missing/blank."""
    raw = os.getenv(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []

def batches(seq: List[Dict], size: int = 5000) -> Iterable[List[Dict]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]

def get_sts_account_id() -> str:
    """Return 12-digit Account ID from STS or 'unknown' if not available."""
    try:
        sts = boto_client("sts")
        acct = sts.get_caller_identity()["Account"]
        return acct if re.fullmatch(r"\d{12}", acct) else "unknown"
    except Exception:
        return "unknown"

def is_12digits(acct: Optional[str]) -> bool:
    return bool(acct and re.fullmatch(r"\d{12}", acct))


# ---------------------------
# Core ETL
# ---------------------------


# ----- Region inference from USAGE_TYPE -----

REGION_PREFIX_MAP = {
    "USE1": "us-east-1",
    "USE2": "us-east-2",
    "USW1": "us-west-1",
    "USW2": "us-west-2",
    "EUC1": "eu-central-1",
    "EUW1": "eu-west-1",
    "EUW2": "eu-west-2",
    "EUW3": "eu-west-3",
    "APS1": "ap-south-1",
    "APN1": "ap-northeast-1",
    "APN2": "ap-northeast-2",
    "APN3": "ap-northeast-3",
    "APSE1": "ap-southeast-1",
    "APSE2": "ap-southeast-2",
    "APSE3": "ap-southeast-3",
    "APSE4": "ap-southeast-4",
    "SAE1": "sa-east-1",
    "CAN1": "ca-central-1",
    "AFS1": "af-south-1",
    "MEC1": "me-central-1",
    "MES1": "me-south-1",
}

def infer_region_from_usage_type(usage_type: str | None) -> str:
    """
    ตัวอย่าง USAGE_TYPE:
      - USE1-BoxUsage:t3.micro
      - APSE1-DataTransfer-Regional-Bytes
    เราจะอ่าน prefix ก่อนขีดแรก แล้ว map เป็น region
    ไม่เจอ → คืน 'global'
    """
    if not usage_type:
        return "global"
    prefix = usage_type.split("-", 1)[0].upper()
    return REGION_PREFIX_MAP.get(prefix, "global")


def fetch_cost_daily(
    days_back: int = 90,
    overlap_days: int = 7,
    accounts: Optional[List[str]] = None,
    regions: Optional[List[Optional[str]]] = None,
) -> List[Dict]:
    """
    Pull daily UnblendedCost grouped by SERVICE + USAGE_TYPE.
    For each (account, region) pair, apply CE Filter instead of extra GroupBy.
    """
    ce = boto_client("ce", region="us-east-1")  # Cost Explorer uses us-east-1
    start, end, _ = daterange_days_back(days_back, overlap_days)

    # ---------- prepare accounts ----------
    if not accounts:
        accounts = env_list("CE_ACCOUNTS")

    if not accounts:
        # try .env AWS_ACCOUNT_ID; if missing, auto-detect via STS
        env_acct = os.getenv("AWS_ACCOUNT_ID")
        if is_12digits(env_acct):
            accounts = [env_acct]
        else:
            detected = get_sts_account_id()
            accounts = [detected] if is_12digits(detected) else [None]  # None => no account filter

    # validate each account (keep only 12-digit); if none valid -> [None]
    valid_accounts = [a for a in accounts if is_12digits(a)]
    if not valid_accounts:
        valid_accounts = [None]
    accounts = valid_accounts

    # ---------- prepare regions ----------
    if regions is None:
        r_list = env_list("CE_REGIONS")
        regions = r_list if r_list else [None]  # None => no region filter

    out_rows: List[Dict] = []

    for acct in accounts:
        for reg in regions:
            next_token = None
            while True:
                params = {
                    "TimePeriod": {"Start": str(start), "End": str(end)},
                    "Granularity": "DAILY",
                    "Metrics": ["UnblendedCost"],
                    "GroupBy": [
                        {"Type": "DIMENSION", "Key": "SERVICE"},
                        {"Type": "DIMENSION", "Key": "USAGE_TYPE"},
                    ],
                }

                # Build CE Filter: AND(LINKED_ACCOUNT=acct?, REGION=reg?) when provided
                and_filters = []
                if is_12digits(acct):
                    and_filters.append({"Dimensions": {"Key": "LINKED_ACCOUNT", "Values": [acct]}})
                if reg:
                    and_filters.append({"Dimensions": {"Key": "REGION", "Values": [reg]}})
                if and_filters:
                    params["Filter"] = and_filters[0] if len(and_filters) == 1 else {"And": and_filters}

                if next_token:
                    params["NextPageToken"] = next_token

                resp = ce_get_cost_and_usage(ce, **params)

                # Each day has Groups[] with Keys: [SERVICE, USAGE_TYPE]
                for by_time in resp.get("ResultsByTime", []):
                    usage_date = by_time["TimePeriod"]["Start"]
                    groups = by_time.get("Groups", [])
                    if not groups:
                        continue

                    for g in groups:
                        keys = g.get("Keys", [])
                        service = keys[0] if len(keys) > 0 else None
                        usage_type = keys[1] if len(keys) > 1 else None
                        metric = g["Metrics"]["UnblendedCost"]
                        amount = float(metric.get("Amount", 0.0))
                        unit = metric.get("Unit", "USD")

                        # --- NEW: กำหนด region จาก reg (ถ้ามี), ไม่งั้นเดาจาก usage_type, สุดท้าย fallback 'global'
                        region_for_row = (reg or infer_region_from_usage_type(usage_type) or "global")
                        usage_type_for_row = usage_type or "unknown"

                        # เลือก account_id ที่จะเก็บ
                        acct_for_row = acct if is_12digits(acct) else get_sts_account_id()

                        rowhash = h(usage_date, acct_for_row or "unknown", region_for_row, service, usage_type_for_row, amount, unit)

                        out_rows.append({
                            "usage_date": usage_date,
                            "account_id": (acct_for_row if is_12digits(acct_for_row) else "unknown"),
                            "region": region_for_row,           # ✅ ไม่เป็น None แล้ว
                            "service": service,
                            "usage_type": usage_type_for_row,   # ✅ กัน None
                            "amount_usd": amount,
                            "currency_src": unit,
                            "tags": json.dumps({}),
                            "source_hash": rowhash,
                        })


                next_token = resp.get("NextPageToken")
                if not next_token:
                    break

    return out_rows


def run(
    days_back: int = 90,
    overlap_days: int = 7,
    accounts: Optional[List[str]] = None,
    regions: Optional[List[str]] = None,
    batch_size: int = 5000,
) -> None:
    rows = fetch_cost_daily(
        days_back=days_back,
        overlap_days=overlap_days,
        accounts=accounts,
        regions=regions,
    )
    if not rows:
        print("ETL Cost: no rows fetched (possibly zero cost in the selected period).")
        return

    total = 0
    for chunk in batches(rows, size=batch_size):
        upsert_many_costs(chunk)
        total += len(chunk)
    print(f"ETL Cost: upserted {total} rows")


# ---------------------------
# CLI
# ---------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL: Cost Explorer -> raw.costs (SERVICE + USAGE_TYPE)")
    p.add_argument("--days-back", type=int, default=90, help="How many days back to fetch (default: 90)")
    p.add_argument("--overlap-days", type=int, default=7, help="Rolling overwrite window to handle CE latency (default: 7)")
    p.add_argument(
        "--accounts",
        type=str,
        default="",
        help="Comma-separated LINKED_ACCOUNTs to filter (12 digits). If omitted, use CE_ACCOUNTS or auto-detect via STS.",
    )
    p.add_argument(
        "--regions",
        type=str,
        default="",
        help="Comma-separated CE regions to filter (e.g., us-east-1,ap-southeast-1). If empty, no region filter.",
    )
    p.add_argument("--batch-size", type=int, default=5000, help="DB upsert batch size (default: 5000)")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()

    acct_list = [a.strip() for a in args.accounts.split(",") if a.strip()] if args.accounts else None
    reg_list = [r.strip() for r in args.regions.split(",") if r.strip()] if args.regions else None

    run(
        days_back=args.days_back,
        overlap_days=args.overlap_days,
        accounts=acct_list,
        regions=reg_list,
        batch_size=args.batch_size,
    )
