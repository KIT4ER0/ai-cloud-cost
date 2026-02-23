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
