import sys
sys.path.append(".")
from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.mock.mock_metrics_lambda import mock_smart_sync_lambda_metrics

def main():
    db = SessionLocal()
    try:
        mock_smart_sync_lambda_metrics(db, "123456789012", "us-east-1", 2)
        print("Success!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
