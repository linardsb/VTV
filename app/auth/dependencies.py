# pyright: reportUnknownMemberType=false
"""FastAPI dependencies for authentication and authorization."""

from collections.abc import Callable, Coroutine
from typing import Any

from cachetools import TTLCache  # pyright: ignore[reportMissingTypeStubs]
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.token import decode_token, is_token_revoked
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)

# Per-worker TTL cache: avoids DB lookup on every authenticated request.
# Token revocation is still checked via Redis (immediate). User deactivation
# has max 30s delay — acceptable since JWT access tokens have 30min lifetime.
# Each Gunicorn worker gets its own cache instance (separate processes).
#
# SAFETY: Caching ORM User objects works because expire_on_commit=False is set
# in database.py:33 and all accessed fields (id, is_active, role, username) are
# eagerly loaded columns — no lazy-loaded relationships. If relationships are
# added to User in the future, they must be eagerly loaded or this cache will
# raise DetachedInstanceError.
_user_cache: TTLCache[int, User] = TTLCache(maxsize=200, ttl=30)


def invalidate_user_cache(user_id: int) -> None:
    """Remove a user from the auth cache (call on update/delete/deactivate)."""
    _user_cache.pop(user_id, None)


def clear_user_cache() -> None:
    """Clear the entire auth user cache. Used by tests for isolation."""
    _user_cache.clear()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> User:
    """Decode JWT access token, fetch user from DB, return User model.

    Uses a TTL cache (30s, max 200 entries) to skip the DB lookup for
    recently-authenticated users. Token revocation is still checked in
    Redis on every request (no cache bypass).

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

    # Check token revocation denylist (always, never cached)
    if await is_token_revoked(payload.jti):
        logger.warning("auth.token_revoked", jti=payload.jti)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check user cache before DB
    cached: User | None = _user_cache.get(payload.sub)
    if cached is not None:
        if not cached.is_active:
            logger.warning("auth.unauthorized_access", reason="inactive_user", user_id=cached.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive",
            )
        return cached

    # Cache miss — query DB
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

    # Detach from session before caching. session.close() triggers rollback
    # which expires all attributes even with expire_on_commit=False.
    # Expunging first preserves the loaded attribute state in the cache.
    db.expunge(user)
    _user_cache[payload.sub] = user
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
