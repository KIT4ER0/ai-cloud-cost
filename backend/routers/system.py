from fastapi import APIRouter
import os, psycopg2

router = APIRouter(tags=["System"])

@router.get("/health")
def health():
    return {"status": "ok"}

@router.get("/db-check")
def db_check():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            dbname=os.getenv("DB_NAME", "ai_cost"),
            user=os.getenv("DB_USER", "ai_user"),
            password=os.getenv("DB_PASSWORD", "ai_password"),
        )
        cur = conn.cursor()
        cur.execute("SELECT NOW();")
        result = cur.fetchone()
        cur.close()
        conn.close()
        return {"db_status": "connected", "time": str(result[0])}
    except Exception as e:
        return {"db_status": "error", "detail": str(e)}
