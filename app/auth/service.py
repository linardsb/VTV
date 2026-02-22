"""Authentication business logic."""

import datetime

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.auth.models import User
from app.auth.repository import UserRepository
from app.auth.schemas import LoginResponse
from app.core.logging import get_logger
from app.shared.models import utcnow

logger = get_logger(__name__)

# Brute-force protection constants
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = datetime.timedelta(minutes=15)


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
        user = await self.repo.find_by_email(email)
        if not user or not user.is_active:
            logger.warning("auth.login_failed", email=email, reason="user_not_found")
            raise InvalidCredentialsError("Invalid email or password")

        # Check lockout
        if user.locked_until and utcnow() < user.locked_until:
            logger.warning("auth.login_locked", email=email)
            raise AccountLockedError("Account is temporarily locked")

        # Clear expired lockout
        if user.locked_until and utcnow() >= user.locked_until:
            user.locked_until = None
            user.failed_attempts = 0

        # Verify password
        if not self.verify_password(password, user.hashed_password):
            user.failed_attempts += 1
            if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
                user.locked_until = utcnow() + LOCKOUT_DURATION
                logger.warning("auth.account_locked", email=email, attempts=user.failed_attempts)
            await self.repo.update(user)
            logger.warning("auth.login_failed", email=email, reason="bad_password")
            raise InvalidCredentialsError("Invalid email or password")

        # Success — clear failed attempts
        if user.failed_attempts > 0:
            user.failed_attempts = 0
            user.locked_until = None
            await self.repo.update(user)

        logger.info("auth.login_success", email=email, role=user.role)
        return LoginResponse(id=user.id, email=user.email, name=user.name, role=user.role)

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
