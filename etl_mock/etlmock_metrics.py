"""
ETL (MOCK): Generate fake CloudWatch Metrics -> raw.metrics
Services: EC2, S3, RDS, Lambda
- สร้างข้อมูลจำลองสำหรับ services ที่เลือกผ่าน --services
- สร้างข้อมูลย้อนหลัง --hours-back
- Upsert idempotent ลง PK: (metric_ts, resource_id, metric_name, stat, period_seconds)
"""

from __future__ import annotations
from .cleaners import clean_metrics_df

import os
import json
import re
import hashlib
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Iterable, Optional, Tuple

# --- MOCK IMPORTS ---
import random
from faker import Faker
import numpy as np
# --- END MOCK IMPORTS ---

from .common import (
    upsert_many_metrics,
)

# ---------------------------
# Utilities
# ---------------------------

fake = Faker()

def h(*parts) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()

def is_12digits(acct: Optional[str]) -> bool:
    return bool(acct and re.fullmatch(r"\d{12}", acct))

def _acct() -> str:
    """ (MOCK) Get Account ID from env or generate one """
    env_acct = os.getenv("AWS_ACCOUNT_ID")
    if is_12digits(env_acct):
        return env_acct
    return os.getenv("MOCK_AWS_ACCOUNT_ID", "123456789012") # <-- Mock Account

def _region_default() -> str:
    return os.getenv("AWS_DEFAULT_REGION", "us-east-1")

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def env_list(name: str) -> List[str]:
    raw = os.getenv(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []

# ... (ฟังก์ชัน normalize_metric_row คงไว้เหมือนเดิม) ...
def normalize_metric_row(r: Dict) -> Dict:
    r["account_id"] = r.get("account_id") or _acct() or "unknown"
    r["region"]     = r.get("region") or _region_default()
    r["resource_id"] = r.get("resource_id") or "unknown"
    r["service"]    = r.get("service") or "UnknownService"
    r["namespace"]  = r.get("namespace") or "Unknown/Namespace"
    r["metric_name"]= r.get("metric_name") or "UnknownMetric"
    r["stat"]       = r.get("stat") or "Average"
    r["period_seconds"] = int(r.get("period_seconds") or 60)
    r["metric_value"]   = float(r.get("metric_value") or 0.0)
    r["unit"]      = r.get("unit")
    dims = r.get("dimensions")
    if isinstance(dims, dict):
        r["dimensions"] = json.dumps(dims)
    elif dims is None:
        r["dimensions"] = json.dumps({})
    if not r.get("source_hash"):
        r["source_hash"] = h(
            r["metric_ts"], r["resource_id"], r["metric_name"], r["stat"], r["period_seconds"], r["metric_value"]
        )
    return r

# ---------------------------
# (MOCK) EC2
# ---------------------------

# นี่คือทรัพยากรจำลองของเรา
# (สำคัญ!) เราสร้าง "idle" instance ไว้ 1 ตัว เพื่อให้ Rule-Engine ของเราตรวจจับได้
MOCK_EC2_INSTANCES = [
    {"Id": fake.bothify(text='i-prod-?????????????????'), "Region": "us-east-1", "Idle": False},
    {"Id": fake.bothify(text='i-idle-?????????????????'), "Region": "us-east-1", "Idle": True}
]

def fetch_ec2_metrics(period: int, hours_back: int) -> List[Dict]:
    print(f"--- MOCK ETL: Generating mock EC2 metrics for {hours_back} hours ---")
    rows: List[Dict] = []
    end = _now_utc()
    start = end - timedelta(hours=hours_back)
    
    current_ts = start
    timestamps = []
    while current_ts < end:
        timestamps.append(current_ts)
        current_ts += timedelta(seconds=period)
    
    if not timestamps: return []

    for inst in MOCK_EC2_INSTANCES:
        # สร้าง Sine wave + Noise เพื่อให้กราฟดู "จริง"
        base_cpu = random.uniform(0.5, 2.0) if inst["Idle"] else random.uniform(20.0, 40.0)
        cpu_noise = np.random.normal(0, 0.5, len(timestamps))
        cpu_wave = base_cpu + (base_cpu * 0.5 * np.sin(np.linspace(0, 4 * np.pi, len(timestamps))))
        
        net_noise = np.random.normal(1, 0.2, len(timestamps))
        net_base = 1e3 if inst["Idle"] else 5e7

        for i, ts in enumerate(timestamps):
            # Metric 1: CPU
            cpu_val = max(0.1, cpu_wave[i] + cpu_noise[i]) # ป้องกันติดลบ
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": inst["Id"], "service": "EC2", "namespace": "AWS/EC2",
                "metric_name": "CPUUtilization", "stat": "Average", "period_seconds": period,
                "metric_value": cpu_val, "unit": "Percent", "dimensions": {"InstanceId": inst["Id"]},
            }))
            
            # Metric 2: NetworkOut
            net_val = max(0, (net_base * np.sin(np.linspace(0, 2 * np.pi, len(timestamps)))[i]**2) * net_noise[i])
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": inst["Id"], "service": "EC2", "namespace": "AWS/EC2",
                "metric_name": "NetworkOut", "stat": "Sum", "period_seconds": period,
                "metric_value": net_val, "unit": "Bytes", "dimensions": {"InstanceId": inst["Id"]},
            }))
    return rows

# ---------------------------
# (MOCK) S3
# ---------------------------

def fetch_s3_bucket_size(bucket: str, period_seconds: int = 86400, region: Optional[str] = None) -> List[Dict]:
    print(f"--- MOCK ETL: Generating mock S3 metrics for bucket {bucket} ---")
    rows: List[Dict] = []
    end = _now_utc().replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=90) # สร้างข้อมูล S3 ย้อนหลัง 90 วัน
    
    current_ts = start
    base_size = random.uniform(1e9, 5e9) # 1-5 GB

    while current_ts < end:
        # จำลอง S3 Bucket ที่ค่อยๆ โตขึ้น
        days_diff = (end - current_ts).days
        val = base_size * (1 + (90 - days_diff) * 0.01) # โตวันละ 1%
        
        rows.append(normalize_metric_row({
            "metric_ts": current_ts, "resource_id": bucket, "service": "S3", "namespace": "AWS/S3",
            "metric_name": "BucketSizeBytes", "stat": "Average", "period_seconds": period_seconds,
            "metric_value": val, "unit": "Bytes", "dimensions": {"BucketName": bucket, "StorageType":"StandardStorage"},
        }))
        current_ts += timedelta(days=1) # S3 Metric เป็นรายวัน
    return rows

# ---------------------------
# (MOCK) RDS
# ---------------------------

MOCK_RDS_INSTANCES = [
    {"Id": fake.bothify(text='db-prod-????????'), "Region": "ap-southeast-1"},
    {"Id": fake.bothify(text='db-dev-????????'), "Region": "ap-southeast-1"}
]

def fetch_rds_core_metrics(period: int, hours_back: int) -> List[Dict]:
    print(f"--- MOCK ETL: Generating mock RDS metrics for {hours_back} hours ---")
    rows: List[Dict] = []
    end = _now_utc()
    start = end - timedelta(hours=hours_back)
    
    current_ts = start
    timestamps = []
    while current_ts < end:
        timestamps.append(current_ts)
        current_ts += timedelta(seconds=period)
    
    if not timestamps: return []

    for db in MOCK_RDS_INSTANCES:
        for ts in timestamps:
            # CPU
            cpu_val = random.uniform(10.0, 50.0)
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": db["Id"], "service": "RDS", "namespace": "AWS/RDS",
                "metric_name": "CPUUtilization", "stat": "Average", "period_seconds": period,
                "metric_value": cpu_val, "unit": "Percent", "dimensions": {"DBInstanceIdentifier": db["Id"]},
            }))
            # Connections
            conn_val = random.randint(5, 50)
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": db["Id"], "service": "RDS", "namespace": "AWS/RDS",
                "metric_name": "DatabaseConnections", "stat": "Average", "period_seconds": period,
                "metric_value": conn_val, "unit": "Count", "dimensions": {"DBInstanceIdentifier": db["Id"]},
            }))
            # Storage
            storage_val = random.uniform(1e10, 2e10) # 10-20 GB free
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": db["Id"], "service": "RDS", "namespace": "AWS/RDS",
                "metric_name": "FreeStorageSpace", "stat": "Minimum", "period_seconds": period,
                "metric_value": storage_val, "unit": "Bytes", "dimensions": {"DBInstanceIdentifier": db["Id"]},
            }))
    return rows

# ---------------------------
# (MOCK) Lambda
# ---------------------------

MOCK_LAMBDA_FUNCTIONS = [
    {"Arn": f"arn:aws:lambda:us-east-1:{_acct()}:function:mock-func-1", "Name": "mock-func-1"},
    {"Arn": f"arn:aws:lambda:us-east-1:{_acct()}:function:mock-func-2", "Name": "mock-func-2"}
]

def fetch_lambda_metrics(period: int, hours_back: int) -> List[Dict]:
    print(f"--- MOCK ETL: Generating mock Lambda metrics for {hours_back} hours ---")
    rows: List[Dict] = []
    end = _now_utc()
    start = end - timedelta(hours=hours_back)

    current_ts = start
    timestamps = []
    while current_ts < end:
        timestamps.append(current_ts)
        current_ts += timedelta(seconds=period)
    
    if not timestamps: return []

    for fn in MOCK_LAMBDA_FUNCTIONS:
        for ts in timestamps:
            # Duration
            dur_val = random.uniform(150.0, 1000.0) # 150-1000 ms
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": fn["Arn"], "service": "Lambda", "namespace": "AWS/Lambda",
                "metric_name": "Duration", "stat": "p95", "period_seconds": period,
                "metric_value": dur_val, "unit": "Milliseconds", "dimensions": {"FunctionName": fn["Name"]},
            }))
            # Invocations
            inv_val = random.randint(0, 20) # 0-20 invocations per period
            rows.append(normalize_metric_row({
                "metric_ts": ts, "resource_id": fn["Arn"], "service": "Lambda", "namespace": "AWS/Lambda",
                "metric_name": "Invocations", "stat": "Sum", "period_seconds": period,
                "metric_value": inv_val, "unit": "Count", "dimensions": {"FunctionName": fn["Name"]},
            }))
    return rows

# ---------------------------
# Driver (เหมือนเดิม)
# ---------------------------

def run(services: List[str], hours_back: int = 24, period: int = 300,
        s3_buckets: Optional[List[str]] = None, batch_size: int = 5000) -> None:
    services = [s.lower().strip() for s in services]
    all_rows: List[Dict] = []

    print(f"--- MOCK ETL: Starting metric generation for services: {services} ---")

    if "ec2" in services:
        all_rows += fetch_ec2_metrics(period=period, hours_back=hours_back)

    if "s3" in services:
        # S3 ต้องมีชื่อ Bucket
        buckets = s3_buckets if s3_buckets is not None else env_list("S3_BUCKETS")
        if not buckets:
            print("--- MOCK ETL: S3 specified, but no buckets found in --s3-buckets or S3_BUCKETS env. Skipping S3.")
        for b in buckets:
            all_rows += fetch_s3_bucket_size(bucket=b, period_seconds=86400)

    if "rds" in services:
        all_rows += fetch_rds_core_metrics(period=period, hours_back=hours_back)

    if "lambda" in services:
        lam_period = min(period, 60) # Lambda period มักจะสั้น
        all_rows += fetch_lambda_metrics(period=lam_period, hours_back=hours_back)

    # --- ทำความสะอาดและบันทึก ---
    df = clean_metrics_df(all_rows)
    records = df.to_dict(orient="records")

    if not records:
        print("[etl_metrics] no MOCK rows generated.")
        return

    total = 0
    for i in range(0, len(records), batch_size):
        # เราจะต้องการฟังก์ชันนี้ใน common.py
        upsert_many_metrics(records[i:i+batch_size])
        total += min(batch_size, len(records) - i)
    print(f"[etl_metrics] upserted {total} MOCK rows into raw.metrics")


# ---------------------------
# CLI (เหมือนเดิม)
# ---------------------------
def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL (MOCK): CloudWatch -> raw.metrics")
    p.add_argument("--services", type=str, default="ec2,s3,rds,lambda",
                   help="comma-separated: ec2,s3,rds,lambda (default: all)")
    p.add_argument("--hours-back", type=int, default=72, help="how many hours back (default: 72)") # <-- เพิ่มเป็น 3 วัน
    p.add_argument("--period", type=int, default=3600, help="metric period seconds (default: 3600)") # <-- เพิ่มเป็น 1 ชม.
    p.add_argument("--s3-buckets", type=str, default="",
                   help="comma-separated bucket names (override S3_BUCKETS env)")
    p.add_argument("--batch-size", type=int, default=5000, help="DB upsert batch size (default: 5000)")
    return p.parse_args(argv)

if __name__ == "__main__":
    args = _parse_args()
    svc = [s for s in args.services.split(",") if s.strip()]
    s3b = [b for b in args.s3_buckets.split(",") if b.strip()] if args.s3_buckets else None

    run(
        services=svc,
        hours_back=args.hours_back,
        period=args.period,
        s3_buckets=s3b,
        batch_size=args.batch_size,
    )
