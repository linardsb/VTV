"""Historical GTFS archive importer for ML training data.

Downloads all available GTFS snapshots from data.gov.lv, deduplicates
via SHA-256, and stores each in snapshot-scoped shadow tables. Designed
for CLI usage via scripts/backfill_gtfs_history.py.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import re

import httpx

from app.core.config import Settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.schedules.gtfs_import import GTFSImporter
from app.transit import snapshot_repository as repo
from app.transit.snapshot_models import GtfsSnapshot
from app.transit.snapshot_schemas import BackfillProgress, SnapshotImportResult, SnapshotMeta

logger = get_logger(__name__)

# Maximum download size for a single GTFS ZIP (50 MB)
_MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024


class HistoricalGtfsImporter:
    """Download and archive historical GTFS snapshots from data.gov.lv.

    Args:
        settings: Application settings with data.gov.lv config.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0),
            follow_redirects=True,
        )

    async def list_available_snapshots(self) -> list[SnapshotMeta]:
        """Fetch the list of available GTFS resources from data.gov.lv.

        Returns:
            Sorted list of snapshot metadata (oldest first).
        """
        url = f"{self._settings.data_gov_lv_base_url}/action/package_show"
        logger.info(
            "transit.historical_importer.list_snapshots_started",
            dataset_id=self._settings.data_gov_lv_dataset_id,
        )
        response = await self._client.get(url, params={"id": self._settings.data_gov_lv_dataset_id})
        response.raise_for_status()
        data = response.json()

        resources: list[dict[str, str]] = data.get("result", {}).get("resources", [])
        snapshots: list[SnapshotMeta] = []

        for res in resources:
            fmt = res.get("format", "").upper()
            if fmt != "ZIP":
                continue

            resource_url = res.get("url", "")
            if not resource_url:
                continue

            snapshot_date = _extract_date(res.get("name", ""), res.get("created", ""))

            snapshots.append(
                SnapshotMeta(
                    resource_id=res.get("id", ""),
                    name=res.get("name", ""),
                    description=res.get("description", ""),
                    url=resource_url,
                    format=fmt,
                    created=res.get("created", ""),
                    last_modified=res.get("last_modified", ""),
                    snapshot_date=snapshot_date,
                )
            )

        snapshots.sort(key=lambda s: s.snapshot_date)
        logger.info(
            "transit.historical_importer.list_snapshots_completed",
            count=len(snapshots),
        )
        return snapshots

    async def download_snapshot(self, url: str) -> bytes:
        """Download a GTFS ZIP with streaming size validation.

        Args:
            url: Direct download URL for the ZIP file.

        Returns:
            Raw ZIP bytes.

        Raises:
            ValueError: If download exceeds size limit.
        """
        logger.info("transit.historical_importer.snapshot_download_started", url=url)
        chunks: list[bytes] = []
        total = 0
        async with self._client.stream("GET", url) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=8192):
                total += len(chunk)
                if total > _MAX_DOWNLOAD_BYTES:
                    msg = f"Download exceeds {_MAX_DOWNLOAD_BYTES} byte limit"
                    raise ValueError(msg)
                chunks.append(chunk)

        data = b"".join(chunks)
        logger.info(
            "transit.historical_importer.snapshot_download_completed",
            size_bytes=len(data),
        )
        return data

    async def import_snapshot(self, meta: SnapshotMeta) -> SnapshotImportResult:
        """Download, validate, parse and store a single snapshot.

        Args:
            meta: Snapshot metadata from list_available_snapshots.

        Returns:
            Import result with counts and skip status.
        """
        async with get_db_context() as db:
            # Check duplicate by resource_id
            existing = await repo.get_snapshot_by_resource_id(db, meta.resource_id)
            if existing is not None:
                logger.info(
                    "transit.historical_importer.snapshot_skipped_duplicate",
                    resource_id=meta.resource_id,
                    reason="resource_id",
                )
                return SnapshotImportResult(
                    snapshot_id=existing.id,
                    snapshot_date=meta.snapshot_date,
                    trips_count=0,
                    stop_times_count=0,
                    calendars_count=0,
                    skipped=True,
                )

            # Download
            zip_data = await self.download_snapshot(meta.url)
            sha256 = hashlib.sha256(zip_data).hexdigest()

            # Check duplicate by content hash
            existing_hash = await repo.get_snapshot_by_sha256(db, sha256)
            if existing_hash is not None:
                logger.info(
                    "transit.historical_importer.snapshot_skipped_duplicate",
                    resource_id=meta.resource_id,
                    reason="sha256",
                )
                return SnapshotImportResult(
                    snapshot_id=existing_hash.id,
                    snapshot_date=meta.snapshot_date,
                    trips_count=0,
                    stop_times_count=0,
                    calendars_count=0,
                    skipped=True,
                )

            # Create snapshot record
            snapshot = GtfsSnapshot(
                feed_name="riga",
                snapshot_date=meta.snapshot_date,
                resource_id=meta.resource_id,
                sha256=sha256,
                status="pending",
            )
            snapshot = await repo.create_snapshot(db, snapshot)

            # Parse using existing GTFSImporter (reuses ZIP bomb protection)
            importer = GTFSImporter(zip_data, feed_id="riga")
            parse_result = importer.parse(stop_map={})

            # Map parsed entities to shadow table dicts
            trip_rows: list[dict[str, object]] = [
                {
                    "gtfs_trip_id": t.gtfs_trip_id,
                    "gtfs_route_id": parse_result.trip_route_refs[i].gtfs_route_id
                    if i < len(parse_result.trip_route_refs)
                    else "",
                    "gtfs_service_id": parse_result.trip_calendar_refs[i].gtfs_service_id
                    if i < len(parse_result.trip_calendar_refs)
                    else "",
                    "direction_id": t.direction_id,
                    "trip_headsign": t.trip_headsign,
                    "shape_id": t.shape_id,
                }
                for i, t in enumerate(parse_result.trips)
            ]

            stop_time_rows: list[dict[str, object]] = [
                {
                    "gtfs_trip_id": parse_result.stop_time_trip_refs[i].gtfs_trip_id
                    if i < len(parse_result.stop_time_trip_refs)
                    else "",
                    "gtfs_stop_id": st.stop_id if isinstance(st.stop_id, str) else str(st.stop_id),
                    "stop_sequence": st.stop_sequence,
                    "arrival_time": st.arrival_time,
                    "departure_time": st.departure_time,
                }
                for i, st in enumerate(parse_result.stop_times)
            ]

            calendar_rows: list[dict[str, object]] = [
                {
                    "gtfs_service_id": c.gtfs_service_id,
                    "monday": c.monday,
                    "tuesday": c.tuesday,
                    "wednesday": c.wednesday,
                    "thursday": c.thursday,
                    "friday": c.friday,
                    "saturday": c.saturday,
                    "sunday": c.sunday,
                    "start_date": c.start_date,
                    "end_date": c.end_date,
                }
                for c in parse_result.calendars
            ]

            # Bulk insert
            if trip_rows:
                await repo.bulk_insert_snapshot_trips(db, snapshot.id, trip_rows)
            if stop_time_rows:
                await repo.bulk_insert_snapshot_stop_times(db, snapshot.id, stop_time_rows)
            if calendar_rows:
                await repo.bulk_insert_snapshot_calendars(db, snapshot.id, calendar_rows)

            # Update status
            row_counts = {
                "trips": len(trip_rows),
                "stop_times": len(stop_time_rows),
                "calendars": len(calendar_rows),
            }
            try:
                await repo.update_snapshot_status(db, snapshot.id, "complete", row_counts)
            except Exception:
                logger.exception(
                    "transit.historical_importer.status_update_failed",
                    snapshot_id=snapshot.id,
                )

            await db.commit()

            logger.info(
                "transit.historical_importer.snapshot_import_completed",
                resource_id=meta.resource_id,
                snapshot_date=str(meta.snapshot_date),
                trips=len(trip_rows),
                stop_times=len(stop_time_rows),
                calendars=len(calendar_rows),
            )

            return SnapshotImportResult(
                snapshot_id=snapshot.id,
                snapshot_date=meta.snapshot_date,
                trips_count=len(trip_rows),
                stop_times_count=len(stop_time_rows),
                calendars_count=len(calendar_rows),
                skipped=False,
            )

    async def backfill(
        self,
        since_date: datetime.date | None = None,
        until_date: datetime.date | None = None,
        dry_run: bool = False,
    ) -> BackfillProgress:
        """Run the full backfill pipeline.

        Args:
            since_date: Only import snapshots on or after this date.
            until_date: Only import snapshots on or before this date.
            dry_run: If True, list and count but do not download/import.

        Returns:
            Progress summary.
        """
        logger.info(
            "transit.historical_importer.backfill_started",
            since_date=str(since_date) if since_date else None,
            until_date=str(until_date) if until_date else None,
            dry_run=dry_run,
        )

        snapshots = await self.list_available_snapshots()

        # Filter by date range
        if since_date is not None:
            snapshots = [s for s in snapshots if s.snapshot_date >= since_date]
        if until_date is not None:
            snapshots = [s for s in snapshots if s.snapshot_date <= until_date]

        progress = BackfillProgress(
            total_available=len(snapshots),
            imported=0,
            skipped_duplicate=0,
            failed=0,
        )

        if dry_run:
            logger.info(
                "transit.historical_importer.backfill_dry_run",
                total=len(snapshots),
            )
            return progress

        # Get already-imported resource IDs for fast skip
        async with get_db_context() as db:
            imported_ids = await repo.get_imported_resource_ids(db)

        for meta in snapshots:
            progress.current_resource_id = meta.resource_id

            if meta.resource_id in imported_ids:
                progress.skipped_duplicate += 1
                logger.info(
                    "transit.historical_importer.snapshot_skipped_duplicate",
                    resource_id=meta.resource_id,
                    reason="already_imported",
                )
                continue

            try:
                result = await self.import_snapshot(meta)
                if result.skipped:
                    progress.skipped_duplicate += 1
                else:
                    progress.imported += 1
            except Exception:
                progress.failed += 1
                logger.exception(
                    "transit.historical_importer.snapshot_import_failed",
                    resource_id=meta.resource_id,
                )

            # Rate limit between downloads
            await asyncio.sleep(self._settings.gtfs_backfill_rate_limit_seconds)

        progress.current_resource_id = None
        logger.info(
            "transit.historical_importer.backfill_completed",
            imported=progress.imported,
            skipped=progress.skipped_duplicate,
            failed=progress.failed,
        )
        return progress

    async def close(self) -> None:
        """Close the HTTP client."""
        try:
            await self._client.aclose()
        except RuntimeError:
            pass


def _extract_date(name: str, created: str) -> datetime.date:
    """Extract a snapshot date from resource name or created timestamp.

    Tries common patterns in data.gov.lv resource names:
    - "GTFS 2024-03" or "2024-03-15"
    - Falls back to the CKAN created timestamp.

    Args:
        name: Resource name string.
        created: CKAN created timestamp (ISO format).

    Returns:
        Best-effort date for the snapshot.
    """
    # Try YYYY-MM-DD pattern
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", name)
    if match:
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Try YYYY-MM pattern (use first of month)
    match = re.search(r"(\d{4})-(\d{2})", name)
    if match:
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), 1)
        except ValueError:
            pass

    # Fall back to created timestamp
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", created)
    if match:
        try:
            return datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Last resort: today
    return datetime.datetime.now(datetime.UTC).date()
