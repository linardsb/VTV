"""Analytics service for dashboard summary data.

Aggregates read-only data from existing feature tables (vehicles, drivers)
and transit infrastructure (GTFS-RT feeds, static cache) to produce
dashboard-ready summaries for the CMS frontend.
"""

from __future__ import annotations

import datetime
import time

import httpx
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.schemas import (
    DriverSummaryResponse,
    FleetSummaryResponse,
    FleetTypeSummary,
    OnTimePerformanceResponse,
    RoutePerformanceSummary,
    ShiftCoverageSummary,
)
from app.core.agents.tools.transit.client import GTFSRealtimeClient, TripUpdateData

# NOTE: 2nd consumer of _compute_route_adherence — extract to app/shared/ on 3rd use.
from app.core.agents.tools.transit.get_adherence_report import _compute_route_adherence
from app.core.agents.tools.transit.static_store import get_static_store
from app.core.agents.tools.transit.utils import (
    classify_service_type,
    gtfs_time_to_minutes,
    validate_date,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.drivers.models import Driver
from app.vehicles.models import Vehicle

logger = get_logger(__name__)

_MAX_ROUTES_REST = 25  # Higher than agent's 15 — REST serves charts


class AnalyticsService:
    """Aggregation service for analytics dashboard endpoints.

    Args:
        db: SQLAlchemy async session for vehicle/driver queries.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_fleet_summary(self) -> FleetSummaryResponse:
        """Compute fleet status breakdown from the vehicles table.

        Returns:
            FleetSummaryResponse with counts by type/status and alerts.
        """
        start_time = time.monotonic()
        logger.info("analytics.fleet_summary.started")

        today = datetime.datetime.now(tz=datetime.UTC).date()

        # Grouped counts by vehicle_type and status
        group_query = (
            select(Vehicle.vehicle_type, Vehicle.status, func.count().label("cnt"))
            .where(Vehicle.is_active.is_(True))
            .group_by(Vehicle.vehicle_type, Vehicle.status)
        )
        group_result = await self.db.execute(group_query)
        rows: list[Row[tuple[str, str, int]]] = list(group_result.all())

        # Pivot into FleetTypeSummary objects
        type_data: dict[str, dict[str, int]] = {}
        for row in rows:
            vtype, vstatus, cnt = row[0], row[1], row[2]
            if vtype not in type_data:
                type_data[vtype] = {"active": 0, "inactive": 0, "maintenance": 0, "total": 0}
            type_data[vtype]["total"] += cnt
            if vstatus == "active":
                type_data[vtype]["active"] += cnt
            elif vstatus == "inactive":
                type_data[vtype]["inactive"] += cnt
            elif vstatus == "maintenance":
                type_data[vtype]["maintenance"] += cnt

        by_type = [
            FleetTypeSummary(
                vehicle_type=vtype,  # pyright: ignore[reportArgumentType]  # DB str → Literal, validated by Pydantic
                total=data["total"],
                active=data["active"],
                inactive=data["inactive"],
                in_maintenance=data["maintenance"],
            )
            for vtype, data in sorted(type_data.items())
        ]

        total_vehicles = sum(t.total for t in by_type)
        active_vehicles = sum(t.active for t in by_type)
        inactive_vehicles = sum(t.inactive for t in by_type)
        in_maintenance = sum(t.in_maintenance for t in by_type)

        # Maintenance due within 7 days
        maint_query = (
            select(func.count())
            .select_from(Vehicle)
            .where(
                Vehicle.is_active.is_(True),
                Vehicle.next_maintenance_date.isnot(None),
                Vehicle.next_maintenance_date >= today,
                Vehicle.next_maintenance_date <= today + datetime.timedelta(days=7),
            )
        )
        maint_result = await self.db.execute(maint_query)
        maintenance_due_7d: int = maint_result.scalar_one()

        # Registration expiring within 30 days
        reg_query = (
            select(func.count())
            .select_from(Vehicle)
            .where(
                Vehicle.is_active.is_(True),
                Vehicle.registration_expiry.isnot(None),
                Vehicle.registration_expiry >= today,
                Vehicle.registration_expiry <= today + datetime.timedelta(days=30),
            )
        )
        reg_result = await self.db.execute(reg_query)
        registration_expiring_30d: int = reg_result.scalar_one()

        # Unassigned active vehicles
        unassigned_query = (
            select(func.count())
            .select_from(Vehicle)
            .where(
                Vehicle.is_active.is_(True),
                Vehicle.status == "active",
                Vehicle.current_driver_id.is_(None),
            )
        )
        unassigned_result = await self.db.execute(unassigned_query)
        unassigned_vehicles: int = unassigned_result.scalar_one()

        # Average mileage
        avg_query = (
            select(func.avg(Vehicle.mileage_km))
            .select_from(Vehicle)
            .where(Vehicle.is_active.is_(True))
        )
        avg_result = await self.db.execute(avg_query)
        raw_avg = avg_result.scalar_one()
        average_mileage_km = round(float(raw_avg), 1) if raw_avg is not None else 0.0

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "analytics.fleet_summary.completed",
            duration_ms=duration_ms,
            total_vehicles=total_vehicles,
        )

        return FleetSummaryResponse(
            total_vehicles=total_vehicles,
            active_vehicles=active_vehicles,
            inactive_vehicles=inactive_vehicles,
            in_maintenance=in_maintenance,
            by_type=by_type,
            maintenance_due_7d=maintenance_due_7d,
            registration_expiring_30d=registration_expiring_30d,
            unassigned_vehicles=unassigned_vehicles,
            average_mileage_km=average_mileage_km,
            generated_at=datetime.datetime.now(tz=datetime.UTC),
        )

    async def get_driver_summary(self) -> DriverSummaryResponse:
        """Compute driver coverage breakdown from the drivers table.

        Returns:
            DriverSummaryResponse with counts by shift/status and alerts.
        """
        start_time = time.monotonic()
        logger.info("analytics.driver_summary.started")

        today = datetime.datetime.now(tz=datetime.UTC).date()

        # Grouped counts by default_shift and status
        group_query = (
            select(Driver.default_shift, Driver.status, func.count().label("cnt"))
            .where(Driver.is_active.is_(True))
            .group_by(Driver.default_shift, Driver.status)
        )
        group_result = await self.db.execute(group_query)
        rows: list[Row[tuple[str, str, int]]] = list(group_result.all())

        # Pivot into ShiftCoverageSummary objects
        shift_data: dict[str, dict[str, int]] = {}
        for row in rows:
            shift, status, cnt = row[0], row[1], row[2]
            if shift not in shift_data:
                shift_data[shift] = {
                    "available": 0,
                    "on_duty": 0,
                    "on_leave": 0,
                    "sick": 0,
                    "total": 0,
                }
            shift_data[shift]["total"] += cnt
            if status in shift_data[shift]:
                shift_data[shift][status] += cnt

        by_shift = [
            ShiftCoverageSummary(
                shift=shift,  # pyright: ignore[reportArgumentType]  # DB str → Literal, validated by Pydantic
                total=data["total"],
                available=data["available"],
                on_duty=data["on_duty"],
                on_leave=data["on_leave"],
                sick=data["sick"],
            )
            for shift, data in sorted(shift_data.items())
        ]

        total_drivers = sum(s.total for s in by_shift)
        available_drivers = sum(s.available for s in by_shift)
        on_duty_drivers = sum(s.on_duty for s in by_shift)
        on_leave_drivers = sum(s.on_leave for s in by_shift)
        sick_drivers = sum(s.sick for s in by_shift)

        # License expiring within 30 days
        lic_query = (
            select(func.count())
            .select_from(Driver)
            .where(
                Driver.is_active.is_(True),
                Driver.license_expiry_date.isnot(None),
                Driver.license_expiry_date >= today,
                Driver.license_expiry_date <= today + datetime.timedelta(days=30),
            )
        )
        lic_result = await self.db.execute(lic_query)
        license_expiring_30d: int = lic_result.scalar_one()

        # Medical cert expiring within 30 days
        med_query = (
            select(func.count())
            .select_from(Driver)
            .where(
                Driver.is_active.is_(True),
                Driver.medical_cert_expiry.isnot(None),
                Driver.medical_cert_expiry >= today,
                Driver.medical_cert_expiry <= today + datetime.timedelta(days=30),
            )
        )
        med_result = await self.db.execute(med_query)
        medical_expiring_30d: int = med_result.scalar_one()

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "analytics.driver_summary.completed",
            duration_ms=duration_ms,
            total_drivers=total_drivers,
        )

        return DriverSummaryResponse(
            total_drivers=total_drivers,
            available_drivers=available_drivers,
            on_duty_drivers=on_duty_drivers,
            on_leave_drivers=on_leave_drivers,
            sick_drivers=sick_drivers,
            by_shift=by_shift,
            license_expiring_30d=license_expiring_30d,
            medical_expiring_30d=medical_expiring_30d,
            generated_at=datetime.datetime.now(tz=datetime.UTC),
        )

    async def get_on_time_performance(
        self,
        *,
        route_id: str | None = None,
        date: str | None = None,
        time_from: str | None = None,
        time_until: str | None = None,
    ) -> OnTimePerformanceResponse:
        """Compute on-time adherence metrics from live GTFS-RT data.

        Args:
            route_id: GTFS route ID for single-route analysis, or None for network.
            date: Service date as YYYY-MM-DD. Defaults to today (Riga timezone).
            time_from: Start of analysis window (HH:MM).
            time_until: End of analysis window (HH:MM).

        Returns:
            OnTimePerformanceResponse with per-route and network metrics.

        Raises:
            ValueError: If date format is invalid.
        """
        start_time = time.monotonic()
        logger.info(
            "analytics.on_time.started",
            route_id=route_id,
            date=date,
            time_from=time_from,
            time_until=time_until,
        )

        # Validate date
        date_result = validate_date(date)
        if isinstance(date_result, str):
            raise ValueError(date_result)
        query_date, date_str = date_result

        try:
            settings = get_settings()
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as http_client:
                client = GTFSRealtimeClient(http_client, settings)
                from app.core.database import get_db_context

                static = await get_static_store(get_db_context, settings)
                trip_updates = await client.fetch_trip_updates()

                # Build trip update lookup
                trip_update_map: dict[str, TripUpdateData] = {tu.trip_id: tu for tu in trip_updates}

                # Active services for the date
                service_ids = static.get_active_service_ids(query_date)

                # Time window
                time_from_minutes = gtfs_time_to_minutes(time_from) if time_from else None
                time_until_minutes = gtfs_time_to_minutes(time_until) if time_until else None

                service_type = classify_service_type(query_date)
                route_summaries: list[RoutePerformanceSummary] = []

                if route_id is not None:
                    # Single route report
                    if route_id not in static.routes:
                        raise ValueError(f"Route '{route_id}' not found in GTFS data.")

                    route_info = static.routes[route_id]
                    all_route_trips = static.route_trips.get(route_id, [])
                    active_trips = [t for t in all_route_trips if t.service_id in service_ids]

                    if active_trips:
                        adherence = _compute_route_adherence(
                            route_id,
                            route_info.route_short_name,
                            active_trips,
                            trip_update_map,
                            static.trip_stop_times,
                            time_from_minutes,
                            time_until_minutes,
                        )
                        route_summaries.append(
                            RoutePerformanceSummary(
                                route_id=adherence.route_id,
                                route_short_name=adherence.route_short_name,
                                scheduled_trips=adherence.scheduled_trips,
                                tracked_trips=adherence.tracked_trips,
                                on_time_count=adherence.on_time_count,
                                late_count=adherence.late_count,
                                early_count=adherence.early_count,
                                on_time_percentage=adherence.on_time_percentage,
                                average_delay_seconds=adherence.average_delay_seconds,
                            )
                        )
                else:
                    # Network report — routes with real-time data
                    rt_route_ids: set[str] = set()
                    for tu in trip_updates:
                        trip_info = static.trips.get(tu.trip_id)
                        if trip_info is not None:
                            rt_route_ids.add(trip_info.route_id)

                    for rid in rt_route_ids:
                        if rid not in static.routes:
                            continue
                        r_info = static.routes[rid]
                        all_trips = static.route_trips.get(rid, [])
                        active = [t for t in all_trips if t.service_id in service_ids]
                        if not active:
                            continue

                        adherence = _compute_route_adherence(
                            rid,
                            r_info.route_short_name,
                            active,
                            trip_update_map,
                            static.trip_stop_times,
                            time_from_minutes,
                            time_until_minutes,
                        )
                        if adherence.scheduled_trips > 0:
                            route_summaries.append(
                                RoutePerformanceSummary(
                                    route_id=adherence.route_id,
                                    route_short_name=adherence.route_short_name,
                                    scheduled_trips=adherence.scheduled_trips,
                                    tracked_trips=adherence.tracked_trips,
                                    on_time_count=adherence.on_time_count,
                                    late_count=adherence.late_count,
                                    early_count=adherence.early_count,
                                    on_time_percentage=adherence.on_time_percentage,
                                    average_delay_seconds=adherence.average_delay_seconds,
                                )
                            )

                    # Sort by worst on-time percentage, cap results
                    route_summaries.sort(key=lambda r: r.on_time_percentage)
                    route_summaries = route_summaries[:_MAX_ROUTES_REST]

            # Network averages
            total_tracked = sum(r.tracked_trips for r in route_summaries)
            total_on_time = sum(r.on_time_count for r in route_summaries)
            total_delay_sum = sum(
                r.average_delay_seconds * r.tracked_trips for r in route_summaries
            )
            network_on_time_pct = (
                round(total_on_time / total_tracked * 100, 1) if total_tracked > 0 else 0.0
            )
            network_avg_delay = (
                round(total_delay_sum / total_tracked, 1) if total_tracked > 0 else 0.0
            )

            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "analytics.on_time.completed",
                duration_ms=duration_ms,
                total_routes=len(route_summaries),
                network_on_time_pct=network_on_time_pct,
            )

            return OnTimePerformanceResponse(
                service_date=date_str,
                service_type=service_type,  # pyright: ignore[reportArgumentType]  # classify_service_type returns str
                time_from=time_from,
                time_until=time_until,
                total_routes=len(route_summaries),
                network_on_time_percentage=network_on_time_pct,
                network_average_delay_seconds=network_avg_delay,
                routes=route_summaries,
                generated_at=datetime.datetime.now(tz=datetime.UTC),
            )

        except ValueError:
            raise
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error(
                "analytics.on_time.failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=duration_ms,
            )
            raise
