# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Tests for schedule management service."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.schedules.exceptions import (
    CalendarAlreadyExistsError,
    RouteAlreadyExistsError,
    RouteNotFoundError,
    TripAlreadyExistsError,
    TripNotFoundError,
)
from app.schedules.schemas import (
    CalendarCreate,
    RouteCreate,
    RouteUpdate,
    StopTimeCreate,
    StopTimesBulkUpdate,
    TripCreate,
)
from app.schedules.service import ScheduleService
from app.schedules.tests.conftest import (
    make_agency,
    make_calendar,
    make_route,
    make_stop_time,
    make_trip,
)
from app.shared.schemas import PaginationParams


@pytest.fixture
def service():
    mock_db = AsyncMock()
    return ScheduleService(mock_db)


# --- Route tests ---


@pytest.mark.asyncio
async def test_create_route_success(service):
    data = RouteCreate(
        gtfs_route_id="bus_22",
        agency_id=1,
        route_short_name="22",
        route_long_name="Centrs - Jugla",
        route_type=3,
        route_color=None,
        route_text_color=None,
        route_sort_order=None,
    )
    route = make_route()
    service.repository.get_route_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_route = AsyncMock(return_value=route)

    result = await service.create_route(data)
    assert result.gtfs_route_id == "bus_22"
    assert result.route_type == 3


@pytest.mark.asyncio
async def test_create_route_duplicate_raises(service):
    data = RouteCreate(
        gtfs_route_id="bus_22",
        agency_id=1,
        route_short_name="22",
        route_long_name="Centrs - Jugla",
        route_type=3,
        route_color=None,
        route_text_color=None,
        route_sort_order=None,
    )
    service.repository.get_route_by_gtfs_id = AsyncMock(return_value=make_route())

    with pytest.raises(RouteAlreadyExistsError):
        await service.create_route(data)


@pytest.mark.asyncio
async def test_get_route_success(service):
    route = make_route()
    service.repository.get_route = AsyncMock(return_value=route)

    result = await service.get_route(1)
    assert result.id == 1
    assert result.route_short_name == "22"


@pytest.mark.asyncio
async def test_get_route_not_found(service):
    service.repository.get_route = AsyncMock(return_value=None)

    with pytest.raises(RouteNotFoundError):
        await service.get_route(999)


@pytest.mark.asyncio
async def test_list_routes_paginated(service):
    routes = [make_route(id=i, gtfs_route_id=f"r_{i}") for i in range(1, 4)]
    service.repository.list_routes = AsyncMock(return_value=routes)
    service.repository.count_routes = AsyncMock(return_value=3)

    result = await service.list_routes(PaginationParams(page=1, page_size=20))
    assert result.total == 3
    assert len(result.items) == 3


@pytest.mark.asyncio
async def test_update_route_success(service):
    route = make_route()
    updated = make_route(route_long_name="Updated Name")
    service.repository.get_route = AsyncMock(return_value=route)
    service.repository.update_route = AsyncMock(return_value=updated)

    result = await service.update_route(
        1,
        RouteUpdate(
            gtfs_route_id=None,
            route_short_name=None,
            route_long_name="Updated Name",
            route_type=None,
            route_color=None,
            route_text_color=None,
        ),
    )
    assert result.route_long_name == "Updated Name"


@pytest.mark.asyncio
async def test_delete_route_success(service):
    route = make_route()
    service.repository.get_route = AsyncMock(return_value=route)
    service.repository.delete_route = AsyncMock()

    await service.delete_route(1)
    service.repository.delete_route.assert_called_once_with(route)


@pytest.mark.asyncio
async def test_delete_route_not_found(service):
    service.repository.get_route = AsyncMock(return_value=None)

    with pytest.raises(RouteNotFoundError):
        await service.delete_route(999)


# --- Calendar tests ---


@pytest.mark.asyncio
async def test_create_calendar_success(service):
    data = CalendarCreate(
        gtfs_service_id="weekday_1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    calendar = make_calendar(created_by_id=42)
    service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_calendar = AsyncMock(return_value=calendar)

    result = await service.create_calendar(data, user_id=42)
    assert result.gtfs_service_id == "weekday_1"
    assert result.created_by_id == 42


@pytest.mark.asyncio
async def test_create_calendar_created_by_name_resolved(service):
    """When creator relationship is loaded, created_by_name returns the user's name."""
    calendar = make_calendar(created_by_id=42)
    # Simulate a loaded creator relationship (as the DB would provide via joinedload)
    object.__setattr__(calendar, "creator", SimpleNamespace(name="Janis Berzins"))
    service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_calendar = AsyncMock(return_value=calendar)

    data = CalendarCreate(
        gtfs_service_id="weekday_1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    result = await service.create_calendar(data, user_id=42)
    assert result.created_by_name == "Janis Berzins"
    assert result.created_by_id == 42


@pytest.mark.asyncio
async def test_create_calendar_without_user(service):
    """Calendar created without user_id (e.g. GTFS import) has created_by_id=None."""
    data = CalendarCreate(
        gtfs_service_id="weekend_1",
        monday=False,
        tuesday=False,
        wednesday=False,
        thursday=False,
        friday=False,
        saturday=True,
        sunday=True,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    calendar = make_calendar(gtfs_service_id="weekend_1", created_by_id=None)
    service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_calendar = AsyncMock(return_value=calendar)

    result = await service.create_calendar(data)
    assert result.created_by_id is None
    assert result.created_by_name is None


@pytest.mark.asyncio
async def test_create_calendar_duplicate_raises(service):
    data = CalendarCreate(
        gtfs_service_id="weekday_1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
    )
    service.repository.get_calendar_by_gtfs_id = AsyncMock(return_value=make_calendar())

    with pytest.raises(CalendarAlreadyExistsError):
        await service.create_calendar(data)


@pytest.mark.asyncio
async def test_get_calendar_success(service):
    calendar = make_calendar()
    service.repository.get_calendar = AsyncMock(return_value=calendar)

    result = await service.get_calendar(1)
    assert result.gtfs_service_id == "weekday_1"


@pytest.mark.asyncio
async def test_list_calendars(service):
    calendars = [make_calendar(id=1), make_calendar(id=2, gtfs_service_id="weekend_1")]
    service.repository.list_calendars = AsyncMock(return_value=calendars)
    service.repository.count_calendars = AsyncMock(return_value=2)

    result = await service.list_calendars(PaginationParams(page=1, page_size=20))
    assert result.total == 2


@pytest.mark.asyncio
async def test_delete_calendar(service):
    calendar = make_calendar()
    service.repository.get_calendar = AsyncMock(return_value=calendar)
    service.repository.delete_calendar = AsyncMock()

    await service.delete_calendar(1)
    service.repository.delete_calendar.assert_called_once()


# --- Trip tests ---


@pytest.mark.asyncio
async def test_create_trip_success(service):
    data = TripCreate(
        gtfs_trip_id="trip_22_1",
        route_id=1,
        calendar_id=1,
        direction_id=0,
        trip_headsign="Jugla",
        block_id=None,
    )
    trip = make_trip()
    service.repository.get_route = AsyncMock(return_value=make_route())
    service.repository.get_calendar = AsyncMock(return_value=make_calendar())
    service.repository.get_trip_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_trip = AsyncMock(return_value=trip)

    result = await service.create_trip(data)
    assert result.gtfs_trip_id == "trip_22_1"


@pytest.mark.asyncio
async def test_create_trip_duplicate_raises(service):
    data = TripCreate(
        gtfs_trip_id="trip_22_1",
        route_id=1,
        calendar_id=1,
        direction_id=0,
        trip_headsign="Jugla",
        block_id=None,
    )
    service.repository.get_route = AsyncMock(return_value=make_route())
    service.repository.get_calendar = AsyncMock(return_value=make_calendar())
    service.repository.get_trip_by_gtfs_id = AsyncMock(return_value=make_trip())

    with pytest.raises(TripAlreadyExistsError):
        await service.create_trip(data)


@pytest.mark.asyncio
async def test_create_trip_route_not_found(service):
    data = TripCreate(
        gtfs_trip_id="trip_22_1",
        route_id=999,
        calendar_id=1,
        direction_id=0,
        trip_headsign="Jugla",
        block_id=None,
    )
    service.repository.get_route = AsyncMock(return_value=None)

    with pytest.raises(RouteNotFoundError):
        await service.create_trip(data)


@pytest.mark.asyncio
async def test_get_trip_with_stop_times(service):
    trip = make_trip()
    stop_times = [
        make_stop_time(id=1, stop_sequence=1),
        make_stop_time(id=2, stop_sequence=2, stop_id=2),
    ]
    service.repository.get_trip = AsyncMock(return_value=trip)
    service.repository.list_stop_times = AsyncMock(return_value=stop_times)

    result = await service.get_trip(1)
    assert result.gtfs_trip_id == "trip_22_1"
    assert len(result.stop_times) == 2


@pytest.mark.asyncio
async def test_list_trips_filter_by_route(service):
    trips = [make_trip(id=1), make_trip(id=2, gtfs_trip_id="trip_22_2")]
    service.repository.list_trips = AsyncMock(return_value=trips)
    service.repository.count_trips = AsyncMock(return_value=2)

    result = await service.list_trips(PaginationParams(page=1, page_size=20), route_id=1)
    assert result.total == 2
    service.repository.list_trips.assert_called_once()


@pytest.mark.asyncio
async def test_replace_stop_times(service):
    trip = make_trip()
    new_stop_times = [
        make_stop_time(id=10, stop_sequence=1),
        make_stop_time(id=11, stop_sequence=2, stop_id=2),
    ]
    service.repository.get_trip = AsyncMock(return_value=trip)
    service.repository.replace_stop_times = AsyncMock(return_value=new_stop_times)

    data = StopTimesBulkUpdate(
        stop_times=[
            StopTimeCreate(
                stop_id=1,
                stop_sequence=1,
                arrival_time="08:00:00",
                departure_time="08:01:00",
            ),
            StopTimeCreate(
                stop_id=2,
                stop_sequence=2,
                arrival_time="08:05:00",
                departure_time="08:06:00",
            ),
        ]
    )
    result = await service.replace_stop_times(1, data)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_delete_trip(service):
    trip = make_trip()
    service.repository.get_trip = AsyncMock(return_value=trip)
    service.repository.delete_trip = AsyncMock()

    await service.delete_trip(1)
    service.repository.delete_trip.assert_called_once()


@pytest.mark.asyncio
async def test_delete_trip_not_found(service):
    service.repository.get_trip = AsyncMock(return_value=None)

    with pytest.raises(TripNotFoundError):
        await service.delete_trip(999)


# --- Validation tests ---


@pytest.mark.asyncio
async def test_validate_valid_schedule(service):
    calendars = [make_calendar()]
    trips = [make_trip()]
    stop_times = [make_stop_time()]

    service.repository.list_calendars = AsyncMock(return_value=calendars)
    service.repository.list_trips = AsyncMock(return_value=trips)
    service.repository.get_route = AsyncMock(return_value=make_route())
    service.repository.get_calendar = AsyncMock(return_value=make_calendar())
    service.repository.list_stop_times = AsyncMock(return_value=stop_times)

    result = await service.validate_schedule()
    assert result.valid is True
    assert len(result.errors) == 0


@pytest.mark.asyncio
async def test_validate_orphaned_trips(service):
    calendars = [make_calendar()]
    trips = [make_trip(route_id=999)]

    service.repository.list_calendars = AsyncMock(return_value=calendars)
    service.repository.list_trips = AsyncMock(return_value=trips)
    service.repository.get_route = AsyncMock(return_value=None)
    service.repository.get_calendar = AsyncMock(return_value=make_calendar())
    service.repository.list_stop_times = AsyncMock(return_value=[])

    result = await service.validate_schedule()
    assert result.valid is False
    assert any("non-existent route" in e for e in result.errors)


@pytest.mark.asyncio
async def test_validate_invalid_time_format(service):
    calendars = [make_calendar()]
    trips = [make_trip()]
    bad_stop_time = make_stop_time(arrival_time="8:00", departure_time="08:01:00")

    service.repository.list_calendars = AsyncMock(return_value=calendars)
    service.repository.list_trips = AsyncMock(return_value=trips)
    service.repository.get_route = AsyncMock(return_value=make_route())
    service.repository.get_calendar = AsyncMock(return_value=make_calendar())
    service.repository.list_stop_times = AsyncMock(return_value=[bad_stop_time])

    result = await service.validate_schedule()
    assert result.valid is False
    assert any("invalid arrival_time" in e for e in result.errors)


# --- Import tests ---


@pytest.mark.asyncio
async def test_import_gtfs_success(service):
    from app.schedules.schemas import GTFSImportResponse

    mock_stop = AsyncMock()
    mock_stop.gtfs_stop_id = "1001"
    mock_stop.id = 42

    with patch("app.schedules.service.StopRepository") as mock_stop_repo_cls:
        mock_stop_repo = mock_stop_repo_cls.return_value
        mock_stop_repo.list = AsyncMock(return_value=[mock_stop])
        mock_stop_repo.bulk_upsert = AsyncMock(return_value=(0, 0))
        mock_stop_repo.get_gtfs_map = AsyncMock(return_value={"1001": 42})

        service.repository.bulk_upsert_agencies = AsyncMock(return_value=(1, 0))
        service.repository.get_agency_gtfs_map = AsyncMock(return_value={"RS": 1})
        service.repository.bulk_upsert_routes = AsyncMock(return_value=(1, 0))
        service.repository.get_route_gtfs_map = AsyncMock(return_value={"bus_22": 1})
        service.repository.bulk_upsert_calendars = AsyncMock(return_value=(1, 0))
        service.repository.get_calendar_gtfs_map = AsyncMock(return_value={"weekday_1": 1})
        service.repository.bulk_upsert_trips = AsyncMock(return_value=(1, 0))
        service.repository.get_trip_gtfs_map = AsyncMock(return_value={"trip_22_1": 1})
        service.repository.delete_stop_times_for_trips = AsyncMock()
        service.repository.bulk_create_stop_times = AsyncMock()

        with patch("app.schedules.service.GTFSImporter") as mock_importer_cls:
            mock_importer = mock_importer_cls.return_value
            mock_result = AsyncMock()
            mock_result.agencies = [make_agency()]
            mock_result.routes = [make_route()]
            mock_result.route_agency_refs = [make_agency()]
            mock_result.calendars = [make_calendar()]
            mock_result.calendar_dates = []
            mock_result.trips = [make_trip()]
            mock_result.trip_route_refs = [make_route()]
            mock_result.trip_calendar_refs = [make_calendar()]
            mock_result.stop_times = [make_stop_time()]
            mock_result.stop_time_trip_refs = [make_trip()]
            mock_result.stop_time_stop_refs = [None]
            mock_result.stops = []
            mock_result.skipped_stop_times = 0
            mock_result.warnings = []
            mock_importer.parse.return_value = mock_result

            result = await service.import_gtfs(b"fake_zip")
            assert isinstance(result, GTFSImportResponse)
            assert result.agencies_count == 1
            assert result.agencies_created == 1
            assert result.routes_count == 1
            assert result.routes_created == 1


@pytest.mark.asyncio
async def test_import_merges_existing_data(service):
    mock_stop = AsyncMock()
    mock_stop.gtfs_stop_id = "1001"
    mock_stop.id = 42

    with patch("app.schedules.service.StopRepository") as mock_stop_repo_cls:
        mock_stop_repo = mock_stop_repo_cls.return_value
        mock_stop_repo.list = AsyncMock(return_value=[mock_stop])
        mock_stop_repo.bulk_upsert = AsyncMock(return_value=(0, 0))
        mock_stop_repo.get_gtfs_map = AsyncMock(return_value={"1001": 42})

        service.repository.bulk_upsert_agencies = AsyncMock(return_value=(0, 0))
        service.repository.get_agency_gtfs_map = AsyncMock(return_value={})
        service.repository.bulk_upsert_routes = AsyncMock(return_value=(0, 0))
        service.repository.get_route_gtfs_map = AsyncMock(return_value={})
        service.repository.bulk_upsert_calendars = AsyncMock(return_value=(0, 0))
        service.repository.get_calendar_gtfs_map = AsyncMock(return_value={})
        service.repository.bulk_upsert_trips = AsyncMock(return_value=(0, 0))
        service.repository.get_trip_gtfs_map = AsyncMock(return_value={})
        service.repository.delete_stop_times_for_trips = AsyncMock()
        service.repository.bulk_create_stop_times = AsyncMock()

        with patch("app.schedules.service.GTFSImporter") as mock_importer_cls:
            mock_importer = mock_importer_cls.return_value
            mock_result = AsyncMock()
            mock_result.agencies = []
            mock_result.routes = []
            mock_result.calendars = []
            mock_result.calendar_dates = []
            mock_result.trips = []
            mock_result.stop_times = []
            mock_result.stops = []
            mock_result.skipped_stop_times = 0
            mock_result.warnings = []
            mock_importer.parse.return_value = mock_result

            result = await service.import_gtfs(b"fake_zip")
            # Verify merge behavior: no clear_all called, upsert maps loaded
            service.repository.get_agency_gtfs_map.assert_called_once()
            assert result.agencies_count == 0


# --- Edge case tests (security audit #2) ---


@pytest.mark.asyncio
async def test_update_calendar_not_found(service):
    """CalendarNotFoundError when updating non-existent calendar."""
    from app.schedules.exceptions import CalendarNotFoundError
    from app.schedules.schemas import CalendarUpdate

    service.repository.get_calendar = AsyncMock(return_value=None)

    with pytest.raises(CalendarNotFoundError):
        await service.update_calendar(999, CalendarUpdate(monday=False))


@pytest.mark.asyncio
async def test_update_trip_not_found(service):
    """TripNotFoundError when updating non-existent trip."""
    from app.schedules.schemas import TripUpdate

    service.repository.get_trip = AsyncMock(return_value=None)

    with pytest.raises(TripNotFoundError):
        await service.update_trip(999, TripUpdate(trip_headsign="New"))


@pytest.mark.asyncio
async def test_get_trip_not_found(service):
    """TripNotFoundError when getting non-existent trip."""
    service.repository.get_trip = AsyncMock(return_value=None)

    with pytest.raises(TripNotFoundError):
        await service.get_trip(999)


@pytest.mark.asyncio
async def test_add_calendar_exception_calendar_not_found(service):
    """CalendarNotFoundError when adding exception to non-existent calendar."""
    from app.schedules.exceptions import CalendarNotFoundError
    from app.schedules.schemas import CalendarDateCreate

    service.repository.get_calendar = AsyncMock(return_value=None)

    with pytest.raises(CalendarNotFoundError):
        await service.add_calendar_exception(
            999, CalendarDateCreate(date=date(2026, 3, 15), exception_type=1)
        )


@pytest.mark.asyncio
async def test_remove_calendar_exception_not_found(service):
    """CalendarDateNotFoundError when removing non-existent exception."""
    from app.schedules.exceptions import CalendarDateNotFoundError

    service.repository.get_calendar_date = AsyncMock(return_value=None)

    with pytest.raises(CalendarDateNotFoundError):
        await service.remove_calendar_exception(999)


@pytest.mark.asyncio
async def test_replace_stop_times_trip_not_found(service):
    """TripNotFoundError when replacing stop times on non-existent trip."""
    service.repository.get_trip = AsyncMock(return_value=None)

    data = StopTimesBulkUpdate(
        stop_times=[
            StopTimeCreate(
                stop_id=1,
                stop_sequence=1,
                arrival_time="08:00:00",
                departure_time="08:01:00",
            ),
        ]
    )
    with pytest.raises(TripNotFoundError):
        await service.replace_stop_times(999, data)


@pytest.mark.asyncio
async def test_validate_calendar_date_range(service):
    """Validation detects start_date > end_date."""
    bad_calendar = make_calendar(
        start_date=date(2026, 12, 31),
        end_date=date(2026, 1, 1),
    )
    service.repository.list_calendars = AsyncMock(return_value=[bad_calendar])
    service.repository.list_trips = AsyncMock(return_value=[])

    result = await service.validate_schedule()
    assert result.valid is False
    assert any("end_date" in e or "date range" in e.lower() for e in result.errors)


@pytest.mark.asyncio
async def test_import_gtfs_failure_path(service):
    """Exception during GTFS import is handled."""
    from app.schedules.exceptions import GTFSImportError

    with patch("app.schedules.service.StopRepository") as mock_stop_repo_cls:
        mock_stop_repo = mock_stop_repo_cls.return_value
        mock_stop_repo.list = AsyncMock(return_value=[])

        with patch("app.schedules.service.GTFSImporter") as mock_importer_cls:
            mock_importer = mock_importer_cls.return_value
            mock_importer.parse.side_effect = ValueError("Corrupt ZIP")

            with pytest.raises(GTFSImportError, match="Corrupt ZIP"):
                await service.import_gtfs(b"bad_zip")
