"""Transit tool: predict_eta (ML-2.3).

Provides ML-based ETA predictions for vehicles arriving at stops,
consumed by dispatchers via the agent chat interface.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pydantic_ai import RunContext

from app.core.agents.tools.transit.deps import UnifiedDeps
from app.core.logging import get_logger
from app.ml.eta_service import get_eta_service

logger = get_logger(__name__)


async def predict_eta(
    ctx: RunContext[UnifiedDeps],
    vehicle_id: str,
    stop_id: str,
) -> str:
    """Predict when a specific vehicle will arrive at a specific stop.

    WHEN TO USE: Dispatcher asks "when will bus X reach stop Y?", "what is
    the ETA for vehicle 22-47?", or "kad autobuss ieradīsies pieturā?".
    Returns ML-predicted arrival time with confidence interval.

    WHEN NOT TO USE: For current vehicle position or delay status (use
    query_bus_status with action='status'). For upcoming departures at a
    stop from any route (use query_bus_status with action='stop_departures').

    COMPOSITION: Use search_stops first to resolve a stop name to stop_id,
    then pass the stop_id here. Use query_bus_status(action='status') to
    get the vehicle_id if the dispatcher only mentions a route number.

    Args:
        ctx: Pydantic AI run context with UnifiedDeps.
        vehicle_id: Fleet vehicle identifier (e.g., "4521", "22-47").
        stop_id: GTFS stop identifier (e.g., "a0072"). Use search_stops
            to find the stop_id from a stop name.

    Returns:
        JSON string with ETA prediction including predicted_arrival_at,
        delay_s, confidence interval, and whether fallback was used.
        On error, returns an actionable error message string.
    """
    _settings = ctx.deps.settings
    start_time = time.monotonic()

    logger.info(
        "agent.predict_eta.started",
        vehicle_id=vehicle_id,
        stop_id=stop_id,
    )

    if ctx.deps.db_session_factory is None:
        return "Database session not available. ETA prediction requires database access."

    try:
        async with ctx.deps.db_session_factory() as db:
            eta_service = get_eta_service(_settings)
            result: dict[str, Any] = await eta_service.predict(db, vehicle_id, stop_id)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(
            "agent.predict_eta.completed",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            fallback=result.get("fallback", False),
            duration_ms=duration_ms,
        )
        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "agent.predict_eta.failed",
            exc_info=True,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
        )
        return (
            f"ETA prediction error: {e}. "
            "The prediction service may be temporarily unavailable. "
            "Try query_bus_status(action='status') for current delay info instead."
        )
