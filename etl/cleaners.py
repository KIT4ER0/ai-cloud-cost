# etl/cleaners.py
from __future__ import annotations
import pandas as pd
import numpy as np
import re
from typing import List, Dict

# mapping prefix -> region (สำหรับเดาจาก USAGE_TYPE หากต้องการ)
REGION_PREFIX_MAP = {
    "USE1":"us-east-1","USE2":"us-east-2","USW1":"us-west-1","USW2":"us-west-2",
    "EUC1":"eu-central-1","EUW1":"eu-west-1","EUW2":"eu-west-2","EUW3":"eu-west-3",
    "APS1":"ap-south-1","APN1":"ap-northeast-1","APN2":"ap-northeast-2","APN3":"ap-northeast-3",
    "APSE1":"ap-southeast-1","APSE2":"ap-southeast-2","APSE3":"ap-southeast-3","APSE4":"ap-southeast-4",
    "SAE1":"sa-east-1","CAN1":"ca-central-1","AFS1":"af-south-1","MEC1":"me-central-1","MES1":"me-south-1",
}

def _infer_region_from_usage_type(usage_type: str | None) -> str:
    if not usage_type or "-" not in usage_type:
        return "global"
    prefix = usage_type.split("-", 1)[0].upper()
    return REGION_PREFIX_MAP.get(prefix, "global")

def clean_costs_df(rows: List[Dict], infer_region: bool = True) -> pd.DataFrame:
    """
    รับ list[dict] (จาก CE) -> คืน DataFrame ที่สะอาด พร้อม upsert
    """
    if not rows:
        return pd.DataFrame(columns=[
            "usage_date","account_id","region","service","usage_type",
            "amount_usd","currency_src","tags","source_hash"
        ])

    df = pd.DataFrame(rows)

    # แปลงชนิด & เติมค่า missing
    df["usage_date"]  = pd.to_datetime(df["usage_date"]).dt.date
    for col, default in [("account_id","unknown"), ("service",""), ("usage_type","unknown")]:
        if col not in df: df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()

    # region: ใช้ของเดิมก่อน ถ้าว่างและเลือก infer_region ให้เดาจาก usage_type, ไม่งั้น 'global'
    if "region" not in df: df["region"] = np.nan
    if infer_region:
        df["region"] = df["region"].where(df["region"].notna(), df["usage_type"].map(_infer_region_from_usage_type))
    df["region"] = df["region"].fillna("global").replace("", "global")

    # amount/currency
    df["amount_usd"]  = pd.to_numeric(df.get("amount_usd", 0), errors="coerce").fillna(0.0)
    df["currency_src"] = df.get("currency_src","USD")
    if isinstance(df["currency_src"], pd.Series):
        df["currency_src"] = df["currency_src"].fillna("USD").astype(str)
    else:
        df["currency_src"] = "USD"

    # tags -> เก็บเป็นสตริง JSON (ปล่อยให้ฝั่ง SQL แปลงเป็น JSONB)
    if "tags" not in df:
        df["tags"] = "{}"
    else:
        df["tags"] = df["tags"].apply(lambda x: "{}" if x in (None, "", {}) else (x if isinstance(x, str) else str(x)))

    # กำจัดแถวซ้ำตามคีย์ธุรกิจ (เก็บแถวท้ายสุด)
    df = df.sort_values(["usage_date"]).drop_duplicates(
        subset=["usage_date","account_id","region","service","usage_type"],
        keep="last"
    )

    # ตรวจคอลัมน์ให้ครบ
    want_cols = ["usage_date","account_id","region","service","usage_type","amount_usd","currency_src","tags","source_hash"]
    if "source_hash" not in df:
        # สร้าง source_hash เบื้องต้น (ปล. คุณมีของเดิมจาก ETL ก็ใช้ต่อได้)
        df["source_hash"] = (
            df["usage_date"].astype(str) + "|" + df["account_id"] + "|" + df["region"] + "|" +
            df["service"] + "|" + df["usage_type"] + "|" + df["amount_usd"].round(6).astype(str)
        ).map(lambda s: pd.util.hash_pandas_object(pd.Series([s])).astype(str).values[0])
    return df[want_cols].reset_index(drop=True)

# ต่อใน etl/cleaners.py
def _bytes_to_gb(x):
    try:
        return float(x) / (1024.0**3)
    except Exception:
        return 0.0

def clean_metrics_df(rows: List[Dict]) -> pd.DataFrame:
    """
    รับ list[dict] (จาก CloudWatch) -> คืน DataFrame ที่สะอาด พร้อม upsert
    """
    if not rows:
        return pd.DataFrame(columns=[
            "metric_ts","account_id","region","resource_id","service","namespace",
            "metric_name","stat","period_seconds","metric_value","unit","dimensions","source_hash"
        ])

    df = pd.DataFrame(rows)

    # แกนเวลาและฟิลด์หลัก
    df["metric_ts"] = pd.to_datetime(df["metric_ts"], utc=True)
    for col, default in [
        ("account_id","unknown"), ("region","us-east-1"), ("resource_id","unknown"),
        ("service","UnknownService"), ("namespace","Unknown/Namespace"),
        ("metric_name","UnknownMetric"), ("stat","Average")
    ]:
        if col not in df: df[col] = default
        df[col] = df[col].fillna(default).astype(str).str.strip()

    # period / value / unit
    df["period_seconds"] = pd.to_numeric(df.get("period_seconds", 60), errors="coerce").fillna(60).astype(int)
    df["metric_value"]   = pd.to_numeric(df.get("metric_value", 0.0), errors="coerce").fillna(0.0).astype(float)
    df["unit"]           = df.get("unit","").fillna("").astype(str)

    # แปลงหน่วยยอดนิยมให้สม่ำเสมอ (ถ้าอยากเก็บดิบไว้ด้วย ให้ทำคอลัมน์ใหม่)
    # ตัวอย่าง: Network/Storage ให้เป็น GB
    mask_bytes = df["unit"].str.contains("Bytes", case=False, na=False)
    df.loc[mask_bytes, "metric_value"] = df.loc[mask_bytes, "metric_value"].map(_bytes_to_gb)
    df.loc[mask_bytes, "unit"] = "GB"

    # Duration milliseconds -> milliseconds (คงไว้), ถ้าต้องการ seconds ให้แปลง:
    # mask_ms = df["unit"].str.fullmatch("Milliseconds", case=False)
    # df.loc[mask_ms, "metric_value"] = df.loc[mask_ms, "metric_value"] / 1000.0
    # df.loc[mask_ms, "unit"] = "Seconds"

    # dimensions -> string JSON
    if "dimensions" not in df:
        df["dimensions"] = "{}"
    else:
        df["dimensions"] = df["dimensions"].apply(lambda x: "{}" if x in (None,"",{}) else (x if isinstance(x,str) else str(x)))

    # กำจัดแถวซ้ำตามคีย์ PK
    df = df.sort_values(["metric_ts"]).drop_duplicates(
        subset=["metric_ts","resource_id","metric_name","stat","period_seconds"],
        keep="last"
    )

    want = ["metric_ts","account_id","region","resource_id","service","namespace",
            "metric_name","stat","period_seconds","metric_value","unit","dimensions","source_hash"]

    if "source_hash" not in df:
        df["source_hash"] = (
            df["metric_ts"].astype(str)+"|"+df["resource_id"]+"|"+df["metric_name"]+"|"+
            df["stat"]+"|"+df["period_seconds"].astype(str)+"|"+df["metric_value"].round(6).astype(str)
        ).map(lambda s: pd.util.hash_pandas_object(pd.Series([s])).astype(str).values[0])

    return df[want].reset_index(drop=True)
