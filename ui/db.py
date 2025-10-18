import os
import time
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import streamlit as st

# Default สำหรับรันใน Docker Compose (host = db)
DEFAULT_DB_URL = "postgresql+psycopg2://ai_user:ai_password@db:5432/ai_cost"

@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    db_url = os.getenv("DATABASE_URL", DEFAULT_DB_URL)
    return create_engine(db_url, pool_pre_ping=True, future=True)

def wait_for_db(timeout: int = 60, interval: float = 2.0):
    """รอให้ DB พร้อมก่อนใช้งานครั้งแรก (สำคัญมากเวลาใช้ Docker)"""
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:
            last_err = e
            time.sleep(interval)
    # หมดเวลาแล้ว คาย error ให้เห็นในหน้า UI
    raise RuntimeError(f"Database not ready after {timeout}s: {last_err}")

@st.cache_data(ttl=300, show_spinner=False)
def q(sql: str, params: dict | None = None) -> pd.DataFrame:
    """คืนค่าเป็น DataFrame; ใช้ named params ของ SQLAlchemy เช่น :start, :end"""
    wait_for_db()
    with get_engine().connect() as conn:
        return pd.read_sql(text(sql), conn, params=params or {})