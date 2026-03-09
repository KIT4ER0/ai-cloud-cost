from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import database, models, auth, schemas

router = APIRouter(tags=["Auth"])


@router.get("/me", response_model=schemas.UserProfileResponse)
def get_me(
    current_user: models.UserProfile = Depends(auth.get_current_user),
):
    """Return the current user's profile (auto-created on first call)."""
    return current_user
