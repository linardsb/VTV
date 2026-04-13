# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Tests for multi-feed management (LV-1.2)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schedules.feed_status import GTFSFeedStatusRepository
from app.schedules.schemas import FeedStatusResponse, GTFSImportResponse
from app.schedules.service import ScheduleService
from app.schedules.tests.conftest import make_agency, make_feed_status, make_route


@pytest.fixture
def service():
    mock_db = AsyncMock()
    return ScheduleService(mock_db)


# --- Feed status repository tests ---


@pytest.mark.asyncio
async def test_upsert_feed_status_creates_new():
    """First upsert creates a new feed status row."""
    mock_db = AsyncMock()
    repo = GTFSFeedStatusRepository(mock_db)

    # No existing status
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    result = await repo.upsert_feed_status(
        feed_id="atd",
        operator_name="Autobusu Parks",
    )
    assert result.feed_id == "atd"
    assert result.operator_name == "Autobusu Parks"
    mock_db.add.assert_called_once()
    mock_db.flush.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_feed_status_updates_existing():
    """Second upsert updates existing, not duplicates."""
    mock_db = AsyncMock()
    repo = GTFSFeedStatusRepository(mock_db)

    existing = make_feed_status(feed_id="riga", last_import_routes=50)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing
    mock_db.execute.return_value = mock_result

    result = await repo.upsert_feed_status(
        feed_id="riga",
        operator_name="Rigas Satiksme",
        last_import_routes=75,
    )
    assert result.last_import_routes == 75
    mock_db.add.assert_not_called()
    mock_db.flush.assert_called_once()


# --- Service list_feeds tests ---


@pytest.mark.asyncio
async def test_list_feeds_returns_configured_feeds(service):
    """GET /feeds returns configured feeds enriched with DB status."""
    db_status = make_feed_status(feed_id="riga", last_import_routes=50, last_import_trips=200)

    service.feed_status_repo.list_feed_statuses = AsyncMock(return_value=[db_status])

    with patch("app.schedules.service.get_settings") as mock_settings:
        from app.core.config import TransitFeedConfig

        mock_settings.return_value.transit_feeds = [
            TransitFeedConfig(
                feed_id="riga",
                operator_name="Rigas Satiksme",
                rt_vehicle_positions_url="http://example.com/vp",
                rt_trip_updates_url="http://example.com/tu",
                static_url="https://saraksti.rigassatiksme.lv/gtfs.zip",
                enabled=True,
            ),
        ]

        result = await service.list_feeds()

    assert len(result) == 1
    assert result[0].feed_id == "riga"
    assert result[0].last_import_routes == 50
    assert result[0].enabled is True


# --- Service import_feed_from_url tests ---


@pytest.mark.asyncio
async def test_import_feed_unknown_feed_id_404(service):
    """feed_id not in config raises NotFoundError."""
    from app.core.exceptions import NotFoundError

    with patch("app.schedules.service.get_settings") as mock_settings:
        from app.core.config import TransitFeedConfig

        mock_settings.return_value.transit_feeds = [
            TransitFeedConfig(
                feed_id="riga",
                operator_name="Rigas Satiksme",
                rt_vehicle_positions_url="http://example.com/vp",
                rt_trip_updates_url="http://example.com/tu",
                static_url="https://saraksti.rigassatiksme.lv/gtfs.zip",
                enabled=True,
            ),
        ]

        with pytest.raises(NotFoundError, match="unknown"):
            await service.import_feed_from_url("unknown")


@pytest.mark.asyncio
@patch("app.schedules.service.invalidate_route_cache", new_callable=AsyncMock)
@patch("app.schedules.service.invalidate_stop_cache", new_callable=AsyncMock)
async def test_import_feed_from_url_success(mock_inv_stops, mock_inv_routes, service):
    """Successful feed import via URL download."""

    with patch("app.schedules.service.get_settings") as mock_settings:
        from app.core.config import TransitFeedConfig

        mock_settings.return_value.transit_feeds = [
            TransitFeedConfig(
                feed_id="riga",
                operator_name="Rigas Satiksme",
                rt_vehicle_positions_url="http://example.com/vp",
                rt_trip_updates_url="http://example.com/tu",
                static_url="https://saraksti.rigassatiksme.lv/gtfs.zip",
                enabled=True,
            ),
        ]

        # Mock httpx download
        with patch("app.schedules.service.httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.content = b"fake_zip"
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_resp
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            # Mock the import_gtfs method to avoid the full import flow
            expected_result = GTFSImportResponse(
                feed_id="riga",
                agencies_count=1,
                routes_count=5,
                calendars_count=2,
                calendar_dates_count=0,
                trips_count=10,
                stop_times_count=50,
                skipped_stop_times=0,
                warnings=[],
            )
            service.import_gtfs = AsyncMock(return_value=expected_result)

            result = await service.import_feed_from_url("riga")

    assert result.feed_id == "riga"
    assert result.routes_count == 5
    service.import_gtfs.assert_called_once_with(b"fake_zip", feed_id="riga")


# --- Background task tests ---


@pytest.mark.asyncio
async def test_feed_task_starts_when_enabled():
    """With gtfs_auto_import_enabled=True, task starts."""
    from app.schedules.feed_task import start_feed_import_task, stop_feed_import_task

    with patch("app.schedules.feed_task.get_settings") as mock_settings:
        mock_settings.return_value.gtfs_auto_import_enabled = True
        mock_settings.return_value.gtfs_auto_import_hour_utc = 3

        with patch("app.schedules.feed_task.asyncio.create_task") as mock_create:
            mock_create.return_value = AsyncMock()
            await start_feed_import_task()
            mock_create.assert_called_once()

    # Cleanup
    await stop_feed_import_task()


@pytest.mark.asyncio
async def test_feed_task_skips_when_disabled():
    """With gtfs_auto_import_enabled=False, task does NOT start."""
    from app.schedules.feed_task import start_feed_import_task

    with patch("app.schedules.feed_task.get_settings") as mock_settings:
        mock_settings.return_value.gtfs_auto_import_enabled = False

        with patch("app.schedules.feed_task.asyncio.create_task") as mock_create:
            await start_feed_import_task()
            mock_create.assert_not_called()


# --- Service duplicate-check with feed_id tests ---


@pytest.mark.asyncio
async def test_create_route_duplicate_check_scoped_to_feed(service):
    """create_route duplicate check passes feed_id='riga'."""
    from app.schedules.schemas import RouteCreate

    data = RouteCreate(
        gtfs_route_id="bus_22",
        agency_id=1,
        route_short_name="22",
        route_long_name="Centrs - Jugla",
        route_type=3,
    )

    service.repository.get_route_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_route = AsyncMock(return_value=make_route())

    await service.create_route(data)

    service.repository.get_route_by_gtfs_id.assert_called_once_with("bus_22", feed_id="riga")


@pytest.mark.asyncio
async def test_create_agency_duplicate_check_scoped_to_feed(service):
    """create_agency duplicate check passes feed_id='riga'."""
    from app.schedules.schemas import AgencyCreate

    data = AgencyCreate(
        gtfs_agency_id="RS",
        agency_name="Rigas Satiksme",
    )

    service.repository.get_agency_by_gtfs_id = AsyncMock(return_value=None)
    service.repository.create_agency = AsyncMock(return_value=make_agency())

    await service.create_agency(data)

    service.repository.get_agency_by_gtfs_id.assert_called_once_with("RS", feed_id="riga")


# --- Feed status model tests ---


def test_feed_status_model_fields():
    """GTFSFeedStatus model has expected fields."""
    fs = make_feed_status()
    assert fs.feed_id == "riga"
    assert fs.operator_name == "Rigas Satiksme"
    assert fs.auto_import_enabled is True
    assert fs.last_import_routes == 50
    assert fs.last_import_trips == 200
    assert fs.last_import_error is None


def test_feed_status_response_schema():
    """FeedStatusResponse accepts valid data."""
    resp = FeedStatusResponse(
        feed_id="riga",
        operator_name="Rigas Satiksme",
        static_url="https://example.com/gtfs.zip",
        last_imported_at=None,
        last_import_routes=0,
        last_import_trips=0,
        last_import_error=None,
        auto_import_enabled=True,
        enabled=True,
    )
    assert resp.feed_id == "riga"
    assert resp.enabled is True
