"""Driver availability data provider for Riga's transit system.

Queries the drivers database when available, falling back to mock data
for tests and environments without a database connection.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)

_FALLBACK_DRIVERS: list[dict[str, str | list[str] | None]] = [
    # --- Morning shift (6 drivers) ---
    {
        "driver_id": "DRV-001",
        "name": "J. Berzins",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_1", "bus_3", "bus_7", "bus_22", "bus_24"],
        "shift": "morning",
        "status": "available",
        "phone": "+371 2610 1001",
        "notes": "senior driver",
    },
    {
        "driver_id": "DRV-002",
        "name": "A. Kalnina",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_7", "bus_13", "bus_15", "bus_22"],
        "shift": "morning",
        "status": "available",
        "phone": "+371 2610 1002",
        "notes": None,
    },
    {
        "driver_id": "DRV-003",
        "name": "M. Ozols",
        "license_categories": ["D", "DE"],
        "qualified_route_ids": ["bus_22", "bus_24", "bus_30", "bus_32", "bus_37"],
        "shift": "morning",
        "status": "available",
        "phone": "+371 2610 1003",
        "notes": "overtime eligible",
    },
    {
        "driver_id": "DRV-004",
        "name": "R. Liepins",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_3", "bus_40", "bus_45"],
        "shift": "morning",
        "status": "on_duty",
        "phone": None,
        "notes": None,
    },
    {
        "driver_id": "DRV-005",
        "name": "I. Jansone",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_7", "bus_15", "bus_48", "bus_53"],
        "shift": "morning",
        "status": "on_leave",
        "phone": None,
        "notes": None,
    },
    {
        "driver_id": "DRV-006",
        "name": "E. Vitols",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_3", "bus_13", "bus_22", "bus_30", "bus_37", "bus_40"],
        "shift": "morning",
        "status": "available",
        "phone": "+371 2610 1006",
        "notes": None,
    },
    # --- Afternoon shift (5 drivers) ---
    {
        "driver_id": "DRV-007",
        "name": "K. Krumins",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_7", "bus_22", "bus_24", "bus_32"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1007",
        "notes": None,
    },
    {
        "driver_id": "DRV-008",
        "name": "D. Ozolina",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_3", "bus_15", "bus_30", "bus_45", "bus_48", "bus_53"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1008",
        "notes": "senior driver",
    },
    {
        "driver_id": "DRV-009",
        "name": "V. Zarins",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_7", "bus_13", "bus_22", "bus_37"],
        "shift": "afternoon",
        "status": "on_duty",
        "phone": None,
        "notes": None,
    },
    {
        "driver_id": "DRV-010",
        "name": "S. Balode",
        "license_categories": ["D", "DE"],
        "qualified_route_ids": ["bus_1", "bus_3", "bus_24", "bus_40"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1010",
        "notes": "overtime eligible",
    },
    {
        "driver_id": "DRV-011",
        "name": "N. Lacis",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_15", "bus_32", "bus_45"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1011",
        "notes": None,
    },
    # --- Evening shift (5 drivers) ---
    {
        "driver_id": "DRV-012",
        "name": "G. Celmins",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_7", "bus_13", "bus_22"],
        "shift": "evening",
        "status": "available",
        "phone": "+371 2610 1012",
        "notes": None,
    },
    {
        "driver_id": "DRV-013",
        "name": "L. Petersone",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_3", "bus_15", "bus_24", "bus_30", "bus_37"],
        "shift": "evening",
        "status": "available",
        "phone": "+371 2610 1013",
        "notes": None,
    },
    {
        "driver_id": "DRV-014",
        "name": "T. Kalejs",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_22", "bus_32", "bus_40", "bus_45", "bus_48"],
        "shift": "evening",
        "status": "on_duty",
        "phone": None,
        "notes": None,
    },
    {
        "driver_id": "DRV-015",
        "name": "P. Vanags",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_7", "bus_13", "bus_53"],
        "shift": "evening",
        "status": "available",
        "phone": "+371 2610 1015",
        "notes": "trainee - supervised only",
    },
    {
        "driver_id": "DRV-016",
        "name": "Z. Auzina",
        "license_categories": ["D", "DE"],
        "qualified_route_ids": ["bus_1", "bus_3", "bus_22", "bus_24", "bus_30", "bus_40"],
        "shift": "evening",
        "status": "on_leave",
        "phone": None,
        "notes": None,
    },
    # --- Night shift (4 drivers) ---
    {
        "driver_id": "DRV-017",
        "name": "U. Grants",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_7", "bus_22", "bus_32"],
        "shift": "night",
        "status": "available",
        "phone": "+371 2610 1017",
        "notes": None,
    },
    {
        "driver_id": "DRV-018",
        "name": "O. Rubenis",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_3", "bus_13", "bus_15", "bus_37", "bus_45", "bus_48"],
        "shift": "night",
        "status": "available",
        "phone": "+371 2610 1018",
        "notes": "senior driver",
    },
    {
        "driver_id": "DRV-019",
        "name": "B. Simanis",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_22", "bus_24", "bus_30", "bus_53"],
        "shift": "night",
        "status": "available",
        "phone": "+371 2610 1019",
        "notes": None,
    },
    {
        "driver_id": "DRV-020",
        "name": "H. Abele",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_40", "bus_45"],
        "shift": "night",
        "status": "sick",
        "phone": None,
        "notes": None,
    },
]

_SHIFT_HOURS: dict[str, str] = {
    "morning": "05:00-13:00",
    "afternoon": "13:00-21:00",
    "evening": "17:00-01:00",
    "night": "22:00-06:00",
}

VALID_SHIFTS: frozenset[str] = frozenset(_SHIFT_HOURS.keys())


async def _query_drivers_from_db(
    db_session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]],
    shift: str | None,
    route_id: str | None,
) -> list[dict[str, str | list[str] | None]]:
    """Query drivers from the database and convert to dict format.

    Args:
        db_session_factory: Factory for creating standalone DB sessions.
        shift: Optional shift filter.
        route_id: Optional route ID filter.

    Returns:
        List of driver dicts matching DriverInfo schema fields.
    """
    from app.drivers.repository import DriverRepository

    async with db_session_factory() as session:
        repo = DriverRepository(session)
        drivers = await repo.list_for_agent(shift=shift, route_id=route_id)

    result: list[dict[str, str | list[str] | None]] = []
    for driver in drivers:
        result.append(
            {
                "driver_id": driver.employee_number,
                "name": f"{driver.first_name[0]}. {driver.last_name}",
                "license_categories": (
                    driver.license_categories.split(",") if driver.license_categories else []
                ),
                "qualified_route_ids": (
                    driver.qualified_route_ids.split(",") if driver.qualified_route_ids else []
                ),
                "shift": driver.default_shift,
                "status": driver.status,
                "phone": driver.phone,
                "notes": driver.notes,
            }
        )
    return result


async def get_driver_availability(
    date_str: str,
    shift: str | None,
    route_id: str | None,
    *,
    db_session_factory: (Callable[[], AbstractAsyncContextManager[AsyncSession]] | None) = None,
) -> list[dict[str, str | list[str] | None]]:
    """Fetch driver availability data for a given date and optional filters.

    Queries the database when db_session_factory is provided. Falls back
    to mock data when the database is unavailable or in test environments.

    Args:
        date_str: ISO date string (YYYY-MM-DD) for the query.
        shift: Filter to a specific shift, or None for all shifts.
        route_id: Filter to drivers qualified for this route, or None for all.
        db_session_factory: Optional factory for creating standalone DB sessions.

    Returns:
        List of driver dicts matching DriverInfo schema fields.
    """
    # Try database query first
    if db_session_factory is not None:
        try:
            return await _query_drivers_from_db(db_session_factory, shift, route_id)
        except Exception:
            logger.warning(
                "transit.driver_data.db_fallback",
                reason="database_unavailable",
            )

    # Fallback to mock data
    drivers: list[dict[str, str | list[str] | None]] = [dict(d) for d in _FALLBACK_DRIVERS]

    # Date-based variation: 0-2 extra drivers become "sick" deterministically
    extra_sick_count = hash(date_str) % 3
    sick_applied = 0
    for driver in drivers:
        if sick_applied >= extra_sick_count:
            break
        if driver["status"] == "available":
            driver["status"] = "sick"
            driver["phone"] = None
            sick_applied += 1

    # Apply shift filter
    if shift is not None:
        drivers = [d for d in drivers if d["shift"] == shift]

    # Apply route filter
    if route_id is not None:
        drivers = [
            d
            for d in drivers
            if isinstance(d["qualified_route_ids"], list) and route_id in d["qualified_route_ids"]
        ]

    return drivers
