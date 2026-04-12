"""Data access layer for API key management."""

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.public_api.models import APIKey, APIKeyUsage
from app.shared.models import utcnow


class PublicAPIRepository:
    """Database operations for API keys and usage tracking."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    async def create_key(
        self,
        *,
        key_hash: str,
        key_preview: str,
        name: str,
        owner_user_id: int,
        tier: str = "free",
    ) -> APIKey:
        """Create a new API key record.

        Args:
            key_hash: SHA-256 hex digest of the raw key.
            key_preview: Truncated preview (vtv_pk_...last4).
            name: Human-readable key name.
            owner_user_id: ID of the user who owns this key.
            tier: Rate limit tier (free/basic/pro).

        Returns:
            The created APIKey model.
        """
        api_key = APIKey(
            key_hash=key_hash,
            key_preview=key_preview,
            name=name,
            owner_user_id=owner_user_id,
            tier=tier,
        )
        self.db.add(api_key)
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def find_by_hash(self, key_hash: str) -> APIKey | None:
        """Look up an API key by its SHA-256 hash (indexed O(1)).

        Args:
            key_hash: SHA-256 hex digest to look up.

        Returns:
            APIKey instance or None if not found.
        """
        result = await self.db.execute(select(APIKey).where(APIKey.key_hash == key_hash))
        return result.scalar_one_or_none()

    async def find_by_id(self, key_id: int) -> APIKey | None:
        """Look up an API key by primary key.

        Args:
            key_id: The key's database ID.

        Returns:
            APIKey instance or None if not found.
        """
        result = await self.db.execute(select(APIKey).where(APIKey.id == key_id))
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_user_id: int, *, offset: int = 0, limit: int = 20
    ) -> tuple[list[APIKey], int]:
        """List API keys owned by a user with pagination.

        Args:
            owner_user_id: The owner user's ID.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (list of APIKey models, total count).
        """
        base = select(APIKey).where(APIKey.owner_user_id == owner_user_id)
        count_result = await self.db.execute(select(func.count()).select_from(base.subquery()))
        total = count_result.scalar_one()

        result = await self.db.execute(
            base.order_by(APIKey.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def revoke_key(self, key_id: int) -> APIKey | None:
        """Revoke an API key by setting revoked_at and is_active=False.

        Args:
            key_id: The key's database ID.

        Returns:
            Updated APIKey or None if not found.
        """
        api_key = await self.find_by_id(key_id)
        if api_key is None:
            return None
        api_key.revoked_at = utcnow()
        api_key.is_active = False
        await self.db.commit()
        await self.db.refresh(api_key)
        return api_key

    async def update_last_used(self, key_id: int) -> None:
        """Update the last_used_at timestamp (fire-and-forget).

        Args:
            key_id: The key's database ID.
        """
        api_key = await self.find_by_id(key_id)
        if api_key is not None:
            api_key.last_used_at = utcnow()
            await self.db.commit()

    async def record_usage(
        self,
        *,
        api_key_id: int,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: int,
    ) -> None:
        """Record a usage entry for an API key.

        Args:
            api_key_id: The API key's database ID.
            endpoint: The endpoint path.
            method: HTTP method (GET, POST, etc.).
            status_code: HTTP response status code.
            response_time_ms: Response time in milliseconds.
        """
        usage = APIKeyUsage(
            api_key_id=api_key_id,
            recorded_at=utcnow(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
        )
        self.db.add(usage)
        await self.db.commit()

    async def get_usage_stats(
        self,
        api_key_id: int,
        *,
        since: datetime.datetime | None = None,
    ) -> int:
        """Count usage records for an API key.

        Args:
            api_key_id: The API key's database ID.
            since: Optional start time filter.

        Returns:
            Total usage count.
        """
        stmt = (
            select(func.count())
            .select_from(APIKeyUsage)
            .where(APIKeyUsage.api_key_id == api_key_id)
        )
        if since is not None:
            stmt = stmt.where(APIKeyUsage.recorded_at >= since)
        result = await self.db.execute(stmt)
        return result.scalar_one()
