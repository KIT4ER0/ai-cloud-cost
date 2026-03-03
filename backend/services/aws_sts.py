import os
import boto3
from typing import Optional

def boto_client(name: str, region: Optional[str] = None):
    """
    Create boto3 client with AWS credentials from environment variables.
    Supports both permanent (ACCESS_KEY) and temporary (SESSION_TOKEN) credentials.
    """
    region = region or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    
    kwargs = {
        "region_name": region,
        "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
    }
    
    session_token = os.getenv("AWS_SESSION_TOKEN")
    if session_token:
        kwargs["aws_session_token"] = session_token
        
    return boto3.client(name, **kwargs)

def get_account_id() -> str:
    """
    Return AWS Account ID from environment or STS.
    Returns 'unknown' if failed.
    """
    env_acct = os.getenv("AWS_ACCOUNT_ID")
    if env_acct and len(env_acct) == 12:
        return env_acct
        
    try:
        sts = boto_client("sts")
        return sts.get_caller_identity()["Account"]
    except Exception:
        return "unknown"


# ─── Platform (Third-party) STS Credentials ───────────────────────
TP_ACCESS_KEY = os.getenv("TP_AWS_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
TP_SECRET_KEY = os.getenv("TP_AWS_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")


def _get_sts_client():
    """Create an STS client using our platform's AWS credentials."""
    if not TP_ACCESS_KEY or not TP_SECRET_KEY:
        raise RuntimeError(
            "Missing Platform AWS credentials in backend env "
            "(either TP_AWS_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID)"
        )
    return boto3.client(
        "sts",
        aws_access_key_id=TP_ACCESS_KEY,
        aws_secret_access_key=TP_SECRET_KEY,
    )


def get_assumed_session(role_arn: str, session_name: str, external_id: str) -> boto3.Session:
    """
    Call STS AssumeRole and return a boto3.Session with temporary credentials.
    Use this session to create clients for any AWS service (CloudWatch, EC2, etc.).

    Raises:
        RuntimeError: if platform credentials are missing.
        ValueError: if AWS rejects the AssumeRole call.
    """
    from botocore.exceptions import ClientError

    sts = _get_sts_client()
    try:
        assume_resp = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
            ExternalId=external_id,
        )
    except ClientError as e:
        raise ValueError(e.response["Error"]["Message"]) from e

    creds = assume_resp["Credentials"]

    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def assume_role(role_arn: str, session_name: str, external_id: str) -> dict:
    """
    Call STS AssumeRole and verify identity with the assumed credentials.
    Returns a dict with aws_account_id and arn.

    Raises:
        RuntimeError: if platform credentials are missing.
        ValueError: if AWS rejects the AssumeRole call.
    """
    session = get_assumed_session(role_arn, session_name, external_id)
    identity = session.client("sts").get_caller_identity()

    return {
        "aws_account_id": identity["Account"],
        "arn": identity["Arn"],
    }
