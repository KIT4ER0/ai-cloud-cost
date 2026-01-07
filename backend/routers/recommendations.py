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
def get_recommendations(db: Session = Depends(database.get_db)):
    recs = db.query(models.Recommendation).filter(models.Recommendation.status == "Active").all()
    return [
        {
            "title": r.title,
            "impact": r.impact,
            "priority_score": r.priority_score,
            "description": r.description
        }
        for r in recs
    ]
