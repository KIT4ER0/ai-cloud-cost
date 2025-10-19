"""
Common utilities for ETL scripts
- Database connection (reads DATABASE_URL from .env)
- Upsert functions
- Date helpers
"""

import os
import sys
from functools import lru_cache
from datetime import date, timedelta
from typing import List, Dict, Any, Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# --- Load .env file at the start ---
# This makes DATABASE_URL available to os.getenv()
load_dotenv()


# ---------------------------
# Database Connection
# ---------------------------

@lru_cache(maxsize=1)
def get_db_url() -> str:
    """
    Get DATABASE_URL from environment variable.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("FATAL: DATABASE_URL environment variable is not set.", file=sys.stderr)
        print("Please create a .env file with DATABASE_URL='postgresql://user:pass@host:port/db'", file=sys.stderr)
        sys.exit(1)
    return db_url

@lru_cache(maxsize=2)
def get_db_conn() -> psycopg2.extensions.connection:
    """
    Establish and cache a database connection.
    """
    try:
        conn = psycopg2.connect(get_db_url())
        conn.autocommit = False # Use transactions
        return conn
    except Exception as e:
        print(f"FATAL: Could not connect to database: {e}", file=sys.stderr)
        sys.exit(1)

# ---------------------------
# Database Upsert Functions
# ---------------------------

def upsert_many_costs(records: List[Dict[str, Any]]) -> None:
    """
    Upsert a batch of records into raw.costs using ON CONFLICT.
    """
    if not records:
        return

    conn = get_db_conn()
    cursor = conn.cursor()
    
    # --- Columns in schema.sql ---
    cols = [
        "usage_date", "account_id", "region", "service", "usage_type",
        "amount_usd", "currency_src", "tags", "source_hash"
    ]
    
    # --- The PK columns to check for conflict ---
    conflict_cols = "usage_date, account_id, region, service, usage_type"
    
    # --- Columns to update if conflict occurs ---
    update_cols = "amount_usd = EXCLUDED.amount_usd, source_hash = EXCLUDED.source_hash"
    
    sql = f"""
        INSERT INTO raw.costs ({", ".join(cols)})
        VALUES %s
        ON CONFLICT ({conflict_cols})
        DO UPDATE SET {update_cols};
    """
    
    try:
        # 1. Prepare data tuples
        data_tuples = []
        for r in records:
            t = tuple(r.get(c) for c in cols) # Ensure order is correct
            data_tuples.append(t)
            
        # 2. Execute batch upsert
        psycopg2.extras.execute_values(
            cursor, sql, data_tuples, template=None, page_size=len(data_tuples)
        )
        
        # 3. Commit transaction
        conn.commit()
        
    except Exception as e:
        conn.rollback() # Rollback on error
        print(f"ERROR: Failed to upsert costs: {e}", file=sys.stderr)
        # Re-raise error to stop ETL
        raise
    finally:
        cursor.close()
        # We keep the connection open (cached) for the next batch


# ---------------------------
# Date Utilities
# ---------------------------

def daterange_days_back(days_back: int, overlap_days: int = 0) -> tuple[date, date, date]:
    """
    Calculate start/end dates for ETL pull.
    Returns (start, end, overlap_start)
    """
    # end = today (exclusive, so it means "up to end of yesterday")
    end_date = date.today()
    
    # start = N days back
    start_date = end_date - timedelta(days=days_back)
    
    # overlap_start = for overwriting recent data
    overlap_start_date = end_date - timedelta(days=overlap_days)

    return start_date, end_date, overlap_start_date

# ---------------------------
# (STUBS for Boto3 functions)
# ---------------------------
# We keep these here in 'common' so other ETL scripts
# can import them, even though etl_cost.py doesn't use them.

def boto_client(service_name: str, region: Optional[str] = None):
    """
    (MOCK STUB) This would normally create a Boto3 client.
    We return None to signify it's not implemented.
    """
    print(f"--- MOCK: Boto3 client requested for {service_name} (returning None) ---", file=sys.stderr)
    # Returning None will cause the *original* ETL scripts to fail
    # which is correct, because they must also be mocked.
    return None

def ce_get_cost_and_usage(ce_client, **params):
    """
    (MOCK STUB) This would normally call Cost Explorer.
    """
    print("--- MOCK: ce_get_cost_and_usage called (returning empty) ---", file=sys.stderr)
    return {}


def upsert_many_metrics(records: List[Dict[str, Any]]) -> None:
    """
    Upsert a batch of records into raw.metrics using ON CONFLICT.
    """
    if not records:
        return

    conn = get_db_conn()
    cursor = conn.cursor()
    
    cols = [
        "metric_ts", "account_id", "region", "resource_id", "service",
        "namespace", "metric_name", "stat", "period_seconds",
        "metric_value", "unit", "dimensions", "source_hash"
    ]
    
    conflict_cols = "metric_ts, resource_id, metric_name, stat, period_seconds"
    update_cols = "metric_value = EXCLUDED.metric_value, source_hash = EXCLUDED.source_hash"
    
    sql = f"""
        INSERT INTO raw.metrics ({", ".join(cols)})
        VALUES %s
        ON CONFLICT ({conflict_cols})
        DO UPDATE SET {update_cols};
    """
    
    try:
        data_tuples = []
        for r in records:
            t = tuple(r.get(c) for c in cols)
            data_tuples.append(t)
            
        psycopg2.extras.execute_values(
            cursor, sql, data_tuples, template=None, page_size=len(data_tuples)
        )
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print(f"ERROR: Failed to upsert metrics: {e}", file=sys.stderr)
        raise
    finally:
        cursor.close()