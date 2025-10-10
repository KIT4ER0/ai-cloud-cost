# etl/common.py
from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt
import boto3
from sqlalchemy import create_engine, text

load_dotenv()

# ---------- DB ----------
def _db_name() -> str:
    # รองรับโหมดเทสต์ผ่าน ENV=test
    if os.getenv("ENV") == "test" and os.getenv("DB_NAME_TEST"):
        return os.getenv("DB_NAME_TEST")
    return os.getenv("DB_NAME")

def db_url() -> str:
    return (
        f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
        f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{_db_name()}"
    )

engine = create_engine(
    db_url(),
    pool_pre_ping=True,
    pool_recycle=1800,  # รีไซเคิลทุก 30 นาที กัน connection ค้าง
    future=True,
)

def _exec_many(sql_text, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    with engine.begin() as conn:
        # มาตรฐานเวลาให้เป็น UTC เสมอ
        conn.execute(text("SET TIME ZONE 'UTC'"))
        conn.execute(sql_text, rows)

def upsert_many_costs(rows: List[Dict[str, Any]]) -> None:
    """
    rows keys:
      usage_date, account_id, region, service, usage_type,
      amount_usd, currency_src, tags (str JSON), source_hash
    """
    sql = text("""
        INSERT INTO raw.costs
          (usage_date, account_id, region, service, usage_type,
           amount_usd, currency_src, tags, source_hash)
        VALUES
          (:usage_date, :account_id, :region, :service, :usage_type,
           :amount_usd, :currency_src, CAST(:tags AS JSONB), :source_hash)
        ON CONFLICT (usage_date, account_id, region, service, usage_type)
        DO UPDATE SET
           amount_usd   = EXCLUDED.amount_usd,
           currency_src = EXCLUDED.currency_src,
           tags         = EXCLUDED.tags,
           source_hash  = EXCLUDED.source_hash,
           ingested_at  = NOW();
    """)
    _exec_many(sql, rows)

def upsert_many_metrics(rows: List[Dict[str, Any]]) -> None:
    """
    rows keys:
      metric_ts, account_id, region, resource_id, service, namespace,
      metric_name, stat, period_seconds, metric_value, unit,
      dimensions (str JSON), source_hash
    """
    sql = text("""
        INSERT INTO raw.metrics
          (metric_ts, account_id, region, resource_id, service, namespace,
           metric_name, stat, period_seconds, metric_value, unit, dimensions, source_hash)
        VALUES
          (:metric_ts, :account_id, :region, :resource_id, :service, :namespace,
           :metric_name, :stat, :period_seconds, :metric_value, :unit, CAST(:dimensions AS JSONB), :source_hash)
        ON CONFLICT (metric_ts, resource_id, metric_name, stat, period_seconds)
        DO UPDATE SET
           account_id    = EXCLUDED.account_id,
           region        = EXCLUDED.region,
           service       = EXCLUDED.service,
           namespace     = EXCLUDED.namespace,
           metric_value  = EXCLUDED.metric_value,
           unit          = EXCLUDED.unit,
           dimensions    = EXCLUDED.dimensions,
           source_hash   = EXCLUDED.source_hash,
           ingested_at   = NOW();
    """)
    _exec_many(sql, rows)

def upsert_many_features(rows):
    sql = text("""
        INSERT INTO core.features
          (feature_date, account_id, region, service, resource_id, usage_type,
           cpu_p95, storage_gb, network_gb,
           lambda_duration_p95_ms, lambda_invocations,
           rds_cpu_p95, rds_conn_avg, rds_free_storage_gb_min, records_from)
        VALUES
          (:feature_date, :account_id, :region, :service, :resource_id, COALESCE(:usage_type, 'n/a'),
           :cpu_p95, :storage_gb, :network_gb,
           :lambda_duration_p95_ms, :lambda_invocations,
           :rds_cpu_p95, :rds_conn_avg, :rds_free_storage_gb_min, CURRENT_DATE)
        ON CONFLICT (feature_date, account_id, region, service, resource_id, usage_type)
        DO UPDATE SET
           cpu_p95                 = EXCLUDED.cpu_p95,
           storage_gb              = EXCLUDED.storage_gb,
           network_gb              = EXCLUDED.network_gb,
           lambda_duration_p95_ms  = EXCLUDED.lambda_duration_p95_ms,
           lambda_invocations      = EXCLUDED.lambda_invocations,
           rds_cpu_p95             = EXCLUDED.rds_cpu_p95,
           rds_conn_avg            = EXCLUDED.rds_conn_avg,
           rds_free_storage_gb_min = EXCLUDED.rds_free_storage_gb_min,
           ingested_at             = NOW();
    """)
    _exec_many(sql, rows)

# ---------- AWS ----------
def boto_client(name: str, region: Optional[str] = None):
    """
    Create boto3 client with AWS credentials from .env
    Supports both permanent and temporary credentials
    """
    kwargs = {
        "region_name": region or os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    session_token = os.getenv("AWS_SESSION_TOKEN")
    if session_token:
        kwargs["aws_session_token"] = session_token
    return boto3.client(name, **kwargs)

@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(6))
def ce_get_cost_and_usage(ce, **kwargs):
    return ce.get_cost_and_usage(**kwargs)

@retry(wait=wait_exponential(multiplier=1, min=1, max=30), stop=stop_after_attempt(6))
def cw_get_metric_data(cw, **kwargs):
    return cw.get_metric_data(**kwargs)

def daterange_days_back(days_back: int = 90, overlap_days: int = 7):
    """
    คืนช่วงวัน (start, end, start_over) สำหรับดึง CE แบบ rolling overwrite
    - start: end - days_back
    - start_over: end - overlap_days (เอาไว้ overwrite ช่วงล่าสุดที่ CE ชอบแก้ย้อนหลัง)
    """
    end = date.today()
    start = end - timedelta(days=days_back)
    start_over = end - timedelta(days=overlap_days)
    return start, end, start_over
