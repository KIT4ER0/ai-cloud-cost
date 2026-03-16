import sys
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from services.sync import sync_aws_costs
from database import SessionLocal
from models import UserProfile

db = SessionLocal()
user = db.query(UserProfile).first()
if not user:
    print('No UserProfile found in DB.')
    sys.exit(1)

print(f'Starting test sync for profile_id: {user.profile_id}')
try:
    sync_aws_costs(user.profile_id, days_back=7)
    print('Test sync completed successfully without raising an exception.')
except Exception as e:
    print(f'Sync failed with exception: {e}')
finally:
    db.close()
