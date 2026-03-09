import secrets
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import database, models, auth, schemas
from ..services.aws_sts import assume_role

router = APIRouter(
    prefix="/api/aws",
    tags=["AWS"],
    dependencies=[Depends(auth.get_current_user)]
)


# ─── 1) Generate External ID ───────────────────────────────────────

@router.post("/generate-external-id", response_model=schemas.ExternalIdResponse)
def generate_external_id(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Return the user's permanent aws_external_id from the DB."""
    if not current_user.aws_external_id:
        current_user.aws_external_id = secrets.token_urlsafe(24)
        db.commit()

    return schemas.ExternalIdResponse(
        external_id=current_user.aws_external_id,
        account_id=current_user.profile_id,
    )


# ─── 2) Connect (verify via STS AssumeRole) ────────────────────────

@router.post("/connect", response_model=schemas.AwsConnectResponse)
def connect_aws(
    req: schemas.AwsConnectRequest,
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Accept the user's Role ARN, look up their external ID,
    then call STS AssumeRole to verify the cross-account trust.
    """
    if not current_user.aws_external_id:
        raise HTTPException(
            status_code=404,
            detail="No external_id found for current user.",
        )

    try:
        result = assume_role(
            role_arn=req.role_arn,
            session_name=req.session_name,
            external_id=current_user.aws_external_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Persist the role ARN directly to the user profile
    current_user.aws_role_arn = req.role_arn
    db.commit()

    return schemas.AwsConnectResponse(
        aws_account_id=result["aws_account_id"],
        arn=result["arn"],
        status="connected",
    )


# ─── 3) List linked accounts ───────────────────────────────────────

@router.get("/accounts", response_model=list[schemas.AwsAccountOut])
def list_accounts(
    current_user: models.UserProfile = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Return the AWS account linked to the current user, formatted as a list."""
    if not current_user.aws_role_arn:
        return []

    return [{
        "account_id": current_user.profile_id,
        "user_id": current_user.profile_id,
        "aws_role_arn": current_user.aws_role_arn,
        "external_id": current_user.aws_external_id,
    }]
