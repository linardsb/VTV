"""DB-backed GTFS static data store.

Replaces the HTTP/ZIP-based GTFSStaticCache with a store that reads
from existing PostgreSQL tables (schedules + stops). Presents the same
public interface so all transit tools work without changes.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.static_cache import (
    CalendarDateException,
    CalendarEntry,
    GTFSStaticCache,
    RouteInfo,
    StopInfo,
    StopTimeEntry,
    TripInfo,
)
from app.core.config import Settings
from app.core.logging import get_logger
from app.schedules.repository import ScheduleRepository
from app.stops.models import Stop

logger = get_logger(__name__)


class GTFSStaticStore(GTFSStaticCache):
    """DB-backed GTFS static data store.

    Inherits all lookup methods and index builders from GTFSStaticCache.
    Overrides data loading to read from PostgreSQL instead of HTTP ZIP.
    """

    async def load_from_db(
        self,
        db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    ) -> None:
        """Load GTFS static data from the database.

        Reads from the schedules and stops tables, converts ORM models
        to the same lightweight dataclass structures used by all tools.

        Args:
            db_session_factory: Factory for creating async DB sessions.

        Raises:
            Exception: If database queries fail.
        """
        logger.info("transit.static_store.load_started")
        start = datetime.now(tz=UTC)

        try:
            async with db_session_factory() as db:
                repo = ScheduleRepository(db)

                # --- Load routes ---
                all_routes = await repo.list_all_routes()
                route_pk_to_gtfs: dict[int, str] = {}
                for r in all_routes:
                    route_pk_to_gtfs[r.id] = r.gtfs_route_id
                    self.routes[r.gtfs_route_id] = RouteInfo(
                        route_id=r.gtfs_route_id,
                        route_short_name=r.route_short_name,
                        route_long_name=r.route_long_name,
                        route_type=r.route_type,
                    )

                # --- Load stops (direct query, not via StopRepository) ---
                result = await db.execute(select(Stop))
                all_stops = result.scalars().all()
                stop_pk_to_gtfs: dict[int, str] = {}
                for s in all_stops:
                    stop_pk_to_gtfs[s.id] = s.gtfs_stop_id
                    self.stops[s.gtfs_stop_id] = StopInfo(
                        stop_id=s.gtfs_stop_id,
                        stop_name=s.stop_name,
                        stop_lat=s.stop_lat,
                        stop_lon=s.stop_lon,
                    )

                # --- Load calendars ---
                all_calendars = await repo.list_all_calendars()
                calendar_pk_to_gtfs: dict[int, str] = {}
                for c in all_calendars:
                    calendar_pk_to_gtfs[c.id] = c.gtfs_service_id
                    self.calendar.append(
                        CalendarEntry(
                            service_id=c.gtfs_service_id,
                            monday=c.monday,
                            tuesday=c.tuesday,
                            wednesday=c.wednesday,
                            thursday=c.thursday,
                            friday=c.friday,
                            saturday=c.saturday,
                            sunday=c.sunday,
                            start_date=c.start_date.strftime("%Y%m%d"),
                            end_date=c.end_date.strftime("%Y%m%d"),
                        )
                    )

                # --- Load calendar dates ---
                all_cal_dates = await repo.list_all_calendar_dates()
                for cd in all_cal_dates:
                    service_id = calendar_pk_to_gtfs.get(cd.calendar_id, "")
                    self.calendar_dates.append(
                        CalendarDateException(
                            service_id=service_id,
                            date=cd.date.strftime("%Y%m%d"),
                            exception_type=cd.exception_type,
                        )
                    )

                # --- Load trips ---
                all_trips = await repo.list_all_trips()
                trip_pk_to_gtfs: dict[int, str] = {}
                for t in all_trips:
                    trip_pk_to_gtfs[t.id] = t.gtfs_trip_id
                    gtfs_route_id = route_pk_to_gtfs.get(t.route_id, "")
                    gtfs_service_id = calendar_pk_to_gtfs.get(t.calendar_id, "")
                    self.trips[t.gtfs_trip_id] = TripInfo(
                        trip_id=t.gtfs_trip_id,
                        route_id=gtfs_route_id,
                        service_id=gtfs_service_id,
                        direction_id=t.direction_id,
                        trip_headsign=t.trip_headsign,
                    )

                # --- Load stop times ---
                all_stop_times = await repo.list_all_stop_times()
                for st in all_stop_times:
                    gtfs_trip_id = trip_pk_to_gtfs.get(st.trip_id, "")
                    gtfs_stop_id = stop_pk_to_gtfs.get(st.stop_id, "")
                    entry = StopTimeEntry(
                        stop_id=gtfs_stop_id,
                        stop_sequence=st.stop_sequence,
                        arrival_time=st.arrival_time,
                        departure_time=st.departure_time,
                    )
                    if gtfs_trip_id not in self.trip_stop_times:
                        self.trip_stop_times[gtfs_trip_id] = []
                    self.trip_stop_times[gtfs_trip_id].append(entry)

                # Sort each trip's stops by sequence
                for stops in self.trip_stop_times.values():
                    stops.sort(key=lambda s: s.stop_sequence)

                # Build indexes (inherited from GTFSStaticCache)
                self._build_route_trips_index()
                self._build_stop_routes_index()

            self._loaded_at = datetime.now(tz=UTC)

            logger.info(
                "transit.static_store.load_completed",
                route_count=len(self.routes),
                stop_count=len(self.stops),
                trip_count=len(self.trips),
                stop_time_trips=len(self.trip_stop_times),
                calendar_entries=len(self.calendar),
                calendar_exceptions=len(self.calendar_dates),
                stop_routes_count=len(self.stop_routes),
                duration_ms=int((datetime.now(tz=UTC) - start).total_seconds() * 1000),
            )

        except Exception:
            logger.error(
                "transit.static_store.load_failed",
                exc_info=True,
            )
            raise


# --- Module-level singleton ---

_static_store: GTFSStaticStore | None = None


async def get_static_store(
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    settings: Settings,
) -> GTFSStaticStore:
    """Get or create the DB-backed GTFS static store singleton.

    Loads data from PostgreSQL on first call, then returns cached data
    until the TTL expires.

    Args:
        db_session_factory: Factory for creating async DB sessions.
        settings: Application settings with cache TTL.

    Returns:
        Populated GTFSStaticStore instance.
    """
    global _static_store
    if _static_store is None or _static_store.is_stale(settings.gtfs_static_cache_ttl_hours):
        _static_store = GTFSStaticStore()
        await _static_store.load_from_db(db_session_factory)
    return _static_store
