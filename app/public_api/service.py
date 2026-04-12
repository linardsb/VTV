"""Business logic for public developer API key management."""

import asyncio
import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.redis import get_redis
from app.public_api.exceptions import (
    APIKeyRateLimitError,
    APIKeyRevokedError,
    InvalidAPIKeyError,
)
from app.public_api.models import APIKey
from app.public_api.repository import PublicAPIRepository
from app.shared.schemas import PaginationParams

logger = get_logger(__name__)
_background_tasks: set[asyncio.Task[None]] = set()


class PublicAPIService:
    """Service for API key lifecycle, rate limiting, and usage tracking."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.repo = PublicAPIRepository(db)
        self._settings = get_settings()

    def _hash_key(self, raw_key: str) -> str:
        """Compute SHA-256 hex digest of a raw API key.

        Args:
            raw_key: The raw API key string.

        Returns:
            64-character hex digest.
        """
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _make_preview(self, raw_key: str) -> str:
        """Create a truncated preview of a raw API key.

        Args:
            raw_key: The raw API key string.

        Returns:
            Preview in format 'vtv_pk_...last4'.
        """
        prefix = self._settings.public_api_key_prefix
        return f"{prefix}...{raw_key[-4:]}"

    async def generate_key(
        self,
        *,
        name: str,
        owner_user_id: int,
        tier: str = "free",
    ) -> tuple[str, APIKey]:
        """Generate a new API key with SHA-256 hash storage.

        Args:
            name: Human-readable key name.
            owner_user_id: ID of the user creating the key.
            tier: Rate limit tier.

        Returns:
            Tuple of (raw_key, APIKey model). Raw key is shown once.
        """
        raw_key = f"{self._settings.public_api_key_prefix}{secrets.token_hex(16)}"
        key_hash = self._hash_key(raw_key)
        key_preview = self._make_preview(raw_key)

        api_key = await self.repo.create_key(
            key_hash=key_hash,
            key_preview=key_preview,
            name=name,
            owner_user_id=owner_user_id,
            tier=tier,
        )

        logger.info(
            "public_api.service.key_created",
            key_id=api_key.id,
            owner_user_id=owner_user_id,
            tier=tier,
        )

        return raw_key, api_key

    async def validate_key(self, raw_key: str) -> APIKey:
        """Validate a raw API key and return the corresponding model.

        Fail-closed: any error results in 401, never silent pass.

        Args:
            raw_key: The raw API key from X-API-Key header.

        Returns:
            The validated APIKey model.

        Raises:
            InvalidAPIKeyError: If key is missing, invalid, or expired.
            APIKeyRevokedError: If key has been revoked.
        """
        key_hash = self._hash_key(raw_key)
        api_key = await self.repo.find_by_hash(key_hash)

        if api_key is None:
            logger.warning("public_api.service.key_validation_failed", reason="not_found")
            raise InvalidAPIKeyError("Invalid API key")

        if api_key.revoked_at is not None:
            logger.warning(
                "public_api.service.key_validation_failed",
                reason="revoked",
                key_id=api_key.id,
            )
            raise APIKeyRevokedError("API key has been revoked")

        if not api_key.is_active:
            logger.warning(
                "public_api.service.key_validation_failed",
                reason="inactive",
                key_id=api_key.id,
            )
            raise InvalidAPIKeyError("API key is inactive")

        if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
            logger.warning(
                "public_api.service.key_validation_failed",
                reason="expired",
                key_id=api_key.id,
            )
            raise InvalidAPIKeyError("API key has expired")

        return api_key

    async def check_rate_limit(self, api_key: APIKey) -> tuple[int, int]:
        """Check per-key rate limit using Redis fixed-window counter.

        On Redis failure: allow request (rate limiting is non-critical).

        Args:
            api_key: The validated API key model.

        Returns:
            Tuple of (limit, remaining) for response headers.

        Raises:
            APIKeyRateLimitError: If rate limit exceeded.
        """
        tier_limits = self._settings.public_api_tier_limits
        limit = tier_limits.get(api_key.tier, self._settings.public_api_default_rate_limit)

        try:
            redis = await get_redis()
            redis_key = f"public_api:ratelimit:{api_key.id}"
            count = await redis.incr(redis_key)
            if count == 1:
                await redis.expire(redis_key, 60)

            if count > limit:
                logger.warning(
                    "public_api.service.rate_limit_exceeded",
                    key_id=api_key.id,
                    tier=api_key.tier,
                    count=count,
                    limit=limit,
                )
                raise APIKeyRateLimitError(retry_after=60)

            return limit, max(0, limit - count)
        except APIKeyRateLimitError:
            raise
        except Exception:
            logger.warning(
                "public_api.service.rate_limit_redis_error",
                key_id=api_key.id,
                exc_info=True,
            )
            return limit, limit

    async def revoke_key(self, key_id: int, owner_user_id: int) -> APIKey:
        """Revoke an API key (verify ownership first).

        Args:
            key_id: The key's database ID.
            owner_user_id: The requesting user's ID.

        Returns:
            The revoked APIKey model.

        Raises:
            NotFoundError: If key not found or not owned by user.
        """
        api_key = await self.repo.find_by_id(key_id)
        if api_key is None or api_key.owner_user_id != owner_user_id:
            raise NotFoundError("API key not found")

        revoked = await self.repo.revoke_key(key_id)
        if revoked is None:
            raise NotFoundError("API key not found")

        logger.info(
            "public_api.service.key_revoked",
            key_id=key_id,
            owner_user_id=owner_user_id,
        )

        return revoked

    async def list_keys(
        self, owner_user_id: int, pagination: PaginationParams
    ) -> tuple[list[APIKey], int]:
        """List API keys for a user with pagination.

        Args:
            owner_user_id: The owner user's ID.
            pagination: Pagination parameters.

        Returns:
            Tuple of (list of APIKey models, total count).
        """
        return await self.repo.list_by_owner(
            owner_user_id,
            offset=pagination.offset,
            limit=pagination.page_size,
        )

    def record_usage_async(
        self,
        *,
        api_key_id: int,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
    ) -> None:
        """Fire-and-forget usage recording via asyncio.create_task.

        Args:
            api_key_id: The API key's database ID.
            endpoint: The endpoint path.
            method: HTTP method.
            status_code: HTTP response status code.
            response_time_ms: Response time in milliseconds.
        """

        async def _record() -> None:
            try:
                async with get_db_context() as db:
                    repo = PublicAPIRepository(db)
                    await repo.record_usage(
                        api_key_id=api_key_id,
                        endpoint=endpoint,
                        method=method,
                        status_code=status_code,
                        response_time_ms=response_time_ms,
                    )
                    await repo.update_last_used(api_key_id)
            except Exception:
                logger.warning(
                    "public_api.service.usage_recording_failed",
                    api_key_id=api_key_id,
                    exc_info=True,
                )

        _background_tasks.add(task := asyncio.create_task(_record()))
        task.add_done_callback(_background_tasks.discard)
