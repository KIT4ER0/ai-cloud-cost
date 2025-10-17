# etl/etl_features.py
from __future__ import annotations

import os
from typing import Dict, List, Optional
from functools import reduce

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from dotenv import load_dotenv

from etl.common import upsert_many_features, db_url

load_dotenv()

# ---------- DB helpers ----------
def engine() -> Engine:
    return create_engine(db_url(), future=True)

def read_metrics(days_back: int = 30,
                 services: Optional[List[str]] = None) -> pd.DataFrame:
    """
    ดึง raw.metrics ช่วง N วันล่าสุด (เลือก service ได้)
    """
    svc_filter = ""
    if services:
        # ป้องกัน SQL injection แบบง่าย — จำกัดให้เป็นตัวอักษร/ตัวเลข/ขีดล่าง
        svcs = [s for s in services if s and s.replace("_","").isalnum()]
        if svcs:
            inlist = ", ".join([f"'{s}'" for s in svcs])
            svc_filter = f"AND service IN ({inlist})"
    sql = f"""
    SET TIME ZONE 'UTC';
    SELECT metric_ts, account_id, region, resource_id, service, namespace,
           metric_name, stat, period_seconds, metric_value, unit
    FROM raw.metrics
    WHERE metric_ts >= NOW() - INTERVAL '{int(days_back)} days'
      {svc_filter};
    """
    with engine().begin() as conn:
        df = pd.read_sql(sql, conn, parse_dates=["metric_ts"])
    return df

# ---------- Aggregations (daily per resource) ----------
def to_daily_parts(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if df.empty:
        return {}

    # ทำวันที่ (UTC)
    if df["metric_ts"].dt.tz is None:
        df["metric_ts"] = df["metric_ts"].dt.tz_localize("UTC")
    feature_date = df["metric_ts"].dt.tz_convert("UTC").dt.date
    df = df.assign(feature_date=feature_date)

    parts: Dict[str, pd.DataFrame] = {}

    # --- EC2 ---
    m = (df["service"] == "EC2") & (df["metric_name"] == "CPUUtilization") & (df["stat"] == "Average")
    if m.any():
        ec2_cpu = (
            df[m]
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .quantile(0.95)
            .reset_index()
            .rename(columns={"metric_value": "cpu_p95"})
        )
        parts["ec2_cpu"] = ec2_cpu

    m = (df["service"] == "EC2") & (df["metric_name"] == "NetworkOut")
    if m.any():
        ec2_net = df[m].copy()
        # Bytes/Second → ปริมาณข้อมูลช่วงนั้น = value * period_seconds
        bps = ec2_net["unit"].str.lower().eq("bytes/second")
        ec2_net.loc[bps, "metric_value"] = ec2_net.loc[bps, "metric_value"] * ec2_net.loc[bps, "period_seconds"]
        # Bytes → GB
        is_bytes = ec2_net["unit"].str.lower().eq("bytes")
        ec2_net.loc[is_bytes | bps, "metric_value"] = ec2_net.loc[is_bytes | bps, "metric_value"] / (1024 ** 3)
        ec2_net_gb = (
            ec2_net
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .sum().reset_index()
            .rename(columns={"metric_value": "network_gb"})
        )
        parts["ec2_net_gb"] = ec2_net_gb

    # --- S3 ---
    m = (df["service"] == "S3") & (df["metric_name"] == "BucketSizeBytes")
    if m.any():
        s3 = df[m].copy()
        # Bytes → GB (ถ้ายังไม่แปลงตั้งแต่ขั้น clean)
        is_bytes = s3["unit"].str.contains("byte", case=False, na=False)
        s3.loc[is_bytes, "metric_value"] = s3.loc[is_bytes, "metric_value"] / (1024 ** 3)
        s3_storage = (
            s3.groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
              .mean().reset_index()
              .rename(columns={"metric_value": "storage_gb"})
        )
        parts["s3_storage"] = s3_storage

    # --- RDS ---
    m = (df["service"] == "RDS") & (df["metric_name"] == "CPUUtilization")
    if m.any():
        rds_cpu = (
            df[m]
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .quantile(0.95)
            .reset_index()
            .rename(columns={"metric_value": "rds_cpu_p95"})
        )
        parts["rds_cpu"] = rds_cpu

    m = (df["service"] == "RDS") & (df["metric_name"] == "DatabaseConnections")
    if m.any():
        rds_conn = (
            df[m]
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .mean().reset_index()
            .rename(columns={"metric_value": "rds_conn_avg"})
        )
        parts["rds_conn"] = rds_conn

    m = (df["service"] == "RDS") & (df["metric_name"] == "FreeStorageSpace")
    if m.any():
        rds_free = df[m].copy()
        is_bytes = rds_free["unit"].str.contains("byte", case=False, na=False)
        rds_free.loc[is_bytes, "metric_value"] = rds_free.loc[is_bytes, "metric_value"] / (1024 ** 3)
        rds_free_min = (
            rds_free
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .min().reset_index()
            .rename(columns={"metric_value": "rds_free_storage_gb_min"})
        )
        parts["rds_free"] = rds_free_min

    # --- Lambda ---
    m = (df["service"] == "Lambda") & (df["metric_name"] == "Duration")  # หน่วยมักเป็น ms
    if m.any():
        lam_dur = (
            df[m]
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .quantile(0.95).reset_index()
            .rename(columns={"metric_value": "lambda_duration_p95_ms"})
        )
        parts["lam_dur"] = lam_dur

    m = (df["service"] == "Lambda") & (df["metric_name"] == "Invocations") & (df["stat"] == "Sum")
    if m.any():
        lam_inv = (
            df[m]
            .groupby(["feature_date", "account_id", "region", "resource_id"])["metric_value"]
            .sum().reset_index()
            .rename(columns={"metric_value": "lambda_invocations"})
        )
        parts["lam_inv"] = lam_inv

    return parts

def merge_parts(parts: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    keys = ["feature_date", "account_id", "region", "resource_id"]
    frames = [v for v in parts.values() if isinstance(v, pd.DataFrame) and not v.empty]
    if not frames:
        # โครงคอลัมน์ว่างพร้อม upsert
        return pd.DataFrame(columns=keys + [
            "cpu_p95", "network_gb", "storage_gb",
            "rds_cpu_p95", "rds_conn_avg", "rds_free_storage_gb_min",
            "lambda_duration_p95_ms", "lambda_invocations",
            "service", "usage_type"
        ])
    def _merge(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
        return pd.merge(a, b, on=keys, how="outer")
    merged = reduce(_merge, frames)

    # เดา service แบบ heuristic จาก resource_id (ถ้ามี mapping ที่ดีกว่า แทนที่ได้)
    merged["service"] = None
    rid = merged["resource_id"].astype(str)
    merged.loc[rid.str.startswith("i-"), "service"] = "EC2"
    merged.loc[rid.str.contains("lambda", case=False, na=False), "service"] = "Lambda"
    merged.loc[rid.str.contains("rds", case=False, na=False), "service"] = "RDS"
    # S3: bucket name (มักไม่ใช่ ARN / ไม่ขึ้นต้นด้วย i-)
    merged.loc[
        (~rid.str.startswith("i-")) & (~rid.str.contains("arn:", na=False)) & merged["service"].isna(),
        "service"
    ] = "S3"

    merged["usage_type"] = None
    return merged

def upsert_features(df: pd.DataFrame, batch_size: int = 5000, dry_run: bool = False) -> None:
    if df.empty:
        print("[etl_features] no rows to upsert.")
        return
    # เตรียมคอลัมน์ให้ครบ
    cols = [
        "feature_date","account_id","region","service","resource_id","usage_type",
        "cpu_p95","storage_gb","network_gb",
        "lambda_duration_p95_ms","lambda_invocations",
        "rds_cpu_p95","rds_conn_avg","rds_free_storage_gb_min",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    records = df[cols].where(pd.notnull(df), None).to_dict(orient="records")

    if dry_run:
        print(f"[etl_features][dry-run] prepared {len(records)} rows (not inserted).")
        # แสดงตัวอย่าง 5 แถว
        print(df[cols].head())
        return

    total = 0
    for i in range(0, len(records), batch_size):
        upsert_many_features(records[i:i+batch_size])
        total += min(batch_size, len(records) - i)
    print(f"[etl_features] upserted {total} rows into core.features")

# ---------- CLI ----------
def run(days_back: int = 30,
        services: Optional[List[str]] = None,
        batch_size: int = 5000,
        dry_run: bool = False) -> None:
    print(f"[etl_features] start days_back={days_back} services={services or 'ALL'}")
    dfm = read_metrics(days_back=days_back, services=services)
    if dfm.empty:
        print("[etl_features] no metrics found in the selected window.")
        return
    parts = to_daily_parts(dfm)
    merged = merge_parts(parts)
    upsert_features(merged, batch_size=batch_size, dry_run=dry_run)

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Aggregate raw.metrics → core.features (daily).")
    p.add_argument("--days-back", type=int, default=int(os.getenv("FEATURE_DAYS_BACK", "30")))
    p.add_argument("--services", type=str, default="",
                   help="comma-separated services filter: ec2,s3,rds,lambda")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true", help="do not write to DB; print sample instead")
    args = p.parse_args()

    svcs = [s.strip() for s in args.services.split(",") if s.strip()] if args.services else None
    run(days_back=args.days_back, services=svcs, batch_size=args.batch_size, dry_run=args.dry_run)
