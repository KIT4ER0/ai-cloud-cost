"""
Data cleaning utilities for ETL processes.
Used to convert raw dict lists into clean pandas DataFrames.
"""

import pandas as pd
from typing import List, Dict, Any

def clean_costs_df(
    rows: List[Dict[str, Any]], 
    infer_region: bool = False
) -> pd.DataFrame:
    """
    Convert raw Cost Explorer dicts into a clean DataFrame.
    
    Args:
        rows: List of dictionary records from fetch_cost_daily (mock or real).
        infer_region: (No longer used by mock) Flag to infer region from usage type.
    """
    if not rows:
        return pd.DataFrame() # Return empty DataFrame if no rows

    df = pd.DataFrame(rows)

    # --- Basic Data Cleaning & Type Conversion ---

    # 1. Convert date string to datetime object (important!)
    #    (errors='coerce' will turn bad dates into NaT)
    df["usage_date"] = pd.to_datetime(df["usage_date"], errors='coerce')

    # 2. Fill missing string values with a placeholder
    #    (schema.sql has NOT NULL, but good practice)
    df["account_id"] = df["account_id"].fillna("unknown")
    df["region"] = df["region"].fillna("global")
    df["service"] = df["service"].fillna("UnknownService")
    df["usage_type"] = df["usage_type"].fillna("UnknownUsageType")
    df["currency_src"] = df["currency_src"].fillna("USD")

    # 3. Fill missing numeric values
    df["amount_usd"] = pd.to_numeric(df["amount_usd"], errors='coerce').fillna(0.0)

    # 4. Handle JSON tags (schema expects json, not None)
    df["tags"] = df["tags"].fillna('{}')

    # 5. Drop any rows where the date failed to parse (NaT)
    df = df.dropna(subset=["usage_date"])

    # --- Schema Check ---
    # Ensure all columns required by raw.costs are present
    
    required_cols = [
        "usage_date", "account_id", "region", "service", "usage_type",
        "amount_usd", "currency_src", "tags", "source_hash"
    ]
    
    for col in required_cols:
        if col not in df.columns:
            # Add missing column with default value if it doesn't exist
            if col == 'tags':
                df[col] = '{}'
            elif col == 'source_hash':
                df[col] = None # Or generate a hash
            else:
                # This should ideally not happen if the mock generator is correct
                df[col] = None 

    # Re-order columns to match schema (good practice for `upsert_many_costs`)
    df = df[required_cols]

    return df


def clean_metrics_df(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert raw CloudWatch dicts into a clean DataFrame for raw.metrics.
    """
    if not rows:
        return pd.DataFrame() # Return empty DataFrame if no rows

    df = pd.DataFrame(rows)

    # 1. Convert timestamp
    df["metric_ts"] = pd.to_datetime(df["metric_ts"], errors='coerce', utc=True)

    # 2. Fill missing strings
    df["account_id"] = df["account_id"].fillna("unknown")
    df["region"] = df["region"].fillna("global")
    df["resource_id"] = df["resource_id"].fillna("unknown")
    df["service"] = df["service"].fillna("UnknownService")
    df["namespace"] = df["namespace"].fillna("Unknown/Namespace")
    df["metric_name"] = df["metric_name"].fillna("UnknownMetric")
    df["stat"] = df["stat"].fillna("Average")
    df["unit"] = df["unit"].fillna("None")

    # 3. Fill missing numerics
    df["period_seconds"] = pd.to_numeric(df["period_seconds"], errors='coerce').fillna(300).astype(int)
    df["metric_value"] = pd.to_numeric(df["metric_value"], errors='coerce').fillna(0.0)

    # 4. Handle JSON dimensions
    df["dimensions"] = df["dimensions"].fillna('{}')
    
    # 5. Drop rows where timestamp failed to parse
    df = df.dropna(subset=["metric_ts"])
    
    # 6. (สำคัญ) Schema.sql ของคุณมี source_hash แต่ mock row ไม่มี
    # เราต้องสร้างมันขึ้นมาถ้ามันไม่มี
    if 'source_hash' not in df.columns:
        df['source_hash'] = None # ให้ normalize_metric_row จัดการ
    
    # (ฟังก์ชัน normalize_metric_row ในตัว ETL จะจัดการที่เหลือ)

    return df