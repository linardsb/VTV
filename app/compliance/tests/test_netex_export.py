"""Unit tests for NeTEx XML export.

Tests NeTEx exporter in isolation — no DB, no HTTP.
Model instances are constructed in-memory via conftest fixtures.
"""

from lxml import etree

from app.compliance.netex_export import NeTExExporter
from app.schedules.models import Agency, Calendar, CalendarDate, Route, StopTime, Trip
from app.stops.models import Stop

NETEX_NS = "http://www.netex.org.uk/netex"
GML_NS = "http://www.opengis.net/gml/3.2"


def _find(root: etree._Element, xpath: str) -> etree._Element | None:
    """Helper to find elements using namespace-aware XPath."""
    return root.find(xpath, namespaces={"n": NETEX_NS, "gml": GML_NS})


def _findall(root: etree._Element, xpath: str) -> list[etree._Element]:
    """Helper to find all matching elements."""
    return root.findall(xpath, namespaces={"n": NETEX_NS, "gml": GML_NS})


def test_netex_export_empty() -> None:
    """Empty export produces valid NeTEx XML with correct root element."""
    exporter = NeTExExporter(
        agencies=[],
        routes=[],
        calendars=[],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)
    assert root.tag == f"{{{NETEX_NS}}}PublicationDelivery"
    assert root.get("version") == "1.2"


def test_agency_maps_to_operator(sample_agency: Agency) -> None:
    """Agency model maps to NeTEx Operator element."""
    exporter = NeTExExporter(
        agencies=[sample_agency],
        routes=[],
        calendars=[],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    operators = _findall(root, ".//n:Operator")
    assert len(operators) == 1
    name_el = _find(operators[0], "n:Name")
    assert name_el is not None
    assert name_el.text == "Test Transit Agency"


def test_station_stop_maps_to_stop_place(sample_station_stop: Stop) -> None:
    """Stop with location_type=1 maps to NeTEx StopPlace with GML centroid."""
    exporter = NeTExExporter(
        agencies=[],
        routes=[],
        calendars=[],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[sample_station_stop],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    stop_places = _findall(root, ".//n:StopPlace")
    assert len(stop_places) == 1
    # Should have GML centroid
    pos = _find(stop_places[0], ".//gml:pos")
    assert pos is not None
    assert "56.9497" in (pos.text or "")


def test_platform_stop_maps_to_scheduled_stop_point(sample_stop: Stop) -> None:
    """Stop with location_type=0 maps to NeTEx ScheduledStopPoint."""
    exporter = NeTExExporter(
        agencies=[],
        routes=[],
        calendars=[],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[sample_stop],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    stop_points = _findall(root, ".//n:ScheduledStopPoint")
    assert len(stop_points) == 1
    assert "TEST:ScheduledStopPoint:" in (stop_points[0].get("id") or "")


def test_route_maps_to_line_with_transport_mode(sample_agency: Agency, sample_route: Route) -> None:
    """Route with route_type=3 maps to Line with TransportMode 'bus'."""
    exporter = NeTExExporter(
        agencies=[sample_agency],
        routes=[sample_route],
        calendars=[],
        calendar_dates=[],
        trips=[],
        stop_times=[],
        stops=[],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    lines = _findall(root, ".//n:Line")
    assert len(lines) == 1
    mode = _find(lines[0], "n:TransportMode")
    assert mode is not None
    assert mode.text == "bus"


def test_trip_maps_to_service_journey_with_calls(
    sample_agency: Agency,
    sample_route: Route,
    sample_calendar: Calendar,
    sample_trip: Trip,
    sample_stop: Stop,
    sample_stop_times: list[StopTime],
) -> None:
    """Trip with StopTimes maps to ServiceJourney with ordered Call elements."""
    exporter = NeTExExporter(
        agencies=[sample_agency],
        routes=[sample_route],
        calendars=[sample_calendar],
        calendar_dates=[],
        trips=[sample_trip],
        stop_times=sample_stop_times,
        stops=[sample_stop],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    journeys = _findall(root, ".//n:ServiceJourney")
    assert len(journeys) == 1

    calls = _findall(journeys[0], ".//n:Call")
    assert len(calls) == 3

    # Verify order (check first and last call times)
    first_arrival = _find(calls[0], "n:Arrival/n:Time")
    last_arrival = _find(calls[2], "n:Arrival/n:Time")
    assert first_arrival is not None
    assert last_arrival is not None
    assert first_arrival.text == "08:00:00"
    assert last_arrival.text == "08:20:00"


def test_full_export_with_all_entities(
    sample_agency: Agency,
    sample_route: Route,
    sample_calendar: Calendar,
    sample_calendar_date: CalendarDate,
    sample_trip: Trip,
    sample_stop: Stop,
    sample_station_stop: Stop,
    sample_stop_times: list[StopTime],
) -> None:
    """Full export with all entity types produces valid complete XML."""
    exporter = NeTExExporter(
        agencies=[sample_agency],
        routes=[sample_route],
        calendars=[sample_calendar],
        calendar_dates=[sample_calendar_date],
        trips=[sample_trip],
        stop_times=sample_stop_times,
        stops=[sample_stop, sample_station_stop],
        codespace="TEST",
    )
    xml_bytes = exporter.export()
    root = etree.fromstring(xml_bytes)

    # Verify all four frames exist
    assert _findall(root, ".//n:ResourceFrame"), "Missing ResourceFrame"
    assert _findall(root, ".//n:SiteFrame"), "Missing SiteFrame"
    assert _findall(root, ".//n:ServiceFrame"), "Missing ServiceFrame"
    assert _findall(root, ".//n:TimetableFrame"), "Missing TimetableFrame"

    # Verify entity counts
    assert len(_findall(root, ".//n:Operator")) == 1
    assert len(_findall(root, ".//n:StopPlace")) == 1
    assert len(_findall(root, ".//n:ScheduledStopPoint")) == 1
    assert len(_findall(root, ".//n:Line")) == 1
    assert len(_findall(root, ".//n:ServiceJourney")) == 1

    # XML is valid UTF-8
    assert xml_bytes.startswith(b"<?xml")
