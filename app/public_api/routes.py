# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for public developer API.

Two routers:
- key_mgmt_router (/api/v1/public-api/keys) — JWT-authed key management
- public_router (/public/v1) — API key-authed read-only transit data
"""

import time

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.public_api.auth import get_api_key
from app.public_api.models import APIKey
from app.public_api.schemas import (
    APIKeyCreate,
    APIKeyCreateResponse,
    APIKeyListResponse,
    APIKeyResponse,
    PublicRouteResponse,
    PublicStopResponse,
    PublicVehicleResponse,
)
from app.public_api.service import PublicAPIService
from app.schedules.models import Agency
from app.schedules.repository import ScheduleRepository
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.stops.repository import StopRepository
from app.transit.service import get_transit_service

logger = get_logger(__name__)

# --- Key Management Router (JWT-authed, admin/editor only) ---

key_mgmt_router = APIRouter(prefix="/api/v1/public-api/keys", tags=["public-api-keys"])


def _get_service(db: AsyncSession = Depends(get_db)) -> PublicAPIService:  # noqa: B008
    """Dependency to create PublicAPIService with request-scoped session."""
    return PublicAPIService(db)


@key_mgmt_router.post("/", response_model=APIKeyCreateResponse, status_code=201)
@limiter.limit("10/minute")
async def create_api_key(
    request: Request,
    body: APIKeyCreate,
    current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
    service: PublicAPIService = Depends(_get_service),  # noqa: B008
) -> APIKeyCreateResponse:
    """Create a new API key for the authenticated user."""
    _ = request
    raw_key, api_key = await service.generate_key(
        name=body.name,
        owner_user_id=current_user.id,
    )
    return APIKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_preview=api_key.key_preview,
        tier=api_key.tier,  # pyright: ignore[reportArgumentType]
        created_at=api_key.created_at,  # pyright: ignore[reportArgumentType]
    )


@key_mgmt_router.get("/", response_model=APIKeyListResponse)
@limiter.limit("30/minute")
async def list_api_keys(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
    service: PublicAPIService = Depends(_get_service),  # noqa: B008
) -> APIKeyListResponse:
    """List the authenticated user's API keys (paginated)."""
    _ = request
    keys, total = await service.list_keys(current_user.id, pagination)
    return APIKeyListResponse(
        items=[APIKeyResponse.model_validate(k) for k in keys],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@key_mgmt_router.delete("/{key_id}", response_model=APIKeyResponse)
@limiter.limit("10/minute")
async def revoke_api_key(
    request: Request,
    key_id: int,
    current_user: User = Depends(require_role("admin", "editor")),  # noqa: B008
    service: PublicAPIService = Depends(_get_service),  # noqa: B008
) -> APIKeyResponse:
    """Revoke an API key (immediate, irreversible)."""
    _ = request
    revoked = await service.revoke_key(key_id, current_user.id)
    return APIKeyResponse.model_validate(revoked)


# --- Public Data Router (API key-authed, read-only) ---

public_router = APIRouter(prefix="/public/v1", tags=["public-api"])


@public_router.get("/routes", response_model=PaginatedResponse[PublicRouteResponse])
async def public_list_routes(
    response: Response,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    route_type: int | None = Query(None, ge=0),
    api_key: APIKey = Depends(get_api_key),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedResponse[PublicRouteResponse]:
    """List transit routes (paginated, filterable)."""
    start = time.monotonic()

    service = PublicAPIService(db)
    limit, remaining = await service.check_rate_limit(api_key)

    repo = ScheduleRepository(db)
    routes = await repo.list_routes(
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search,
        route_type=route_type,
        is_active=True,
    )
    total = await repo.count_routes(
        search=search,
        route_type=route_type,
        is_active=True,
    )

    # Resolve agency names in bulk
    agency_ids = {r.agency_id for r in routes}
    agency_map: dict[int, str] = {}
    for agency_id in agency_ids:
        agency = await db.get(Agency, agency_id)
        if agency is not None:
            agency_map[agency_id] = agency.agency_name

    items = [
        PublicRouteResponse(
            route_id=r.gtfs_route_id,
            short_name=r.route_short_name,
            long_name=r.route_long_name,
            type=r.route_type,
            agency_name=agency_map.get(r.agency_id, ""),
        )
        for r in routes
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["Cache-Control"] = "public, max-age=30"
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["Access-Control-Allow-Origin"] = "*"

    service.record_usage_async(
        api_key_id=api_key.id,
        endpoint="/public/v1/routes",
        method="GET",
        status_code=200,
        response_time_ms=elapsed_ms,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@public_router.get("/stops", response_model=PaginatedResponse[PublicStopResponse])
async def public_list_stops(
    response: Response,
    pagination: PaginationParams = Depends(),  # noqa: B008
    search: str | None = Query(None, max_length=200),
    api_key: APIKey = Depends(get_api_key),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> PaginatedResponse[PublicStopResponse]:
    """List transit stops (paginated, searchable)."""
    start = time.monotonic()

    service = PublicAPIService(db)
    limit, remaining = await service.check_rate_limit(api_key)

    repo = StopRepository(db)
    stops = await repo.list(
        offset=pagination.offset,
        limit=pagination.page_size,
        search=search,
        active_only=True,
    )
    total = await repo.count(search=search, active_only=True)

    items = [
        PublicStopResponse(
            stop_id=s.gtfs_stop_id,
            name=s.stop_name,
            lat=s.stop_lat,
            lon=s.stop_lon,
        )
        for s in stops
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["Cache-Control"] = "public, max-age=30"
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["Access-Control-Allow-Origin"] = "*"

    service.record_usage_async(
        api_key_id=api_key.id,
        endpoint="/public/v1/stops",
        method="GET",
        status_code=200,
        response_time_ms=elapsed_ms,
    )

    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@public_router.get("/vehicles", response_model=list[PublicVehicleResponse])
async def public_get_vehicles(
    response: Response,
    route_id: str | None = Query(None, max_length=100, pattern=r"^[\w\-.:]+$"),
    feed_id: str | None = Query(None, max_length=50, pattern=r"^[\w\-]+$"),
    api_key: APIKey = Depends(get_api_key),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> list[PublicVehicleResponse]:
    """Get live vehicle positions."""
    start = time.monotonic()

    service = PublicAPIService(db)
    limit, remaining = await service.check_rate_limit(api_key)

    transit_service = get_transit_service()
    positions = await transit_service.get_vehicle_positions(route_id=route_id, feed_id=feed_id)

    items = [
        PublicVehicleResponse(
            vehicle_id=v.vehicle_id,
            route_id=v.route_id,
            latitude=v.latitude,
            longitude=v.longitude,
            bearing=v.bearing,
            speed=v.speed_kmh,
            timestamp=None,
            feed_id=v.feed_id,
        )
        for v in positions.vehicles
    ]

    elapsed_ms = int((time.monotonic() - start) * 1000)
    response.headers["Cache-Control"] = "public, max-age=5"
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["Access-Control-Allow-Origin"] = "*"

    service.record_usage_async(
        api_key_id=api_key.id,
        endpoint="/public/v1/vehicles",
        method="GET",
        status_code=200,
        response_time_ms=elapsed_ms,
    )

    return items
