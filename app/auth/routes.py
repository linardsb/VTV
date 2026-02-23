# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for authentication."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    UserResponse,
)
from app.auth.service import AuthService
from app.auth.token import decode_token
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def get_service(db: AsyncSession = Depends(get_db)) -> AuthService:  # noqa: B008
    """Dependency to create AuthService with request-scoped session."""
    return AuthService(db)


@router.post("/login", response_model=LoginResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    service: AuthService = Depends(get_service),  # noqa: B008
) -> LoginResponse:
    """Authenticate user with email and password. Returns JWT tokens."""
    _ = request
    return await service.authenticate(body.email, body.password)


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    service: AuthService = Depends(get_service),  # noqa: B008
) -> RefreshResponse:
    """Exchange a valid refresh token for a new access token."""
    _ = request
    logger.info("auth.token.refresh_started")
    payload = decode_token(body.refresh_token)
    if payload is None or payload.type != "refresh":
        logger.warning("auth.token.refresh_failed", reason="invalid_refresh_token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    access_token = await service.refresh_access_token(payload.sub)
    logger.info("auth.token.refresh_completed", user_id=payload.sub)
    return RefreshResponse(access_token=access_token)


@router.post("/seed", response_model=list[UserResponse])
@limiter.limit("5/minute")
async def seed_demo_users(
    request: Request,
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
    service: AuthService = Depends(get_service),  # noqa: B008
) -> list[UserResponse]:
    """Seed demo users (development only, admin-only, no-op if users exist)."""
    _ = request
    settings = get_settings()
    if settings.environment != "development":
        logger.info("auth.seed.skipped", environment=settings.environment)
        return []
    users = await service.seed_demo_users()
    return [UserResponse.model_validate(u) for u in users]
