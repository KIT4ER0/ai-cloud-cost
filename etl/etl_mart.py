# etl/etl_mart.py
from __future__ import annotations
import os
import sys
import argparse
from datetime import date, timedelta

import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# -----------------------------
# ENV & ENGINE
# -----------------------------
load_dotenv()

def db_url() -> str:
    # รองรับ DATABASE_URL ถ้ามี (เช่น postgres://user:pass@host:5432/dbname)
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

def assert_table_exists(engine, schema: str, table: str):
    sql = """
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = :schema AND table_name = :table
    """
    with engine.connect() as conn:
        row = conn.execute(text(sql), {"schema": schema, "table": table}).fetchone()
        if not row:
            raise RuntimeError(
                f"Table {schema}.{table} not found. "
                f"Create it first using your schema SQL."
            )

# -----------------------------
# LOAD DATA
# -----------------------------
def load_features(engine, start_d=None, end_d=None):
    params = {}
    where = ""
    if start_d and end_d:
        where = "WHERE feature_date BETWEEN :start AND :end"
        params = {"start": start_d, "end": end_d}

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

def load_costs_agg(engine, start_d=None, end_d=None):
    params = {}
    where = ""
    if start_d and end_d:
        where = "WHERE usage_date BETWEEN :start AND :end"
        params = {"start": start_d, "end": end_d}

    sql = f"""
        SELECT usage_date AS feature_date, account_id, region, service,
               SUM(amount_usd) AS amount_usd
        FROM raw.costs
        {where}
        GROUP BY 1,2,3,4
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn, params=params)

def build_mart_df(engine, start_d: date | None, end_d: date | None) -> pd.DataFrame:
    f = load_features(engine, start_d, end_d)
    if f.empty:
        print("[mart] features empty for range -> nothing to do.")
        return f

    c = load_costs_agg(engine, start_d, end_d)
    mart = f.merge(
        c, on=["feature_date", "account_id", "region", "service"], how="left"
    )

    # ค่าเงินว่างให้เป็น 0 เพื่อการรวมสะดวก
    if "amount_usd" in mart.columns:
        mart["amount_usd"] = mart["amount_usd"].fillna(0)

    # จัดคอลัมน์ให้ตรงกับตารางปลายทาง
    cols = [
        "feature_date", "account_id", "region", "service", "resource_id",
        "amount_usd",
        "cpu_p95", "network_gb", "storage_gb",
        "lambda_duration_p95_ms", "lambda_invocations",
        "rds_cpu_p95", "rds_conn_avg", "rds_free_storage_gb_min",
    ]
    for col in cols:
        if col not in mart.columns:
            mart[col] = None

    # จัดเรียงคอลัมน์และชนิดข้อมูลที่ปลอดภัย
    mart = mart[cols].copy()
    # แปลงวันที่ให้เป็น date (ไม่ใช่ datetime)
    mart["feature_date"] = pd.to_datetime(mart["feature_date"]).dt.date

    return mart

# -----------------------------
# WRITE (No DDL)
# -----------------------------
def write_full(engine, df: pd.DataFrame, dry_run: bool = False):
    if df is None or df.empty:
        print("[mart] nothing to write (full).")
        return
    if dry_run:
        print(f"[dry-run] would TRUNCATE mart.daily_cost_features and insert {len(df):,} rows.")
        return

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE mart.daily_cost_features"))
    df.to_sql(
        "daily_cost_features", engine, schema="mart",
        if_exists="append", index=False, method="multi", chunksize=10_000
    )
    print(f"[mart] wrote {len(df):,} rows (full refresh).")

def write_incremental(engine, df: pd.DataFrame, start_d: date, end_d: date, dry_run: bool = False):
    if df is None or df.empty:
        print("[mart] nothing to upsert for the selected range.")
        return
    if dry_run:
        print(f"[dry-run] would DELETE mart.daily_cost_features where feature_date between {start_d} and {end_d} "
              f"then insert {len(df):,} rows.")
        return

    with engine.begin() as conn:
        conn.execute(text("""
            DELETE FROM mart.daily_cost_features
            WHERE feature_date BETWEEN :start AND :end
        """), {"start": start_d, "end": end_d})

    df.to_sql(
        "daily_cost_features", engine, schema="mart",
        if_exists="append", index=False, method="multi", chunksize=10_000
    )
    print(f"[mart] upserted {len(df):,} rows for {start_d}..{end_d}.")

# -----------------------------
# CLI
# -----------------------------
def parse_args():
    ap = argparse.ArgumentParser(
        description="Build/refresh mart.daily_cost_features without SQL DDL (incremental or full)."
    )
    ap.add_argument("--mode", choices=["incremental", "full"], default="incremental",
                    help="full = TRUNCATE then insert all; incremental = delete+append for date range")
    ap.add_argument("--days-back", type=int, default=7,
                    help="date range back from today (inclusive) for incremental mode")
    ap.add_argument("--dry-run", action="store_true", help="do not write to DB")
    return ap.parse_args()

def main():
    args = parse_args()

    # ตรวจ env จำเป็น
    for k in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
        if not os.getenv(k) and not os.getenv("DATABASE_URL"):
            print(f"[warn] env {k} is empty. (DATABASE_URL can be used instead)")

    engine = get_engine()

    # ยืนยันว่าตารางที่ต้องอ้างอิงมีจริง (ไม่สร้างให้)
    for sch, tbl in [("core", "features"), ("raw", "costs"), ("mart", "daily_cost_features")]:
        assert_table_exists(engine, sch, tbl)

    # คำนวณช่วงวันที่
    end_d = date.today()
    start_d = end_d - timedelta(days=args.days_back)

    if args.mode == "full":
        print("[mart] mode=full -> loading FULL dataset ...")
        df_full = build_mart_df(engine, None, None)
        write_full(engine, df_full, dry_run=args.dry_run)
    else:
        print(f"[mart] mode=incremental -> range {start_d}..{end_d}")
        df = build_mart_df(engine, start_d, end_d)
        write_incremental(engine, df, start_d, end_d, dry_run=args.dry_run)

    print("✅ done.")

if __name__ == "__main__":
    main()
