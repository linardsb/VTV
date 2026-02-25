"""Authentication business logic."""

import datetime

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.schemas import LoginResponse
from app.auth.token import create_access_token, create_refresh_token
from app.core.logging import get_logger
from app.shared.models import utcnow

logger = get_logger(__name__)

# Brute-force protection constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = datetime.timedelta(minutes=15)

# Pre-computed dummy hash for timing normalization (HIGH-1: email enumeration prevention)
_DUMMY_HASH = bcrypt.hashpw(b"timing-normalization-dummy", bcrypt.gensalt()).decode("utf-8")


async def _check_redis_brute_force(email: str) -> bool:
    """Check Redis for brute force lockout. Returns True if locked out."""
    try:
        from app.core.redis import get_redis

        redis_client = await get_redis()
        key = f"auth:lockout:{email}"
        locked = await redis_client.get(key)
        return locked is not None
    except Exception:
        logger.warning("auth.redis_lockout_check_unavailable", email=email)
        return False


async def _record_failed_attempt_redis(email: str) -> None:
    """Record a failed login attempt in Redis with TTL."""
    try:
        from app.core.redis import get_redis

        redis_client = await get_redis()
        key = f"auth:failures:{email}"
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, int(LOCKOUT_DURATION.total_seconds()))
        result = await pipe.execute()
        count = int(result[0]) if result else 0
        if count >= MAX_FAILED_ATTEMPTS:
            lockout_key = f"auth:lockout:{email}"
            await redis_client.setex(lockout_key, int(LOCKOUT_DURATION.total_seconds()), "locked")
    except Exception:
        logger.warning("auth.redis_brute_force_unavailable", email=email, exc_info=True)


async def _clear_redis_brute_force(email: str) -> None:
    """Clear Redis brute force keys on successful login."""
    try:
        from app.core.redis import get_redis

        redis_client = await get_redis()
        await redis_client.delete(
            f"auth:failures:{email}",
            f"auth:lockout:{email}",
        )
    except Exception:
        logger.warning("auth.redis_clear_unavailable", email=email, exc_info=True)


class AuthService:
    """Handles authentication logic with bcrypt password verification."""

    def __init__(self, db: AsyncSession) -> None:
        self.repo = UserRepository(db)

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password with bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its bcrypt hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    async def authenticate(self, email: str, password: str) -> LoginResponse:
        """Authenticate a user by email and password.

        Raises:
            InvalidCredentialsError: If credentials are invalid.
            AccountLockedError: If the account is locked.
        """
        # Redis fast-path lockout check (before DB query)
        if await _check_redis_brute_force(email):
            logger.warning("auth.login_locked_redis", email=email)
            raise AccountLockedError("Account is temporarily locked")

        user = await self.repo.find_by_email(email)
        if not user or not user.is_active:
            # Timing normalization: always run bcrypt to prevent email enumeration
            self.verify_password(password, _DUMMY_HASH)
            logger.warning("auth.login_failed", email=email, reason="user_not_found")
            raise InvalidCredentialsError("Invalid email or password")

        # Check lockout
        if user.locked_until and utcnow() < user.locked_until:
            logger.warning("auth.login_locked", email=email)
            raise AccountLockedError("Account is temporarily locked")

        # Clear expired lockout (both DB and Redis)
        if user.locked_until and utcnow() >= user.locked_until:
            user.locked_until = None
            user.failed_attempts = 0
            await _clear_redis_brute_force(email)

        # Verify password
        if not self.verify_password(password, user.hashed_password):
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = utcnow() + LOCKOUT_DURATION
                logger.warning("auth.account_locked", email=email, attempts=user.failed_attempts)
            await self.repo.update(user)
            await _record_failed_attempt_redis(email)
            logger.warning("auth.login_failed", email=email, reason="bad_password")
            raise InvalidCredentialsError("Invalid email or password")

        # Success — clear failed attempts
        if user.failed_attempts > 0:
            user.failed_attempts = 0
            user.locked_until = None
            await self.repo.update(user)
        await _clear_redis_brute_force(email)

        # Issue JWT tokens
        access_token = create_access_token(user.id, user.role)
        refresh_token = create_refresh_token(user.id)

        logger.info("auth.token_issued", email=email, role=user.role)
        return LoginResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            access_token=access_token,
            refresh_token=refresh_token,
        )

    async def refresh_access_token(self, user_id: int) -> str:
        """Issue a new access token for a valid user.

        Args:
            user_id: The user ID from the refresh token.

        Returns:
            New access token string.

        Raises:
            InvalidCredentialsError: If user not found or inactive.
        """
        user = await self.repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise InvalidCredentialsError("User not found or inactive")

        # Check lockout status — locked users must not refresh tokens
        if user.locked_until and utcnow() < user.locked_until:
            logger.warning("auth.refresh_locked", user_id=user_id)
            raise AccountLockedError("Account is temporarily locked")

        access_token = create_access_token(user.id, user.role)
        logger.info("auth.token_refreshed", user_id=user.id)
        return access_token

    async def reset_password(self, user_id: int, new_password: str) -> None:
        """Reset a user's password (admin action).

        Args:
            user_id: Target user's database ID.
            new_password: The new password (already validated by schema).

        Raises:
            InvalidCredentialsError: If user not found.
        """
        user = await self.repo.find_by_id(user_id)
        if not user:
            raise InvalidCredentialsError("User not found")

        user.hashed_password = self.hash_password(new_password)
        user.failed_attempts = 0
        user.locked_until = None
        await self.repo.update(user)

        # Clear Redis brute force state for this user
        await _clear_redis_brute_force(user.email)

        logger.info("auth.password_reset", user_id=user_id)

    async def delete_user_data(self, user_id: int, requesting_user_id: int) -> bool:
        """Delete all user data for GDPR right-to-erasure compliance.

        Deletes the user record (cascading to related data).
        Clears any Redis brute-force tracking keys.

        Args:
            user_id: The ID of the user to delete.
            requesting_user_id: The ID of the admin requesting deletion.

        Returns:
            True if user was found and deleted, False if not found.

        Raises:
            DomainValidationError: If attempting to delete own account.
        """
        from app.core.exceptions import DomainValidationError

        if user_id == requesting_user_id:
            raise DomainValidationError("Cannot delete your own account")

        # Look up user for email (Redis cleanup) and deletion
        user = await self.repo.find_by_id(user_id)
        if user is None:
            return False

        email = user.email

        # Delete user record from database (reuse fetched object)
        await self.repo.delete(user)

        # Clear any Redis brute-force keys for this user
        await _clear_redis_brute_force(email)

        logger.warning(
            "auth.user_data_deleted",
            deleted_user_id=user_id,
            requesting_user_id=requesting_user_id,
        )
        return True

    async def seed_demo_users(self) -> list[User]:
        """Create demo users if no users exist. Returns created users.

        Only seeds in development environment. Uses configurable password
        from DEMO_USER_PASSWORD env var (defaults to 'admin').
        """
        from app.core.config import get_settings

        settings = get_settings()
        if settings.environment != "development":
            logger.info("auth.demo_seed_skipped", environment=settings.environment)
            return []

        count = await self.repo.count()
        if count > 0:
            return []

        password = settings.demo_user_password
        demo_users = [
            ("linardsberzins@gmail.com", password, "Linards Berzins", "admin"),
            ("admin@vtv.lv", password, "VTV Admin", "admin"),
            ("dispatcher@vtv.lv", password, "VTV Dispatcher", "dispatcher"),
            ("editor@vtv.lv", password, "VTV Editor", "editor"),
            ("viewer@vtv.lv", password, "VTV Viewer", "viewer"),
        ]

        created: list[User] = []
        for email, password, name, role in demo_users:
            user = User(
                email=email,
                hashed_password=self.hash_password(password),
                name=name,
                role=role,
            )
            user = await self.repo.create(user)
            created.append(user)

        logger.info("auth.demo_users_seeded", count=len(created))
        return created
