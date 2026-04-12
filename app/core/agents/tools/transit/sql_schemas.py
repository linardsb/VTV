"""Response schemas for text-to-sql agent tool (ML-5.4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SchemaExample(BaseModel):
    """A retrieved example query used to guide SQL generation."""

    question: str
    sql: str
    similarity: float = Field(ge=0.0, le=1.0)


class AnalyticsSQLResponse(BaseModel):
    """Response from run_analytics_sql tool."""

    query: str = Field(description="The generated and executed SQL query")
    columns: list[str] = Field(description="Column names in result set")
    rows: list[dict[str, Any]] = Field(description="Result rows (max 100)")
    row_count: int = Field(ge=0, description="Number of rows returned")
    execution_time_ms: int = Field(ge=0)
    examples_used: list[SchemaExample] = Field(
        description="Retrieved schema examples that guided generation"
    )
    truncated: bool = Field(
        default=False, description="True if results were truncated at max_result_rows"
    )
