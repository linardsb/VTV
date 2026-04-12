"""API key authentication dependency for public endpoints."""

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.public_api.exceptions import InvalidAPIKeyError
from app.public_api.models import APIKey
from app.public_api.service import PublicAPIService


async def get_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> APIKey:
    """Extract and validate API key from X-API-Key header.

    Returns the validated APIKey model. Rate limiting is handled
    separately in route handlers to allow per-endpoint control.

    Args:
        request: The incoming HTTP request.
        db: Async database session.

    Returns:
        Validated APIKey model.

    Raises:
        InvalidAPIKeyError: If key is missing or invalid.
        APIKeyRevokedError: If key has been revoked.
    """
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise InvalidAPIKeyError("Missing API key")

    service = PublicAPIService(db)
    return await service.validate_key(raw_key)
