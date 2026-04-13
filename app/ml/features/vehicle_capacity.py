# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
"""Vehicle capacity lookup for passenger load factor calculation (ML-3.1)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

# Default capacities by transport type (Riga Satiksme fleet)
DEFAULT_CAPACITY: dict[str, int] = {
    "bus": 60,
    "articulated_bus": 100,  # Solaris Urbino 18
    "tram": 200,
    "trolleybus": 80,
}

FALLBACK_CAPACITY = 60  # Standard bus when type is unknown

CAPACITY_BY_VEHICLE_SQL = """
SELECT v.fleet_number, v.capacity, v.vehicle_type
FROM vehicles v
WHERE v.fleet_number = ANY(:vehicle_numbers)
  AND v.capacity IS NOT NULL
"""


def get_default_capacity(transport_type: str) -> int:
    """Look up default capacity by transport type.

    Args:
        transport_type: Transport type string (bus, tram, trolleybus, etc.).

    Returns:
        Vehicle capacity (passengers). Falls back to 60 for unknown types.
    """
    return DEFAULT_CAPACITY.get(transport_type.lower(), FALLBACK_CAPACITY)


async def get_vehicle_capacities(
    db: AsyncSession,
    vehicle_numbers: list[str],
    transport_types: dict[str, str] | None = None,
) -> dict[str, int]:
    """Resolve capacity for each vehicle: DB override > type default > 60.

    Args:
        db: Async database session.
        vehicle_numbers: List of vehicle fleet numbers to look up.
        transport_types: Optional mapping of vehicle_number -> transport_type
            for type-based default lookup.

    Returns:
        Dict mapping vehicle_number to capacity.
    """
    if not vehicle_numbers:
        return {}

    capacities: dict[str, int] = {}

    # 1. Query DB for explicit capacity overrides
    result = await db.execute(
        text(CAPACITY_BY_VEHICLE_SQL),
        {"vehicle_numbers": vehicle_numbers},
    )
    rows: list[Any] = list(result.mappings().all())
    for row in rows:
        capacities[str(row["fleet_number"])] = int(row["capacity"])

    logger.debug(
        "ml.load.capacity_db_resolved",
        db_overrides=len(capacities),
        total_vehicles=len(vehicle_numbers),
    )

    # 2. Fill remaining from DEFAULT_CAPACITY by transport_type
    types = transport_types or {}
    for vn in vehicle_numbers:
        if vn not in capacities:
            t_type = types.get(vn, "")
            capacities[vn] = get_default_capacity(t_type)

    return capacities
