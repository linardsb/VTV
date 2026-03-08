"""Business logic for schedule management."""

from __future__ import annotations

import re
import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.schedules.exceptions import (
    AgencyAlreadyExistsError,
    CalendarAlreadyExistsError,
    CalendarDateNotFoundError,
    CalendarNotFoundError,
    GTFSImportError,
    RouteAlreadyExistsError,
    RouteNotFoundError,
    TripAlreadyExistsError,
    TripNotFoundError,
)
from app.schedules.gtfs_import import GTFSImporter
from app.schedules.models import (
    Agency,
    Calendar,
    Trip,
)
from app.schedules.repository import ScheduleRepository
from app.schedules.schemas import (
    AgencyCreate,
    AgencyResponse,
    CalendarCreate,
    CalendarDateCreate,
    CalendarDateResponse,
    CalendarResponse,
    CalendarUpdate,
    GTFSImportResponse,
    RouteCreate,
    RouteResponse,
    RouteShapeResponse,
    RouteShapesResponse,
    RouteUpdate,
    ShapePointResponse,
    StopTimeResponse,
    StopTimesBulkUpdate,
    TripCreate,
    TripDetailResponse,
    TripResponse,
    TripUpdate,
    ValidationResult,
)
from app.shared.schemas import PaginatedResponse, PaginationParams
from app.stops.repository import StopRepository

logger = get_logger(__name__)

_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2}$")


class ScheduleService:
    """Business logic for schedule management."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db
        self.repository = ScheduleRepository(db)

    # --- Agency ---

    async def list_agencies(self, feed_id: str | None = None) -> list[AgencyResponse]:
        """List all agencies.

        Args:
            feed_id: Optional feed filter. If None, returns all feeds.

        Returns:
            List of AgencyResponse.
        """
        agencies = await self.repository.list_agencies(feed_id=feed_id)
        return [AgencyResponse.model_validate(a) for a in agencies]

    async def create_agency(self, data: AgencyCreate) -> AgencyResponse:
        """Create a new agency.

        Args:
            data: Agency creation data.

        Returns:
            AgencyResponse for the created agency.

        Raises:
            RouteAlreadyExistsError: If gtfs_agency_id already exists.
        """
        logger.info("schedules.agency.create_started", gtfs_agency_id=data.gtfs_agency_id)

        existing = await self.repository.get_agency_by_gtfs_id(data.gtfs_agency_id)
        if existing:
            raise AgencyAlreadyExistsError(
                f"Agency with gtfs_agency_id '{data.gtfs_agency_id}' already exists"
            )

        agency = Agency(**data.model_dump())
        agency = await self.repository.create_agency(agency)
        logger.info(
            "schedules.agency.create_completed",
            agency_id=agency.id,
            gtfs_agency_id=agency.gtfs_agency_id,
        )
        return AgencyResponse.model_validate(agency)

    # --- Route ---

    async def get_route(self, route_id: int) -> RouteResponse:
        """Get a route by ID.

        Args:
            route_id: The route's database ID.

        Returns:
            RouteResponse for the found route.

        Raises:
            RouteNotFoundError: If route does not exist.
        """
        route = await self.repository.get_route(route_id)
        if not route:
            raise RouteNotFoundError(f"Route {route_id} not found")
        return RouteResponse.model_validate(route)

    async def list_routes(
        self,
        pagination: PaginationParams,
        search: str | None = None,
        route_type: int | None = None,
        agency_id: int | None = None,
        is_active: bool | None = None,
        feed_id: str | None = None,
    ) -> PaginatedResponse[RouteResponse]:
        """List routes with pagination and filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive substring filter.
            route_type: GTFS route_type filter.
            agency_id: Filter by agency.
            is_active: Filter by active status.

        Returns:
            Paginated list of RouteResponse items.
        """
        logger.info(
            "schedules.route.list_started",
            page=pagination.page,
            search=search,
            route_type=route_type,
            is_active=is_active,
        )
        routes = await self.repository.list_routes(
            offset=pagination.offset,
            limit=pagination.page_size,
            search=search,
            route_type=route_type,
            agency_id=agency_id,
            is_active=is_active,
            feed_id=feed_id,
        )
        total = await self.repository.count_routes(
            search=search,
            route_type=route_type,
            agency_id=agency_id,
            is_active=is_active,
            feed_id=feed_id,
        )
        items = [RouteResponse.model_validate(r) for r in routes]
        logger.info("schedules.route.list_completed", total=total, result_count=len(items))
        return PaginatedResponse[RouteResponse](
            items=items, total=total, page=pagination.page, page_size=pagination.page_size
        )

    async def create_route(self, data: RouteCreate) -> RouteResponse:
        """Create a new route.

        Args:
            data: Route creation data.

        Returns:
            RouteResponse for the created route.

        Raises:
            RouteAlreadyExistsError: If gtfs_route_id already exists.
        """
        logger.info("schedules.route.create_started", gtfs_route_id=data.gtfs_route_id)
        existing = await self.repository.get_route_by_gtfs_id(data.gtfs_route_id)
        if existing:
            raise RouteAlreadyExistsError(
                f"Route with gtfs_route_id '{data.gtfs_route_id}' already exists"
            )
        route = await self.repository.create_route(data)
        logger.info(
            "schedules.route.create_completed",
            route_id=route.id,
            gtfs_route_id=route.gtfs_route_id,
        )
        return RouteResponse.model_validate(route)

    async def update_route(self, route_id: int, data: RouteUpdate) -> RouteResponse:
        """Update an existing route.

        Args:
            route_id: The route's database ID.
            data: Fields to update.

        Returns:
            RouteResponse for the updated route.

        Raises:
            RouteNotFoundError: If route does not exist.
        """
        route = await self.repository.get_route(route_id)
        if not route:
            raise RouteNotFoundError(f"Route {route_id} not found")
        route = await self.repository.update_route(route, data)
        logger.info("schedules.route.update_completed", route_id=route.id)
        return RouteResponse.model_validate(route)

    async def delete_route(self, route_id: int) -> None:
        """Delete a route by ID.

        Args:
            route_id: The route's database ID.

        Raises:
            RouteNotFoundError: If route does not exist.
        """
        route = await self.repository.get_route(route_id)
        if not route:
            raise RouteNotFoundError(f"Route {route_id} not found")
        await self.repository.delete_route(route)
        logger.info("schedules.route.delete_completed", route_id=route_id)

    # --- Calendar ---

    async def get_calendar(self, calendar_id: int) -> CalendarResponse:
        """Get a calendar by ID with its date exceptions.

        Args:
            calendar_id: The calendar's database ID.

        Returns:
            CalendarResponse for the found calendar.

        Raises:
            CalendarNotFoundError: If calendar does not exist.
        """
        calendar = await self.repository.get_calendar(calendar_id)
        if not calendar:
            raise CalendarNotFoundError(f"Calendar {calendar_id} not found")
        return CalendarResponse.model_validate(calendar)

    async def list_calendars(
        self,
        pagination: PaginationParams,
        active_on: date | None = None,
    ) -> PaginatedResponse[CalendarResponse]:
        """List calendars with pagination.

        Args:
            pagination: Page and page_size parameters.
            active_on: Filter calendars active on this date.

        Returns:
            Paginated list of CalendarResponse items.
        """
        calendars = await self.repository.list_calendars(
            offset=pagination.offset, limit=pagination.page_size, active_on=active_on
        )
        total = await self.repository.count_calendars(active_on=active_on)
        items = [CalendarResponse.model_validate(c) for c in calendars]
        return PaginatedResponse[CalendarResponse](
            items=items, total=total, page=pagination.page, page_size=pagination.page_size
        )

    async def create_calendar(
        self, data: CalendarCreate, *, user_id: int | None = None
    ) -> CalendarResponse:
        """Create a new calendar.

        Args:
            data: Calendar creation data.
            user_id: ID of the user creating the calendar (None for GTFS import).

        Returns:
            CalendarResponse for the created calendar.

        Raises:
            CalendarAlreadyExistsError: If gtfs_service_id already exists.
        """
        logger.info("schedules.calendar.create_started", gtfs_service_id=data.gtfs_service_id)
        existing = await self.repository.get_calendar_by_gtfs_id(data.gtfs_service_id)
        if existing:
            raise CalendarAlreadyExistsError(
                f"Calendar with gtfs_service_id '{data.gtfs_service_id}' already exists"
            )
        calendar = Calendar(**data.model_dump(), created_by_id=user_id)
        calendar = await self.repository.create_calendar(calendar)
        logger.info(
            "schedules.calendar.create_completed",
            calendar_id=calendar.id,
            gtfs_service_id=calendar.gtfs_service_id,
            created_by_id=user_id,
        )
        return CalendarResponse.model_validate(calendar)

    async def update_calendar(self, calendar_id: int, data: CalendarUpdate) -> CalendarResponse:
        """Update an existing calendar.

        Args:
            calendar_id: The calendar's database ID.
            data: Fields to update.

        Returns:
            CalendarResponse for the updated calendar.

        Raises:
            CalendarNotFoundError: If calendar does not exist.
        """
        calendar = await self.repository.get_calendar(calendar_id)
        if not calendar:
            raise CalendarNotFoundError(f"Calendar {calendar_id} not found")
        calendar = await self.repository.update_calendar(calendar, data)
        logger.info("schedules.calendar.update_completed", calendar_id=calendar.id)
        return CalendarResponse.model_validate(calendar)

    async def delete_calendar(self, calendar_id: int) -> None:
        """Delete a calendar by ID.

        Args:
            calendar_id: The calendar's database ID.

        Raises:
            CalendarNotFoundError: If calendar does not exist.
        """
        calendar = await self.repository.get_calendar(calendar_id)
        if not calendar:
            raise CalendarNotFoundError(f"Calendar {calendar_id} not found")
        await self.repository.delete_calendar(calendar)
        logger.info("schedules.calendar.delete_completed", calendar_id=calendar_id)

    async def add_calendar_exception(
        self, calendar_id: int, data: CalendarDateCreate
    ) -> CalendarDateResponse:
        """Add a date exception to a calendar.

        Args:
            calendar_id: The calendar's database ID.
            data: Exception date data.

        Returns:
            CalendarDateResponse for the created exception.

        Raises:
            CalendarNotFoundError: If calendar does not exist.
        """
        calendar = await self.repository.get_calendar(calendar_id)
        if not calendar:
            raise CalendarNotFoundError(f"Calendar {calendar_id} not found")
        cal_date = await self.repository.create_calendar_date(calendar_id, data)
        logger.info(
            "schedules.calendar_date.create_completed",
            calendar_id=calendar_id,
            exception_date=str(data.date),
        )
        return CalendarDateResponse.model_validate(cal_date)

    async def remove_calendar_exception(self, exception_id: int) -> None:
        """Remove a calendar date exception.

        Args:
            exception_id: The exception's database ID.

        Raises:
            CalendarDateNotFoundError: If exception does not exist.
        """
        cal_date = await self.repository.get_calendar_date(exception_id)
        if not cal_date:
            raise CalendarDateNotFoundError(f"Calendar exception {exception_id} not found")
        await self.repository.delete_calendar_date(cal_date)
        logger.info("schedules.calendar_date.delete_completed", exception_id=exception_id)

    # --- Trip ---

    async def get_trip(self, trip_id: int) -> TripDetailResponse:
        """Get a trip by ID with its stop times.

        Args:
            trip_id: The trip's database ID.

        Returns:
            TripDetailResponse with stop_times included.

        Raises:
            TripNotFoundError: If trip does not exist.
        """
        trip = await self.repository.get_trip(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip {trip_id} not found")
        stop_times = await self.repository.list_stop_times(trip_id)
        trip_data = TripResponse.model_validate(trip)
        return TripDetailResponse(
            **trip_data.model_dump(),
            stop_times=[StopTimeResponse.model_validate(st) for st in stop_times],
        )

    async def list_trips(
        self,
        pagination: PaginationParams,
        route_id: int | None = None,
        calendar_id: int | None = None,
        direction_id: int | None = None,
    ) -> PaginatedResponse[TripResponse]:
        """List trips with pagination and filtering.

        Args:
            pagination: Page and page_size parameters.
            route_id: Filter by route.
            calendar_id: Filter by calendar.
            direction_id: Filter by direction.

        Returns:
            Paginated list of TripResponse items.
        """
        trips = await self.repository.list_trips(
            offset=pagination.offset,
            limit=pagination.page_size,
            route_id=route_id,
            calendar_id=calendar_id,
            direction_id=direction_id,
        )
        total = await self.repository.count_trips(
            route_id=route_id, calendar_id=calendar_id, direction_id=direction_id
        )
        items = [TripResponse.model_validate(t) for t in trips]
        return PaginatedResponse[TripResponse](
            items=items, total=total, page=pagination.page, page_size=pagination.page_size
        )

    async def create_trip(self, data: TripCreate) -> TripResponse:
        """Create a new trip.

        Args:
            data: Trip creation data.

        Returns:
            TripResponse for the created trip.

        Raises:
            TripAlreadyExistsError: If gtfs_trip_id already exists.
            RouteNotFoundError: If referenced route does not exist.
            CalendarNotFoundError: If referenced calendar does not exist.
        """
        logger.info("schedules.trip.create_started", gtfs_trip_id=data.gtfs_trip_id)

        # Verify route exists
        route = await self.repository.get_route(data.route_id)
        if not route:
            raise RouteNotFoundError(f"Route {data.route_id} not found")

        # Verify calendar exists
        calendar = await self.repository.get_calendar(data.calendar_id)
        if not calendar:
            raise CalendarNotFoundError(f"Calendar {data.calendar_id} not found")

        # Check duplicate
        existing = await self.repository.get_trip_by_gtfs_id(data.gtfs_trip_id)
        if existing:
            raise TripAlreadyExistsError(
                f"Trip with gtfs_trip_id '{data.gtfs_trip_id}' already exists"
            )

        trip = Trip(**data.model_dump())
        trip = await self.repository.create_trip(trip)
        logger.info(
            "schedules.trip.create_completed",
            trip_id=trip.id,
            gtfs_trip_id=trip.gtfs_trip_id,
        )
        return TripResponse.model_validate(trip)

    async def update_trip(self, trip_id: int, data: TripUpdate) -> TripResponse:
        """Update an existing trip.

        Args:
            trip_id: The trip's database ID.
            data: Fields to update.

        Returns:
            TripResponse for the updated trip.

        Raises:
            TripNotFoundError: If trip does not exist.
        """
        trip = await self.repository.get_trip(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip {trip_id} not found")
        trip = await self.repository.update_trip(trip, data)
        logger.info("schedules.trip.update_completed", trip_id=trip.id)
        return TripResponse.model_validate(trip)

    async def delete_trip(self, trip_id: int) -> None:
        """Delete a trip by ID.

        Args:
            trip_id: The trip's database ID.

        Raises:
            TripNotFoundError: If trip does not exist.
        """
        trip = await self.repository.get_trip(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip {trip_id} not found")
        await self.repository.delete_trip(trip)
        logger.info("schedules.trip.delete_completed", trip_id=trip_id)

    # --- StopTime ---

    async def replace_stop_times(
        self, trip_id: int, data: StopTimesBulkUpdate
    ) -> list[StopTimeResponse]:
        """Replace all stop times for a trip.

        Args:
            trip_id: The trip's database ID.
            data: New stop times data.

        Returns:
            List of StopTimeResponse for the new stop times.

        Raises:
            TripNotFoundError: If trip does not exist.
        """
        trip = await self.repository.get_trip(trip_id)
        if not trip:
            raise TripNotFoundError(f"Trip {trip_id} not found")
        stop_times = await self.repository.replace_stop_times(trip_id, data.stop_times)
        logger.info(
            "schedules.stop_times.replace_completed",
            trip_id=trip_id,
            count=len(stop_times),
        )
        return [StopTimeResponse.model_validate(st) for st in stop_times]

    # --- GTFS Import ---

    async def import_gtfs(self, zip_data: bytes, feed_id: str = "riga") -> GTFSImportResponse:
        """Import schedule data from a GTFS ZIP file using merge/upsert.

        Entities with matching GTFS IDs are updated in place, new entities are
        created, and existing entities not in the ZIP are preserved. This allows
        partial ZIP uploads to update only the included entity types without
        wiping unrelated data.

        Args:
            zip_data: Raw bytes of a GTFS ZIP file.

        Returns:
            GTFSImportResponse with entity counts and created/updated breakdown.

        Raises:
            GTFSImportError: If import fails critically.
        """
        logger.info("schedules.import_started", feed_id=feed_id)
        start_time = time.monotonic()

        try:
            # Build stop_map from existing stops (cross-feature read)
            stop_repo = StopRepository(self.db)
            all_stops = await stop_repo.list(offset=0, limit=100000, active_only=False)
            stop_map: dict[str, int] = {s.gtfs_stop_id: s.id for s in all_stops}

            # Parse GTFS ZIP (if stop_map empty, parser also parses stops.txt)
            importer = GTFSImporter(zip_data, feed_id=feed_id)
            result = importer.parse(stop_map=stop_map)

            # --- Merge/upsert flow (no clear_all) ---

            # 1. Upsert stops if parsed from ZIP (fresh DB or stops.txt present)
            stops_created = 0
            stops_updated = 0
            if result.stops:
                stop_values = [
                    {
                        "gtfs_stop_id": s.gtfs_stop_id,
                        "stop_name": s.stop_name,
                        "stop_lat": s.stop_lat,
                        "stop_lon": s.stop_lon,
                        "stop_desc": s.stop_desc,
                        "location_type": s.location_type,
                        "wheelchair_boarding": s.wheelchair_boarding,
                        "is_active": True,
                    }
                    for s in result.stops
                ]
                stops_created, stops_updated = await stop_repo.bulk_upsert(stop_values)

            # 2. Upsert agencies
            agencies_created = 0
            agencies_updated = 0
            if result.agencies:
                agency_values = [
                    {
                        "gtfs_agency_id": a.gtfs_agency_id,
                        "feed_id": feed_id,
                        "agency_name": a.agency_name,
                        "agency_url": a.agency_url,
                        "agency_timezone": a.agency_timezone,
                        "agency_lang": a.agency_lang,
                    }
                    for a in result.agencies
                ]
                agencies_created, agencies_updated = await self.repository.bulk_upsert_agencies(
                    agency_values
                )

            # Reload agency map: gtfs_agency_id -> DB id (scoped to feed)
            agency_map = await self.repository.get_agency_gtfs_map(feed_id=feed_id)

            # 3. Upsert routes (resolve agency_id via map)
            routes_created = 0
            routes_updated = 0
            if result.routes:
                route_values = [
                    {
                        "gtfs_route_id": r.gtfs_route_id,
                        "feed_id": feed_id,
                        "agency_id": agency_map[result.route_agency_refs[i].gtfs_agency_id],
                        "route_short_name": r.route_short_name,
                        "route_long_name": r.route_long_name,
                        "route_type": r.route_type,
                        "route_color": r.route_color,
                        "route_text_color": r.route_text_color,
                        "route_sort_order": r.route_sort_order,
                        "is_active": True,
                    }
                    for i, r in enumerate(result.routes)
                ]
                routes_created, routes_updated = await self.repository.bulk_upsert_routes(
                    route_values
                )

            # 4. Upsert calendars
            calendars_created = 0
            calendars_updated = 0
            if result.calendars:
                calendar_values = [
                    {
                        "gtfs_service_id": c.gtfs_service_id,
                        "feed_id": feed_id,
                        "monday": c.monday,
                        "tuesday": c.tuesday,
                        "wednesday": c.wednesday,
                        "thursday": c.thursday,
                        "friday": c.friday,
                        "saturday": c.saturday,
                        "sunday": c.sunday,
                        "start_date": c.start_date,
                        "end_date": c.end_date,
                    }
                    for c in result.calendars
                ]
                calendars_created, calendars_updated = await self.repository.bulk_upsert_calendars(
                    calendar_values
                )

            # Reload calendar map: gtfs_service_id -> DB id (scoped to feed)
            calendar_map = await self.repository.get_calendar_gtfs_map(feed_id=feed_id)

            # 5. Delete + re-insert calendar_dates for affected calendars
            if result.calendar_dates:
                affected_cal_ids = list(
                    {
                        calendar_map[result.calendar_date_calendar_refs[i].gtfs_service_id]
                        for i in range(len(result.calendar_dates))
                    }
                )
                await self.repository.delete_calendar_dates_for_calendars(affected_cal_ids)
                for i, cd in enumerate(result.calendar_dates):
                    cd.calendar_id = calendar_map[
                        result.calendar_date_calendar_refs[i].gtfs_service_id
                    ]
                await self.repository.bulk_create_calendar_dates(result.calendar_dates)

            # Reload route map: gtfs_route_id -> DB id (scoped to feed)
            route_map = await self.repository.get_route_gtfs_map(feed_id=feed_id)

            # 6. Upsert trips (resolve route_id + calendar_id via maps)
            trips_created = 0
            trips_updated = 0
            if result.trips:
                trip_values = [
                    {
                        "gtfs_trip_id": t.gtfs_trip_id,
                        "feed_id": feed_id,
                        "route_id": route_map[result.trip_route_refs[i].gtfs_route_id],
                        "calendar_id": calendar_map[result.trip_calendar_refs[i].gtfs_service_id],
                        "direction_id": t.direction_id,
                        "trip_headsign": t.trip_headsign,
                        "block_id": t.block_id,
                        "shape_id": t.shape_id,
                    }
                    for i, t in enumerate(result.trips)
                ]
                trips_created, trips_updated = await self.repository.bulk_upsert_trips(trip_values)

            # Reload trip + stop maps for stop_time FK resolution (scoped to feed)
            trip_map = await self.repository.get_trip_gtfs_map(feed_id=feed_id)
            stop_id_map = await stop_repo.get_gtfs_map()

            # 7. Delete + re-insert stop_times for affected trips
            if result.stop_times:
                affected_trip_ids = list(
                    {
                        trip_map[result.stop_time_trip_refs[i].gtfs_trip_id]
                        for i in range(len(result.stop_times))
                    }
                )
                await self.repository.delete_stop_times_for_trips(affected_trip_ids)
                for i, st in enumerate(result.stop_times):
                    st.trip_id = trip_map[result.stop_time_trip_refs[i].gtfs_trip_id]
                    stop_ref = result.stop_time_stop_refs[i]
                    if stop_ref is not None:
                        st.stop_id = stop_id_map.get(stop_ref.gtfs_stop_id, st.stop_id)
                await self.repository.bulk_create_stop_times(result.stop_times)

            # 8. Delete + re-insert shapes for this feed
            shapes_count = 0
            if result.shapes:
                await self.repository.delete_shapes_for_feed(feed_id)
                await self.repository.bulk_create_shapes(result.shapes)
                shapes_count = len(result.shapes)

            await self.db.commit()

            duration = time.monotonic() - start_time
            logger.info(
                "schedules.import_completed",
                agencies=len(result.agencies),
                routes=len(result.routes),
                calendars=len(result.calendars),
                calendar_dates=len(result.calendar_dates),
                trips=len(result.trips),
                stop_times=len(result.stop_times),
                stops=len(result.stops),
                shapes=shapes_count,
                skipped_stop_times=result.skipped_stop_times,
                duration_seconds=round(duration, 2),
            )

            return GTFSImportResponse(
                feed_id=feed_id,
                agencies_count=len(result.agencies),
                agencies_created=agencies_created,
                agencies_updated=agencies_updated,
                routes_count=len(result.routes),
                routes_created=routes_created,
                routes_updated=routes_updated,
                calendars_count=len(result.calendars),
                calendars_created=calendars_created,
                calendars_updated=calendars_updated,
                calendar_dates_count=len(result.calendar_dates),
                trips_count=len(result.trips),
                trips_created=trips_created,
                trips_updated=trips_updated,
                stop_times_count=len(result.stop_times),
                stops_count=len(result.stops),
                stops_created=stops_created,
                stops_updated=stops_updated,
                shapes_count=shapes_count,
                skipped_stop_times=result.skipped_stop_times,
                warnings=result.warnings,
            )
        except Exception as e:
            logger.error(
                "schedules.import_failed",
                exc_info=True,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise GTFSImportError(f"GTFS import failed: {e}") from e

    # --- Validation ---

    async def validate_schedule(self) -> ValidationResult:
        """Validate referential integrity of all schedule data.

        Returns:
            ValidationResult with errors and warnings.
        """
        logger.info("schedules.validate_started")
        errors: list[str] = []
        warnings: list[str] = []

        # Check calendar date ranges
        calendars = await self.repository.list_calendars(offset=0, limit=100000)
        for cal in calendars:
            if cal.start_date > cal.end_date:
                errors.append(f"Calendar {cal.gtfs_service_id}: start_date > end_date")

        # Check trips reference valid routes and calendars
        trips = await self.repository.list_trips(offset=0, limit=100000)
        route_ids: set[int] = set()
        calendar_ids: set[int] = set()
        for trip in trips:
            route_ids.add(trip.route_id)
            calendar_ids.add(trip.calendar_id)

        for rid in route_ids:
            route = await self.repository.get_route(rid)
            if not route:
                errors.append(f"Trip references non-existent route_id={rid}")

        for cid in calendar_ids:
            found_cal = await self.repository.get_calendar(cid)
            if not found_cal:
                errors.append(f"Trip references non-existent calendar_id={cid}")

        # Check stop_time ordering and time formats per trip
        for trip in trips:
            stop_times = await self.repository.list_stop_times(trip.id)
            prev_seq = 0
            for st in stop_times:
                if st.stop_sequence <= prev_seq:
                    warnings.append(
                        f"Trip {trip.gtfs_trip_id}: non-sequential stop_sequence at {st.stop_sequence}"
                    )
                prev_seq = st.stop_sequence

                if not _TIME_PATTERN.match(st.arrival_time):
                    errors.append(
                        f"Trip {trip.gtfs_trip_id}: invalid arrival_time '{st.arrival_time}'"
                    )
                if not _TIME_PATTERN.match(st.departure_time):
                    errors.append(
                        f"Trip {trip.gtfs_trip_id}: invalid departure_time '{st.departure_time}'"
                    )

        valid = len(errors) == 0
        logger.info(
            "schedules.validate_completed",
            valid=valid,
            error_count=len(errors),
            warning_count=len(warnings),
        )
        return ValidationResult(valid=valid, errors=errors, warnings=warnings)

    # --- GTFS Export ---

    async def export_gtfs(self, agency_id: int | None = None, feed_id: str | None = None) -> bytes:
        """Export schedule data as a GTFS-compliant ZIP file.

        Args:
            agency_id: Optional agency ID to filter export to a single agency.
            feed_id: Optional feed filter. If None, exports all feeds.

        Returns:
            ZIP file bytes.
        """
        from app.schedules.gtfs_export import GTFSExporter

        agencies = await self.repository.list_all_agencies(feed_id=feed_id)
        routes = await self.repository.list_all_routes(agency_id=agency_id, feed_id=feed_id)
        calendars = await self.repository.list_all_calendars(feed_id=feed_id)
        calendar_dates = await self.repository.list_all_calendar_dates(feed_id=feed_id)

        route_ids = [r.id for r in routes] if agency_id is not None else None
        trips = await self.repository.list_all_trips(route_ids=route_ids, feed_id=feed_id)

        trip_ids = [t.id for t in trips]
        stop_times = await self.repository.list_all_stop_times(
            trip_ids=trip_ids if trip_ids else None, feed_id=feed_id
        )

        # Cross-feature read: get stops referenced by stop_times
        stop_repo = StopRepository(self.db)
        stops = await stop_repo.list_all()

        shapes = await self.repository.list_all_shapes(feed_id=feed_id)

        exporter = GTFSExporter(
            agencies=agencies,
            routes=routes,
            calendars=calendars,
            calendar_dates=calendar_dates,
            trips=trips,
            stop_times=stop_times,
            stops=stops,
            shapes=shapes,
        )

        logger.info(
            "schedules.export_completed",
            agency_count=len(agencies),
            route_count=len(routes),
            trip_count=len(trips),
            stop_count=len(stops),
        )

        return exporter.export()

    # --- Shape ---

    async def get_route_shapes(self, route_id: int) -> RouteShapesResponse:
        """Get all shapes for a route, grouped by shape_id.

        Args:
            route_id: Database route ID.

        Returns:
            RouteShapesResponse with ordered coordinate arrays per shape.

        Raises:
            NotFoundError: If route does not exist.
        """
        route = await self.repository.get_route(route_id)
        if route is None:
            raise NotFoundError(f"Route {route_id} not found")

        shape_points = await self.repository.get_shapes_for_route(route_id)

        # Group points by shape_id
        shapes_by_id: dict[str, list[ShapePointResponse]] = {}
        for sp in shape_points:
            if sp.gtfs_shape_id not in shapes_by_id:
                shapes_by_id[sp.gtfs_shape_id] = []
            shapes_by_id[sp.gtfs_shape_id].append(
                ShapePointResponse(
                    lat=sp.shape_pt_lat,
                    lon=sp.shape_pt_lon,
                    sequence=sp.shape_pt_sequence,
                    dist_traveled=sp.shape_dist_traveled,
                )
            )

        return RouteShapesResponse(
            route_id=route.id,
            gtfs_route_id=route.gtfs_route_id,
            shapes=[
                RouteShapeResponse(shape_id=sid, points=pts) for sid, pts in shapes_by_id.items()
            ],
        )
