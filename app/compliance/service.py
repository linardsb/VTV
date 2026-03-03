"""Business logic for NeTEx/SIRI compliance exports.

Orchestrates data gathering from existing repositories and transforms
it into EU-compliant XML documents using the NeTEx and SIRI builders.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.netex_export import NeTExExporter
from app.compliance.schemas import ExportMetadata
from app.compliance.siri_sm import SiriStopMonitoringBuilder
from app.compliance.siri_vm import SiriVehicleMonitoringBuilder
from app.core.config import Settings
from app.core.logging import get_logger
from app.schedules.repository import ScheduleRepository
from app.stops.repository import StopRepository
from app.transit.service import get_transit_service

logger = get_logger(__name__)


class ComplianceService:
    """Service for generating NeTEx and SIRI compliance exports.

    Gathers data from existing schedule, stop, and transit repositories,
    then delegates XML generation to specialised builder classes.

    Args:
        db: Async database session for schedule/stop queries.
        settings: Application settings with codespace configuration.
    """

    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._settings = settings

    async def export_netex(self, agency_id: int | None = None) -> bytes:
        """Export schedule data as NeTEx EPIP XML.

        Args:
            agency_id: Optional agency ID to filter export scope.

        Returns:
            UTF-8 encoded NeTEx XML bytes.
        """
        start_time = time.monotonic()
        schedule_repo = ScheduleRepository(self._db)
        stop_repo = StopRepository(self._db)

        agencies = await schedule_repo.list_all_agencies()
        routes = await schedule_repo.list_all_routes(agency_id=agency_id)
        calendars = await schedule_repo.list_all_calendars()
        calendar_dates = await schedule_repo.list_all_calendar_dates()

        route_ids = [r.id for r in routes] if agency_id is not None else None
        trips = await schedule_repo.list_all_trips(route_ids=route_ids)

        trip_ids = [t.id for t in trips]
        stop_times = await schedule_repo.list_all_stop_times(
            trip_ids=trip_ids if trip_ids else None
        )

        stops = await stop_repo.list_all()

        logger.info(
            "compliance.netex.export_started",
            agency_count=len(agencies),
            route_count=len(routes),
            trip_count=len(trips),
            stop_count=len(stops),
        )

        exporter = NeTExExporter(
            agencies=agencies,
            routes=routes,
            calendars=calendars,
            calendar_dates=calendar_dates,
            trips=trips,
            stop_times=stop_times,
            stops=stops,
            codespace=self._settings.netex_codespace,
        )
        result = exporter.export()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "compliance.netex.export_completed",
            byte_size=len(result),
            duration_ms=duration_ms,
        )
        return result

    async def get_siri_vm(
        self,
        route_id: str | None = None,
        feed_id: str | None = None,
    ) -> bytes:
        """Generate SIRI-VM XML from real-time vehicle positions.

        Args:
            route_id: Optional route ID filter.
            feed_id: Optional feed ID filter.

        Returns:
            UTF-8 encoded SIRI-VM XML bytes.
        """
        transit_service = get_transit_service()
        response = await transit_service.get_vehicle_positions(route_id=route_id, feed_id=feed_id)

        builder = SiriVehicleMonitoringBuilder(
            participant_ref=self._settings.netex_participant_ref,
        )
        return builder.build(
            vehicles=response.vehicles,
            response_timestamp=response.fetched_at,
        )

    async def get_siri_sm(
        self,
        stop_name: str,
        feed_id: str | None = None,
    ) -> bytes:
        """Generate SIRI-SM XML for a specific stop.

        Args:
            stop_name: Stop name to filter vehicles by.
            feed_id: Optional feed ID filter.

        Returns:
            UTF-8 encoded SIRI-SM XML bytes.
        """
        transit_service = get_transit_service()
        response = await transit_service.get_vehicle_positions(feed_id=feed_id)

        builder = SiriStopMonitoringBuilder(
            participant_ref=self._settings.netex_participant_ref,
        )
        return builder.build(
            stop_name=stop_name,
            vehicles=response.vehicles,
            response_timestamp=response.fetched_at,
        )

    async def get_export_status(self) -> ExportMetadata:
        """Get export availability status with entity counts.

        Returns:
            ExportMetadata with current entity counts.
        """
        schedule_repo = ScheduleRepository(self._db)
        stop_repo = StopRepository(self._db)

        agencies = await schedule_repo.list_all_agencies()
        routes = await schedule_repo.list_all_routes()
        trips = await schedule_repo.list_all_trips()
        stops = await stop_repo.list_all()

        now = datetime.now(UTC).isoformat()

        return ExportMetadata(
            format="NeTEx",
            version="1.2",
            codespace=self._settings.netex_codespace,
            generated_at=now,
            entity_counts={
                "agencies": len(agencies),
                "routes": len(routes),
                "trips": len(trips),
                "stops": len(stops),
            },
        )
