# pyright: reportUnknownVariableType=false
"""Pydantic schemas for agent skills feature."""

import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TOKEN_BUDGET_CHARS = 8000
"""Maximum characters injected into agent prompt (~2000 tokens)."""

CategoryType = Literal["transit_ops", "procedures", "glossary", "reporting"]


class SkillBase(BaseModel):
    """Shared skill attributes for create and response schemas."""

    name: str = Field(..., min_length=1, max_length=100, description="Skill name")
    description: str = Field(..., min_length=1, max_length=500, description="Short description")
    content: str = Field(..., min_length=1, max_length=10000, description="Skill content")
    category: CategoryType = Field(default="transit_ops", description="Skill category")
    is_active: bool = Field(default=True, description="Whether skill is active")
    priority: int = Field(
        default=0, ge=0, le=100, description="Priority (0-100, higher = loaded first)"
    )


class SkillCreate(SkillBase):
    """Schema for creating an agent skill."""


class SkillUpdate(BaseModel):
    """Schema for updating an agent skill. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, min_length=1, max_length=500)
    content: str | None = Field(None, min_length=1, max_length=10000)
    category: CategoryType | None = Field(None)
    is_active: bool | None = None
    priority: int | None = Field(None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def reject_empty_body(cls, data: Any) -> Any:  # noqa: ANN401
        """Reject PATCH requests with no fields to update."""
        if isinstance(data, dict) and not any(v is not None for v in data.values()):
            msg = "At least one field must be provided"
            raise ValueError(msg)
        return data


class SkillResponse(SkillBase):
    """Schema for skill responses."""

    id: int
    created_by_id: int | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
