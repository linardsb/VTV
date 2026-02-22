# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Redis client singleton for shared state across the application."""

from urllib.parse import urlparse

from redis.asyncio import Redis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None


def _redact_url(url: str) -> str:
    """Redact credentials from a URL before logging.

    Args:
        url: URL that may contain embedded credentials.

    Returns:
        URL with password replaced by '***'.
    """
    parsed = urlparse(url)
    if parsed.password:
        return url.replace(f":{parsed.password}@", ":***@")
    return url


async def get_redis() -> Redis:
    """Get or create the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        logger.info("redis.connection_initialized", redis_url=_redact_url(settings.redis_url))
    return _redis_client


async def close_redis() -> None:
    """Close the Redis client. Called on app shutdown."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except RuntimeError:
            pass  # Event loop already closed
        _redis_client = None
        logger.info("redis.connection_closed")
