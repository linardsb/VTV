"""Pydantic schemas for dispatcher assignment CRUD."""

import datetime

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
