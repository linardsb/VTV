"""Data access layer for schedule management."""

from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import InstrumentedAttribute

from app.schedules.models import (
    Agency,
    Calendar,
    CalendarDate,
    Route,
    StopTime,
    Trip,
)
from app.schedules.schemas import (
    CalendarDateCreate,
    CalendarUpdate,
    RouteCreate,
    RouteUpdate,
    StopTimeCreate,
    TripUpdate,
)

# Basic GTFS type → extended GTFS type range mapping.
# Riga's GTFS feed uses extended types (800=trolleybus, 900=tram).
# When filtering by basic type (e.g. 0=tram), also match extended range (900-999).
_BASIC_TO_EXTENDED: dict[int, tuple[int, int]] = {
    0: (900, 999),  # tram → 900-999
    3: (700, 799),  # bus → 700-799
    11: (800, 899),  # trolleybus → 800-899
}


def _route_type_filter(route_type: int) -> sa.ColumnElement[bool]:
    """Build a SQLAlchemy filter matching both basic and extended GTFS route types."""
    extended_range = _BASIC_TO_EXTENDED.get(route_type)
    if extended_range:
        return or_(
            Route.route_type == route_type,
            Route.route_type.between(extended_range[0], extended_range[1]),
        )
    return Route.route_type == route_type


class ScheduleRepository:
    """Database operations for schedule entities."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session.

        Args:
            db: SQLAlchemy async session.
        """
        self.db = db

    # --- Agency ---

    async def create_agency(self, agency: Agency) -> Agency:
        """Create a new agency record.

        Args:
            agency: Agency model instance.

        Returns:
            The persisted Agency instance.
        """
        self.db.add(agency)
        await self.db.commit()
        await self.db.refresh(agency)
        return agency

    async def get_agency(self, agency_id: int) -> Agency | None:
        """Get an agency by primary key.

        Args:
            agency_id: The agency's database ID.

        Returns:
            Agency instance or None.
        """
        result = await self.db.execute(select(Agency).where(Agency.id == agency_id))
        return result.scalar_one_or_none()

    async def get_agency_by_gtfs_id(self, gtfs_agency_id: str) -> Agency | None:
        """Get an agency by GTFS agency_id.

        Args:
            gtfs_agency_id: The GTFS identifier string.

        Returns:
            Agency instance or None.
        """
        result = await self.db.execute(
            select(Agency).where(Agency.gtfs_agency_id == gtfs_agency_id)
        )
        return result.scalar_one_or_none()

    async def list_agencies(self) -> list[Agency]:
        """List all agencies.

        Returns:
            List of all Agency instances.
        """
        result = await self.db.execute(select(Agency).order_by(Agency.agency_name))
        return list(result.scalars().all())

    # --- Route ---

    async def create_route(self, data: RouteCreate) -> Route:
        """Create a new route record.

        Args:
            data: Route creation data.

        Returns:
            The newly created Route instance.
        """
        route = Route(**data.model_dump())
        self.db.add(route)
        await self.db.commit()
        await self.db.refresh(route)
        return route

    async def get_route(self, route_id: int) -> Route | None:
        """Get a route by primary key.

        Args:
            route_id: The route's database ID.

        Returns:
            Route instance or None.
        """
        result = await self.db.execute(select(Route).where(Route.id == route_id))
        return result.scalar_one_or_none()

    async def get_route_by_gtfs_id(self, gtfs_route_id: str) -> Route | None:
        """Get a route by GTFS route_id.

        Args:
            gtfs_route_id: The GTFS identifier string.

        Returns:
            Route instance or None.
        """
        result = await self.db.execute(select(Route).where(Route.gtfs_route_id == gtfs_route_id))
        return result.scalar_one_or_none()

    async def list_routes(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        search: str | None = None,
        route_type: int | None = None,
        agency_id: int | None = None,
        is_active: bool | None = None,
    ) -> list[Route]:
        """List routes with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            search: Case-insensitive substring on route_short_name or route_long_name.
            route_type: GTFS route_type filter.
            agency_id: Filter by agency.
            is_active: Filter by active status.

        Returns:
            List of Route instances.
        """
        query = select(Route)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                Route.route_short_name.ilike(pattern) | Route.route_long_name.ilike(pattern)
            )
        if route_type is not None:
            query = query.where(_route_type_filter(route_type))
        if agency_id is not None:
            query = query.where(Route.agency_id == agency_id)
        if is_active is not None:
            query = query.where(Route.is_active == is_active)
        query = query.order_by(Route.route_short_name).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_routes(
        self,
        *,
        search: str | None = None,
        route_type: int | None = None,
        agency_id: int | None = None,
        is_active: bool | None = None,
    ) -> int:
        """Count routes matching filters.

        Args:
            search: Case-insensitive substring filter.
            route_type: GTFS route_type filter.
            agency_id: Filter by agency.
            is_active: Filter by active status.

        Returns:
            Total count of matching routes.
        """
        query = select(func.count()).select_from(Route)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                Route.route_short_name.ilike(pattern) | Route.route_long_name.ilike(pattern)
            )
        if route_type is not None:
            query = query.where(_route_type_filter(route_type))
        if agency_id is not None:
            query = query.where(Route.agency_id == agency_id)
        if is_active is not None:
            query = query.where(Route.is_active == is_active)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update_route(self, route: Route, data: RouteUpdate) -> Route:
        """Update an existing route record.

        Args:
            route: The route instance to update.
            data: Fields to update (only set fields are applied).

        Returns:
            The updated Route instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(route, field, value)
        await self.db.commit()
        await self.db.refresh(route)
        return route

    async def delete_route(self, route: Route) -> None:
        """Delete a route record.

        Args:
            route: The route instance to delete.
        """
        await self.db.delete(route)
        await self.db.commit()

    # --- Calendar ---

    async def create_calendar(self, calendar: Calendar) -> Calendar:
        """Create a new calendar record.

        Args:
            calendar: Calendar model instance.

        Returns:
            The persisted Calendar instance.
        """
        self.db.add(calendar)
        await self.db.commit()
        await self.db.refresh(calendar)
        return calendar

    async def get_calendar(self, calendar_id: int) -> Calendar | None:
        """Get a calendar by primary key.

        Args:
            calendar_id: The calendar's database ID.

        Returns:
            Calendar instance or None.
        """
        result = await self.db.execute(select(Calendar).where(Calendar.id == calendar_id))
        return result.scalar_one_or_none()

    async def get_calendar_by_gtfs_id(self, gtfs_service_id: str) -> Calendar | None:
        """Get a calendar by GTFS service_id.

        Args:
            gtfs_service_id: The GTFS identifier string.

        Returns:
            Calendar instance or None.
        """
        result = await self.db.execute(
            select(Calendar).where(Calendar.gtfs_service_id == gtfs_service_id)
        )
        return result.scalar_one_or_none()

    async def list_calendars(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        active_on: date | None = None,
    ) -> list[Calendar]:
        """List calendars with pagination and optional date filter.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            active_on: Filter calendars active on this date.

        Returns:
            List of Calendar instances.
        """
        query = select(Calendar)
        if active_on is not None:
            query = query.where(Calendar.start_date <= active_on, Calendar.end_date >= active_on)
        query = query.order_by(Calendar.gtfs_service_id).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_calendars(self, *, active_on: date | None = None) -> int:
        """Count calendars matching filters.

        Args:
            active_on: Filter calendars active on this date.

        Returns:
            Total count of matching calendars.
        """
        query = select(func.count()).select_from(Calendar)
        if active_on is not None:
            query = query.where(Calendar.start_date <= active_on, Calendar.end_date >= active_on)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update_calendar(self, calendar: Calendar, data: CalendarUpdate) -> Calendar:
        """Update an existing calendar record.

        Args:
            calendar: The calendar instance to update.
            data: Fields to update.

        Returns:
            The updated Calendar instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(calendar, field, value)
        await self.db.commit()
        await self.db.refresh(calendar)
        return calendar

    async def delete_calendar(self, calendar: Calendar) -> None:
        """Delete a calendar record.

        Args:
            calendar: The calendar instance to delete.
        """
        await self.db.delete(calendar)
        await self.db.commit()

    # --- CalendarDate ---

    async def create_calendar_date(
        self, calendar_id: int, data: CalendarDateCreate
    ) -> CalendarDate:
        """Create a calendar date exception.

        Args:
            calendar_id: The parent calendar's ID.
            data: Exception date data.

        Returns:
            The newly created CalendarDate instance.
        """
        calendar_date = CalendarDate(calendar_id=calendar_id, **data.model_dump())
        self.db.add(calendar_date)
        await self.db.commit()
        await self.db.refresh(calendar_date)
        return calendar_date

    async def list_calendar_dates(self, calendar_id: int) -> list[CalendarDate]:
        """List all date exceptions for a calendar.

        Args:
            calendar_id: The parent calendar's ID.

        Returns:
            List of CalendarDate instances.
        """
        result = await self.db.execute(
            select(CalendarDate)
            .where(CalendarDate.calendar_id == calendar_id)
            .order_by(CalendarDate.date)
        )
        return list(result.scalars().all())

    async def get_calendar_date(self, exception_id: int) -> CalendarDate | None:
        """Get a calendar date exception by ID.

        Args:
            exception_id: The exception's database ID.

        Returns:
            CalendarDate instance or None.
        """
        result = await self.db.execute(select(CalendarDate).where(CalendarDate.id == exception_id))
        return result.scalar_one_or_none()

    async def delete_calendar_date(self, calendar_date: CalendarDate) -> None:
        """Delete a calendar date exception.

        Args:
            calendar_date: The CalendarDate instance to delete.
        """
        await self.db.delete(calendar_date)
        await self.db.commit()

    # --- Trip ---

    async def create_trip(self, trip: Trip) -> Trip:
        """Create a new trip record.

        Args:
            trip: Trip model instance.

        Returns:
            The persisted Trip instance.
        """
        self.db.add(trip)
        await self.db.commit()
        await self.db.refresh(trip)
        return trip

    async def get_trip(self, trip_id: int) -> Trip | None:
        """Get a trip by primary key.

        Args:
            trip_id: The trip's database ID.

        Returns:
            Trip instance or None.
        """
        result = await self.db.execute(select(Trip).where(Trip.id == trip_id))
        return result.scalar_one_or_none()

    async def get_trip_by_gtfs_id(self, gtfs_trip_id: str) -> Trip | None:
        """Get a trip by GTFS trip_id.

        Args:
            gtfs_trip_id: The GTFS identifier string.

        Returns:
            Trip instance or None.
        """
        result = await self.db.execute(select(Trip).where(Trip.gtfs_trip_id == gtfs_trip_id))
        return result.scalar_one_or_none()

    async def list_trips(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        route_id: int | None = None,
        calendar_id: int | None = None,
        direction_id: int | None = None,
    ) -> list[Trip]:
        """List trips with pagination and filtering.

        Args:
            offset: Number of records to skip.
            limit: Maximum records to return.
            route_id: Filter by route.
            calendar_id: Filter by calendar.
            direction_id: Filter by direction.

        Returns:
            List of Trip instances.
        """
        query = select(Trip)
        if route_id is not None:
            query = query.where(Trip.route_id == route_id)
        if calendar_id is not None:
            query = query.where(Trip.calendar_id == calendar_id)
        if direction_id is not None:
            query = query.where(Trip.direction_id == direction_id)
        query = query.order_by(Trip.gtfs_trip_id).offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def count_trips(
        self,
        *,
        route_id: int | None = None,
        calendar_id: int | None = None,
        direction_id: int | None = None,
    ) -> int:
        """Count trips matching filters.

        Args:
            route_id: Filter by route.
            calendar_id: Filter by calendar.
            direction_id: Filter by direction.

        Returns:
            Total count of matching trips.
        """
        query = select(func.count()).select_from(Trip)
        if route_id is not None:
            query = query.where(Trip.route_id == route_id)
        if calendar_id is not None:
            query = query.where(Trip.calendar_id == calendar_id)
        if direction_id is not None:
            query = query.where(Trip.direction_id == direction_id)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def update_trip(self, trip: Trip, data: TripUpdate) -> Trip:
        """Update an existing trip record.

        Args:
            trip: The trip instance to update.
            data: Fields to update.

        Returns:
            The updated Trip instance.
        """
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(trip, field, value)
        await self.db.commit()
        await self.db.refresh(trip)
        return trip

    async def delete_trip(self, trip: Trip) -> None:
        """Delete a trip record.

        Args:
            trip: The trip instance to delete.
        """
        await self.db.delete(trip)
        await self.db.commit()

    # --- StopTime ---

    async def list_stop_times(self, trip_id: int) -> list[StopTime]:
        """List all stop times for a trip, ordered by sequence.

        Args:
            trip_id: The parent trip's ID.

        Returns:
            List of StopTime instances ordered by stop_sequence.
        """
        result = await self.db.execute(
            select(StopTime).where(StopTime.trip_id == trip_id).order_by(StopTime.stop_sequence)
        )
        return list(result.scalars().all())

    async def create_stop_time(self, trip_id: int, data: StopTimeCreate) -> StopTime:
        """Create a single stop time.

        Args:
            trip_id: The parent trip's ID.
            data: Stop time creation data.

        Returns:
            The newly created StopTime instance.
        """
        stop_time = StopTime(trip_id=trip_id, **data.model_dump())
        self.db.add(stop_time)
        await self.db.commit()
        await self.db.refresh(stop_time)
        return stop_time

    async def get_stop_time(self, stop_time_id: int) -> StopTime | None:
        """Get a stop time by ID.

        Args:
            stop_time_id: The stop time's database ID.

        Returns:
            StopTime instance or None.
        """
        result = await self.db.execute(select(StopTime).where(StopTime.id == stop_time_id))
        return result.scalar_one_or_none()

    async def delete_stop_time(self, stop_time: StopTime) -> None:
        """Delete a stop time record.

        Args:
            stop_time: The StopTime instance to delete.
        """
        await self.db.delete(stop_time)
        await self.db.commit()

    async def replace_stop_times(
        self, trip_id: int, stop_times: list[StopTimeCreate]
    ) -> list[StopTime]:
        """Replace all stop times for a trip.

        Deletes existing stop_times and creates new ones.

        Args:
            trip_id: The trip's database ID.
            stop_times: New stop time data.

        Returns:
            List of newly created StopTime instances.
        """
        await self.db.execute(delete(StopTime).where(StopTime.trip_id == trip_id))
        new_stop_times: list[StopTime] = []
        for st_data in stop_times:
            st = StopTime(trip_id=trip_id, **st_data.model_dump())
            self.db.add(st)
            new_stop_times.append(st)
        await self.db.commit()
        for st in new_stop_times:
            await self.db.refresh(st)
        return new_stop_times

    # --- Export helpers (unpaginated) ---

    async def list_all_agencies(self) -> list[Agency]:
        """List all agencies without pagination (for GTFS export)."""
        result = await self.db.execute(select(Agency).order_by(Agency.id))
        return list(result.scalars().all())

    async def list_all_routes(self, agency_id: int | None = None) -> list[Route]:
        """List all routes without pagination (for GTFS export)."""
        query = select(Route)
        if agency_id is not None:
            query = query.where(Route.agency_id == agency_id)
        query = query.order_by(Route.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_all_calendars(self) -> list[Calendar]:
        """List all calendars without pagination (for GTFS export)."""
        result = await self.db.execute(select(Calendar).order_by(Calendar.id))
        return list(result.scalars().all())

    async def list_all_calendar_dates(self) -> list[CalendarDate]:
        """List all calendar date exceptions without pagination (for GTFS export)."""
        result = await self.db.execute(select(CalendarDate).order_by(CalendarDate.id))
        return list(result.scalars().all())

    async def list_all_trips(self, route_ids: list[int] | None = None) -> list[Trip]:
        """List all trips without pagination (for GTFS export)."""
        query = select(Trip)
        if route_ids is not None:
            query = query.where(Trip.route_id.in_(route_ids))
        query = query.order_by(Trip.id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_all_stop_times(self, trip_ids: list[int] | None = None) -> list[StopTime]:
        """List all stop times without pagination (for GTFS export)."""
        query = select(StopTime)
        if trip_ids is not None:
            query = query.where(StopTime.trip_id.in_(trip_ids))
        query = query.order_by(StopTime.trip_id, StopTime.stop_sequence)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # --- Bulk operations (for GTFS import) ---

    async def bulk_create_agencies(self, items: list[Agency]) -> None:
        """Bulk create agencies (flush only, no commit).

        Args:
            items: List of Agency model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    async def bulk_create_routes(self, items: list[Route]) -> None:
        """Bulk create routes (flush only, no commit).

        Args:
            items: List of Route model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    async def bulk_create_calendars(self, items: list[Calendar]) -> None:
        """Bulk create calendars (flush only, no commit).

        Args:
            items: List of Calendar model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    async def bulk_create_calendar_dates(self, items: list[CalendarDate]) -> None:
        """Bulk create calendar dates (flush only, no commit).

        Args:
            items: List of CalendarDate model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    async def bulk_create_trips(self, items: list[Trip]) -> None:
        """Bulk create trips (flush only, no commit).

        Args:
            items: List of Trip model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    async def bulk_create_stop_times(self, items: list[StopTime]) -> None:
        """Bulk create stop times (flush only, no commit).

        Args:
            items: List of StopTime model instances.
        """
        self.db.add_all(items)
        await self.db.flush()

    # --- Bulk upsert operations (for GTFS merge import) ---

    async def bulk_upsert_agencies(
        self,
        values: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Upsert agencies by gtfs_agency_id. Flush only, no commit.

        Args:
            values: List of column dicts for each agency.

        Returns:
            Tuple of (created_count, updated_count).
        """
        if not values:
            return 0, 0
        existing_ids = await self._existing_gtfs_ids(
            Agency.gtfs_agency_id, [v["gtfs_agency_id"] for v in values]
        )
        update_cols = ["agency_name", "agency_url", "agency_timezone", "agency_lang"]
        stmt = pg_insert(Agency).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["gtfs_agency_id"],
            set_={c: stmt.excluded[c] for c in update_cols},
        )
        await self.db.execute(stmt)
        await self.db.flush()
        updated = len(existing_ids & {v["gtfs_agency_id"] for v in values})
        return len(values) - updated, updated

    async def bulk_upsert_routes(
        self,
        values: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Upsert routes by gtfs_route_id. Flush only, no commit.

        Args:
            values: List of column dicts for each route.

        Returns:
            Tuple of (created_count, updated_count).
        """
        if not values:
            return 0, 0
        existing_ids = await self._existing_gtfs_ids(
            Route.gtfs_route_id, [v["gtfs_route_id"] for v in values]
        )
        update_cols = [
            "agency_id",
            "route_short_name",
            "route_long_name",
            "route_type",
            "route_color",
            "route_text_color",
            "route_sort_order",
        ]
        stmt = pg_insert(Route).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["gtfs_route_id"],
            set_={c: stmt.excluded[c] for c in update_cols},
        )
        await self.db.execute(stmt)
        await self.db.flush()
        updated = len(existing_ids & {v["gtfs_route_id"] for v in values})
        return len(values) - updated, updated

    async def bulk_upsert_calendars(
        self,
        values: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Upsert calendars by gtfs_service_id. Flush only, no commit.

        Args:
            values: List of column dicts for each calendar.

        Returns:
            Tuple of (created_count, updated_count).
        """
        if not values:
            return 0, 0
        existing_ids = await self._existing_gtfs_ids(
            Calendar.gtfs_service_id, [v["gtfs_service_id"] for v in values]
        )
        update_cols = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ]
        stmt = pg_insert(Calendar).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["gtfs_service_id"],
            set_={c: stmt.excluded[c] for c in update_cols},
        )
        await self.db.execute(stmt)
        await self.db.flush()
        updated = len(existing_ids & {v["gtfs_service_id"] for v in values})
        return len(values) - updated, updated

    async def bulk_upsert_trips(
        self,
        values: list[dict[str, Any]],
    ) -> tuple[int, int]:
        """Upsert trips by gtfs_trip_id. Flush only, no commit.

        Args:
            values: List of column dicts for each trip.

        Returns:
            Tuple of (created_count, updated_count).
        """
        if not values:
            return 0, 0
        existing_ids = await self._existing_gtfs_ids(
            Trip.gtfs_trip_id, [v["gtfs_trip_id"] for v in values]
        )
        update_cols = ["route_id", "calendar_id", "direction_id", "trip_headsign", "block_id"]
        stmt = pg_insert(Trip).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["gtfs_trip_id"],
            set_={c: stmt.excluded[c] for c in update_cols},
        )
        await self.db.execute(stmt)
        await self.db.flush()
        updated = len(existing_ids & {v["gtfs_trip_id"] for v in values})
        return len(values) - updated, updated

    async def delete_calendar_dates_for_calendars(self, calendar_ids: list[int]) -> None:
        """Delete all calendar_dates for the given calendar IDs.

        Args:
            calendar_ids: List of calendar primary keys.
        """
        if not calendar_ids:
            return
        await self.db.execute(
            delete(CalendarDate).where(CalendarDate.calendar_id.in_(calendar_ids))
        )
        await self.db.flush()

    async def delete_stop_times_for_trips(self, trip_ids: list[int]) -> None:
        """Delete all stop_times for the given trip IDs.

        Args:
            trip_ids: List of trip primary keys.
        """
        if not trip_ids:
            return
        await self.db.execute(delete(StopTime).where(StopTime.trip_id.in_(trip_ids)))
        await self.db.flush()

    async def get_agency_gtfs_map(self) -> dict[str, int]:
        """Get mapping of gtfs_agency_id to database id for all agencies.

        Returns:
            Dict mapping GTFS agency ID strings to integer database IDs.
        """
        result = await self.db.execute(select(Agency.gtfs_agency_id, Agency.id))
        return {row[0]: row[1] for row in result.all()}

    async def get_route_gtfs_map(self) -> dict[str, int]:
        """Get mapping of gtfs_route_id to database id for all routes.

        Returns:
            Dict mapping GTFS route ID strings to integer database IDs.
        """
        result = await self.db.execute(select(Route.gtfs_route_id, Route.id))
        return {row[0]: row[1] for row in result.all()}

    async def get_calendar_gtfs_map(self) -> dict[str, int]:
        """Get mapping of gtfs_service_id to database id for all calendars.

        Returns:
            Dict mapping GTFS service ID strings to integer database IDs.
        """
        result = await self.db.execute(select(Calendar.gtfs_service_id, Calendar.id))
        return {row[0]: row[1] for row in result.all()}

    async def get_trip_gtfs_map(self) -> dict[str, int]:
        """Get mapping of gtfs_trip_id to database id for all trips.

        Returns:
            Dict mapping GTFS trip ID strings to integer database IDs.
        """
        result = await self.db.execute(select(Trip.gtfs_trip_id, Trip.id))
        return {row[0]: row[1] for row in result.all()}

    async def _existing_gtfs_ids(
        self,
        column: InstrumentedAttribute[str],
        gtfs_ids: list[str],
    ) -> set[str]:
        """Find which GTFS IDs already exist in the database.

        Args:
            column: The GTFS ID column to filter on.
            gtfs_ids: List of GTFS ID strings to check.

        Returns:
            Set of GTFS IDs that already exist.
        """
        if not gtfs_ids:
            return set()
        result = await self.db.execute(select(column).where(column.in_(gtfs_ids)))
        return set(result.scalars().all())

    async def clear_all_schedule_data(self) -> None:
        """Delete all schedule data in reverse FK order.

        Order: stop_times -> trips -> calendar_dates -> calendars -> routes -> agencies.
        """
        await self.db.execute(delete(StopTime))
        await self.db.execute(delete(Trip))
        await self.db.execute(delete(CalendarDate))
        await self.db.execute(delete(Calendar))
        await self.db.execute(delete(Route))
        await self.db.execute(delete(Agency))
        await self.db.flush()
