"""Unit tests for SIRI-VM and SIRI-SM XML builders.

Tests builders in isolation — no DB, no HTTP, no Redis.
VehiclePosition instances constructed via conftest fixtures.
"""

from lxml import etree

from app.compliance.siri_sm import SiriStopMonitoringBuilder
from app.compliance.siri_vm import SiriVehicleMonitoringBuilder
from app.transit.schemas import VehiclePosition

SIRI_NS = "http://www.siri.org.uk/siri"
TIMESTAMP = "2026-03-03T12:00:00Z"


def _find(root: etree._Element, xpath: str) -> etree._Element | None:
    """Helper to find elements using namespace-aware XPath."""
    return root.find(xpath, namespaces={"s": SIRI_NS})


def _findall(root: etree._Element, xpath: str) -> list[etree._Element]:
    """Helper to find all matching elements."""
    return root.findall(xpath, namespaces={"s": SIRI_NS})


# --- SIRI-VM Tests ---


def test_siri_vm_empty() -> None:
    """Empty vehicle list produces valid SIRI-VM XML."""
    builder = SiriVehicleMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(vehicles=[], response_timestamp=TIMESTAMP)
    root = etree.fromstring(xml_bytes)
    assert root.tag == f"{{{SIRI_NS}}}Siri"
    assert root.get("version") == "2.0"

    # Should have delivery structure but no activities
    vm_delivery = _find(root, ".//s:VehicleMonitoringDelivery")
    assert vm_delivery is not None
    activities = _findall(root, ".//s:VehicleActivity")
    assert len(activities) == 0


def test_siri_vm_vehicle_maps_to_activity(
    sample_vehicle_position: VehiclePosition,
) -> None:
    """VehiclePosition maps to VehicleActivity with correct fields."""
    builder = SiriVehicleMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(vehicles=[sample_vehicle_position], response_timestamp=TIMESTAMP)
    root = etree.fromstring(xml_bytes)

    activities = _findall(root, ".//s:VehicleActivity")
    assert len(activities) == 1

    # Check key fields
    vehicle_ref = _find(root, ".//s:VehicleRef")
    assert vehicle_ref is not None
    assert vehicle_ref.text == "4521"

    line_ref = _find(root, ".//s:LineRef")
    assert line_ref is not None
    assert line_ref.text == "R1"

    lon = _find(root, ".//s:Longitude")
    lat = _find(root, ".//s:Latitude")
    assert lon is not None
    assert lat is not None
    assert lon.text == "24.1134"
    assert lat.text == "56.9496"


def test_siri_vm_delay_formatting(sample_vehicle_position: VehiclePosition) -> None:
    """Positive delay formats as PT{n}S, negative as -PT{n}S."""
    builder = SiriVehicleMonitoringBuilder(participant_ref="TEST")

    # Positive delay (120s late)
    xml_bytes = builder.build(vehicles=[sample_vehicle_position], response_timestamp=TIMESTAMP)
    root = etree.fromstring(xml_bytes)
    delay = _find(root, ".//s:Delay")
    assert delay is not None
    assert delay.text == "PT120S"

    # Negative delay (30s early)
    early_vehicle = VehiclePosition(
        vehicle_id="4522",
        route_id="R1",
        route_short_name="22",
        route_type=3,
        latitude=56.95,
        longitude=24.11,
        delay_seconds=-30,
        current_status="IN_TRANSIT_TO",
        timestamp=TIMESTAMP,
    )
    xml_bytes = builder.build(vehicles=[early_vehicle], response_timestamp=TIMESTAMP)
    root = etree.fromstring(xml_bytes)
    delay = _find(root, ".//s:Delay")
    assert delay is not None
    assert delay.text == "-PT30S"


def test_siri_vm_optional_fields_omitted() -> None:
    """Optional fields (bearing, next_stop) omitted when None."""
    vehicle = VehiclePosition(
        vehicle_id="4523",
        route_id="R2",
        route_short_name="15",
        route_type=3,
        latitude=56.95,
        longitude=24.11,
        bearing=None,
        delay_seconds=0,
        current_status="STOPPED_AT",
        next_stop_name=None,
        timestamp=TIMESTAMP,
    )
    builder = SiriVehicleMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(vehicles=[vehicle], response_timestamp=TIMESTAMP)
    root = etree.fromstring(xml_bytes)

    # No Bearing element
    bearing = _find(root, ".//s:Bearing")
    assert bearing is None

    # No Delay element (delay_seconds=0)
    delay = _find(root, ".//s:Delay")
    assert delay is None

    # No MonitoredCall element (next_stop_name=None)
    monitored_call = _find(root, ".//s:MonitoredCall")
    assert monitored_call is None


# --- SIRI-SM Tests ---


def test_siri_sm_filters_by_stop_name() -> None:
    """Only vehicles at the requested stop appear in MonitoredStopVisit."""
    vehicles = [
        VehiclePosition(
            vehicle_id="V1",
            route_id="R1",
            route_short_name="22",
            route_type=3,
            latitude=56.95,
            longitude=24.11,
            delay_seconds=0,
            current_status="IN_TRANSIT_TO",
            next_stop_name="Centrālā stacija",
            timestamp=TIMESTAMP,
        ),
        VehiclePosition(
            vehicle_id="V2",
            route_id="R2",
            route_short_name="15",
            route_type=3,
            latitude=56.96,
            longitude=24.12,
            delay_seconds=0,
            current_status="IN_TRANSIT_TO",
            next_stop_name="Origo",
            timestamp=TIMESTAMP,
        ),
        VehiclePosition(
            vehicle_id="V3",
            route_id="R3",
            route_short_name="7",
            route_type=0,
            latitude=56.94,
            longitude=24.10,
            delay_seconds=0,
            current_status="STOPPED_AT",
            current_stop_name="Centrālā stacija",
            timestamp=TIMESTAMP,
        ),
    ]

    builder = SiriStopMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(
        stop_name="Centrālā stacija",
        vehicles=vehicles,
        response_timestamp=TIMESTAMP,
    )
    root = etree.fromstring(xml_bytes)

    visits = _findall(root, ".//s:MonitoredStopVisit")
    assert len(visits) == 2  # V1 (next_stop) and V3 (current_stop)

    # MonitoringRef should be the stop name
    monitoring_ref = _find(root, ".//s:MonitoringRef")
    assert monitoring_ref is not None
    assert monitoring_ref.text == "Centrālā stacija"


def test_siri_sm_empty_when_no_vehicles_at_stop() -> None:
    """No MonitoredStopVisit elements when no vehicles at the requested stop."""
    vehicles = [
        VehiclePosition(
            vehicle_id="V1",
            route_id="R1",
            route_short_name="22",
            route_type=3,
            latitude=56.95,
            longitude=24.11,
            delay_seconds=0,
            current_status="IN_TRANSIT_TO",
            next_stop_name="Origo",
            timestamp=TIMESTAMP,
        ),
    ]

    builder = SiriStopMonitoringBuilder(participant_ref="TEST")
    xml_bytes = builder.build(
        stop_name="Centrālā stacija",
        vehicles=vehicles,
        response_timestamp=TIMESTAMP,
    )
    root = etree.fromstring(xml_bytes)

    visits = _findall(root, ".//s:MonitoredStopVisit")
    assert len(visits) == 0

    # MonitoringRef should still be present
    monitoring_ref = _find(root, ".//s:MonitoringRef")
    assert monitoring_ref is not None
    assert monitoring_ref.text == "Centrālā stacija"

    # Delivery structure should exist
    sm_delivery = _find(root, ".//s:StopMonitoringDelivery")
    assert sm_delivery is not None
