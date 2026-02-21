# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Tests for GTFS ZIP file parser."""

import io
import zipfile

import pytest

from app.schedules.gtfs_import import GTFSImporter


def _make_gtfs_zip(**files: str) -> bytes:
    """Create an in-memory GTFS ZIP with CSV content.

    Args:
        **files: Filename to CSV content mapping (e.g., agency_txt="...").
            Use underscores instead of dots in keys: agency_txt -> agency.txt.

    Returns:
        Raw bytes of the ZIP file.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, content in files.items():
            filename = key.replace("_txt", ".txt")
            zf.writestr(filename, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_parse_agencies():
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_url,agency_timezone,agency_lang\n"
        "RS,Rigas Satiksme,https://www.rigassatiksme.lv,Europe/Riga,lv\n"
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map={})

    assert len(result.agencies) == 1
    assert result.agencies[0].gtfs_agency_id == "RS"
    assert result.agencies[0].agency_name == "Rigas Satiksme"
    assert result.agencies[0].agency_timezone == "Europe/Riga"
    assert result.agencies[0].agency_lang == "lv"


@pytest.mark.asyncio
async def test_parse_routes():
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Rigas Satiksme,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "bus_22,RS,22,Centrs - Jugla,3\n"
        "trol_14,RS,14,Centrs - Imanta,11\n"
        "tram_1,RS,1,Jugla - Imanta,0\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map={})

    assert len(result.routes) == 3
    assert result.routes[0].gtfs_route_id == "bus_22"
    assert result.routes[0].route_type == 3
    assert result.routes[1].route_type == 11
    assert result.routes[2].route_type == 0


@pytest.mark.asyncio
async def test_parse_calendars_and_dates():
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Rigas Satiksme,Europe/Riga\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "weekday_1,1,1,1,1,1,0,0,20260101,20261231\n",
        calendar_dates_txt="service_id,date,exception_type\n"
        "weekday_1,20260315,2\n"
        "weekday_1,20260316,1\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map={})

    assert len(result.calendars) == 1
    cal = result.calendars[0]
    assert cal.gtfs_service_id == "weekday_1"
    assert cal.monday is True
    assert cal.saturday is False

    assert len(result.calendar_dates) == 2
    assert result.calendar_dates[0].exception_type == 2
    assert result.calendar_dates[1].exception_type == 1


@pytest.mark.asyncio
async def test_parse_trips():
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Rigas Satiksme,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "bus_22,RS,22,Centrs - Jugla,3\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "weekday_1,1,1,1,1,1,0,0,20260101,20261231\n",
        trips_txt="route_id,service_id,trip_id,direction_id,trip_headsign\n"
        "bus_22,weekday_1,trip_22_1,0,Jugla\n"
        "bus_22,weekday_1,trip_22_2,1,Centrs\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map={})

    assert len(result.trips) == 2
    assert result.trips[0].gtfs_trip_id == "trip_22_1"
    assert result.trips[0].direction_id == 0
    assert result.trips[0].trip_headsign == "Jugla"
    assert result.trips[1].direction_id == 1


@pytest.mark.asyncio
async def test_parse_stop_times_with_stop_map():
    stop_map = {"1001": 42, "1002": 43}
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Rigas Satiksme,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "bus_22,RS,22,Centrs - Jugla,3\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "weekday_1,1,1,1,1,1,0,0,20260101,20261231\n",
        trips_txt="route_id,service_id,trip_id,direction_id,trip_headsign\n"
        "bus_22,weekday_1,trip_22_1,0,Jugla\n",
        stop_times_txt="trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "trip_22_1,08:00:00,08:01:00,1001,1\n"
        "trip_22_1,08:05:00,08:06:00,1002,2\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map=stop_map)

    assert len(result.stop_times) == 2
    assert result.stop_times[0].stop_id == 42
    assert result.stop_times[0].arrival_time == "08:00:00"
    assert result.stop_times[1].stop_id == 43
    assert result.stop_times[1].stop_sequence == 2
    assert result.skipped_stop_times == 0


@pytest.mark.asyncio
async def test_parse_stop_times_missing_stop_skipped():
    stop_map = {"1001": 42}  # 1002 is NOT in the map
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Rigas Satiksme,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "bus_22,RS,22,Centrs - Jugla,3\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n"
        "weekday_1,1,1,1,1,1,0,0,20260101,20261231\n",
        trips_txt="route_id,service_id,trip_id,direction_id,trip_headsign\n"
        "bus_22,weekday_1,trip_22_1,0,Jugla\n",
        stop_times_txt="trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
        "trip_22_1,08:00:00,08:01:00,1001,1\n"
        "trip_22_1,08:05:00,08:06:00,1002,2\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map=stop_map)

    assert len(result.stop_times) == 1
    assert result.skipped_stop_times == 1
    assert any("Skipped" in w for w in result.warnings)


@pytest.mark.asyncio
async def test_missing_agencies_file_creates_default():
    zip_data = _make_gtfs_zip(
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\n"
        "bus_22,,22,Centrs - Jugla,3\n",
    )
    importer = GTFSImporter(zip_data)
    result = importer.parse(stop_map={})

    assert len(result.agencies) == 1
    assert result.agencies[0].gtfs_agency_id == "default"
    assert result.agencies[0].agency_name == "Default Agency"
    assert any("agency.txt not found" in w for w in result.warnings)
    # Route should still be parsed with the default agency
    assert len(result.routes) == 1
