"""Business logic for schedule management."""

from __future__ import annotations

import re
import time
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.schedules.exceptions import (
    CalendarAlreadyExistsError,
    CalendarNotFoundError,
    GTFSImportError,
    RouteAlreadyExistsError,
    RouteNotFoundError,
    StopTimeNotFoundError,
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
    RouteUpdate,
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

    async def list_agencies(self) -> list[AgencyResponse]:
        """List all agencies.

        Returns:
            List of AgencyResponse.
        """
        agencies = await self.repository.list_agencies()
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
            raise RouteAlreadyExistsError(
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
    ) -> PaginatedResponse[RouteResponse]:
        """List routes with pagination and filtering.

        Args:
            pagination: Page and page_size parameters.
            search: Case-insensitive substring filter.
            route_type: GTFS route_type filter.
            agency_id: Filter by agency.

        Returns:
            Paginated list of RouteResponse items.
        """
        logger.info(
            "schedules.route.list_started",
            page=pagination.page,
            search=search,
            route_type=route_type,
        )
        routes = await self.repository.list_routes(
            offset=pagination.offset,
            limit=pagination.page_size,
            search=search,
            route_type=route_type,
            agency_id=agency_id,
        )
        total = await self.repository.count_routes(
            search=search, route_type=route_type, agency_id=agency_id
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

    async def create_calendar(self, data: CalendarCreate) -> CalendarResponse:
        """Create a new calendar.

        Args:
            data: Calendar creation data.

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
        calendar = Calendar(**data.model_dump())
        calendar = await self.repository.create_calendar(calendar)
        logger.info(
            "schedules.calendar.create_completed",
            calendar_id=calendar.id,
            gtfs_service_id=calendar.gtfs_service_id,
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
            StopTimeNotFoundError: If exception does not exist.
        """
        cal_date = await self.repository.get_calendar_date(exception_id)
        if not cal_date:
            raise StopTimeNotFoundError(f"Calendar exception {exception_id} not found")
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

    async def import_gtfs(self, zip_data: bytes) -> GTFSImportResponse:
        """Import schedule data from a GTFS ZIP file.

        Replaces all existing schedule data with the contents of the ZIP.

        Args:
            zip_data: Raw bytes of a GTFS ZIP file.

        Returns:
            GTFSImportResponse with entity counts and warnings.

        Raises:
            GTFSImportError: If import fails critically.
        """
        logger.info("schedules.import_started")
        start_time = time.monotonic()

        try:
            # Build stop_map from existing stops (cross-feature read)
            stop_repo = StopRepository(self.db)
            all_stops = await stop_repo.list(offset=0, limit=100000, active_only=False)
            stop_map: dict[str, int] = {s.gtfs_stop_id: s.id for s in all_stops}

            # Parse GTFS ZIP
            importer = GTFSImporter(zip_data)
            result = importer.parse(stop_map=stop_map)

            # Clear existing data
            await self.repository.clear_all_schedule_data()

            # Interleaved insert: agencies
            if result.agencies:
                await self.repository.bulk_create_agencies(result.agencies)
                agency_map = {a.gtfs_agency_id: a.id for a in result.agencies}
            else:
                agency_map = {}

            # Resolve route agency_ids and insert
            for route in result.routes:
                if agency_map:
                    route.agency_id = next(iter(agency_map.values()))
            if result.routes:
                await self.repository.bulk_create_routes(result.routes)

            # Insert calendars
            if result.calendars:
                await self.repository.bulk_create_calendars(result.calendars)

            # Insert calendar dates
            if result.calendar_dates:
                await self.repository.bulk_create_calendar_dates(result.calendar_dates)

            # Insert trips
            if result.trips:
                await self.repository.bulk_create_trips(result.trips)

            # Insert stop times
            if result.stop_times:
                await self.repository.bulk_create_stop_times(result.stop_times)

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
                skipped_stop_times=result.skipped_stop_times,
                duration_seconds=round(duration, 2),
            )

            return GTFSImportResponse(
                agencies_count=len(result.agencies),
                routes_count=len(result.routes),
                calendars_count=len(result.calendars),
                calendar_dates_count=len(result.calendar_dates),
                trips_count=len(result.trips),
                stop_times_count=len(result.stop_times),
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
