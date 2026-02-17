"""Transit tool dependency injection types.

Provides TransitDeps dataclass injected into tools via RunContext,
and a factory function for creating configured instances.
"""

from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings


@dataclass
class TransitDeps:
    """Dependencies injected into transit tools via RunContext.

    Attributes:
        http_client: Connection-pooled async HTTP client for GTFS-RT fetching.
        settings: Application settings containing feed URLs and cache TTL.
    """

    http_client: httpx.AsyncClient
    settings: Settings


def create_transit_deps(settings: Settings | None = None) -> TransitDeps:
    """Create TransitDeps with a configured httpx client.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Configured TransitDeps instance.
    """
    if settings is None:
        settings = get_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    return TransitDeps(http_client=client, settings=settings)
