"""SIRI-SM (Stop Monitoring) XML builder.

Transforms VehiclePosition objects from the transit module into a SIRI 2.0
ServiceDelivery XML document containing MonitoredStopVisit elements,
filtered to a specific stop.
"""

from lxml import etree

from app.compliance.xml_namespaces import SIRI_NS, SIRI_NSMAP
from app.core.logging import get_logger
from app.transit.schemas import VehiclePosition

logger = get_logger(__name__)


def _siri_sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    """Create a namespaced sub-element under parent using SIRI namespace.

    Args:
        parent: Parent XML element.
        tag: Local tag name (without namespace).
        text: Optional text content.

    Returns:
        The created sub-element.
    """
    el = etree.SubElement(parent, f"{{{SIRI_NS}}}{tag}")
    if text is not None:
        el.text = text
    return el


def _format_delay(seconds: int) -> str:
    """Format delay seconds as ISO 8601 duration.

    Args:
        seconds: Delay in seconds (positive=late, negative=early).

    Returns:
        ISO 8601 duration string (e.g. "PT120S" or "-PT30S").
    """
    if seconds < 0:
        return f"-PT{abs(seconds)}S"
    return f"PT{seconds}S"


class SiriStopMonitoringBuilder:
    """Builds a SIRI-SM ServiceDelivery XML document for a specific stop.

    Filters vehicle positions to those approaching or at the given stop,
    then generates MonitoredStopVisit elements for each matching vehicle.

    Args:
        participant_ref: Producer reference identifying this system.
    """

    def __init__(self, *, participant_ref: str) -> None:
        self._participant_ref = participant_ref

    def build(
        self,
        stop_name: str,
        vehicles: list[VehiclePosition],
        response_timestamp: str,
    ) -> bytes:
        """Generate SIRI-SM XML bytes for a specific stop.

        Args:
            stop_name: Stop name to filter vehicles by.
            vehicles: List of all current vehicle positions.
            response_timestamp: ISO 8601 timestamp for the response.

        Returns:
            UTF-8 encoded SIRI XML document.
        """
        # Filter vehicles to those at or approaching the stop
        matching = [
            v for v in vehicles if v.next_stop_name == stop_name or v.current_stop_name == stop_name
        ]

        logger.info(
            "compliance.siri_sm.build_started",
            stop_name=stop_name,
            vehicle_count=len(vehicles),
            matching_count=len(matching),
        )

        root = etree.Element(
            f"{{{SIRI_NS}}}Siri",
            nsmap=SIRI_NSMAP,  # type: ignore[arg-type]  # lxml accepts None keys
        )
        root.set("version", "2.0")

        delivery = _siri_sub(root, "ServiceDelivery")
        _siri_sub(delivery, "ResponseTimestamp", response_timestamp)
        _siri_sub(delivery, "ProducerRef", self._participant_ref)

        sm_delivery = _siri_sub(delivery, "StopMonitoringDelivery")
        sm_delivery.set("version", "2.0")
        _siri_sub(sm_delivery, "ResponseTimestamp", response_timestamp)
        _siri_sub(sm_delivery, "MonitoringRef", stop_name)

        for vehicle in matching:
            self._build_stop_visit(sm_delivery, vehicle, stop_name)

        result: bytes = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )
        logger.info(
            "compliance.siri_sm.build_completed",
            stop_name=stop_name,
            visit_count=len(matching),
            byte_size=len(result),
        )
        return result

    def _build_stop_visit(
        self,
        parent: etree._Element,
        vehicle: VehiclePosition,
        stop_name: str,
    ) -> None:
        """Build a MonitoredStopVisit element from a VehiclePosition."""
        visit = _siri_sub(parent, "MonitoredStopVisit")
        _siri_sub(visit, "RecordedAtTime", vehicle.timestamp)

        mvj = _siri_sub(visit, "MonitoredVehicleJourney")
        _siri_sub(mvj, "LineRef", vehicle.route_id)
        _siri_sub(mvj, "PublishedLineName", vehicle.route_short_name)
        _siri_sub(mvj, "VehicleRef", vehicle.vehicle_id)

        # Monitored call for the stop
        monitored_call = _siri_sub(mvj, "MonitoredCall")
        _siri_sub(monitored_call, "StopPointName", stop_name)

        # Include delay as expected arrival offset if non-zero
        if vehicle.delay_seconds != 0:
            _siri_sub(mvj, "Delay", _format_delay(vehicle.delay_seconds))
