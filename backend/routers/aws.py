import secrets
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import database, models, auth, schemas

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore

router = APIRouter(
    prefix="/api/aws",
    tags=["AWS"],
    dependencies=[Depends(auth.get_current_user)]
)

# Third-party (our platform) AWS credentials — set these in .env
TP_ACCESS_KEY = os.getenv("TP_AWS_ACCESS_KEY_ID")
TP_SECRET_KEY = os.getenv("TP_AWS_SECRET_ACCESS_KEY")


def _get_sts_client():
    """Create an STS client using our platform's AWS credentials."""
    if not boto3:
        raise HTTPException(status_code=500, detail="boto3 is not installed")
    if not TP_ACCESS_KEY or not TP_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Missing TP credentials in env (TP_AWS_ACCESS_KEY_ID / TP_AWS_SECRET_ACCESS_KEY)"
        )
    return boto3.client(
        "sts",
        aws_access_key_id=TP_ACCESS_KEY,
        aws_secret_access_key=TP_SECRET_KEY,
    )


# ─── 1) Generate External ID ───────────────────────────────────────

@router.post("/generate-external-id", response_model=schemas.ExternalIdResponse)
def generate_external_id(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Generate a cryptographically secure external_id and create
    a placeholder AccountAWS record for the current user.
    """
    ext_id = secrets.token_urlsafe(24)

    account = models.AccountAWS(
        user_id=current_user.user_id,
        aws_role_arn="",  # placeholder until connect
        external_id=ext_id,
    )
    db.add(account)
    db.commit()
    db.refresh(account)

    return schemas.ExternalIdResponse(
        external_id=ext_id,
        account_id=account.account_id,
    )


# ─── 2) Connect (verify via STS AssumeRole) ────────────────────────

@router.post("/connect", response_model=schemas.AwsConnectResponse)
def connect_aws(
    req: schemas.AwsConnectRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Accept the user's Role ARN, look up their pending AccountAWS record,
    then call STS AssumeRole to verify the cross-account trust.
    """
    # Find the user's pending account (role_arn still empty)
    account = (
        db.query(models.AccountAWS)
        .filter(
            models.AccountAWS.user_id == current_user.user_id,
            models.AccountAWS.aws_role_arn == "",
        )
        .order_by(models.AccountAWS.account_id.desc())
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=404,
            detail="No pending external_id found. Please generate one first.",
        )

    # Call STS AssumeRole
    sts = _get_sts_client()
    try:
        assume_resp = sts.assume_role(
            RoleArn=req.role_arn,
            RoleSessionName=req.session_name,
            ExternalId=account.external_id,
        )
    except ClientError as e:
        raise HTTPException(status_code=400, detail=e.response["Error"]["Message"])

    creds = assume_resp["Credentials"]

    # Verify identity with the assumed credentials
    assumed_session = boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )
    identity = assumed_session.client("sts").get_caller_identity()

    # Persist the role ARN
    account.aws_role_arn = req.role_arn
    db.commit()

    return schemas.AwsConnectResponse(
        aws_account_id=identity["Account"],
        arn=identity["Arn"],
        status="connected",
    )


# ─── 3) List linked accounts ───────────────────────────────────────

@router.get("/accounts", response_model=list[schemas.AwsAccountOut])
def list_accounts(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Return all AWS accounts linked to the current user."""
    accounts = (
        db.query(models.AccountAWS)
        .filter(models.AccountAWS.user_id == current_user.user_id)
        .all()
    )
    return accounts
