# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false
"""Load prediction inference service with in-memory model caching (ML-3.3).

Singleton service that loads the production LightGBM load model from the
model registry, caches it in-process, and provides predict() for both
the crowding evaluator and the agent tool.

Fallback: if the model is unavailable or feature extraction fails, returns
a fallback result with ``fallback: true``.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agents.tools.transit.static_cache import StopTimeEntry
from app.core.agents.tools.transit.static_store import GTFSStaticStore, get_static_store
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.models.load_gbm import LoadModel
from app.ml.models.schemas import LoadPrediction
from app.ml.registry import ModelRegistry

logger = get_logger(__name__)

_MODEL_NAME = "load_gbm"


class LoadPredictionService:
    """In-process load prediction inference with model caching and hot-reload.

    Args:
        settings: Application settings.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry = ModelRegistry()
        self._model: LoadModel | None = None
        self._model_version: int | None = None
        self._last_reload_check: float = 0.0

    def _maybe_reload(self) -> None:
        """Check if a newer production model is available and reload if so."""
        now = time.monotonic()
        if now - self._last_reload_check < self._settings.eta_model_reload_interval_seconds:
            return
        self._last_reload_check = now

        try:
            result = self._registry.get_production(_MODEL_NAME)
            if result is None:
                return
            model, metadata = result
            if metadata.version != self._model_version:
                self._model = model
                self._model_version = metadata.version
                logger.info(
                    "ml.load_service.reload_completed",
                    version=metadata.version,
                )
        except Exception:
            logger.warning("ml.load_service.reload_failed", exc_info=True)

    def _ensure_model_loaded(self) -> bool:
        """Lazy-load the production model on first call.

        Returns:
            True if model is available, False otherwise.
        """
        if self._model is not None:
            self._maybe_reload()
            return True

        try:
            result = self._registry.get_production(_MODEL_NAME)
            if result is None:
                result = self._registry.load_latest(_MODEL_NAME)
            model, metadata = result
            self._model = model
            self._model_version = metadata.version
            self._last_reload_check = time.monotonic()
            logger.info(
                "ml.load_service.model_loaded",
                version=metadata.version,
            )
            return True
        except Exception:
            logger.warning("ml.load_service.model_load_failed", exc_info=True)
            return False

    async def predict(
        self,
        db: AsyncSession,
        vehicle_id: str,
        stop_id: str,
    ) -> dict[str, Any]:
        """Predict passenger load for a vehicle at a stop.

        Resolves vehicle_id to its current trip, extracts features from
        available data, and runs inference. Falls back gracefully if any
        step fails.

        Args:
            db: Async database session.
            vehicle_id: Fleet vehicle identifier (GTFS vehicle_id string).
            stop_id: GTFS stop identifier string.

        Returns:
            Dict with prediction fields: predicted_passenger_count,
            crowding_bucket, confidence_lower, confidence_upper, fallback.
        """
        logger.info(
            "ml.load_service.predict_started",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
        )

        # Step 1: Resolve vehicle_id -> latest trip_id
        try:
            gtfs_trip_id = await self._resolve_trip_id(db, vehicle_id)
        except Exception:
            logger.warning(
                "ml.load_service.resolve_trip_failed",
                vehicle_id=vehicle_id,
                exc_info=True,
            )
            return self._fallback_result(vehicle_id, stop_id, reason="resolve_trip_failed")
        if gtfs_trip_id is None:
            return self._fallback_result(vehicle_id, stop_id, reason="vehicle_not_tracked")

        # Step 2: Resolve stop_sequence from GTFS static data
        static = await self._get_static_store()
        stop_sequence = self._resolve_stop_sequence(static, gtfs_trip_id, stop_id)
        if stop_sequence is None:
            return self._fallback_result(vehicle_id, stop_id, reason="stop_not_in_trip")

        # Step 3: Resolve route info for features
        route_info = await self._resolve_route_info(db, gtfs_trip_id)
        if route_info is None:
            return self._fallback_result(vehicle_id, stop_id, reason="route_not_found")

        # Step 4: Resolve vehicle capacity
        capacity = await self._resolve_capacity(db, vehicle_id)

        # Step 5: Ensure model is loaded
        if not self._ensure_model_loaded() or self._model is None:
            return self._fallback_result(vehicle_id, stop_id, reason="model_unavailable")

        # Step 6: Build feature dict and predict
        try:
            now = datetime.now(tz=UTC)
            feature_dict: dict[str, Any] = {
                "route_code": route_info["route_code"],
                "transport_type": route_info["transport_type"],
                "hour": now.hour,
                "stop_sequence": stop_sequence,
                "tap_count": 0,  # not available in real-time
                "capacity": capacity,
                "load_factor_pct": 0.0,  # not available in real-time
            }
            prediction: LoadPrediction = self._model.predict(feature_dict)
        except Exception:
            logger.warning(
                "ml.load_service.prediction_failed",
                vehicle_id=vehicle_id,
                stop_id=stop_id,
                exc_info=True,
            )
            return self._fallback_result(vehicle_id, stop_id, reason="prediction_failed")

        logger.info(
            "ml.load_service.predict_completed",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            crowding_bucket=prediction.crowding_bucket,
            model_version=self._model_version,
        )

        return {
            "vehicle_id": vehicle_id,
            "stop_id": stop_id,
            "predicted_passenger_count": round(prediction.predicted_passenger_count),
            "confidence_lower": round(prediction.confidence_lower),
            "confidence_upper": round(prediction.confidence_upper),
            "crowding_bucket": prediction.crowding_bucket,
            "load_factor_pct": None,
            "model_version": str(self._model_version),
            "fallback": False,
        }

    async def _resolve_trip_id(self, db: AsyncSession, vehicle_id: str) -> str | None:
        """Look up the most recent trip_id for a vehicle from vehicle_positions."""
        result = await db.execute(
            text(
                "SELECT trip_id FROM vehicle_positions "
                "WHERE vehicle_id = :vehicle_id AND trip_id IS NOT NULL "
                "ORDER BY recorded_at DESC LIMIT 1"
            ),
            {"vehicle_id": vehicle_id},
        )
        row = result.first()
        return str(row[0]) if row else None

    async def _get_static_store(self) -> GTFSStaticStore | None:
        """Get the GTFS static store, fail-open to None."""
        try:
            from app.core.database import get_db_context

            return await get_static_store(get_db_context, self._settings)
        except Exception:
            logger.warning("ml.load_service.static_store_unavailable", exc_info=True)
            return None

    def _resolve_stop_sequence(
        self,
        static: GTFSStaticStore | None,
        gtfs_trip_id: str,
        stop_id: str,
    ) -> int | None:
        """Find stop_sequence for a stop within a trip using static GTFS data."""
        if static is None:
            return None
        stop_times: list[StopTimeEntry] = static.trip_stop_times.get(gtfs_trip_id, [])
        for st in stop_times:
            if st.stop_id == stop_id:
                return st.stop_sequence
        return None

    async def _resolve_route_info(
        self,
        db: AsyncSession,
        gtfs_trip_id: str,
    ) -> dict[str, str] | None:
        """Resolve route_code and transport_type from a trip_id."""
        result = await db.execute(
            text(
                "SELECT r.route_short_name, r.route_type "
                "FROM trips t JOIN routes r ON t.route_id = r.id "
                "WHERE t.gtfs_trip_id = :trip_id LIMIT 1"
            ),
            {"trip_id": gtfs_trip_id},
        )
        row = result.first()
        if row is None:
            return None
        route_type_int = int(row[1])
        transport_map = {0: "tram", 3: "bus", 11: "trolleybus"}
        return {
            "route_code": str(row[0]),
            "transport_type": transport_map.get(route_type_int, "bus"),
        }

    async def _resolve_capacity(self, db: AsyncSession, vehicle_id: str) -> int:
        """Resolve vehicle capacity, defaulting to 100 if unknown."""
        result = await db.execute(
            text("SELECT capacity FROM vehicles WHERE fleet_number = :vehicle_id LIMIT 1"),
            {"vehicle_id": vehicle_id},
        )
        row = result.first()
        if row is not None and row[0] is not None:
            return int(row[0])
        return 100  # default bus capacity

    def _fallback_result(
        self,
        vehicle_id: str,
        stop_id: str,
        *,
        reason: str,
    ) -> dict[str, Any]:
        """Build a fallback prediction result."""
        logger.info(
            "ml.load_service.fallback_used",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            reason=reason,
        )
        return {
            "vehicle_id": vehicle_id,
            "stop_id": stop_id,
            "predicted_passenger_count": None,
            "confidence_lower": None,
            "confidence_upper": None,
            "crowding_bucket": None,
            "load_factor_pct": None,
            "model_version": None,
            "fallback": True,
        }


# --- Module-level singleton ---

_load_service: LoadPredictionService | None = None


def get_load_service(settings: Settings | None = None) -> LoadPredictionService:
    """Get or create the load prediction service singleton.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Singleton LoadPredictionService instance.
    """
    global _load_service
    if _load_service is None:
        if settings is None:
            settings = get_settings()
        _load_service = LoadPredictionService(settings)
    return _load_service


def reset_load_service() -> None:
    """Reset the singleton for testing."""
    global _load_service
    _load_service = None
