# etl/common.py
import os
from datetime import date, timedelta
from dotenv import load_dotenv
from tenacity import retry, wait_exponential, stop_after_attempt
import boto3
from sqlalchemy import create_engine, text

load_dotenv()

# ---------- DB ----------
def db_url():
    return (f"postgresql+psycopg2://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
            f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}")

engine = create_engine(db_url(), pool_pre_ping=True)

def upsert_many_costs(rows):
    """
    rows: list[dict] with keys:
      usage_date, account_id, region, service, usage_type,
      amount_usd, currency_src, tags, source_hash
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
    if rows:
        with engine.begin() as conn:
            conn.execute(sql, rows)

def upsert_many_metrics(rows):
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
    if rows:
        with engine.begin() as conn:
            conn.execute(sql, rows)

# ---------- AWS ----------
def boto_client(name, region=None):
    """
    Create boto3 client with AWS credentials from .env
    Supports both permanent and temporary credentials
    """
    kwargs = {
        "region_name": region or os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }

    # ถ้ามี AWS_SESSION_TOKEN → ใส่เพิ่ม
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

def daterange_days_back(days_back=90, overlap_days=7):
    end = date.today()
    start = end - timedelta(days=days_back)
    start_over = end - timedelta(days=overlap_days)
    return start, end, start_over
