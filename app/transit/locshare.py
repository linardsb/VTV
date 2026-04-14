# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false
"""Shareable tracking link JWT signing, verification, and QR code generation (LV-3.4)."""

import base64
import datetime
import hashlib
import io
import uuid
from typing import Any

import qrcode  # type: ignore[import-untyped]
from jose import JWTError, jwt  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShareTokenPayload(BaseModel):
    """Decoded share link JWT claims."""

    sub: str  # vehicle_id
    route_id: str | None
    feed_id: str
    exp: datetime.datetime
    type: str  # "share"
    jti: str


def create_share_token(
    vehicle_id: str,
    route_id: str | None,
    feed_id: str,
    expiry_hours: int,
) -> tuple[str, str]:
    """Sign a share link JWT. Returns (token, token_hash)."""
    settings = get_settings()
    secret = settings.share_link_secret_key or settings.jwt_secret_key
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=expiry_hours)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": vehicle_id,
        "route_id": route_id,
        "feed_id": feed_id,
        "exp": expire,
        "type": "share",
        "jti": jti,
    }
    token: str = jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def decode_share_token(token: str) -> ShareTokenPayload | None:
    """Decode and validate a share link JWT. Returns None if invalid/expired."""
    settings = get_settings()
    secret = settings.share_link_secret_key or settings.jwt_secret_key
    try:
        data = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
        )
        if data.get("type") != "share":
            logger.warning("transit.share_link.invalid_type", token_type=data.get("type"))
            return None
        return ShareTokenPayload(**data)
    except JWTError:
        return None


def generate_qr_code_base64(url: str) -> str:
    """Generate a QR code PNG as a base64 string."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # pyright: ignore[reportCallIssue]
    return base64.b64encode(buf.getvalue()).decode("ascii")


def hash_token(token: str) -> str:
    """SHA-256 hash of a token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
