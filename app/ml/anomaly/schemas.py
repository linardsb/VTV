"""Anomaly detection schemas and types (ML-4.3).

Defines AnomalyEvent (detector output), AnomalyResponse (API response),
and the channel routing matrix.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.alerts.schemas import (
    AlertRuleType,
    AlertSeverityType,
    AlertStatusType,
    SourceEntityType,
)

AnomalyType = Literal["off_route", "stuck_vehicle", "gps_gap", "feed_outage"]
AnomalySeverity = Literal["critical", "high", "medium", "low"]
AnomalyChannel = Literal["dashboard", "slack", "sms", "pager"]

CHANNEL_MATRIX: dict[AnomalyType, list[AnomalyChannel]] = {
    "off_route": ["dashboard", "slack"],
    "stuck_vehicle": ["dashboard", "slack"],
    "gps_gap": ["dashboard"],
    "feed_outage": ["slack", "pager"],
}


@dataclass(frozen=True)
class AnomalyEvent:
    """Detector output - immutable event before routing policy."""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    source_entity_type: SourceEntityType | None
    source_entity_id: str | None
    title: str
    details: dict[str, str | int | float | bool | None]
    detected_at: datetime.datetime


class AnomalyResponse(BaseModel):
    """API response for a single anomaly alert."""

    id: int
    title: str = Field(..., max_length=300)
    severity: AlertSeverityType
    alert_type: AlertRuleType
    source_entity_type: str | None
    source_entity_id: str | None
    details: dict[str, int | float | str | bool | None] | None
    status: AlertStatusType
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
