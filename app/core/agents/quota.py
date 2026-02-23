"""Daily query quota enforcement for the agent LLM endpoint.

Tracks per-IP query counts with automatic daily reset. Uses Redis for
persistence across restarts, with in-memory fallback when Redis is unavailable.
Returns HTTP 429 when a client exceeds the configured daily quota.
"""

import time
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SECONDS_PER_DAY: int = 86_400


@dataclass
class _QuotaEntry:
    """Tracks query count and reset time for a single IP."""

    count: int = 0
    reset_at: float = field(default_factory=lambda: time.monotonic() + _SECONDS_PER_DAY)


class _InMemoryQuotaTracker:
    """In-memory daily query quota tracker per IP address (fallback)."""

    def __init__(self, daily_limit: int) -> None:
        self._daily_limit = daily_limit
        self._entries: dict[str, _QuotaEntry] = {}

    def check_and_increment(self, client_ip: str) -> bool:
        """Check quota and increment synchronously (fallback path)."""
        now = time.monotonic()
        entry = self._entries.get(client_ip)

        if entry is None or now >= entry.reset_at:
            self._entries[client_ip] = _QuotaEntry(count=1, reset_at=now + _SECONDS_PER_DAY)
            return True

        if entry.count >= self._daily_limit:
            logger.warning(
                "agent.quota_exceeded",
                client_ip=client_ip,
                daily_limit=self._daily_limit,
                current_count=entry.count,
            )
            return False

        entry.count += 1
        return True

    def get_remaining(self, client_ip: str) -> int:
        """Get remaining quota count synchronously."""
        now = time.monotonic()
        entry = self._entries.get(client_ip)
        if entry is None or now >= entry.reset_at:
            return self._daily_limit
        return max(0, self._daily_limit - entry.count)


class QueryQuotaTracker:
    """Redis-backed daily query quota tracker with in-memory fallback.

    Uses Redis INCR with TTL for persistence across server restarts.
    Falls back to in-memory tracking when Redis is unavailable.
    """

    def __init__(self, daily_limit: int) -> None:
        """Initialize with the maximum queries per IP per day.

        Args:
            daily_limit: Maximum number of queries allowed per IP per day.
        """
        self._daily_limit = daily_limit
        self._fallback = _InMemoryQuotaTracker(daily_limit)

    async def check_and_increment(self, client_ip: str) -> bool:
        """Check if the client has quota remaining and increment if so.

        Uses Redis for persistence. Falls back to in-memory on Redis failure.

        Args:
            client_ip: The client's IP address.

        Returns:
            True if the request is allowed, False if quota exceeded.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            key = f"quota:daily:{client_ip}"
            count = await redis_client.incr(key)
            if int(count) == 1:
                # First request today - set TTL to 24h
                await redis_client.expire(key, _SECONDS_PER_DAY)
            if int(count) > self._daily_limit:
                logger.warning(
                    "agent.quota_exceeded",
                    client_ip=client_ip,
                    daily_limit=self._daily_limit,
                    current_count=int(count),
                )
                return False
            return True
        except Exception:
            # Fall back to in-memory
            return self._fallback.check_and_increment(client_ip)

    async def get_remaining(self, client_ip: str) -> int:
        """Get the number of queries remaining for a client.

        Args:
            client_ip: The client's IP address.

        Returns:
            Number of queries remaining in the current period.
        """
        try:
            from app.core.redis import get_redis

            redis_client = await get_redis()
            key = f"quota:daily:{client_ip}"
            count_raw = await redis_client.get(key)
            if count_raw is None:
                return self._daily_limit
            return max(0, self._daily_limit - int(count_raw))
        except Exception:
            return self._fallback.get_remaining(client_ip)


# --- Module-level singleton ---

_quota_tracker: QueryQuotaTracker | None = None


def get_quota_tracker() -> QueryQuotaTracker:
    """Get or create the quota tracker singleton.

    Returns:
        Singleton QueryQuotaTracker instance.
    """
    global _quota_tracker
    if _quota_tracker is None:
        settings = get_settings()
        _quota_tracker = QueryQuotaTracker(daily_limit=settings.agent_daily_quota)
    return _quota_tracker
