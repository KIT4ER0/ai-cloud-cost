from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from .. import database, models, auth, schemas

router = APIRouter(
    prefix="/api",
    tags=["Recommendations"],
    dependencies=[Depends(auth.get_current_user)]
)

@router.get("/recommendations", response_model=List[schemas.RecommendationItem])
def get_recommendations(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    return db.query(models.Recommendation).filter(
        models.Recommendation.profile_id == current_user.profile_id,
        models.Recommendation.status == "open",
    ).all()
