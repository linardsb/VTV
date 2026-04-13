# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""REST API routes for anomaly detection (ML-4.3)."""

import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.requests import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.models import AlertInstance
from app.alerts.schemas import AlertRuleType, AlertSeverityType
from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.ml.anomaly.schemas import AnomalyResponse, AnomalyType
from app.shared.schemas import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/ml/anomalies", tags=["anomalies"])

ANOMALY_TYPES: set[AnomalyType] = {"stuck_vehicle", "gps_gap", "feed_outage", "off_route"}


@router.get("/recent", response_model=PaginatedResponse[AnomalyResponse])
@limiter.limit("30/minute")
async def list_recent_anomalies(
    request: Request,
    pagination: PaginationParams = Depends(),  # noqa: B008
    alert_type: AlertRuleType | None = Query(None, max_length=50),  # noqa: B008
    severity: AlertSeverityType | None = Query(None, max_length=20),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
    _user: User = Depends(require_role("admin", "dispatcher", "viewer")),  # noqa: B008
) -> PaginatedResponse[AnomalyResponse]:
    """List recent anomaly alerts with optional filters."""
    _ = request

    settings = get_settings()
    window = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
        hours=settings.anomaly_recent_window_hours,
    )

    query = select(AlertInstance).where(
        AlertInstance.alert_type.in_(ANOMALY_TYPES),
        AlertInstance.created_at >= window,
    )

    if alert_type is not None:
        query = query.where(AlertInstance.alert_type == alert_type)
    if severity is not None:
        query = query.where(AlertInstance.severity == severity)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Paginated results
    query = query.order_by(AlertInstance.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return PaginatedResponse[AnomalyResponse](
        items=[AnomalyResponse.model_validate(item) for item in items],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
