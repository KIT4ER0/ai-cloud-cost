from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from .. import database, models, auth, schemas
from ..services.recommendation_engine import RecommendationEngine

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

@router.post("/recommendations/generate")
def generate_recommendations(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    try:
        engine = RecommendationEngine(db, current_user.profile_id)
        engine.run_all()
    except Exception as e:
        print(f"[Engine Error] {e}")
    return {"message": "Analysis completed."}
