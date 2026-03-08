# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for notification/alerts."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.schemas import (
    AlertInstanceCreate,
    AlertInstanceResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
    AlertSummaryResponse,
)
from app.alerts.service import AlertService
from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def get_service(db: AsyncSession = Depends(get_db)) -> AlertService:  # noqa: B008
    """Dependency to create AlertService with request-scoped session."""
    return AlertService(db)


# --- Alert Rule endpoints (admin-only) ---
# NOTE: These must be defined BEFORE /{alert_id} to avoid path parameter conflicts


@router.get("/rules", response_model=PaginatedResponse[AlertRuleResponse])
@limiter.limit("30/minute")
async def list_rules(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    enabled_only: bool = Query(False),
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> PaginatedResponse[AlertRuleResponse]:
    """List alert rules. Admin only."""
    _ = request
    return await service.list_rules(pagination, enabled_only=enabled_only)


@router.get("/rules/{rule_id}", response_model=AlertRuleResponse)
@limiter.limit("30/minute")
async def get_rule(
    request: Request,
    rule_id: int,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> AlertRuleResponse:
    """Get a single alert rule by ID. Admin only."""
    _ = request
    return await service.get_rule(rule_id)


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_rule(
    request: Request,
    data: AlertRuleCreate,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> AlertRuleResponse:
    """Create a new alert rule. Admin only."""
    _ = request
    return await service.create_rule(data)


@router.patch("/rules/{rule_id}", response_model=AlertRuleResponse)
@limiter.limit("10/minute")
async def update_rule(
    request: Request,
    rule_id: int,
    data: AlertRuleUpdate,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> AlertRuleResponse:
    """Update an alert rule. Admin only."""
    _ = request
    return await service.update_rule(rule_id, data)


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_rule(
    request: Request,
    rule_id: int,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> None:
    """Delete an alert rule. Admin only."""
    _ = request
    await service.delete_rule(rule_id)


# --- Alert Instance endpoints ---


@router.get("/", response_model=PaginatedResponse[AlertInstanceResponse])
@limiter.limit("30/minute")
async def list_alerts(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    status_filter: str | None = Query(None, alias="status", max_length=20),
    severity: str | None = Query(None, max_length=20),
    alert_type: str | None = Query(None, max_length=30),
    source_entity_type: str | None = Query(None, max_length=20),
    source_entity_id: str | None = Query(None, max_length=100),
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> PaginatedResponse[AlertInstanceResponse]:
    """List alert instances with optional filters."""
    _ = request
    return await service.list_alerts(
        pagination,
        status=status_filter,
        severity=severity,
        alert_type=alert_type,
        source_entity_type=source_entity_type,
        source_entity_id=source_entity_id,
    )


@router.get("/summary", response_model=AlertSummaryResponse)
@limiter.limit("60/minute")
async def get_summary(
    request: Request,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher", "editor", "viewer")),  # noqa: B008
) -> AlertSummaryResponse:
    """Get dashboard badge counts for active alerts."""
    _ = request
    return await service.get_summary()


@router.get("/{alert_id}", response_model=AlertInstanceResponse)
@limiter.limit("30/minute")
async def get_alert(
    request: Request,
    alert_id: int,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> AlertInstanceResponse:
    """Get a single alert instance by ID."""
    _ = request
    return await service.get_alert(alert_id)


@router.post("/", response_model=AlertInstanceResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_alert(
    request: Request,
    data: AlertInstanceCreate,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> AlertInstanceResponse:
    """Create a manual alert instance."""
    _ = request
    return await service.create_alert(data)


@router.post("/{alert_id}/acknowledge", response_model=AlertInstanceResponse)
@limiter.limit("10/minute")
async def acknowledge_alert(
    request: Request,
    alert_id: int,
    service: AlertService = Depends(get_service),  # noqa: B008
    current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> AlertInstanceResponse:
    """Acknowledge an active alert."""
    _ = request
    return await service.acknowledge_alert(alert_id, current_user.id)


@router.post("/{alert_id}/resolve", response_model=AlertInstanceResponse)
@limiter.limit("10/minute")
async def resolve_alert(
    request: Request,
    alert_id: int,
    service: AlertService = Depends(get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "dispatcher")),  # noqa: B008
) -> AlertInstanceResponse:
    """Resolve an alert instance."""
    _ = request
    return await service.resolve_alert(alert_id)
