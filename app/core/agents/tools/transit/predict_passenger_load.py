"""Transit tool: predict_passenger_load (ML-3.3).

Provides ML-based passenger load predictions for vehicles at stops,
consumed by dispatchers via the agent chat interface.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger
from app.ml.load_service import get_load_service

logger = get_logger(__name__)


async def predict_passenger_load(
    ctx: RunContext[UnifiedDeps],
    vehicle_id: str,
    stop_id: str,
) -> str:
    """Predict how crowded a vehicle will be at a specific stop.

    WHEN TO USE: Dispatcher asks "how full is bus X?", "will route 22
    be crowded?", "cik pilns bus autobuss?", or "vai bus parparildota?".
    Returns ML-predicted passenger count and crowding level (empty, light,
    moderate, full, overcrowded).

    WHEN NOT TO USE: For current vehicle position or delay (use
    query_bus_status with action='status'). For arrival time prediction
    (use predict_eta).

    COMPOSITION: Use search_stops first to resolve a stop name to stop_id,
    then pass the stop_id here. Use query_bus_status(action='status') to
    get the vehicle_id if the dispatcher only mentions a route number.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        vehicle_id: Fleet vehicle identifier (e.g., "4521", "22-47").
        stop_id: GTFS stop identifier (e.g., "a0072"). Use search_stops
            to find the stop_id from a stop name.

    Returns:
        JSON string with load prediction including predicted_passenger_count,
        crowding_bucket, confidence interval, and whether fallback was used.
        On error, returns an actionable error message string.
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "agent.predict_passenger_load.started",
        vehicle_id=vehicle_id,
        stop_id=stop_id,
    )

    if ctx.deps.db_session_factory is None:
        return "Database session not available. Load prediction requires database access."

    try:
        async with ctx.deps.db_session_factory() as db:
            load_service = get_load_service(_settings)
            result: dict[str, Any] = await load_service.predict(db, vehicle_id, stop_id)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "agent.predict_passenger_load.completed",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            fallback=result.get("fallback", False),
            duration_ms=duration_ms,
        )
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "agent.predict_passenger_load.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"Load prediction error: {e}. "
            "The prediction service may be temporarily unavailable. "
            "Try query_bus_status(action='status') for current vehicle info instead."
        )
