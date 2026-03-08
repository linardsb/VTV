# pyright: reportUnknownVariableType=false
"""Pydantic schemas for the notification/alerts feature."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AlertSeverityType = Literal["critical", "high", "medium", "low", "info"]
AlertStatusType = Literal["active", "acknowledged", "resolved"]
AlertRuleType = Literal["delay_threshold", "maintenance_due", "registration_expiry", "manual"]
SourceEntityType = Literal["vehicle", "route", "driver"]


class AlertRuleBase(BaseModel):
    """Shared alert rule attributes for create and response schemas."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=1000)
    rule_type: AlertRuleType
    severity: AlertSeverityType = Field(default="medium")
    threshold_config: dict[str, int | float | str | bool] = Field(default_factory=dict)
    enabled: bool = Field(default=True)


class AlertRuleCreate(AlertRuleBase):
    """Schema for creating an alert rule."""


class AlertRuleUpdate(BaseModel):
    """Schema for updating an alert rule. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    rule_type: AlertRuleType | None = None
    severity: AlertSeverityType | None = None
    threshold_config: dict[str, int | float | str | bool] | None = None
    enabled: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields to update."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data


class AlertRuleResponse(AlertRuleBase):
    """Schema for alert rule responses."""

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class AlertInstanceBase(BaseModel):
    """Shared alert instance attributes."""

    title: str = Field(..., min_length=1, max_length=300)
    severity: AlertSeverityType
    alert_type: AlertRuleType
    source_entity_type: SourceEntityType | None = Field(None)
    source_entity_id: str | None = Field(None, max_length=100)
    details: dict[str, int | float | str | bool | None] | None = Field(None)


class AlertInstanceCreate(AlertInstanceBase):
    """Schema for creating an alert instance."""

    rule_id: int | None = Field(None)


class AlertInstanceResponse(AlertInstanceBase):
    """Schema for alert instance responses."""

    id: int
    status: AlertStatusType
    rule_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    acknowledged_at: datetime.datetime | None
    acknowledged_by_id: int | None
    resolved_at: datetime.datetime | None

    model_config = ConfigDict(from_attributes=True)


class AlertAcknowledge(BaseModel):
    """Schema for acknowledging an alert."""

    note: str | None = Field(None, max_length=1000)


class AlertSummaryResponse(BaseModel):
    """Dashboard badge counts for active alerts."""

    total_active: int
    critical: int
    high: int
    medium: int
    low: int
    info: int
