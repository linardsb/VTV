# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""JWT token creation and validation utilities."""

import datetime
import uuid
from typing import Any

from jose import JWTError, jwt  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class TokenPayload(BaseModel):
    """Decoded JWT token payload."""

    sub: int  # user_id
    role: str
    exp: datetime.datetime
    type: str  # "access" or "refresh"
    jti: str  # unique token ID for revocation


def create_access_token(user_id: int, role: str) -> str:
    """Create a short-lived access token.

    Args:
        user_id: The database ID of the authenticated user.
        role: The user's role (admin, dispatcher, editor, viewer).

    Returns:
        Encoded JWT access token string.
    """
    settings = get_settings()
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    payload: dict[str, Any] = {  # JWT payload values are heterogeneous (str, datetime, int)
        "sub": str(user_id),
        "role": role,
        "exp": expire,
        "type": "access",
        "jti": uuid.uuid4().hex,
    }
    token: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def create_refresh_token(user_id: int) -> str:
    """Create a longer-lived refresh token.

    Args:
        user_id: The database ID of the authenticated user.

    Returns:
        Encoded JWT refresh token string.
    """
    settings = get_settings()
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": "",  # refresh tokens don't carry role — re-fetched on refresh
        "exp": expire,
        "type": "refresh",
        "jti": uuid.uuid4().hex,
    }
    token: str = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: The encoded JWT token string.

    Returns:
        TokenPayload if valid, None if invalid/expired.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return TokenPayload(
            sub=int(payload["sub"]),
            role=str(payload.get("role", "")),
            exp=datetime.datetime.fromtimestamp(float(payload["exp"]), tz=datetime.UTC),
            type=str(payload.get("type", "access")),
            jti=str(payload.get("jti", "")),
        )
    except (JWTError, KeyError, ValueError) as e:
        logger.warning("auth.token.decode_failed", error=str(e))
        return None
