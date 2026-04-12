"""Response schemas for the admin job status endpoint."""

from __future__ import annotations

import datetime

from pydantic import BaseModel


class JobStatusEntry(BaseModel):
    """Status of a single registered background job."""

    name: str
    last_run: datetime.datetime | None
    next_run: datetime.datetime | None
    last_result: str | None
    failure_count: int
    last_duration_seconds: float | None


class JobStatusResponse(BaseModel):
    """Aggregate status of the durable job queue."""

    queue_enabled: bool
    jobs: list[JobStatusEntry]
