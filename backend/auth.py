"""
Supabase Auth integration for FastAPI.
Verifies Supabase JWT tokens (ES256 via JWKS) and manages user profiles.
"""
import os
import secrets
import logging
from typing import Optional
from functools import lru_cache

import jwt as pyjwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

try:
    from . import models, database
except ImportError:
    from backend import models, database

logger = logging.getLogger(__name__)

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL", "")

# Use HTTPBearer (Supabase sends Bearer tokens)
security = HTTPBearer()


@lru_cache(maxsize=1)
def _get_jwks_client() -> PyJWKClient:
    """Create and cache a PyJWKClient that fetches public keys from Supabase."""
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL not configured")
    jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
    logger.info(f"JWKS endpoint: {jwks_url}")
    return PyJWKClient(jwks_url, cache_keys=True)


def _decode_supabase_token(token: str) -> dict:
    """Decode and verify a Supabase JWT token using JWKS (ES256)."""
    try:
        jwks_client = _get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except pyjwt.InvalidTokenError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(database.get_db),
) -> models.UserProfile:
    """
    Verify Supabase JWT → extract user UUID → get-or-create UserProfile.
    Returns the UserProfile ORM object.
    """
    payload = _decode_supabase_token(credentials.credentials)

    supabase_user_id: Optional[str] = payload.get("sub")
    if not supabase_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )

    email: str = payload.get("email", "")

    # Get or create UserProfile
    profile = db.query(models.UserProfile).filter_by(
        supabase_user_id=supabase_user_id
    ).first()

    if not profile:
        profile = models.UserProfile(
            supabase_user_id=supabase_user_id,
            email=email,
            aws_external_id=secrets.token_urlsafe(24),
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"Created UserProfile for {email} (supabase_id={supabase_user_id})")

    return profile
