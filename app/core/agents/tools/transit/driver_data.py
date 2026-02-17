"""Mock driver availability data provider for Riga's transit system.

This module provides simulated driver data for the check_driver_availability
tool. It will be replaced by a CMS API client (driver_client.py) in Phase 2
when the CMS driver management module is implemented. The async interface
is intentionally identical to the future real client so the tool function
requires no changes when the data source is swapped.
"""

from __future__ import annotations

_MOCK_DRIVERS: list[dict[str, str | list[str] | None]] = [
    # --- Morning shift (6 drivers) ---
    {
        "driver_id": "DRV-001",
        "name": "J. Bērziņš",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_1", "bus_3", "bus_7", "bus_22", "bus_24"],
        "shift": "morning",
        "status": "available",
        "phone": "+371 2610 1001",
        "notes": "senior driver",
    },
    {
        "driver_id": "DRV-002",
        "name": "A. Kalniņa",
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
        "name": "R. Liepiņš",
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
        "name": "E. Vītols",
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
        "name": "K. Krūmiņš",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_7", "bus_22", "bus_24", "bus_32"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1007",
        "notes": None,
    },
    {
        "driver_id": "DRV-008",
        "name": "D. Ozoliņa",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_3", "bus_15", "bus_30", "bus_45", "bus_48", "bus_53"],
        "shift": "afternoon",
        "status": "available",
        "phone": "+371 2610 1008",
        "notes": "senior driver",
    },
    {
        "driver_id": "DRV-009",
        "name": "V. Zariņš",
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
        "name": "N. Lācis",
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
        "name": "G. Celmiņš",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_1", "bus_7", "bus_13", "bus_22"],
        "shift": "evening",
        "status": "available",
        "phone": "+371 2610 1012",
        "notes": None,
    },
    {
        "driver_id": "DRV-013",
        "name": "L. Pētersone",
        "license_categories": ["D", "D1"],
        "qualified_route_ids": ["bus_3", "bus_15", "bus_24", "bus_30", "bus_37"],
        "shift": "evening",
        "status": "available",
        "phone": "+371 2610 1013",
        "notes": None,
    },
    {
        "driver_id": "DRV-014",
        "name": "T. Kalējs",
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
        "name": "Z. Auziņa",
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
        "name": "B. Šīmanis",
        "license_categories": ["D"],
        "qualified_route_ids": ["bus_22", "bus_24", "bus_30", "bus_53"],
        "shift": "night",
        "status": "available",
        "phone": "+371 2610 1019",
        "notes": None,
    },
    {
        "driver_id": "DRV-020",
        "name": "H. Ābele",
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


async def get_driver_availability(
    date_str: str,
    shift: str | None,
    route_id: str | None,
) -> list[dict[str, str | list[str] | None]]:
    """Fetch driver availability data for a given date and optional filters.

    This mock implementation returns simulated data with slight date-based
    variation (deterministic per date for testability). It will be replaced
    by a CMS tRPC API call in Phase 2.

    Args:
        date_str: ISO date string (YYYY-MM-DD) for the query.
        shift: Filter to a specific shift, or None for all shifts.
        route_id: Filter to drivers qualified for this route, or None for all.

    Returns:
        List of driver dicts matching DriverInfo schema fields.
    """
    # Start with a copy of all mock drivers
    drivers: list[dict[str, str | list[str] | None]] = [dict(d) for d in _MOCK_DRIVERS]

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
