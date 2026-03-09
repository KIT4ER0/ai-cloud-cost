"""
Test script: Pull EC2 + RDS metrics from CloudWatch, aggregate hourly→daily, save to DB.
Run inside Docker:  docker compose exec api python -m backend.services.debug_metrics_sync

Reads aws_role_arn + aws_external_id from cloudcost.users table,
then uses AssumeRole to get a session with proper permissions.
"""
import os
import sys
import logging
import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_role_from_db() -> dict:
    """Fetch aws_role_arn and aws_external_id from existing user data."""
    from backend.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        # Try cloudcost.user_profiles
        try:
            row = db.execute(text(
                "SELECT aws_role_arn, aws_external_id FROM cloudcost.user_profiles "
                "WHERE aws_role_arn IS NOT NULL LIMIT 1"
            )).fetchone()
            if row:
                return {"role_arn": row[0], "external_id": row[1]}
        except Exception:
            pass

        # Try user_profiles (new table)
        try:
            row = db.execute(text(
                "SELECT aws_role_arn, aws_external_id FROM user_profiles "
                "WHERE aws_role_arn IS NOT NULL LIMIT 1"
            )).fetchone()
            if row:
                return {"role_arn": row[0], "external_id": row[1]}
        except Exception:
            pass

        return {}
    finally:
        db.close()


def create_session(role_arn: str, external_id: str) -> boto3.Session:
    """Create boto3 Session via STS AssumeRole."""
    from backend.services.aws_sts import get_assumed_session

    logger.info(f"AssumeRole: {role_arn}")
    return get_assumed_session(
        role_arn=role_arn,
        session_name="TestPullMetrics",
        external_id=external_id,
    )


def get_account_id(session: boto3.Session) -> str:
    """Get AWS account ID via STS."""
    sts = session.client("sts")
    identity = sts.get_caller_identity()
    logger.info(f"Assumed identity: {identity['Arn']}")
    return identity["Account"]


def test_ec2(session: boto3.Session, account_id: str, region: str):
    """Test: Pull EC2 metrics → aggregate → save."""
    from backend.services.metrics_ec2 import pull_ec2_metrics, save_ec2_metrics
    from backend.services.cloudwatch_utils import print_all_datapoints

    logger.info("=" * 60)
    logger.info("TEST: EC2 Metrics")
    logger.info("=" * 60)

    try:
        results = pull_ec2_metrics(
            customer_session=session,
            region=region,
            days_back=30,
            timezone_offset_hours=7,
        )
    except Exception as e:
        logger.error(f"❌ EC2 pull failed: {e}")
        return

    if not results:
        logger.warning("No EC2 instances found — skipping")
        return

    for iid, data in list(results.items())[:2]:
        logger.info(f"\n--- EC2 Instance: {iid} ({data['instance']['instance_type']}) ---")
        print_all_datapoints(data["metrics"], timezone_offset_hours=7)

    logger.info("Saving EC2 metrics to database...")
    save_ec2_metrics(results, account_id=account_id, region=region)
    logger.info("✅ EC2 metrics saved successfully!")


def test_rds(session: boto3.Session, account_id: str, region: str):
    """Test: Pull RDS metrics → aggregate → save."""
    from backend.services.metrics_rds import pull_rds_metrics, save_rds_metrics
    from backend.services.cloudwatch_utils import print_all_datapoints

    logger.info("=" * 60)
    logger.info("TEST: RDS Metrics")
    logger.info("=" * 60)

    try:
        results = pull_rds_metrics(
            customer_session=session,
            region=region,
            days_back=30,
            timezone_offset_hours=7,
        )
    except Exception as e:
        logger.error(f"❌ RDS pull failed: {e}")
        return

    if not results:
        logger.warning("No RDS instances found — skipping")
        return

    for db_id, data in list(results.items())[:2]:
        logger.info(f"\n--- RDS Instance: {db_id} ({data['instance']['engine']}) ---")
        print_all_datapoints(data["metrics"], timezone_offset_hours=7)

    logger.info("Saving RDS metrics to database...")
    save_rds_metrics(results, account_id=account_id, region=region)
    logger.info("✅ RDS metrics saved successfully!")


def verify_db():
    """Quick check: count rows in metric tables."""
    from backend.database import SessionLocal
    from sqlalchemy import text

    db = SessionLocal()
    try:
        for table in ["ec2_resources", "ec2_metrics", "rds_resources", "rds_metrics"]:
            result = db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            logger.info(f"  📊 {table}: {count} rows")
    except Exception as e:
        logger.error(f"DB verification failed: {e}")
    finally:
        db.close()


def main():
    logger.info("🚀 Starting pull metric test...")

    # Get Role ARN from DB
    creds = get_role_from_db()
    if not creds:
        logger.error("❌ No aws_role_arn found in database. Cannot proceed.")
        sys.exit(1)

    logger.info(f"Found Role ARN: {creds['role_arn']}")

    # AssumeRole
    session = create_session(creds["role_arn"], creds["external_id"])
    account_id = get_account_id(session)
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    logger.info(f"AWS Account: {account_id}, Region: {region}")

    # Ensure tables exist
    from backend.database import engine
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    logger.info("DB tables ensured")

    # Run tests
    test_ec2(session, account_id, region)
    test_rds(session, account_id, region)

    # Verify
    logger.info("\n" + "=" * 60)
    logger.info("DB Verification:")
    verify_db()

    logger.info("\n🎉 All tests completed!")


if __name__ == "__main__":
    main()
