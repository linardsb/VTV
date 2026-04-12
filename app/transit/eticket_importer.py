"""E-ticket validation data pipeline for ML passenger load prediction.

Parses semicolon-delimited TXT files from Rigas Satiksme monthly archives,
validates and batch-inserts into the eticket_validations TimescaleDB hypertable.
Supports resume semantics via the eticket_imports tracking table.
"""

from __future__ import annotations

import dataclasses
import datetime
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from sqlalchemy import select, update

from app.core.config import Settings
from app.core.logging import get_logger
from app.transit.models import EticketImport, EticketValidation

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)

_EXPECTED_FIELD_COUNT = 9


@dataclasses.dataclass(frozen=True, slots=True)
class EticketRecord:
    """A single parsed e-ticket validation record."""

    record_id: str
    depot: str
    transport_type: str
    vehicle_number: str
    route_name: str
    route_code: str
    direction: str
    validation_id: str
    validated_at: datetime.datetime


def parse_eticket_txt(path: Path) -> Iterator[EticketRecord]:
    """Parse a semicolon-delimited e-ticket TXT file.

    Args:
        path: Path to the TXT file (Latin-1 encoded).

    Yields:
        EticketRecord for each valid line. Malformed lines are logged and skipped.
    """
    with path.open(encoding="latin-1") as f:
        # Skip header line
        header = f.readline()
        if not header:
            return

        for line_num, raw_line in enumerate(f, start=2):
            line = raw_line.strip()
            if not line:
                continue

            fields = line.split(";")
            if len(fields) != _EXPECTED_FIELD_COUNT:
                logger.warning(
                    "eticket.parser.line_skipped",
                    line_number=line_num,
                    reason=f"expected {_EXPECTED_FIELD_COUNT} fields, got {len(fields)}",
                )
                continue

            try:
                validated_at = datetime.datetime.strptime(
                    fields[8].strip(),
                    "%Y-%m-%d %H:%M:%S",
                ).replace(tzinfo=datetime.UTC)
            except ValueError:
                logger.warning(
                    "eticket.parser.line_skipped",
                    line_number=line_num,
                    reason=f"invalid datetime: {fields[8]!r}",
                )
                continue

            yield EticketRecord(
                record_id=fields[0].strip(),
                depot=fields[1].strip(),
                transport_type=fields[2].strip(),
                vehicle_number=fields[3].strip(),
                route_name=fields[4].strip(),
                route_code=fields[5].strip(),
                direction=fields[6].strip(),
                validation_id=fields[7].strip(),
                validated_at=validated_at,
            )


def _check_zip_bomb(zf: zipfile.ZipFile, max_size_mb: int) -> None:
    """Raise ValueError if total uncompressed size exceeds the guard limit."""
    total_bytes = sum(info.file_size for info in zf.infolist())
    max_bytes = max_size_mb * 1024 * 1024
    if total_bytes > max_bytes:
        msg = (
            f"Archive uncompressed size {total_bytes / 1024 / 1024:.1f} MB "
            f"exceeds limit of {max_size_mb} MB"
        )
        raise ValueError(msg)


def build_archive_url(base_url: str, month: str) -> str:
    """Build the archive download URL for a given month.

    Args:
        base_url: Base URL from settings (e.g., "https://data.rigassatiksme.lv/eticket/").
        month: Month string in YYYY-MM format.

    Returns:
        Full archive URL.
    """
    return f"{base_url.rstrip('/')}/{month}.zip"


async def import_monthly_archive(
    archive_url: str,
    archive_month: str,
    *,
    db: AsyncSession,
    settings: Settings,
    dry_run: bool = False,
) -> int:
    """Download and import a single monthly e-ticket archive.

    Args:
        archive_url: URL to the ZIP archive.
        archive_month: Month identifier in YYYY-MM format.
        db: Async database session.
        settings: Application settings.
        dry_run: If True, parse and count records without inserting.

    Returns:
        Number of records imported (or counted in dry-run mode).
    """
    # Check for existing completed import
    result = await db.execute(
        select(EticketImport).where(
            EticketImport.archive_month == archive_month,
            EticketImport.status == "completed",
        )
    )
    if result.scalar_one_or_none() is not None:
        logger.info(
            "eticket.importer.archive_skipped",
            archive_month=archive_month,
            reason="already completed",
        )
        return 0

    logger.info(
        "eticket.importer.archive_started",
        archive_month=archive_month,
        archive_url=archive_url,
        dry_run=dry_run,
    )

    tmp_dir = tempfile.mkdtemp(prefix="eticket_")
    try:
        # Download archive with streaming and size guard
        zip_path = Path(tmp_dir) / f"{archive_month}.zip"
        downloaded_bytes = 0
        max_download_bytes = settings.eticket_max_archive_size_mb * 1024 * 1024

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream("GET", archive_url) as response:
                response.raise_for_status()
                with zip_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > max_download_bytes:
                            msg = (
                                f"Download size exceeds "
                                f"{settings.eticket_max_archive_size_mb} MB limit"
                            )
                            raise ValueError(msg)
                        f.write(chunk)

        # Validate ZIP and check for zip bomb
        with zipfile.ZipFile(zip_path, "r") as zf:
            _check_zip_bomb(zf, settings.eticket_max_archive_size_mb)
            zf.extractall(tmp_dir)

        # Create or update tracking row
        if not dry_run:
            existing = await db.execute(
                select(EticketImport).where(
                    EticketImport.archive_month == archive_month,
                )
            )
            tracking_row = existing.scalar_one_or_none()
            if tracking_row is None:
                tracking_row = EticketImport(
                    archive_month=archive_month,
                    status="in_progress",
                )
                db.add(tracking_row)
                await db.flush()
            else:
                await db.execute(
                    update(EticketImport)
                    .where(EticketImport.archive_month == archive_month)
                    .values(status="in_progress")
                )

        # Parse and insert records
        total_records = 0
        batch: list[EticketValidation] = []

        txt_files = sorted(Path(tmp_dir).glob("*.txt"))
        for txt_path in txt_files:
            if txt_path.name.endswith(".zip"):
                continue
            for record in parse_eticket_txt(txt_path):
                if dry_run:
                    total_records += 1
                    continue

                batch.append(
                    EticketValidation(
                        record_id=record.record_id,
                        depot=record.depot,
                        transport_type=record.transport_type,
                        vehicle_number=record.vehicle_number,
                        route_name=record.route_name,
                        route_code=record.route_code,
                        direction=record.direction,
                        validation_id=record.validation_id,
                        validated_at=record.validated_at,
                    )
                )
                if len(batch) >= settings.eticket_batch_size:
                    db.add_all(batch)
                    await db.flush()
                    total_records += len(batch)
                    batch = []

        # Flush remaining batch
        if batch and not dry_run:
            db.add_all(batch)
            await db.flush()
            total_records += len(batch)

        # Mark completed
        if not dry_run:
            await db.execute(
                update(EticketImport)
                .where(EticketImport.archive_month == archive_month)
                .values(status="completed", record_count=total_records)
            )
            await db.commit()

        logger.info(
            "eticket.importer.archive_completed",
            archive_month=archive_month,
            record_count=total_records,
            dry_run=dry_run,
        )
        return total_records

    except Exception:
        # Mark failed in tracking table
        if not dry_run:
            try:
                await db.rollback()
                await db.execute(
                    update(EticketImport)
                    .where(EticketImport.archive_month == archive_month)
                    .values(status="failed")
                )
                await db.commit()
            except Exception:
                logger.exception("eticket.importer.tracking_update_failed")
        logger.exception(
            "eticket.importer.archive_failed",
            archive_month=archive_month,
        )
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def backfill_all(
    *,
    db: AsyncSession,
    settings: Settings,
    dry_run: bool = False,
) -> int:
    """Backfill all monthly archives from 2018-01 to current month.

    Args:
        db: Async database session.
        settings: Application settings.
        dry_run: If True, parse and count records without inserting.

    Returns:
        Total number of records imported across all months.
    """
    now = datetime.datetime.now(tz=datetime.UTC)
    months: list[str] = []
    year, month = 2018, 1
    while (year, month) <= (now.year, now.month):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1

    # Query completed months to skip
    result = await db.execute(
        select(EticketImport.archive_month).where(
            EticketImport.status == "completed",
        )
    )
    completed = {row[0] for row in result.all()}

    remaining = [m for m in months if m not in completed]
    logger.info(
        "eticket.backfill.started",
        total_months=len(months),
        completed_months=len(completed),
        remaining_months=len(remaining),
        dry_run=dry_run,
    )

    total_records = 0
    for archive_month in remaining:
        url = build_archive_url(settings.eticket_archive_base_url, archive_month)
        count = await import_monthly_archive(
            url,
            archive_month,
            db=db,
            settings=settings,
            dry_run=dry_run,
        )
        total_records += count

    logger.info(
        "eticket.backfill.completed",
        total_records=total_records,
        months_processed=len(remaining),
    )
    return total_records
