# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for authentication."""

from fastapi import APIRouter, Depends
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import LoginRequest, LoginResponse, UserResponse
from app.auth.service import AuthService
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
    """Authenticate user with email and password."""
    _ = request
    return await service.authenticate(body.email, body.password)


@router.post("/seed", response_model=list[UserResponse])
@limiter.limit("5/minute")
async def seed_demo_users(
    request: Request,
    service: AuthService = Depends(get_service),  # noqa: B008
) -> list[UserResponse]:
    """Seed demo users (development only, no-op if users exist)."""
    _ = request
    settings = get_settings()
    if settings.environment != "development":
        logger.info("auth.seed.skipped", environment=settings.environment)
        return []
    users = await service.seed_demo_users()
    return [UserResponse.model_validate(u) for u in users]
