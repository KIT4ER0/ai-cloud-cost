"""
ETL: MOCK AWS Cost -> raw.costs
- สร้างข้อมูลจำลอง (Mock Data) สำหรับตาราง raw.costs
- Idempotent upsert ด้วย PK: (usage_date, account_id, region, service, usage_type)
"""

from __future__ import annotations
from .cleaners import clean_costs_df

import os
import re
import json
import hashlib
import argparse
from typing import Iterable, List, Optional, Dict

# --- START: MOCK DATA IMPORTS ---
import random
from datetime import datetime, timedelta
from faker import Faker
# --- END: MOCK DATA IMPORTS ---

from .common import (
    upsert_many_costs,
    daterange_days_back,
)

# ---------------------------
# Utilities
# ---------------------------

def h(*parts) -> str:
    """Stable hash for source row tracking"""
    return hashlib.sha256("|".join("" if p is None else str(p) for p in parts).encode()).hexdigest()

def env_list(name: str) -> List[str]:
    """Read comma-separated list from env; return [] if missing/blank."""
    raw = os.getenv(name, "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()] if raw else []

# ... (ฟังก์ชัน is_12digits และ region inference คงไว้เหมือนเดิม) ...

REGION_PREFIX_MAP = {
    "USE1": "us-east-1", "USE2": "us-east-2", "USW1": "us-west-1", "USW2": "us-west-2",
    "EUC1": "eu-central-1", "EUW1": "eu-west-1", "EUW2": "eu-west-2", "EUW3": "eu-west-3",
    "APS1": "ap-south-1", "APN1": "ap-northeast-1", "APN2": "ap-northeast-2", "APN3": "ap-northeast-3",
    "APSE1": "ap-southeast-1", "APSE2": "ap-southeast-2", "APSE3": "ap-southeast-3", "APSE4": "ap-southeast-4",
    "SAE1": "sa-east-1", "CAN1": "ca-central-1", "AFS1": "af-south-1", "MEC1": "me-central-1", "MES1": "me-south-1",
}

def infer_region_from_usage_type(usage_type: str | None) -> str:
    if not usage_type: return "global"
    prefix = usage_type.split("-", 1)[0].upper()
    return REGION_PREFIX_MAP.get(prefix, "global")

def is_12digits(acct: Optional[str]) -> bool:
    return bool(acct and re.fullmatch(r"\d{12}", acct))

# ---------------------------
# Core ETL (Mock Version)
# ---------------------------

def fetch_cost_daily(
    days_back: int = 90,
    overlap_days: int = 7,
    accounts: Optional[List[str]] = None,
    regions: Optional[List[Optional[str]]] = None, # (Mock) พารามิเตอร์นี้จะถูกเมิน
) -> List[Dict]:
    """
    (MOCK) สร้างข้อมูลจำลองรายวันสำหรับ raw.costs
    """
    print(f"--- MOCK ETL: Generating mock cost data for {days_back} days back ---")
    
    fake = Faker()
    out_rows: List[Dict] = []
    
    # ถ้าไม่ได้ระบุ account มา, เราจะสร้าง mock account ขึ้นมา 1 อัน
    if not accounts or not is_12digits(accounts[0]):
        mock_account_id = os.getenv("AWS_ACCOUNT_ID", fake.numerify(text="############"))
    else:
        mock_account_id = accounts[0]
        
    start, end, _ = daterange_days_back(days_back, overlap_days)
    
    # แปลง start/end (date object) เป็น datetime object เพื่อวน loop
    current_date = datetime.combine(start, datetime.min.time())
    end_datetime = datetime.combine(end, datetime.min.time())

    # --- Config สำหรับการสร้างข้อมูลจำลอง ---
    services_config = {
        
        # 1. EC2 + Elastic IP
        # (ค่าใช้จ่าย EIP จะถูกคิดรวมใน Service EC2)
        'Amazon Elastic Compute Cloud - Compute': {
            'base_cost': 0.42, # $0.30 (EC2 t2.micro) + $0.12 (Unattached EIP)
            'noise': 0.05,     # noise จาก EC2
            'unit': 'UsageHours',
            'usage_types': [
                'USE1-BoxUsage:t2.micro',      # <-- จำลอง EC2 Instance
                'USE1-EIP:IdleAddress',        # <-- จำลอง Elastic IP ที่ไม่ได้ใช้งาน
                'USE1-DataTransfer-Out-Bytes'  # <-- จำลองค่า Data Transfer
            ]
        },
        
        # 2. S3
        'Amazon Simple Storage Service': {
            'base_cost': 0.01, # ค่า S3 สำหรับไฟล์ไม่กี่ไฟล์
            'noise': 0.005,
            'unit': 'GB-Month',
            'usage_types': [
                'APSE1-StandardStorage',   # <-- จำลองค่าจัดเก็บไฟล์
                'APSE1-Requests-Tier1'     # <-- จำลองค่าเรียก API
            ]
        },

        # 3. EBS
        'Amazon Elastic Block Store': {
            'base_cost': 0.03, # ค่า EBS สำหรับ Volume 2 ก้อน (ทั้งที่ติดกับ EC2 และที่ไม่ได้ติด)
            'noise': 0.01,
            'unit': 'GB-Month',
            'usage_types': [
                'APSE1-EBS:VolumeUsage.gp3', # <-- จำลอง Volume 2 ก้อน
            ]
        },
        # 4. RDS (เพิ่มใหม่)
        'Amazon Relational Database Service': {
            'base_cost': 0.50, # จำลอง db.t3.micro + storage
            'noise': 0.05,
            'unit': 'UsageHours',
            'usage_types': [
                'APSE1-InstanceUsage:db.t3.micro', # ค่า Instance
                'APSE1-StorageUsage'               # ค่า Storage
            ]
        },

        # 5. Lambda (เพิ่มใหม่)
        'AWS Lambda': {
            'base_cost': 0.02, # จำลองการใช้งานเล็กน้อย
            'noise': 0.01,
            'unit': 'Requests',
            'usage_types': [
                'APSE1-Requests',           # ค่า Requests
                'APSE1-Lambda-GB-Second'    # ค่า Duration (GB-Seconds)
            ]
        }
    }

    while current_date < end_datetime:
        usage_date_str = current_date.strftime("%Y-%m-%d")
        
        for service, config in services_config.items():
            for usage_type in config['usage_types']:
                
                # สร้าง cost ให้ดู "จริง"
                cost = config['base_cost'] + random.uniform(-config['noise'], config['noise'])
                
                # เพิ่ม Trend (ให้ S3 ค่อยๆ แพงขึ้นตามเวลา)
                if 'S3' in service:
                    days_since_start = (current_date - (datetime.now() - timedelta(days=days_back))).days
                    cost += (days_since_start * 0.05) # S3 โตวันละ 5 เซนต์
                    
                # ทำให้วันเสาร์-อาทิตย์ ถูกลง (จำลองว่าคนทำงานน้อยลง)
                if current_date.weekday() >= 5: # 5=Sat, 6=Sun
                    cost *= 0.7 
                
                amount = max(0, cost / len(config['usage_types'])) # แบ่ง cost ตาม usage_type
                unit = "USD"
                
                # เดา region จาก usage_type
                region_for_row = infer_region_from_usage_type(usage_type)

                rowhash = h(usage_date_str, mock_account_id, region_for_row, service, usage_type, amount, unit)

                out_rows.append({
                    "usage_date": usage_date_str,
                    "account_id": mock_account_id,
                    "region": region_for_row,
                    "service": service,
                    "usage_type": usage_type,
                    "amount_usd": amount,
                    "currency_src": unit,
                    "tags": json.dumps({"mock": "true", "owner": "etl_cost"}),
                    "source_hash": rowhash,
                })

        current_date += timedelta(days=1)

    print(f"--- MOCK ETL: Generated {len(out_rows)} mock records ---")
    return out_rows


def run(
    days_back: int = 90,
    overlap_days: int = 7,
    accounts: Optional[List[str]] = None,
    regions: Optional[List[str]] = None,
    batch_size: int = 5000,
) -> None:
    # 1. เรียกฟังก์ชัน Mock (แทนฟังก์ชัน Boto3)
    rows = fetch_cost_daily(
        days_back=days_back,
        overlap_days=overlap_days,
        accounts=accounts,
        regions=regions,
    )

    # 2. ทำความสะอาด (เหมือนเดิม)
    df = clean_costs_df(rows, infer_region=False) # ปิด infer_region เพราะเราทำเองแล้ว
    records = df.to_dict(orient="records")

    if not records:
        print("ETL Cost: no MOCK rows generated.")
        return

    # 3. บันทึกลง DB (เหมือนเดิม)
    # ฟังก์ชัน upsert_many_costs จะทำงานกับฐานข้อมูล PostgreSQL
    # ที่เชื่อมต่อผ่าน .env (DATABASE_URL)
    total = 0
    for i in range(0, len(records), batch_size):
        upsert_many_costs(records[i:i+batch_size])
        total += min(batch_size, len(records) - i)
    print(f"ETL Cost: upserted {total} MOCK rows into raw.costs")


# ---------------------------
# CLI (คงไว้เหมือนเดิม)
# ---------------------------

def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="ETL: Cost Explorer -> raw.costs (SERVICE + USAGE_TYPE)")
    p.add_argument("--days-back", type=int, default=90, help="How many days back to fetch (default: 90)")
    p.add_argument("--overlap-days", type=int, default=7, help="Rolling overwrite window to handle CE latency (default: 7)")
    p.add_argument(
        "--accounts", type=str, default="",
        help="Comma-separated MOCK ACCOUNTs (12 digits). If omitted, use AWS_ACCOUNT_ID or auto-generate.",
    )
    p.add_argument(
        "--regions", type=str, default="",
        help="(Ignored by Mock) Comma-separated CE regions to filter.",
    )
    p.add_argument("--batch-size", type=int, default=5000, help="DB upsert batch size (default: 5000)")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args()

    acct_list = [a.strip() for a in args.accounts.split(",") if a.strip()] if args.accounts else None
    reg_list = [r.strip() for r in args.regions.split(",") if r.strip()] if args.regions else None

    run(
        days_back=args.days_back,
        overlap_days=args.overlap_days,
        accounts=acct_list,
        regions=reg_list,
        batch_size=args.batch_size,
    )