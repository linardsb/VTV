# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeStubs=false
"""ETA inference service with in-memory model caching (ML-2.3).

Singleton service that loads the production LightGBM ETA model from the
model registry, caches it in-process, and provides predict() for both
the REST endpoint and the agent tool.

Fallback: if the model is unavailable or feature extraction fails, returns
the scheduled arrival time with ``fallback: true``.
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
from app.ml.features.eta_features import ETAFeatures, extract_features
from app.ml.models.eta_gbm import ETAModel
from app.ml.models.schemas import ETAPrediction
from app.ml.registry import ModelRegistry

logger = get_logger(__name__)

_MODEL_NAME = "eta_gbm"


def _apply_delay(gtfs_time: str, delay_seconds: float) -> str:
    """Add delay to a GTFS HH:MM:SS time string.

    Args:
        gtfs_time: GTFS-format time string (e.g. "08:30:00", may exceed 24h).
        delay_seconds: Delay in seconds to add (positive = later).

    Returns:
        Adjusted time string in HH:MM:SS format.
    """
    parts = gtfs_time.strip().split(":")
    total_seconds = int(parts[0]) * 3600
    if len(parts) > 1:
        total_seconds += int(parts[1]) * 60
    if len(parts) > 2:
        total_seconds += int(parts[2])
    total_seconds += round(delay_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class ETAService:
    """In-process ETA inference with model caching and hot-reload.

    Args:
        settings: Application settings.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._registry = ModelRegistry()
        self._model: ETAModel | None = None
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
                    "ml.eta_service.reload_completed",
                    version=metadata.version,
                )
        except Exception:
            logger.warning("ml.eta_service.reload_failed", exc_info=True)

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
                # Try latest if no production pointer set
                result = self._registry.load_latest(_MODEL_NAME)
            model, metadata = result
            self._model = model
            self._model_version = metadata.version
            self._last_reload_check = time.monotonic()
            logger.info(
                "ml.eta_service.model_loaded",
                version=metadata.version,
            )
            return True
        except Exception:
            logger.warning("ml.eta_service.model_load_failed", exc_info=True)
            return False

    async def predict(
        self,
        db: AsyncSession,
        vehicle_id: str,
        stop_id: str,
    ) -> dict[str, Any]:
        """Predict ETA for a vehicle arriving at a stop.

        Resolves vehicle_id to its current trip, extracts ML features, and
        runs inference. Falls back to scheduled arrival time if any step
        fails.

        Args:
            db: Async database session.
            vehicle_id: Fleet vehicle identifier (GTFS vehicle_id string).
            stop_id: GTFS stop identifier string.

        Returns:
            Dict with prediction fields suitable for ETAResponse construction.
        """
        logger.info(
            "ml.eta_service.prediction_started",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
        )

        # Step 1: Resolve vehicle_id -> latest trip_id from vehicle_positions
        try:
            gtfs_trip_id = await self._resolve_trip_id(db, vehicle_id)
        except Exception:
            logger.warning(
                "ml.eta_service.resolve_trip_failed",
                vehicle_id=vehicle_id,
                exc_info=True,
            )
            return self._fallback_result(vehicle_id, stop_id, reason="resolve_trip_failed")
        if gtfs_trip_id is None:
            return self._fallback_result(vehicle_id, stop_id, reason="vehicle_not_tracked")

        # Step 2: Resolve GTFS string trip_id -> integer PK from trips table
        try:
            trip_pk = await self._resolve_trip_pk(db, gtfs_trip_id)
        except Exception:
            logger.warning(
                "ml.eta_service.resolve_trip_pk_failed",
                vehicle_id=vehicle_id,
                exc_info=True,
            )
            return self._fallback_result(vehicle_id, stop_id, reason="resolve_trip_pk_failed")
        if trip_pk is None:
            return self._fallback_result(vehicle_id, stop_id, reason="trip_not_in_db")

        # Step 3: Resolve stop_id -> stop_sequence from GTFS static cache
        static = await self._get_static_store()
        stop_sequence = self._resolve_stop_sequence(static, gtfs_trip_id, stop_id)
        scheduled_arrival = self._get_scheduled_arrival(static, gtfs_trip_id, stop_id)

        if stop_sequence is None:
            return self._fallback_result(
                vehicle_id,
                stop_id,
                reason="stop_not_in_trip",
                scheduled_arrival_at=scheduled_arrival,
            )

        # Step 4: Ensure model is loaded
        if not self._ensure_model_loaded() or self._model is None:
            return self._fallback_result(
                vehicle_id,
                stop_id,
                reason="model_unavailable",
                scheduled_arrival_at=scheduled_arrival,
            )

        # Step 5: Extract features and predict
        try:
            features: ETAFeatures = await extract_features(
                db,
                trip_pk,
                stop_sequence,
                datetime.now(tz=UTC),
            )
            prediction: ETAPrediction = self._model.predict(features)
        except Exception:
            logger.warning(
                "ml.eta_service.feature_extraction_failed",
                vehicle_id=vehicle_id,
                stop_id=stop_id,
                exc_info=True,
            )
            return self._fallback_result(
                vehicle_id,
                stop_id,
                reason="feature_extraction_failed",
                scheduled_arrival_at=scheduled_arrival,
            )

        # Step 6: Compute predicted arrival time (scheduled + predicted delay)
        predicted_arrival_at: str | None = None
        if scheduled_arrival is not None:
            predicted_arrival_at = _apply_delay(scheduled_arrival, prediction.predicted_delay_s)

        logger.info(
            "ml.eta_service.prediction_completed",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            delay_s=prediction.predicted_delay_s,
            model_version=self._model_version,
        )

        return {
            "vehicle_id": vehicle_id,
            "stop_id": stop_id,
            "predicted_arrival_at": predicted_arrival_at or "",
            "delay_s": round(prediction.predicted_delay_s),
            "confidence_lower_s": round(prediction.confidence_lower),
            "confidence_upper_s": round(prediction.confidence_upper),
            "scheduled_arrival_at": scheduled_arrival,
            "model_version": str(self._model_version),
            "fallback": False,
            "source": "model",
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

    async def _resolve_trip_pk(self, db: AsyncSession, gtfs_trip_id: str) -> int | None:
        """Resolve a GTFS trip_id string to the integer PK in the trips table."""
        result = await db.execute(
            text("SELECT id FROM trips WHERE gtfs_trip_id = :gtfs_trip_id LIMIT 1"),
            {"gtfs_trip_id": gtfs_trip_id},
        )
        row = result.first()
        return int(row[0]) if row else None

    async def _get_static_store(self) -> GTFSStaticStore | None:
        """Get the GTFS static store, fail-open to None."""
        try:
            from app.core.database import get_db_context

            return await get_static_store(get_db_context, self._settings)
        except Exception:
            logger.warning("ml.eta_service.static_store_unavailable", exc_info=True)
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

    def _get_scheduled_arrival(
        self,
        static: GTFSStaticStore | None,
        gtfs_trip_id: str,
        stop_id: str,
    ) -> str | None:
        """Get the scheduled arrival time string for a stop within a trip."""
        if static is None:
            return None
        stop_times: list[StopTimeEntry] = static.trip_stop_times.get(gtfs_trip_id, [])
        for st in stop_times:
            if st.stop_id == stop_id:
                return st.arrival_time
        return None

    def _fallback_result(
        self,
        vehicle_id: str,
        stop_id: str,
        *,
        reason: str,
        scheduled_arrival_at: str | None = None,
    ) -> dict[str, Any]:
        """Build a fallback prediction using scheduled time."""
        logger.info(
            "ml.eta_service.fallback_used",
            vehicle_id=vehicle_id,
            stop_id=stop_id,
            reason=reason,
        )
        return {
            "vehicle_id": vehicle_id,
            "stop_id": stop_id,
            "predicted_arrival_at": scheduled_arrival_at or "",
            "delay_s": 0,
            "confidence_lower_s": 0,
            "confidence_upper_s": 0,
            "scheduled_arrival_at": scheduled_arrival_at,
            "model_version": None,
            "fallback": True,
            "source": "fallback",
        }


# --- Module-level singleton ---

_eta_service: ETAService | None = None


def get_eta_service(settings: Settings | None = None) -> ETAService:
    """Get or create the ETA service singleton.

    Args:
        settings: Optional settings override. Uses get_settings() if None.

    Returns:
        Singleton ETAService instance.
    """
    global _eta_service
    if _eta_service is None:
        if settings is None:
            settings = get_settings()
        _eta_service = ETAService(settings)
    return _eta_service


def reset_eta_service() -> None:
    """Reset the singleton for testing."""
    global _eta_service
    _eta_service = None
