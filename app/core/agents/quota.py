"""Daily query quota enforcement for the agent LLM endpoint.

Tracks per-IP query counts with automatic daily reset. Returns HTTP 429
when a client exceeds the configured daily quota.
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


class QueryQuotaTracker:
    """In-memory daily query quota tracker per IP address.

    Automatically resets counts after 24 hours per IP. Thread-safe
    for single-process async usage (no cross-process sharing).
    """

    def __init__(self, daily_limit: int) -> None:
        """Initialize with the maximum queries per IP per day.

        Args:
            daily_limit: Maximum number of queries allowed per IP per day.
        """
        self._daily_limit = daily_limit
        self._entries: dict[str, _QuotaEntry] = {}

    def check_and_increment(self, client_ip: str) -> bool:
        """Check if the client has quota remaining and increment if so.

        Args:
            client_ip: The client's IP address.

        Returns:
            True if the request is allowed, False if quota exceeded.
        """
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
        """Get the number of queries remaining for a client.

        Args:
            client_ip: The client's IP address.

        Returns:
            Number of queries remaining in the current period.
        """
        now = time.monotonic()
        entry = self._entries.get(client_ip)
        if entry is None or now >= entry.reset_at:
            return self._daily_limit
        return max(0, self._daily_limit - entry.count)


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
