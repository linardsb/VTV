# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for authentication."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.requests import Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_role, security
from app.auth.models import User
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    RefreshRequest,
    RefreshResponse,
    UserResponse,
)
from app.auth.service import AuthService
from app.auth.token import decode_token, revoke_token
from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter

logger = get_logger(__name__)

# Refresh token lifetime in seconds (7 days) — used for revocation TTL
REFRESH_TOKEN_TTL_SECONDS = 604800

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
    # Revoke the used refresh token to prevent replay attacks
    await revoke_token(payload.jti, ttl_seconds=REFRESH_TOKEN_TTL_SECONDS)
    logger.info("auth.token.refresh_completed", user_id=payload.sub)
    return RefreshResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> None:
    """Revoke the current access token, effectively logging out."""
    _ = request
    logger.info("auth.logout_started", user_id=current_user.id)
    # get_current_user already validated the token; decode again to extract JTI for revocation
    if credentials is not None:
        payload = decode_token(credentials.credentials)
        if payload is not None:
            await revoke_token(payload.jti)
    logger.info("auth.logout_completed", user_id=current_user.id)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    body: PasswordResetRequest,
    service: AuthService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Reset a user's password (admin only)."""
    _ = request
    await service.reset_password(body.user_id, body.new_password)


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


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("5/minute")
async def delete_user_data(
    request: Request,
    user_id: int,
    current_user: User = Depends(require_role("admin")),  # noqa: B008
    service: AuthService = Depends(get_service),  # noqa: B008
) -> None:
    """Delete user data for GDPR right-to-erasure compliance.

    Admin-only. Permanently removes user record and clears associated
    Redis tracking data. Cannot delete own account.
    """
    _ = request
    deleted = await service.delete_user_data(user_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
