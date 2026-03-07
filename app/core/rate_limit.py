"""Rate limiting configuration using slowapi.

Provides a configured Limiter instance and key extraction function
for per-IP rate limiting across all API endpoints.

Uses Redis as the storage backend when available so rate limits are enforced
across all Gunicorn workers. Falls back to in-memory storage for development
and test environments where Redis may not be reachable.
"""

import ipaddress

from slowapi import Limiter  # pyright: ignore[reportMissingTypeStubs]
from slowapi.util import get_remote_address  # pyright: ignore[reportMissingTypeStubs]
from starlette.requests import Request

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Docker bridge network ranges — only trust X-Real-IP from known reverse proxies
_TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("172.16.0.0/12"),  # Docker default bridge
    ipaddress.ip_network("10.0.0.0/8"),  # Docker custom networks
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
)


def _get_client_ip(request: Request) -> str:
    """Extract client IP, only trusting X-Real-IP from known proxy networks.

    When the request comes from a trusted proxy (Docker internal network),
    use the X-Real-IP header set by nginx. Otherwise, use the direct
    connection address to prevent IP spoofing via direct backend access.

    Args:
        request: The incoming Starlette request.

    Returns:
        Client IP address string.
    """
    direct_ip = get_remote_address(request)
    try:
        addr = ipaddress.ip_address(direct_ip)
        if any(addr in net for net in _TRUSTED_PROXY_NETWORKS):
            real_ip = request.headers.get("X-Real-IP")
            if real_ip:
                return real_ip.strip()
    except ValueError:
        pass
    return direct_ip


def _get_storage_uri() -> str | None:
    """Return Redis URI for rate limit storage, or None for in-memory fallback.

    Tests Redis connectivity at startup. If Redis is unreachable (e.g. unit tests
    without Docker), falls back to in-memory storage with a warning.
    """
    import redis

    settings = get_settings()
    try:
        client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1)  # pyright: ignore[reportUnknownMemberType]
        client.ping()  # pyright: ignore[reportUnknownMemberType]
        client.close()
        return settings.redis_url
    except Exception as e:
        logger.warning(
            "rate_limit.redis_unavailable",
            error=str(e),
            error_type=type(e).__name__,
            detail="Falling back to in-memory storage (rate limits per-worker only)",
        )
        return None


_storage_uri = _get_storage_uri()
limiter = Limiter(
    key_func=_get_client_ip,
    storage_uri=_storage_uri,
)
