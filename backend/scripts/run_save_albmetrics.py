"""
Standalone script: Smart sync ALB/LoadBalancer metrics (Mock).

Usage:
    python -m backend.scripts.run_save_albmetrics [--region ap-southeast-1]
"""
import argparse
import logging
import sys
import os

# Ensure project root is on sys.path so `backend.*` imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.database import SessionLocal
from backend.models import UserProfile, ALBResource
from backend.services.aws_sts import get_assumed_session
# from backend.services.metrics_alb import smart_sync_alb_metrics

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_save_albmetrics")


def run(region: str = "ap-southeast-1", profile_id: int = None):
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
                    session_name=f"cron-alb-{profile.profile_id}",
                    external_id=profile.aws_external_id,
                )
            except Exception as e:
                logger.error(f"  AssumeRole failed for profile {profile.profile_id}: {e}")
                continue

            # 3. Get account_id
            try:
                account_id = session.client("sts").get_caller_identity()["Account"]
            except Exception:
                first_resource = db.query(ALBResource).filter_by(profile_id=profile.profile_id).first()
                account_id = first_resource.account_id if first_resource else "123456789012"

            # 4. MOCK Smart sync
            try:
                from backend.mock.mock_metrics_alb import mock_smart_sync_alb_metrics
                mock_smart_sync_alb_metrics(
                    db=db,
                    account_id=account_id,
                    region=region,
                    profile_id=profile.profile_id,
                )
                logger.info(f"  ✅ Mock Smart sync completed for profile {profile.profile_id}")
                
                # Real Sync (commented for now)
                # smart_sync_alb_metrics(
                #     customer_session=session,
                #     account_id=account_id,
                #     region=region,
                #     profile_id=profile.profile_id,
                # )
                # logger.info(f"  ✅ Smart sync completed for profile {profile.profile_id}")
            except Exception as e:
                logger.error(f"  Failed mock sync for profile {profile.profile_id}: {e}")
                continue

        logger.info("🎉 All profiles processed!")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart sync ALB metrics (Mock)")
    parser.add_argument("--region", type=str, default="ap-southeast-1", help="AWS region")
    parser.add_argument("--profile-id", type=int, help="Optional profile_id to filter")
    args = parser.parse_args()

    run(region=args.region, profile_id=args.profile_id)
