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
from backend.services.metrics_ec2 import smart_sync_ec2_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_save_ec2metrics")


def run(region: str = "us-east-1"):
    """Main entry point: iterate profiles → smart sync."""
    db = SessionLocal()
    try:
        # 1. Find all profiles with AWS role configured
        profiles = (
            db.query(UserProfile)
            .filter(
                UserProfile.aws_role_arn.isnot(None),
                UserProfile.aws_external_id.isnot(None),
            )
            .all()
        )
        logger.info(f"Found {len(profiles)} profiles with AWS role configured")

        if not profiles:
            logger.warning("No profiles found, nothing to do.")
            return

        for profile in profiles:
            logger.info(
                f"Processing profile_id={profile.profile_id} "
                f"email={profile.email}"
            )

            # 2. Get account_id from existing resources
            first_resource = (
                db.query(EC2Resource)
                .filter_by(profile_id=profile.profile_id)
                .first()
            )
            account_id = first_resource.account_id if first_resource else "unknown"

            # 3. AssumeRole
            try:
                session = get_assumed_session(
                    role_arn=profile.aws_role_arn,
                    session_name=f"cron-ec2-{profile.profile_id}",
                    external_id=profile.aws_external_id,
                )
            except Exception as e:
                logger.error(f"  AssumeRole failed for profile {profile.profile_id}: {e}")
                continue

            # 4. Smart sync — checks DB, pulls only missing, saves
            try:
                smart_sync_ec2_metrics(
                    customer_session=session,
                    account_id=account_id,
                    region=region,
                    profile_id=profile.profile_id,
                )
                logger.info(f"  ✅ Smart sync completed for profile {profile.profile_id}")
            except Exception as e:
                logger.error(f"  Failed smart sync for profile {profile.profile_id}: {e}")
                continue

        logger.info("🎉 All profiles processed!")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart sync EC2 CloudWatch metrics")
    parser.add_argument("--region", type=str, default="us-east-1", help="AWS region (default: us-east-1)")
    args = parser.parse_args()

    logger.info(f"Starting EC2 smart metric sync: region={args.region}")
    run(region=args.region)
