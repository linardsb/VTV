"""Pydantic response schema for the ETA prediction endpoint (ML-2.3)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ETASource = Literal["model", "fallback"]


class ETAResponse(BaseModel):
    """Predicted arrival time for a vehicle at a specific stop.

    Attributes:
        vehicle_id: Fleet vehicle identifier.
        stop_id: GTFS stop identifier.
        predicted_arrival_at: ISO 8601 UTC predicted arrival, empty if unknown.
        delay_s: Predicted delay in seconds (positive = late).
        confidence_lower_s: 10th percentile delay bound.
        confidence_upper_s: 90th percentile delay bound.
        scheduled_arrival_at: ISO 8601 scheduled arrival if known.
        model_version: Model version used, null if fallback.
        fallback: True if using scheduled time instead of ML prediction.
        source: Whether prediction came from model or fallback.
    """

    model_config = ConfigDict(strict=True)

    vehicle_id: str
    stop_id: str
    predicted_arrival_at: str = Field(description="ISO 8601 UTC predicted arrival")
    delay_s: int = Field(description="Predicted delay in seconds (positive = late)")
    confidence_lower_s: int = Field(description="10th percentile delay bound")
    confidence_upper_s: int = Field(description="90th percentile delay bound")
    scheduled_arrival_at: str | None = Field(
        None, description="ISO 8601 scheduled arrival if known"
    )
    model_version: str | None = Field(None, description="Model version used, null if fallback")
    fallback: bool = Field(
        False, description="True if using scheduled time instead of ML prediction"
    )
    source: ETASource = "model"
