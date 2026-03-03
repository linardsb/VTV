"""SIRI-VM (Vehicle Monitoring) XML builder.

Transforms VehiclePosition objects from the transit module into a SIRI 2.0
ServiceDelivery XML document containing VehicleActivity elements.
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


class SiriVehicleMonitoringBuilder:
    """Builds a SIRI-VM ServiceDelivery XML document from vehicle positions.

    Args:
        participant_ref: Producer reference identifying this system.
    """

    def __init__(self, *, participant_ref: str) -> None:
        self._participant_ref = participant_ref

    def build(
        self,
        vehicles: list[VehiclePosition],
        response_timestamp: str,
    ) -> bytes:
        """Generate SIRI-VM XML bytes.

        Args:
            vehicles: List of current vehicle positions.
            response_timestamp: ISO 8601 timestamp for the response.

        Returns:
            UTF-8 encoded SIRI XML document.
        """
        logger.info(
            "compliance.siri_vm.build_started",
            vehicle_count=len(vehicles),
        )

        root = etree.Element(
            f"{{{SIRI_NS}}}Siri",
            nsmap=SIRI_NSMAP,  # type: ignore[arg-type]  # lxml accepts None keys
        )
        root.set("version", "2.0")

        delivery = _siri_sub(root, "ServiceDelivery")
        _siri_sub(delivery, "ResponseTimestamp", response_timestamp)
        _siri_sub(delivery, "ProducerRef", self._participant_ref)

        vm_delivery = _siri_sub(delivery, "VehicleMonitoringDelivery")
        vm_delivery.set("version", "2.0")
        _siri_sub(vm_delivery, "ResponseTimestamp", response_timestamp)

        for vehicle in vehicles:
            self._build_vehicle_activity(vm_delivery, vehicle)

        result: bytes = etree.tostring(
            root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )
        logger.info(
            "compliance.siri_vm.build_completed",
            vehicle_count=len(vehicles),
            byte_size=len(result),
        )
        return result

    def _build_vehicle_activity(
        self,
        parent: etree._Element,
        vehicle: VehiclePosition,
    ) -> None:
        """Build a VehicleActivity element from a VehiclePosition."""
        activity = _siri_sub(parent, "VehicleActivity")
        _siri_sub(activity, "RecordedAtTime", vehicle.timestamp)

        mvj = _siri_sub(activity, "MonitoredVehicleJourney")
        _siri_sub(mvj, "LineRef", vehicle.route_id)
        _siri_sub(mvj, "PublishedLineName", vehicle.route_short_name)
        _siri_sub(mvj, "VehicleRef", vehicle.vehicle_id)

        # Vehicle location
        location = _siri_sub(mvj, "VehicleLocation")
        _siri_sub(location, "Longitude", str(vehicle.longitude))
        _siri_sub(location, "Latitude", str(vehicle.latitude))

        # Optional bearing
        if vehicle.bearing is not None:
            _siri_sub(mvj, "Bearing", str(vehicle.bearing))

        # Delay (always include if non-zero)
        if vehicle.delay_seconds != 0:
            _siri_sub(mvj, "Delay", _format_delay(vehicle.delay_seconds))

        # Monitored call with next stop
        if vehicle.next_stop_name is not None:
            monitored_call = _siri_sub(mvj, "MonitoredCall")
            _siri_sub(monitored_call, "StopPointName", vehicle.next_stop_name)
