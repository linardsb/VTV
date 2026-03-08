# pyright: reportUnknownMemberType=false, reportUntypedFunctionDecorator=false
"""Compliance export REST API routes for NeTEx and SIRI XML.

Endpoints:
- GET /api/v1/compliance/netex - NeTEx PublicationDelivery XML export
- GET /api/v1/compliance/siri/vm - SIRI Vehicle Monitoring XML
- GET /api/v1/compliance/siri/sm - SIRI Stop Monitoring XML
- GET /api/v1/compliance/status - Export status and entity counts
"""

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.compliance.schemas import (
    NETEX_RESPONSES,
    SIRI_SM_RESPONSES,
    SIRI_VM_RESPONSES,
    ExportMetadata,
)
from app.compliance.service import ComplianceService
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


def _get_service(
    db: AsyncSession = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ComplianceService:
    """Dependency to create ComplianceService with request-scoped session."""
    return ComplianceService(db, settings)


@router.get("/netex", responses=NETEX_RESPONSES)
@limiter.limit("3/minute")
async def export_netex(
    request: Request,
    agency_id: int | None = Query(None),
    service: ComplianceService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Export schedule data as NeTEx EPIP XML."""
    _ = request
    xml_bytes = await service.export_netex(agency_id=agency_id)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": "attachment; filename=netex.xml"},
    )


@router.get("/siri/vm", responses=SIRI_VM_RESPONSES)
@limiter.limit("10/minute")
async def get_siri_vm(
    request: Request,
    route_id: str | None = Query(None, max_length=100),
    feed_id: str | None = Query(None, max_length=50),
    service: ComplianceService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Get real-time vehicle positions as SIRI-VM XML."""
    _ = request
    xml_bytes = await service.get_siri_vm(route_id=route_id, feed_id=feed_id)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
    )


@router.get("/siri/sm", responses=SIRI_SM_RESPONSES)
@limiter.limit("10/minute")
async def get_siri_sm(
    request: Request,
    stop_name: str = Query(..., min_length=1, max_length=200),
    feed_id: str | None = Query(None, max_length=50),
    service: ComplianceService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """Get stop departure predictions as SIRI-SM XML."""
    _ = request
    xml_bytes = await service.get_siri_sm(stop_name=stop_name, feed_id=feed_id)
    return Response(
        content=xml_bytes,
        media_type="application/xml",
    )


@router.get("/status", response_model=ExportMetadata)
@limiter.limit("30/minute")
async def get_export_status(
    request: Request,
    service: ComplianceService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(get_current_user),  # noqa: B008
) -> ExportMetadata:
    """Get export availability status with entity counts."""
    _ = request
    return await service.get_export_status()
