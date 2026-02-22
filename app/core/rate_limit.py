"""Rate limiting configuration using slowapi.

Provides a configured Limiter instance and key extraction function
for per-IP rate limiting across all API endpoints.
"""

from slowapi import Limiter  # pyright: ignore[reportMissingTypeStubs]
from slowapi.util import get_remote_address  # pyright: ignore[reportMissingTypeStubs]
from starlette.requests import Request


def _get_client_ip(request: Request) -> str:
    """Extract client IP from request for rate limiting.

    Uses X-Real-IP header (set by nginx, not client-spoofable) if present,
    falls back to direct client address.

    Args:
        request: The incoming Starlette request.

    Returns:
        Client IP address string.
    """
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_ip)
