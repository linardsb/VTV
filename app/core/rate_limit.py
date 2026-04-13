"""Rate limiting configuration using slowapi.

Provides a configured Limiter instance with per-user bucketing (OPS-4.1).
Authenticated users get rate-limited by user ID with role-based tier limits.
Anonymous requests fall back to per-IP bucketing with the anonymous tier.

Uses Redis as the storage backend when available so rate limits are enforced
across all Gunicorn workers. Falls back to in-memory storage for development
and test environments where Redis may not be reachable.
"""

import ipaddress
from collections.abc import Awaitable, Callable

from slowapi import Limiter  # pyright: ignore[reportMissingTypeStubs]
from slowapi.util import get_remote_address  # pyright: ignore[reportMissingTypeStubs]
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Docker bridge network ranges — only trust X-Real-IP from known reverse proxies
_TRUSTED_PROXY_NETWORKS = (
    ipaddress.ip_network("172.16.0.0/12"),  # Docker default bridge
    ipaddress.ip_network("10.0.0.0/8"),  # Docker custom networks
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
)


class RateLimitIdentityMiddleware(BaseHTTPMiddleware):
    """Lightweight middleware that decodes JWT to populate rate-limit identity.

    Extracts user_id and role from the Authorization header via HMAC-only
    JWT decode (no DB lookup, no revocation check). On success, sets
    ``request.state.rate_limit_user_id`` and ``request.state.rate_limit_role``.
    On failure (missing header, invalid/expired token), does nothing — the
    key function falls back to IP-based bucketing.

    This runs BEFORE rate limit checks so that ``_user_or_ip_key`` can read
    the identity from ``request.state``.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Extract JWT identity and store on request state.

        Args:
            request: The incoming request.
            call_next: The next middleware or route handler.

        Returns:
            Response from the next handler.
        """
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
            try:
                from app.auth.token import decode_token

                payload = decode_token(token)
                if payload is not None:
                    request.state.rate_limit_user_id = payload.sub
                    request.state.rate_limit_role = payload.role
            except Exception as e:
                logger.debug(
                    "rate_limit.identity.decode_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
        return await call_next(request)


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


def _user_or_ip_key(request: Request) -> str:
    """Return a rate-limit key scoped to the authenticated user or client IP.

    Reads identity from ``request.state`` (populated by
    ``RateLimitIdentityMiddleware``). The role is embedded in the key so that
    ``_dynamic_tier_limit`` can parse it for role-based default limits.

    Args:
        request: The incoming Starlette request.

    Returns:
        Key string in format ``user:{id}:{role}`` or ``ip:{ip}:anonymous``.
    """
    user_id = getattr(request.state, "rate_limit_user_id", None)
    role = getattr(request.state, "rate_limit_role", None) or "anonymous"
    if user_id is not None:
        return f"user:{user_id}:{role}"
    return f"ip:{_get_client_ip(request)}:anonymous"


def _dynamic_tier_limit(key: str) -> str:
    """Return the rate limit string for the user's role tier.

    Called by slowapi as a ``default_limits`` callable. Parses the role
    from the key string (format ``prefix:id:role``) and looks up the
    corresponding tier setting.

    Args:
        key: The rate-limit key from ``_user_or_ip_key``.

    Returns:
        Rate limit string (e.g. ``"1000/minute"``).
    """
    settings = get_settings()
    parts = key.rsplit(":", 1)
    role = parts[-1] if len(parts) > 1 else "anonymous"
    tier_map: dict[str, str] = {
        "admin": settings.rate_limit_tier_admin,
        "dispatcher": settings.rate_limit_tier_dispatcher,
        "editor": settings.rate_limit_tier_editor,
        "viewer": settings.rate_limit_tier_viewer,
    }
    return tier_map.get(role, settings.rate_limit_tier_anonymous)


def _chat_subbucket_key(request: Request) -> str:
    """Return a sub-bucket key for the chat endpoint, scoped per user or IP.

    Args:
        request: The incoming Starlette request.

    Returns:
        Key string in format ``chat:user:{id}`` or ``chat:ip:{ip}``.
    """
    user_id = getattr(request.state, "rate_limit_user_id", None)
    if user_id is not None:
        return f"chat:user:{user_id}"
    return f"chat:ip:{_get_client_ip(request)}"


def _analytics_subbucket_key(request: Request) -> str:
    """Return a sub-bucket key for the analytics export endpoint.

    Args:
        request: The incoming Starlette request.

    Returns:
        Key string in format ``analytics:user:{id}`` or ``analytics:ip:{ip}``.
    """
    user_id = getattr(request.state, "rate_limit_user_id", None)
    if user_id is not None:
        return f"analytics:user:{user_id}"
    return f"analytics:ip:{_get_client_ip(request)}"


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
    key_func=_user_or_ip_key,
    default_limits=[_dynamic_tier_limit],
    storage_uri=_storage_uri,
)
