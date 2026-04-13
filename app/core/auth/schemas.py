"""Pydantic schemas for dispatcher assignment CRUD and auth audit queries."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class AssignmentCreate(BaseModel):
    """Create a single dispatcher-to-route assignment."""

    user_id: int
    route_id: int


class AssignmentBulkCreate(BaseModel):
    """Bulk-replace all assignments for a dispatcher."""

    route_ids: list[int]


class AssignmentResponse(BaseModel):
    """Response schema for a dispatcher assignment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    route_id: int
    assigned_by: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime


# --- Auth audit (OPS-4.3) ---

EnforcementLayer = Literal["jwt", "role", "scope", "rate_limit"]


class AuthAuditEventResponse(BaseModel):
    """Single audit event in API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    recorded_at: datetime.datetime
    request_id: str
    user_id: int | None
    path: str
    method: str
    status_code: int
    reason: str
    enforcement_layer: str
    client_ip: str | None
    user_role: str | None
    extra: dict[str, Any] | None
