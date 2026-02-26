# pyright: reportUnknownVariableType=false
"""Pydantic schemas for operational events feature."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

VALID_PRIORITIES = ("high", "medium", "low")
VALID_CATEGORIES = ("maintenance", "route-change", "driver-shift", "service-alert")

PriorityType = Literal["high", "medium", "low"]
CategoryType = Literal["maintenance", "route-change", "driver-shift", "service-alert"]
TransportType = Literal["bus", "trolleybus", "tram"]
GoalItemType = Literal["route", "training", "note", "checklist"]


class GoalItem(BaseModel):
    """A single goal or checklist item within an event's goals."""

    text: str = Field(..., min_length=1, max_length=500, description="Goal description text")
    completed: bool = Field(default=False, description="Whether this goal item is completed")
    item_type: GoalItemType = Field(..., description="Goal type: route/training/note/checklist")


class EventGoals(BaseModel):
    """Structured goals attached to a driver scheduling event."""

    items: list[GoalItem] = Field(
        default_factory=list, max_length=100, description="List of goal/checklist items"
    )
    route_id: int | None = Field(
        None, description="Assigned route ID from driver's qualified routes"
    )
    transport_type: TransportType | None = Field(
        None, description="Assigned transport: bus/trolleybus/tram"
    )
    vehicle_id: str | None = Field(
        None, max_length=50, description="Optional specific vehicle number"
    )


class EventBase(BaseModel):
    """Shared event attributes for create and response schemas."""

    title: str = Field(..., min_length=1, max_length=200, description="Event title")
    description: str | None = Field(None, description="Event description")
    start_datetime: datetime.datetime = Field(..., description="Event start (UTC)")
    end_datetime: datetime.datetime = Field(..., description="Event end (UTC)")
    priority: PriorityType = Field(default="medium", description="Priority: high/medium/low")
    category: CategoryType = Field(
        default="maintenance",
        description="Category: maintenance/route-change/driver-shift/service-alert",
    )
    goals: EventGoals | None = Field(None, description="Structured goals for driver scheduling")
    driver_id: int | None = Field(None, description="Associated driver ID from drivers table")


class EventCreate(EventBase):
    """Schema for creating an operational event."""


class EventUpdate(BaseModel):
    """Schema for updating an operational event. All fields optional."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    start_datetime: datetime.datetime | None = None
    end_datetime: datetime.datetime | None = None
    priority: PriorityType | None = Field(None)
    category: CategoryType | None = Field(None)
    goals: EventGoals | None = None
    driver_id: int | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields to update."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data


class EventResponse(EventBase):
    """Schema for event responses."""

    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
