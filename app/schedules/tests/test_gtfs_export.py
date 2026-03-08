# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for GTFS export functionality."""

import csv
import io
import zipfile
from collections.abc import Generator
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.main import app
from app.schedules.gtfs_export import GTFSExporter
from app.schedules.models import Agency, Calendar, CalendarDate, Route, StopTime, Trip
from app.stops.models import Stop

limiter.enabled = False


def _mock_admin_user() -> User:
    """Return a mock admin user for testing."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.name = "Admin"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    """Ensure auth override is set before each test and restored after."""
    app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def make_agency(
    id: int = 1, gtfs_agency_id: str = "RS", agency_name: str = "Rigas Satiksme"
) -> MagicMock:
    a = MagicMock(spec=Agency)
    a.id = id
    a.gtfs_agency_id = gtfs_agency_id
    a.agency_name = agency_name
    a.agency_url = "https://rigassatiksme.lv"
    a.agency_timezone = "Europe/Riga"
    a.agency_lang = "lv"
    return a


def make_route(id: int = 1, agency_id: int = 1, gtfs_route_id: str = "R1") -> MagicMock:
    r = MagicMock(spec=Route)
    r.id = id
    r.gtfs_route_id = gtfs_route_id
    r.agency_id = agency_id
    r.route_short_name = "1"
    r.route_long_name = "Route One"
    r.route_type = 3
    r.route_color = "FF0000"
    r.route_text_color = "FFFFFF"
    r.route_sort_order = None
    return r


def make_calendar(id: int = 1, gtfs_service_id: str = "WD") -> MagicMock:
    c = MagicMock(spec=Calendar)
    c.id = id
    c.gtfs_service_id = gtfs_service_id
    c.monday = True
    c.tuesday = True
    c.wednesday = True
    c.thursday = True
    c.friday = True
    c.saturday = False
    c.sunday = False
    c.start_date = date(2026, 1, 1)
    c.end_date = date(2026, 12, 31)
    return c


def make_calendar_date(id: int = 1, calendar_id: int = 1) -> MagicMock:
    cd = MagicMock(spec=CalendarDate)
    cd.id = id
    cd.calendar_id = calendar_id
    cd.date = date(2026, 3, 8)
    cd.exception_type = 2
    return cd


def make_trip(
    id: int = 1, route_id: int = 1, calendar_id: int = 1, gtfs_trip_id: str = "T1"
) -> MagicMock:
    t = MagicMock(spec=Trip)
    t.id = id
    t.gtfs_trip_id = gtfs_trip_id
    t.route_id = route_id
    t.calendar_id = calendar_id
    t.direction_id = 0
    t.trip_headsign = "Downtown"
    t.block_id = None
    return t


def make_stop_time(id: int = 1, trip_id: int = 1, stop_id: int = 1, seq: int = 1) -> MagicMock:
    st = MagicMock(spec=StopTime)
    st.id = id
    st.trip_id = trip_id
    st.stop_id = stop_id
    st.stop_sequence = seq
    st.arrival_time = "08:00:00"
    st.departure_time = "08:01:00"
    st.pickup_type = 0
    st.drop_off_type = 0
    return st


def make_stop(id: int = 1, gtfs_stop_id: str = "S1") -> MagicMock:
    s = MagicMock(spec=Stop)
    s.id = id
    s.gtfs_stop_id = gtfs_stop_id
    s.stop_name = "Central Station"
    s.stop_lat = 56.9496
    s.stop_lon = 24.1052
    s.stop_desc = None
    s.location_type = 0
    s.parent_station_id = None
    s.wheelchair_boarding = 1
    return s


class TestGTFSExporter:
    def test_export_produces_valid_zip(self):
        exporter = GTFSExporter(
            agencies=[make_agency()],
            routes=[make_route()],
            calendars=[make_calendar()],
            calendar_dates=[make_calendar_date()],
            trips=[make_trip()],
            stop_times=[make_stop_time()],
            stops=[make_stop()],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        assert "agency.txt" in zf.namelist()
        assert "routes.txt" in zf.namelist()
        assert "calendar.txt" in zf.namelist()
        assert "calendar_dates.txt" in zf.namelist()
        assert "trips.txt" in zf.namelist()
        assert "stop_times.txt" in zf.namelist()
        assert "stops.txt" in zf.namelist()

    def test_agency_csv_headers(self):
        exporter = GTFSExporter(
            agencies=[make_agency()],
            routes=[],
            calendars=[],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        reader = csv.DictReader(io.StringIO(zf.read("agency.txt").decode()))
        row = next(reader)
        assert "agency_id" in row
        assert "agency_name" in row
        assert "agency_timezone" in row

    def test_date_format_yyyymmdd(self):
        exporter = GTFSExporter(
            agencies=[],
            routes=[],
            calendars=[make_calendar()],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        reader = csv.DictReader(io.StringIO(zf.read("calendar.txt").decode()))
        row = next(reader)
        assert row["start_date"] == "20260101"
        assert row["end_date"] == "20261231"

    def test_boolean_days_as_1_0(self):
        exporter = GTFSExporter(
            agencies=[],
            routes=[],
            calendars=[make_calendar()],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        reader = csv.DictReader(io.StringIO(zf.read("calendar.txt").decode()))
        row = next(reader)
        assert row["monday"] == "1"
        assert row["saturday"] == "0"

    def test_empty_database_produces_valid_zip(self):
        exporter = GTFSExporter(
            agencies=[],
            routes=[],
            calendars=[],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        # Should still have required files (except calendar_dates which is conditional)
        assert "agency.txt" in zf.namelist()
        assert "routes.txt" in zf.namelist()
        assert "calendar_dates.txt" not in zf.namelist()

    def test_no_calendar_dates_when_empty(self):
        exporter = GTFSExporter(
            agencies=[make_agency()],
            routes=[],
            calendars=[],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        assert "calendar_dates.txt" not in zf.namelist()

    def test_route_csv_uses_gtfs_ids(self):
        exporter = GTFSExporter(
            agencies=[make_agency()],
            routes=[make_route()],
            calendars=[],
            calendar_dates=[],
            trips=[],
            stop_times=[],
            stops=[],
        )
        result = exporter.export()
        zf = zipfile.ZipFile(io.BytesIO(result))
        reader = csv.DictReader(io.StringIO(zf.read("routes.txt").decode()))
        row = next(reader)
        assert row["route_id"] == "R1"
        assert row["agency_id"] == "RS"


class TestExportEndpoint:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_export_returns_zip(self, client):
        with patch(
            "app.schedules.routes.ScheduleService.export_gtfs",
            new_callable=AsyncMock,
            return_value=b"PK\x03\x04fakezip",
        ):
            response = client.get("/api/v1/schedules/export")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"
        assert "attachment" in response.headers["content-disposition"]

    def test_export_with_agency_filter(self, client):
        with patch(
            "app.schedules.routes.ScheduleService.export_gtfs",
            new_callable=AsyncMock,
            return_value=b"PK\x03\x04fakezip",
        ) as mock_export:
            response = client.get("/api/v1/schedules/export?agency_id=1")
        assert response.status_code == 200
        mock_export.assert_awaited_once_with(agency_id=1, feed_id=None)
