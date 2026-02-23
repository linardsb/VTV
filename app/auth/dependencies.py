# pyright: reportUnknownMemberType=false
"""FastAPI dependencies for authentication and authorization."""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.token import decode_token
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> User:
    """Decode JWT access token, fetch user from DB, return User model.

    Raises:
        HTTPException(401): If token is missing, invalid, expired, or user not found.
        HTTPException(403): If user account is inactive.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload is None or payload.type != "access":
        logger.warning("auth.token_invalid", reason="decode_failed_or_wrong_type")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    repo = UserRepository(db)
    user = await repo.find_by_id(payload.sub)
    if user is None:
        logger.warning("auth.token_invalid", reason="user_not_found", user_id=payload.sub)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("auth.unauthorized_access", reason="inactive_user", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    return user


def require_role(*roles: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Factory that returns a dependency checking user.role is in allowed roles.

    Usage:
        current_user: User = Depends(require_role("admin", "editor"))
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        if current_user.role not in roles:
            logger.warning(
                "auth.role_escalation_attempt",
                user_id=current_user.id,
                user_role=current_user.role,
                required_roles=list(roles),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return _check_role
