"""Tests for GTFS shapes parsing, export, and schema validation."""

import csv
import io
import zipfile

from app.schedules.gtfs_export import GTFSExporter
from app.schedules.gtfs_import import GTFSImporter
from app.schedules.models import Agency, Calendar, Route, Shape, Trip
from app.schedules.schemas import (
    GTFSImportResponse,
    RouteShapeResponse,
    RouteShapesResponse,
    ShapePointResponse,
)


def _make_gtfs_zip(
    files: dict[str, str],
) -> bytes:
    """Create a minimal GTFS ZIP with given files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _minimal_gtfs_files() -> dict[str, str]:
    """Return minimal GTFS files needed for a valid parse."""
    return {
        "agency.txt": "agency_id,agency_name,agency_timezone\ntest_agency,Test Agency,Europe/Riga\n",
        "routes.txt": "route_id,agency_id,route_short_name,route_long_name,route_type\nR1,test_agency,1,Route 1,3\n",
        "calendar.txt": "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nS1,1,1,1,1,1,0,0,20260101,20261231\n",
        "trips.txt": "route_id,service_id,trip_id,direction_id,shape_id\nR1,S1,T1,0,SH1\nR1,S1,T2,1,SH2\n",
        "stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n",
    }


def test_parse_shapes_from_gtfs_zip() -> None:
    """Test that shapes.txt is parsed correctly from a GTFS ZIP."""
    files = _minimal_gtfs_files()
    files["shapes.txt"] = (
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence,shape_dist_traveled\n"
        "SH1,56.9496,24.1052,1,0.0\n"
        "SH1,56.9500,24.1060,2,100.5\n"
        "SH2,56.9510,24.1070,1,\n"
    )
    zip_data = _make_gtfs_zip(files)

    importer = GTFSImporter(zip_data, feed_id="test")
    result = importer.parse(stop_map={})

    assert len(result.shapes) == 3
    # Check first shape
    sh1_points = [s for s in result.shapes if s.gtfs_shape_id == "SH1"]
    assert len(sh1_points) == 2
    assert sh1_points[0].shape_pt_lat == 56.9496
    assert sh1_points[0].shape_pt_lon == 24.1052
    assert sh1_points[0].shape_pt_sequence == 1
    assert sh1_points[0].shape_dist_traveled == 0.0
    assert sh1_points[1].shape_pt_sequence == 2
    assert sh1_points[1].shape_dist_traveled == 100.5

    # Check second shape
    sh2_points = [s for s in result.shapes if s.gtfs_shape_id == "SH2"]
    assert len(sh2_points) == 1
    assert sh2_points[0].shape_dist_traveled is None


def test_parse_shapes_missing_file() -> None:
    """Test that missing shapes.txt produces empty list and no error."""
    files = _minimal_gtfs_files()
    # No shapes.txt
    zip_data = _make_gtfs_zip(files)

    importer = GTFSImporter(zip_data, feed_id="test")
    result = importer.parse(stop_map={})

    assert len(result.shapes) == 0


def test_parse_shapes_invalid_coords() -> None:
    """Test that invalid coordinates are skipped with warning."""
    files = _minimal_gtfs_files()
    files["shapes.txt"] = (
        "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n"
        "SH1,56.9496,24.1052,1\n"
        "SH1,invalid,bad,2\n"
    )
    zip_data = _make_gtfs_zip(files)

    importer = GTFSImporter(zip_data, feed_id="test")
    result = importer.parse(stop_map={})

    assert len(result.shapes) == 1
    assert any("invalid coordinates" in w for w in result.warnings)


def test_parse_trip_shape_id() -> None:
    """Test that shape_id is captured from trips.txt."""
    files = _minimal_gtfs_files()
    zip_data = _make_gtfs_zip(files)

    importer = GTFSImporter(zip_data, feed_id="test")
    result = importer.parse(stop_map={})

    trip_shape_ids = {t.shape_id for t in result.trips}
    assert "SH1" in trip_shape_ids
    assert "SH2" in trip_shape_ids


def test_shapes_csv_export() -> None:
    """Test that shapes are exported to shapes.txt in GTFS ZIP."""
    agency = Agency(id=1, gtfs_agency_id="A1", agency_name="Test", agency_timezone="Europe/Riga")
    route = Route(
        id=1,
        gtfs_route_id="R1",
        agency_id=1,
        route_short_name="1",
        route_long_name="Route 1",
        route_type=3,
    )
    calendar = Calendar(
        id=1,
        gtfs_service_id="S1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    trip = Trip(
        id=1,
        gtfs_trip_id="T1",
        route_id=1,
        calendar_id=1,
        shape_id="SH1",
    )
    shapes = [
        Shape(
            gtfs_shape_id="SH1",
            feed_id="test",
            shape_pt_lat=56.9496,
            shape_pt_lon=24.1052,
            shape_pt_sequence=1,
            shape_dist_traveled=0.0,
        ),
        Shape(
            gtfs_shape_id="SH1",
            feed_id="test",
            shape_pt_lat=56.9500,
            shape_pt_lon=24.1060,
            shape_pt_sequence=2,
            shape_dist_traveled=100.5,
        ),
    ]

    exporter = GTFSExporter(
        agencies=[agency],
        routes=[route],
        calendars=[calendar],
        calendar_dates=[],
        trips=[trip],
        stop_times=[],
        stops=[],
        shapes=shapes,
    )
    zip_bytes = exporter.export()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert "shapes.txt" in zf.namelist()
        reader = csv.DictReader(io.TextIOWrapper(zf.open("shapes.txt"), encoding="utf-8"))
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["shape_id"] == "SH1"
        assert rows[0]["shape_pt_lat"] == "56.9496"
        assert rows[0]["shape_pt_sequence"] == "1"

        # Verify trip has shape_id in trips.txt
        trip_reader = csv.DictReader(io.TextIOWrapper(zf.open("trips.txt"), encoding="utf-8"))
        trip_rows = list(trip_reader)
        assert trip_rows[0]["shape_id"] == "SH1"


def test_export_no_shapes() -> None:
    """Test that shapes.txt is omitted when no shapes exist."""
    agency = Agency(id=1, gtfs_agency_id="A1", agency_name="Test", agency_timezone="Europe/Riga")
    route = Route(
        id=1,
        gtfs_route_id="R1",
        agency_id=1,
        route_short_name="1",
        route_long_name="Route 1",
        route_type=3,
    )
    calendar = Calendar(
        id=1,
        gtfs_service_id="S1",
        monday=True,
        tuesday=True,
        wednesday=True,
        thursday=True,
        friday=True,
        saturday=False,
        sunday=False,
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    exporter = GTFSExporter(
        agencies=[agency],
        routes=[route],
        calendars=[calendar],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[],
    )
    zip_bytes = exporter.export()

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert "shapes.txt" not in zf.namelist()


def test_route_shapes_response_schema() -> None:
    """Test RouteShapesResponse serialization."""
    response = RouteShapesResponse(
        route_id=1,
        gtfs_route_id="R1",
        shapes=[
            RouteShapeResponse(
                shape_id="SH1",
                points=[
                    ShapePointResponse(lat=56.9496, lon=24.1052, sequence=1, dist_traveled=0.0),
                    ShapePointResponse(lat=56.9500, lon=24.1060, sequence=2),
                ],
            ),
        ],
    )
    data = response.model_dump()
    assert data["route_id"] == 1
    assert data["gtfs_route_id"] == "R1"
    assert len(data["shapes"]) == 1
    assert data["shapes"][0]["shape_id"] == "SH1"
    assert len(data["shapes"][0]["points"]) == 2
    assert data["shapes"][0]["points"][1]["dist_traveled"] is None


def test_import_response_includes_shapes_count() -> None:
    """Test that GTFSImportResponse has shapes_count field."""
    response = GTFSImportResponse(
        feed_id="test",
        agencies_count=1,
        routes_count=5,
        calendars_count=2,
        calendar_dates_count=3,
        trips_count=10,
        stop_times_count=100,
        skipped_stop_times=0,
        warnings=[],
    )
    assert response.shapes_count == 0

    response2 = GTFSImportResponse(
        feed_id="test",
        agencies_count=1,
        routes_count=5,
        calendars_count=2,
        calendar_dates_count=3,
        trips_count=10,
        stop_times_count=100,
        shapes_count=500,
        skipped_stop_times=0,
        warnings=[],
    )
    assert response2.shapes_count == 500
