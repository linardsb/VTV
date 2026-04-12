"""Pydantic schemas for GTFS historical snapshot metadata."""

import datetime

from pydantic import BaseModel


class SnapshotMeta(BaseModel):
    """Metadata for a single GTFS resource on data.gov.lv."""

    resource_id: str
    name: str
    description: str
    url: str
    format: str
    created: str
    last_modified: str
    snapshot_date: datetime.date


class SnapshotImportResult(BaseModel):
    """Result of importing a single snapshot."""

    snapshot_id: int
    snapshot_date: datetime.date
    trips_count: int
    stop_times_count: int
    calendars_count: int
    skipped: bool


class BackfillProgress(BaseModel):
    """Overall progress of a backfill run."""

    total_available: int
    imported: int
    skipped_duplicate: int
    failed: int
    current_resource_id: str | None = None
