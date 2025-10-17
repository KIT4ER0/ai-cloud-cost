# etl/etl_recommendations.py
from __future__ import annotations
import os
import sys
import json
import argparse
from datetime import date, timedelta
from typing import List, Dict, Optional

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# ---------------------------
# DB utils
# ---------------------------
def db_url() -> str:
    override = os.getenv("DATABASE_URL")
    if override:
        return override
    host = os.getenv("DB_HOST", "localhost")
    port_raw = os.getenv("DB_PORT", "5432")
    port = (str(port_raw).strip() or "5432")
    name = os.getenv("DB_NAME", "ai_cost")
    user = os.getenv("DB_USER", "ai_user")
    pwd  = os.getenv("DB_PASSWORD", "ai_password")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

def get_engine():
    return create_engine(db_url(), pool_pre_ping=True)

def table_exists(engine, schema: str, name: str) -> bool:
    sql = """
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = :schema AND table_name = :name
    """
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"schema": schema, "name": name}).fetchone()
        return bool(row)

def upsert_recommendations(engine, rows: List[Dict], dry_run: bool = False):
    """
    rows: dict keys:
      rec_date, account_id, region, service, resource_id,
      rec_type, details (dict), est_saving_usd (nullable), confidence (nullable numeric)
    """
    if not rows:
        print("[recs] nothing to write.")
        return
    # convert details dict -> JSON string
    rows = [
        {
            **r,
            "details": json.dumps(r.get("details", {}) if r.get("details") is not None else {})
        }
        for r in rows
    ]
    sql = text("""
        INSERT INTO core.recommendations
          (rec_date, account_id, region, service, resource_id,
           rec_type, details, est_saving_usd, confidence)
        VALUES
          (:rec_date, :account_id, :region, :service, :resource_id,
           :rec_type, CAST(:details AS JSONB), :est_saving_usd, :confidence)
        ON CONFLICT (rec_date, account_id, region, service, resource_id, rec_type)
        DO UPDATE SET
           details        = EXCLUDED.details,
           est_saving_usd = EXCLUDED.est_saving_usd,
           confidence     = EXCLUDED.confidence,
           ingested_at    = NOW();
    """)
    if dry_run:
        print(f"[dry-run] would upsert {len(rows)} recommendations.")
        return
    with engine.begin() as conn:
        conn.execute(sql, rows)
    print(f"[recs] upserted {len(rows)} recommendations.")

# ---------------------------
# Load helpers
# ---------------------------
def load_features(engine, start_d: date, end_d: date, service: Optional[str] = None) -> pd.DataFrame:
    params = {"start": start_d, "end": end_d}
    where = "WHERE feature_date BETWEEN :start AND :end"
    if service:
        where += " AND service = :service"
        params["service"] = service
    sql = f"""
        SELECT feature_date, account_id, region, service, resource_id,
               cpu_p95, network_gb, storage_gb,
               lambda_duration_p95_ms, lambda_invocations,
               rds_cpu_p95, rds_conn_avg, rds_free_storage_gb_min
        FROM core.features
        {where}
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

def load_mart(engine, start_d: date, end_d: date, service: Optional[str] = None) -> pd.DataFrame:
    params = {"start": start_d, "end": end_d}
    where = "WHERE feature_date BETWEEN :start AND :end"
    if service:
        where += " AND service = :service"
        params["service"] = service
    sql = f"""
        SELECT feature_date, account_id, region, service, resource_id,
               amount_usd,
               cpu_p95, network_gb, storage_gb,
               lambda_duration_p95_ms, lambda_invocations,
               rds_cpu_p95, rds_conn_avg, rds_free_storage_gb_min
        FROM mart.daily_cost_features
        {where}
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

# ---------------------------
# Rules (core set; optional sets check table availability)
# ---------------------------
def rule_ec2_rightsize_p95_low(engine, asof: date, days: int = 7,
                               cpu_threshold: float = 20.0) -> List[Dict]:
    """
    ใช้ core.features: EC2 CPU p95 < threshold ต่อเนื่อง 7 วัน
    ประมาณการประหยัดยังไม่คำนวณละเอียด (ตั้งเป็น NULL) หรือจะต่อยอดด้วย pricing ภายหลัง
    """
    start_d = asof - timedelta(days=days)
    df = load_features(engine, start_d, asof, service="EC2")
    if df.empty:
        return []
    g = (df.groupby(["account_id", "region", "resource_id"])
           .agg(cpu_p95_max7d=("cpu_p95", "max"))
           .reset_index())
    cand = g[g["cpu_p95_max7d"].fillna(999) < cpu_threshold]
    if cand.empty:
        return []
    rows = []
    for _, r in cand.iterrows():
        rows.append({
            "rec_date": asof,
            "account_id": r["account_id"],
            "region": r["region"],
            "service": "EC2",
            "resource_id": r["resource_id"],
            "rec_type": "EC2_RIGHTSIZE_P95_LOW",
            "details": {"cpu_p95_max7d": float(r["cpu_p95_max7d"]), "hint": "Low utilization 7d"},
            "est_saving_usd": None,
            "confidence": 0.8
        })
    return rows

def rule_s3_lifecycle_cold(engine, asof: date, days_cold: int = 60) -> List[Dict]:
    """
    ต้องมี inventory.s3_buckets(storage_class, last_access_at, size_gb)
    ถ้าไม่มีก็ข้าม
    """
    if not table_exists(engine, "inventory", "s3_buckets"):
        print("[recs] skip S3_LIFECYCLE_COLD (inventory.s3_buckets not found)")
        return []
    sql = """
      SELECT account_id, region, bucket AS resource_id, storage_class, size_gb,
             last_access_at::date AS last_access_date
      FROM inventory.s3_buckets
      WHERE storage_class = 'STANDARD'
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    if df.empty:
        return []
    df["days_since_access"] = (asof - pd.to_datetime(df["last_access_date"]).dt.date).apply(lambda d: d.days)
    cand = df[(df["days_since_access"] > days_cold) & (df["size_gb"].notna())]
    rows = []
    for _, r in cand.iterrows():
        rows.append({
            "rec_date": asof,
            "account_id": r["account_id"],
            "region": r["region"],
            "service": "S3",
            "resource_id": r["resource_id"],
            "rec_type": "S3_LIFECYCLE_COLD",
            "details": {
                "from": "STANDARD",
                "to": "STANDARD_IA",
                "size_gb": float(r["size_gb"]),
                "days_since_access": int(r["days_since_access"])
            },
            "est_saving_usd": None,   # เติมสูตรจาก pricing.s3_tiers ภายหลังได้
            "confidence": 0.8
        })
    return rows

def rule_rds_rightsize_p95_low(engine, asof: date, days: int = 7,
                               cpu_threshold: float = 20.0) -> List[Dict]:
    start_d = asof - timedelta(days=days)
    df = load_features(engine, start_d, asof, service="RDS")
    if df.empty:
        return []
    g = (df.groupby(["account_id", "region", "resource_id"])
           .agg(cpu_p95_max7d=("rds_cpu_p95", "max"))
           .reset_index())
    cand = g[g["cpu_p95_max7d"].fillna(999) < cpu_threshold]
    rows = []
    for _, r in cand.iterrows():
        rows.append({
            "rec_date": asof,
            "account_id": r["account_id"],
            "region": r["region"],
            "service": "RDS",
            "resource_id": r["resource_id"],
            "rec_type": "RDS_RIGHTSIZE_P95_LOW",
            "details": {"cpu_p95_max7d": float(r["cpu_p95_max7d"]), "hint": "Low utilization 7d"},
            "est_saving_usd": None,
            "confidence": 0.75
        })
    return rows

def rule_lambda_optimize(engine, asof: date,
                         duration_p95_ms: int = 300,
                         min_invocations: int = 1000) -> List[Dict]:
    df = load_features(engine, asof, asof, service="Lambda")
    if df.empty:
        return []
    cand = df[
        (df["lambda_duration_p95_ms"].fillna(0) > duration_p95_ms) &
        (df["lambda_invocations"].fillna(0) > min_invocations)
    ]
    rows = []
    for _, r in cand.iterrows():
        rows.append({
            "rec_date": asof,
            "account_id": r["account_id"],
            "region": r["region"],
            "service": "Lambda",
            "resource_id": r["resource_id"],
            "rec_type": "LAMBDA_OPTIMIZE",
            "details": {
                "duration_p95_ms": float(r["lambda_duration_p95_ms"]) if pd.notna(r["lambda_duration_p95_ms"]) else None,
                "invocations": float(r["lambda_invocations"]) if pd.notna(r["lambda_invocations"]) else None
            },
            "est_saving_usd": None,
            "confidence": 0.6
        })
    return rows

def rule_data_transfer_inter_az(engine, asof: date,
                                gb_threshold: float = 50.0) -> List[Dict]:
    # ต้องมีตารางสรุป data transfer (ถ้ามีก็ใช้ ไม่มีก็ข้าม)
    if not table_exists(engine, "finops", "dt_inter_az"):
        print("[recs] skip DT_INTER_AZ_HIGH (finops.dt_inter_az not found)")
        return []
    sql = """
      SELECT account_id, region, gb_30d, price_per_gb_usd
      FROM finops.dt_inter_az
    """
    with engine.connect() as conn:
        df = pd.read_sql(text(sql), conn)
    if df.empty:
        return []
    cand = df[df["gb_30d"].fillna(0) > gb_threshold]
    rows = []
    for _, r in cand.iterrows():
        est = None
        if pd.notna(r["gb_30d"]) and pd.notna(r["price_per_gb_usd"]):
            est = float(r["gb_30d"]) * float(r["price_per_gb_usd"])
        rows.append({
            "rec_date": asof,
            "account_id": r["account_id"],
            "region": r["region"],
            "service": "DataTransfer",
            "resource_id": "inter-az",
            "rec_type": "DT_INTER_AZ_HIGH",
            "details": {"gb_30d": float(r["gb_30d"]), "hint": "Co-locate workloads in same AZ"},
            "est_saving_usd": est,
            "confidence": 0.7
        })
    return rows

# ---------------------------
# Orchestrator
# ---------------------------
def build_recommendations(engine, asof: date, enabled_rules: List[str]) -> List[Dict]:
    all_rows: List[Dict] = []

    def add(rows: List[Dict]):
        if rows:
            all_rows.extend(rows)

    # แมปรหัสกฎ -> ฟังก์ชัน
    rule_map = {
        "EC2_RIGHTSIZE_P95_LOW": rule_ec2_rightsize_p95_low,
        "S3_LIFECYCLE_COLD":     rule_s3_lifecycle_cold,
        "RDS_RIGHTSIZE_P95_LOW": rule_rds_rightsize_p95_low,
        "LAMBDA_OPTIMIZE":       rule_lambda_optimize,
        "DT_INTER_AZ_HIGH":      rule_data_transfer_inter_az,
    }

    for code in enabled_rules:
        fn = rule_map.get(code)
        if not fn:
            print(f"[recs] unknown rule '{code}' -> skip")
            continue
        try:
            add(fn(engine, asof))
            print(f"[recs] rule {code} -> OK")
        except Exception as e:
            print(f"[recs] rule {code} -> ERROR: {e}")

    return all_rows

# ---------------------------
# CLI
# ---------------------------
def parse_args():
    ap = argparse.ArgumentParser(description="Generate cost optimization recommendations.")
    ap.add_argument("--as-of", type=str, default=None,
                    help="as-of date (YYYY-MM-DD). Default = yesterday")
    ap.add_argument("--rules", type=str, default="EC2_RIGHTSIZE_P95_LOW,S3_LIFECYCLE_COLD,RDS_RIGHTSIZE_P95_LOW,LAMBDA_OPTIMIZE,DT_INTER_AZ_HIGH",
                    help="comma-separated rule codes to run")
    ap.add_argument("--dry-run", action="store_true", help="do not write to DB")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.as_of:
        asof = date.fromisoformat(args.as_of)
    else:
        asof = date.today() - timedelta(days=1)

    enabled_rules = [x.strip() for x in args.rules.split(",") if x.strip()]

    # basic env checks
    if not os.getenv("DATABASE_URL"):
        for k in ["DB_HOST","DB_PORT","DB_NAME","DB_USER","DB_PASSWORD"]:
            if not os.getenv(k):
                print(f"[warn] env {k} is empty")

    engine = get_engine()

    # เช็คว่าตารางปลายทางมีอยู่ (ไม่สร้างให้)
    if not table_exists(engine, "core", "recommendations"):
        raise RuntimeError("core.recommendations not found. Please create schema first.")

    rows = build_recommendations(engine, asof, enabled_rules)
    upsert_recommendations(engine, rows, dry_run=args.dry_run)
    print("✅ done.")

if __name__ == "__main__":
    main()
