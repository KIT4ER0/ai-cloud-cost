from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from collections import defaultdict

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


@router.get("/simulation/preview", response_model=schemas.SimulationPreviewResponse)
def get_simulation_preview(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Return all open recommendations with projected total savings grouped by service."""
    recs = db.query(models.Recommendation).filter(
        models.Recommendation.profile_id == current_user.profile_id,
        models.Recommendation.status == "open",
    ).all()

    items = []
    by_service: dict[str, float] = defaultdict(float)

    for rec in recs:
        saving = float(rec.est_saving_usd or 0.0)
        items.append(schemas.SimulationPreviewItem(
            rec_id=rec.rec_id,
            service=rec.service,
            resource_key=rec.resource_key,
            rec_type=rec.rec_type,
            est_saving_usd=saving,
            confidence=float(rec.confidence or 0.0),
        ))
        by_service[rec.service] += saving

    total = sum(by_service.values())

    return schemas.SimulationPreviewResponse(
        total_savings_usd=round(total, 2),
        items=items,
        by_service={k: round(v, 2) for k, v in by_service.items()},
    )
