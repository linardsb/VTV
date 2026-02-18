"""Agent dependency injection types.

Provides UnifiedDeps dataclass injected into all agent tools via RunContext,
and a factory function for creating configured instances.
"""

from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings


@dataclass
class UnifiedDeps:
    """Dependencies injected into all agent tools via RunContext.

    Attributes:
        transit_http_client: Connection-pooled async HTTP client for GTFS-RT fetching.
        obsidian_http_client: Async HTTP client for Obsidian Local REST API
            (SSL verification disabled for self-signed cert).
        settings: Application settings containing feed URLs, cache TTL, and Obsidian config.
    """

    transit_http_client: httpx.AsyncClient
    obsidian_http_client: httpx.AsyncClient
    settings: Settings


# Keep TransitDeps as an alias for backwards compatibility during migration
TransitDeps = UnifiedDeps


def create_unified_deps(settings: Settings | None = None) -> UnifiedDeps:
    """Create UnifiedDeps with configured httpx clients.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Configured UnifiedDeps instance.
    """
    if settings is None:
        settings = get_settings()
    transit_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    obsidian_client = httpx.AsyncClient(
        timeout=httpx.Timeout(10.0, connect=5.0),
        limits=httpx.Limits(max_connections=5, max_keepalive_connections=3),
        verify=False,  # noqa: S501 - Obsidian Local REST API uses self-signed cert
        headers={"Authorization": f"Bearer {settings.obsidian_api_key or ''}"},
    )
    return UnifiedDeps(
        transit_http_client=transit_client,
        obsidian_http_client=obsidian_client,
        settings=settings,
    )


# Keep old name as alias for backwards compatibility
create_transit_deps = create_unified_deps
