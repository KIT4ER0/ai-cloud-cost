# etl/etl_metrics.py
"""
ETL: CloudWatch Metrics -> raw.metrics
Services: EC2, S3, RDS, Lambda
- เลือกบริการผ่าน --services (เช่น ec2,s3,lambda)
- ปรับระยะเวลา --hours-back และคาบ --period
- Account ID auto-detect (STS) หากไม่ระบุ
- Upsert idempotent ลง PK: (metric_ts, resource_id, metric_name, stat, period_seconds)
"""

from __future__ import annotations
from etl.cleaners import clean_metrics_df

import os
import json
import re
import hashlib
import argparse
import datetime
from typing import List, Dict, Iterable, Optional, Tuple

from etl.common import (
    boto_client,
    cw_get_metric_data,
    upsert_many_metrics,
)

# ---------------------------
# Utilities
# ---------------------------

def h(*parts) -> str:
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()

def is_12digits(acct: Optional[str]) -> bool:
    return bool(acct and re.fullmatch(r"\d{12}", acct))

def get_sts_account_id() -> str:
    try:
        sts = boto_client("sts")
        acct = sts.get_caller_identity()["Account"]
        return acct if is_12digits(acct) else "unknown"
    except Exception:
        return "unknown"

def env_list(name: str) -> List[str]:
    raw = os.getenv(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []

def batches(seq: List, size: int) -> Iterable[List]:
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

def _acct() -> str:
    env_acct = os.getenv("AWS_ACCOUNT_ID")
    if is_12digits(env_acct):
        return env_acct
    return get_sts_account_id()

def _region_default() -> str:
    return os.getenv("AWS_DEFAULT_REGION", "us-east-1")

def _now_utc() -> datetime.datetime:
    return datetime.datetime.utcnow()

# ป้องกัน None ให้มีค่า default เสมอก่อน upsert
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
    # source_hash ถ้ายังไม่มี ให้คำนวน
    if not r.get("source_hash"):
        r["source_hash"] = h(
            r["metric_ts"], r["resource_id"], r["metric_name"], r["stat"], r["period_seconds"], r["metric_value"]
        )
    return r

# ---------------------------
# EC2
# ---------------------------

def list_ec2_instance_ids() -> List[str]:
    ec2 = boto_client("ec2")
    ids, token = [], None
    while True:
        kwargs = {} if token is None else {"NextToken": token}
        resp = ec2.describe_instances(**kwargs)
        for res in resp.get("Reservations", []):
            for inst in res.get("Instances", []):
                if inst.get("State", {}).get("Name") in ("running", "stopped", "stopping", "pending"):
                    ids.append(inst["InstanceId"])
        token = resp.get("NextToken")
        if not token:
            break
    return ids

def fetch_ec2_metrics(period: int, hours_back: int) -> List[Dict]:
    cw = boto_client("cloudwatch")
    end = _now_utc()
    start = end - datetime.timedelta(hours=hours_back)

    ids = list_ec2_instance_ids()
    if not ids:
        return []

    rows: List[Dict] = []
    # 1 instance -> 2 queries (CPU avg, NetworkOut sum)
    # Limit CloudWatch GetMetricData: 500 queries ต่อ request; ใช้ batch 200 ชิลๆ
    BATCH = 200 // 2

    for i in range(0, len(ids), BATCH):
        batch_ids = ids[i:i+BATCH]
        queries = []
        for idx, inst in enumerate(batch_ids):
            # CPUUtilization Average
            queries.append({
                "Id": f"cpu{idx}",
                "MetricStat": {
                    "Metric": {
                        "Namespace": "AWS/EC2",
                        "MetricName": "CPUUtilization",
                        "Dimensions": [{"Name":"InstanceId","Value":inst}],
                    },
                    "Period": period, "Stat":"Average"
                },
                "ReturnData": True
            })
            # NetworkOut Sum
            queries.append({
                "Id": f"nout{idx}",
                "MetricStat": {
                    "Metric": {
                        "Namespace":"AWS/EC2",
                        "MetricName":"NetworkOut",
                        "Dimensions":[{"Name":"InstanceId","Value":inst}],
                    },
                    "Period": period, "Stat":"Sum"
                },
                "ReturnData": True
            })

        resp = cw_get_metric_data(
            cw,
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending"
        )

        for series in resp.get("MetricDataResults", []):
            sid = series["Id"]
            base = "".join([c for c in sid if not c.isdigit()])
            idxs = "".join([c for c in sid if c.isdigit()])
            if not idxs.isdigit():
                continue
            inst = batch_ids[int(idxs)]
            metric_name, stat, unit = ("CPUUtilization","Average","Percent") if base=="cpu" else ("NetworkOut","Sum","Bytes")

            for ts, val in zip(series.get("Timestamps",[]), series.get("Values",[])):
                rows.append(normalize_metric_row({
                    "metric_ts": ts,
                    "account_id": _acct(),
                    "region": _region_default(),
                    "resource_id": inst,
                    "service": "EC2",
                    "namespace": "AWS/EC2",
                    "metric_name": metric_name,
                    "stat": stat,
                    "period_seconds": period,
                    "metric_value": float(val),
                    "unit": unit,
                    "dimensions": {"InstanceId": inst},
                }))

    return rows

# ---------------------------
# S3
# ---------------------------

def fetch_s3_bucket_size(bucket: str, period_seconds: int = 86400, region: Optional[str] = None) -> List[Dict]:
    # S3 storage metrics ส่วนใหญ่ใช้ period 1 วัน (86400)
    cw = boto_client("cloudwatch", region=region or _region_default())
    end = _now_utc()
    start = end - datetime.timedelta(days=3)

    resp = cw_get_metric_data(
        cw,
        MetricDataQueries=[{
            "Id":"bsize",
            "MetricStat":{
                "Metric":{
                    "Namespace":"AWS/S3",
                    "MetricName":"BucketSizeBytes",
                    "Dimensions":[
                        {"Name":"BucketName","Value":bucket},
                        {"Name":"StorageType","Value":"StandardStorage"},
                    ],
                },
                "Period": period_seconds,
                "Stat":"Average"
            },
            "ReturnData": True
        }],
        StartTime=start,
        EndTime=end,
        ScanBy="TimestampAscending"
    )

    rows: List[Dict] = []
    for ts, val in zip(resp.get("MetricDataResults",[{}])[0].get("Timestamps",[]),
                       resp.get("MetricDataResults",[{}])[0].get("Values",[])):
        rows.append(normalize_metric_row({
            "metric_ts": ts,
            "account_id": _acct(),
            "region": region or _region_default(),
            "resource_id": bucket,
            "service": "S3",
            "namespace": "AWS/S3",
            "metric_name": "BucketSizeBytes",
            "stat": "Average",
            "period_seconds": period_seconds,
            "metric_value": float(val),
            "unit": "Bytes",
            "dimensions": {"BucketName": bucket, "StorageType":"StandardStorage"},
        }))
    return rows

# ---------------------------
# RDS
# ---------------------------

def list_rds_instances() -> List[str]:
    rds = boto_client("rds")
    ids: List[str] = []
    for page in rds.get_paginator("describe_db_instances").paginate():
        for db in page.get("DBInstances", []):
            ids.append(db["DBInstanceIdentifier"])
    return ids

def fetch_rds_core_metrics(period: int, hours_back: int) -> List[Dict]:
    cw = boto_client("cloudwatch")
    end = _now_utc()
    start = end - datetime.timedelta(hours=hours_back)

    ids = list_rds_instances()
    if not ids:
        return []

    rows: List[Dict] = []
    # ต่อ 1 DB instance: 3 metrics
    BATCH = max(1, 500 // 3)

    for i in range(0, len(ids), BATCH):
        batch = ids[i:i+BATCH]
        queries = []
        for idx, dbid in enumerate(batch):
            for name, stat in [("CPUUtilization","Average"),
                               ("DatabaseConnections","Average"),
                               ("FreeStorageSpace","Minimum")]:
                queries.append({
                    "Id": f"m{idx}_{name}",
                    "MetricStat":{
                        "Metric":{
                            "Namespace":"AWS/RDS",
                            "MetricName": name,
                            "Dimensions":[{"Name":"DBInstanceIdentifier","Value": dbid}],
                        },
                        "Period": period, "Stat": stat
                    },
                    "ReturnData": True
                })

        resp = cw_get_metric_data(
            cw,
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending"
        )

        for series in resp.get("MetricDataResults", []):
            sid = series["Id"]              # m{idx}_{MetricName}
            idx = sid.split("_")[0][1:]
            mname = sid.split("_",1)[1]
            if not idx.isdigit() or int(idx) >= len(batch):
                continue
            dbid = batch[int(idx)]
            unit = "Percent" if mname=="CPUUtilization" else ("Count" if mname=="DatabaseConnections" else "Bytes")
            stat = "Average" if mname in ("CPUUtilization","DatabaseConnections") else "Minimum"

            for ts, val in zip(series.get("Timestamps",[]), series.get("Values",[])):
                rows.append(normalize_metric_row({
                    "metric_ts": ts,
                    "account_id": _acct(),
                    "region": _region_default(),
                    "resource_id": dbid,
                    "service": "RDS",
                    "namespace": "AWS/RDS",
                    "metric_name": mname,
                    "stat": stat,
                    "period_seconds": period,
                    "metric_value": float(val),
                    "unit": unit,
                    "dimensions": {"DBInstanceIdentifier": dbid},
                }))
    return rows

# ---------------------------
# Lambda
# ---------------------------

def list_lambda_functions() -> List[str]:
    lam = boto_client("lambda")
    arns: List[str] = []
    marker = None
    while True:
        kwargs = {} if marker is None else {"Marker": marker}
        resp = lam.list_functions(**kwargs)
        for f in resp.get("Functions", []):
            arns.append(f["FunctionArn"])
        marker = resp.get("NextMarker")
        if not marker:
            break
    return arns

def fetch_lambda_metrics(period: int, hours_back: int) -> List[Dict]:
    cw = boto_client("cloudwatch")
    end = _now_utc()
    start = end - datetime.timedelta(hours=hours_back)

    fns = list_lambda_functions()
    if not fns:
        return []

    rows: List[Dict] = []
    # ต่อ 1 function: 2 metrics (Duration p95, Invocations Sum)
    BATCH = max(1, 500 // 2)

    for i in range(0, len(fns), BATCH):
        batch = fns[i:i+BATCH]
        queries = []
        for idx, arn in enumerate(batch):
            fn = arn.split(":")[-1]
            # Duration p95 (หากบัญชีไม่รองรับ p95 จะต้องเปลี่ยนเป็น Average)
            queries.append({
                "Id": f"dur{idx}",
                "MetricStat":{
                    "Metric":{
                        "Namespace":"AWS/Lambda",
                        "MetricName":"Duration",
                        "Dimensions":[{"Name":"FunctionName","Value": fn}],
                    },
                    "Period": period, "Stat":"p95"
                },
                "ReturnData": True
            })
            # Invocations Sum
            queries.append({
                "Id": f"inv{idx}",
                "MetricStat":{
                    "Metric":{
                        "Namespace":"AWS/Lambda",
                        "MetricName":"Invocations",
                        "Dimensions":[{"Name":"FunctionName","Value": fn}],
                    },
                    "Period": period, "Stat":"Sum"
                },
                "ReturnData": True
            })

        resp = cw_get_metric_data(
            cw,
            MetricDataQueries=queries,
            StartTime=start,
            EndTime=end,
            ScanBy="TimestampAscending"
        )

        for series in resp.get("MetricDataResults", []):
            sid = series["Id"]
            base = "".join([c for c in sid if not c.isdigit()])
            idxs = "".join([c for c in sid if c.isdigit()])
            if not idxs.isdigit() or int(idxs) >= len(batch):
                continue
            arn = batch[int(idxs)]
            fn = arn.split(":")[-1]
            metric_name, stat, unit = ("Duration","p95","Milliseconds") if base=="dur" else ("Invocations","Sum","Count")

            for ts, val in zip(series.get("Timestamps",[]), series.get("Values",[])):
                rows.append(normalize_metric_row({
                    "metric_ts": ts,
                    "account_id": _acct(),
                    "region": _region_default(),
                    "resource_id": arn,
                    "service": "Lambda",
                    "namespace": "AWS/Lambda",
                    "metric_name": metric_name,
                    "stat": stat,
                    "period_seconds": period,
                    "metric_value": float(val),
                    "unit": unit,
                    "dimensions": {"FunctionName": fn},
                }))
    return rows

# ---------------------------
# Driver
# ---------------------------

def run(services: List[str], hours_back: int = 24, period: int = 300,
        s3_buckets: Optional[List[str]] = None, batch_size: int = 5000) -> None:
    services = [s.lower().strip() for s in services]
    all_rows: List[Dict] = []

    if "ec2" in services:
        all_rows += fetch_ec2_metrics(period=period, hours_back=hours_back)

    if "s3" in services:
        buckets = s3_buckets if s3_buckets is not None else env_list("S3_BUCKETS")
        for b in buckets:
            all_rows += fetch_s3_bucket_size(bucket=b, period_seconds=86400)

    if "rds" in services:
        all_rows += fetch_rds_core_metrics(period=period, hours_back=hours_back)

    if "lambda" in services:
        lam_period = min(period, 60)
        all_rows += fetch_lambda_metrics(period=lam_period, hours_back=hours_back)

    # 🔽🔽 ใส่บล็อกนี้ 🔽🔽
    df = clean_metrics_df(all_rows)
    records = df.to_dict(orient="records")

    if not records:
        print("[etl_metrics] no rows fetched.")
        return

    total = 0
    for i in range(0, len(records), batch_size):
        upsert_many_metrics(records[i:i+batch_size])
        total += min(batch_size, len(records) - i)
    print(f"[etl_metrics] upserted {total} rows")


# ---------------------------
# CLI
# ---------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL: CloudWatch -> raw.metrics")
    p.add_argument("--services", type=str, default="ec2,s3,rds,lambda",
                   help="comma-separated: ec2,s3,rds,lambda (default: all)")
    p.add_argument("--hours-back", type=int, default=24, help="how many hours back (default: 24)")
    p.add_argument("--period", type=int, default=300, help="metric period seconds (default: 300)")
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
