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
TP_ACCESS_KEY = os.getenv("TP_AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
TP_SECRET_KEY = os.getenv("TP_AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")


def _get_sts_client():
    """Create an STS client using our platform's AWS credentials."""
    if not boto3:
        raise HTTPException(status_code=500, detail="boto3 is not installed")
    if not TP_ACCESS_KEY or not TP_SECRET_KEY:
        raise HTTPException(
            status_code=500,
            detail="Missing Platform AWS credentials in backend env (either TP_AWS_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID)"
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
    Return the user's permanent aws_external_id from the DB.
    """
    if not current_user.aws_external_id:
        import secrets
        current_user.aws_external_id = secrets.token_urlsafe(24)
        db.commit()

    return schemas.ExternalIdResponse(
        external_id=current_user.aws_external_id,
        account_id=current_user.user_id,
    )


# ─── 2) Connect (verify via STS AssumeRole) ────────────────────────

@router.post("/connect", response_model=schemas.AwsConnectResponse)
def connect_aws(
    req: schemas.AwsConnectRequest,
    current_user: models.User = Depends(auth.get_current_user),
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

    # Call STS AssumeRole
    sts = _get_sts_client()
    try:
        assume_resp = sts.assume_role(
            RoleArn=req.role_arn,
            RoleSessionName=req.session_name,
            ExternalId=current_user.aws_external_id,
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

    # Persist the role ARN directly to the user
    current_user.aws_role_arn = req.role_arn
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
    """Return the AWS account linked to the current user, formatted as a list."""
    if not current_user.aws_role_arn:
        return []
        
    return [{
        "account_id": current_user.user_id,
        "user_id": current_user.user_id,
        "aws_role_arn": current_user.aws_role_arn,
        "external_id": current_user.aws_external_id,
    }]
