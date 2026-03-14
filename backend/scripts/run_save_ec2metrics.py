"""
Standalone script: Smart sync EC2 CloudWatch metrics.

Usage:
    python -m backend.scripts.run_save_ec2metrics [--region us-east-1]

Flow:
    1. Query all user_profiles that have aws_role_arn configured
    2. For each profile:
       a. AssumeRole into the customer's AWS account
       b. Call smart_sync_ec2_metrics() which:
          - Checks DB for existing metrics per resource
          - Pulls only missing dates from CloudWatch
          - Saves new metric rows via upsert
"""
import argparse
import logging
import sys
import os

# Ensure project root is on sys.path so `backend.*` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import SessionLocal
from backend.models import UserProfile, EC2Resource
from backend.services.aws_sts import get_assumed_session
# from backend.services.metrics_ec2 import smart_sync_ec2_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_save_ec2metrics")


def run(region: str = "us-east-1", profile_id: int = None):
    """Main entry point: iterate profiles → smart sync."""
    db = SessionLocal()
    try:
        # 1. Find profiles with AWS role configured
        query = db.query(UserProfile).filter(
            UserProfile.aws_role_arn.isnot(None),
            UserProfile.aws_external_id.isnot(None),
        )
        
        if profile_id:
            query = query.filter(UserProfile.profile_id == profile_id)
            
        profiles = query.all()
        logger.info(f"Found {len(profiles)} profiles to process")

        if not profiles:
            logger.warning("No profiles found, nothing to do.")
            return

        for profile in profiles:
            logger.info(
                f"Processing profile_id={profile.profile_id} "
                f"email={profile.email}"
            )

            # 2. AssumeRole
            try:
                session = get_assumed_session(
                    role_arn=profile.aws_role_arn,
                    session_name=f"cron-ec2-{profile.profile_id}",
                    external_id=profile.aws_external_id,
                )
            except Exception as e:
                logger.error(f"  AssumeRole failed for profile {profile.profile_id}: {e}")
                continue

            # 3. Get real account_id from assumed session
            try:
                account_id = session.client("sts").get_caller_identity()["Account"]
            except Exception:
                logger.warning(f"  Could not get account_id via STS, falling back to existing resources")
                first_resource = (
                    db.query(EC2Resource)
                    .filter_by(profile_id=profile.profile_id)
                    .first()
                )
                account_id = first_resource.account_id if first_resource else "unknown"

            # 4. Smart sync — checks DB, pulls only missing, saves
            try:
                from backend.mock.mock_metrics_ec2 import mock_smart_sync_ec2_metrics
                mock_smart_sync_ec2_metrics(
                    db=db,
                    account_id=account_id,
                    region=region,
                    profile_id=profile.profile_id,
                )
                logger.info(f"  ✅ Mock Smart sync completed for profile {profile.profile_id}")
                # For Sync
                # smart_sync_ec2_metrics(
                #     customer_session=session,
                #     account_id=account_id,
                #     region=region,
                #     profile_id=profile.profile_id,
                # )
                # logger.info(f"  ✅ Smart sync completed for profile {profile.profile_id}")
            except Exception as e:
                logger.error(f"  Failed smart sync for profile {profile.profile_id}: {e}")
                continue

        logger.info("🎉 All profiles processed!")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart sync EC2 CloudWatch metrics")
    parser.add_argument("--region", type=str, default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile-id", type=int, help="Optional profile_id to filter")
    args = parser.parse_args()

    logger.info(f"Starting EC2 smart metric sync: region={args.region}, profile_id={args.profile_id}")
    run(region=args.region, profile_id=args.profile_id)
