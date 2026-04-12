"""Unit tests for the historical GTFS archive importer."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.transit.historical_gtfs_importer import (
    HistoricalGtfsImporter,
    _extract_date,
)
from app.transit.snapshot_schemas import SnapshotMeta


def _make_settings() -> MagicMock:
    """Create a mock Settings object with data.gov.lv config."""
    settings = MagicMock()
    settings.data_gov_lv_base_url = "https://data.gov.lv/dati/api/3"
    settings.data_gov_lv_dataset_id = "rigas-satiksmes-marsrutu-saraksti-gtfs"
    settings.gtfs_backfill_rate_limit_seconds = 0.0  # no delay in tests
    return settings


def _make_gtfs_zip(**files: str) -> bytes:
    """Create an in-memory GTFS ZIP from CSV strings.

    Args:
        **files: filename_txt -> CSV content. Underscores become dots.

    Returns:
        Raw ZIP bytes.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key, content in files.items():
            filename = key.replace("_txt", ".txt")
            zf.writestr(filename, content)
    return buf.getvalue()


def _make_data_gov_response(resources: list[dict[str, str]]) -> dict[str, object]:
    """Build a data.gov.lv package_show response."""
    return {"result": {"resources": resources}}


def _sample_resource(
    resource_id: str = "res-1",
    name: str = "GTFS 2024-03",
    fmt: str = "ZIP",
    url: str = "https://example.com/gtfs.zip",
) -> dict[str, str]:
    return {
        "id": resource_id,
        "name": name,
        "description": "Test GTFS",
        "url": url,
        "format": fmt,
        "created": "2024-03-01T00:00:00",
        "last_modified": "2024-03-01T00:00:00",
    }


# --- list_available_snapshots ---


@pytest.mark.asyncio
async def test_list_available_snapshots_parses_resources() -> None:
    """Verify that resources are parsed into SnapshotMeta list."""
    importer = HistoricalGtfsImporter(_make_settings())
    response_data = _make_data_gov_response(
        [
            _sample_resource("r1", "GTFS 2024-01"),
            _sample_resource("r2", "GTFS 2024-06"),
        ]
    )

    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(importer._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        snapshots = await importer.list_available_snapshots()

    assert len(snapshots) == 2
    assert snapshots[0].resource_id == "r1"
    assert snapshots[0].snapshot_date == date(2024, 1, 1)
    assert snapshots[1].snapshot_date == date(2024, 6, 1)
    await importer.close()


@pytest.mark.asyncio
async def test_list_available_snapshots_filters_non_zip() -> None:
    """Non-ZIP resources are excluded."""
    importer = HistoricalGtfsImporter(_make_settings())
    response_data = _make_data_gov_response(
        [
            _sample_resource("r1", "GTFS 2024-01", fmt="ZIP"),
            _sample_resource("r2", "Some CSV", fmt="CSV"),
            _sample_resource("r3", "Some PDF", fmt="PDF"),
        ]
    )

    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()

    with patch.object(importer._client, "get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        snapshots = await importer.list_available_snapshots()

    assert len(snapshots) == 1
    assert snapshots[0].resource_id == "r1"
    await importer.close()


# --- duplicate detection ---


@pytest.mark.asyncio
async def test_duplicate_detection_by_resource_id() -> None:
    """Already-imported resource_id is skipped without downloading."""
    importer = HistoricalGtfsImporter(_make_settings())
    meta = SnapshotMeta(
        resource_id="existing-res",
        name="GTFS 2024-03",
        description="",
        url="https://example.com/gtfs.zip",
        format="ZIP",
        created="2024-03-01",
        last_modified="2024-03-01",
        snapshot_date=date(2024, 3, 1),
    )

    mock_existing = MagicMock()
    mock_existing.id = 42

    with (
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_resource_id",
            new_callable=AsyncMock,
            return_value=mock_existing,
        ),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await importer.import_snapshot(meta)

    assert result.skipped is True
    assert result.snapshot_id == 42
    await importer.close()


@pytest.mark.asyncio
async def test_duplicate_detection_by_sha256() -> None:
    """Different resource_id but same content hash is skipped."""
    importer = HistoricalGtfsImporter(_make_settings())
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Test,Europe/Riga\n",
    )
    meta = SnapshotMeta(
        resource_id="new-res",
        name="GTFS 2024-04",
        description="",
        url="https://example.com/gtfs.zip",
        format="ZIP",
        created="2024-04-01",
        last_modified="2024-04-01",
        snapshot_date=date(2024, 4, 1),
    )

    mock_existing_hash = MagicMock()
    mock_existing_hash.id = 99

    with (
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_resource_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_sha256",
            new_callable=AsyncMock,
            return_value=mock_existing_hash,
        ),
        patch.object(importer, "download_snapshot", new_callable=AsyncMock, return_value=zip_data),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await importer.import_snapshot(meta)

    assert result.skipped is True
    assert result.snapshot_id == 99
    await importer.close()


# --- import_snapshot ---


@pytest.mark.asyncio
async def test_import_snapshot_writes_shadow_tables() -> None:
    """Verify bulk insert calls are made with correct data."""
    importer = HistoricalGtfsImporter(_make_settings())
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Test,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\nbus_1,RS,1,Test,3\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nsvc1,1,1,1,1,1,0,0,20240101,20241231\n",
        trips_txt="route_id,service_id,trip_id,direction_id,trip_headsign\nbus_1,svc1,t1,0,Downtown\n",
        stop_times_txt="trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt1,08:00:00,08:01:00,s1,1\n",
        stops_txt="stop_id,stop_name,stop_lat,stop_lon\ns1,Stop 1,56.95,24.10\n",
    )

    meta = SnapshotMeta(
        resource_id="new-res",
        name="GTFS 2024-03",
        description="",
        url="https://example.com/gtfs.zip",
        format="ZIP",
        created="2024-03-01",
        last_modified="2024-03-01",
        snapshot_date=date(2024, 3, 1),
    )

    mock_snapshot = MagicMock()
    mock_snapshot.id = 1

    with (
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_resource_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_sha256",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.create_snapshot",
            new_callable=AsyncMock,
            return_value=mock_snapshot,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_trips",
            new_callable=AsyncMock,
        ) as mock_trips,
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_stop_times",
            new_callable=AsyncMock,
        ) as mock_stop_times,
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_calendars",
            new_callable=AsyncMock,
        ) as mock_calendars,
        patch(
            "app.transit.historical_gtfs_importer.repo.update_snapshot_status",
            new_callable=AsyncMock,
        ),
        patch.object(importer, "download_snapshot", new_callable=AsyncMock, return_value=zip_data),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await importer.import_snapshot(meta)

    assert result.skipped is False
    assert result.trips_count == 1
    assert result.stop_times_count == 1
    assert result.calendars_count == 1
    mock_trips.assert_called_once()
    mock_stop_times.assert_called_once()
    mock_calendars.assert_called_once()
    await importer.close()


@pytest.mark.asyncio
async def test_import_snapshot_maps_gtfs_ids_correctly() -> None:
    """Verify denormalized string IDs in shadow model dicts."""
    importer = HistoricalGtfsImporter(_make_settings())
    zip_data = _make_gtfs_zip(
        agency_txt="agency_id,agency_name,agency_timezone\nRS,Test,Europe/Riga\n",
        routes_txt="route_id,agency_id,route_short_name,route_long_name,route_type\nbus_22,RS,22,Main,3\n",
        calendar_txt="service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\nwd,1,1,1,1,1,0,0,20240101,20241231\n",
        trips_txt="route_id,service_id,trip_id,direction_id,trip_headsign\nbus_22,wd,trip_a,0,North\n",
    )

    meta = SnapshotMeta(
        resource_id="new-res",
        name="GTFS 2024-05",
        description="",
        url="https://example.com/gtfs.zip",
        format="ZIP",
        created="2024-05-01",
        last_modified="2024-05-01",
        snapshot_date=date(2024, 5, 1),
    )

    mock_snapshot = MagicMock()
    mock_snapshot.id = 10
    captured_trips: list[list[dict[str, object]]] = []

    async def capture_trips(db: object, snapshot_id: int, trips: list[dict[str, object]]) -> None:
        captured_trips.append(trips)

    with (
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_resource_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_sha256",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.create_snapshot",
            new_callable=AsyncMock,
            return_value=mock_snapshot,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_trips",
            side_effect=capture_trips,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_stop_times",
            new_callable=AsyncMock,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.bulk_insert_snapshot_calendars",
            new_callable=AsyncMock,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.update_snapshot_status",
            new_callable=AsyncMock,
        ),
        patch.object(importer, "download_snapshot", new_callable=AsyncMock, return_value=zip_data),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await importer.import_snapshot(meta)

    assert len(captured_trips) == 1
    trip = captured_trips[0][0]
    assert trip["gtfs_trip_id"] == "trip_a"
    assert trip["gtfs_route_id"] == "bus_22"
    assert trip["gtfs_service_id"] == "wd"
    await importer.close()


# --- rate limiting ---


@pytest.mark.asyncio
async def test_rate_limiting_between_downloads() -> None:
    """Verify asyncio.sleep is called between snapshots."""
    settings = _make_settings()
    settings.gtfs_backfill_rate_limit_seconds = 0.5
    importer = HistoricalGtfsImporter(settings)

    snapshots = [
        SnapshotMeta(
            resource_id=f"r{i}",
            name=f"GTFS 2024-0{i}",
            description="",
            url=f"https://example.com/gtfs{i}.zip",
            format="ZIP",
            created=f"2024-0{i}-01",
            last_modified=f"2024-0{i}-01",
            snapshot_date=date(2024, i, 1),
        )
        for i in range(1, 3)
    ]

    mock_result = MagicMock()
    mock_result.skipped = False

    with (
        patch.object(
            importer, "list_available_snapshots", new_callable=AsyncMock, return_value=snapshots
        ),
        patch.object(importer, "import_snapshot", new_callable=AsyncMock, return_value=mock_result),
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_imported_resource_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
        patch(
            "app.transit.historical_gtfs_importer.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep,
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        await importer.backfill()

    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(0.5)
    await importer.close()


# --- resumability ---


@pytest.mark.asyncio
async def test_resumability_skips_already_imported() -> None:
    """Snapshots with known resource_ids are skipped in backfill loop."""
    importer = HistoricalGtfsImporter(_make_settings())
    snapshots = [
        SnapshotMeta(
            resource_id="already-done",
            name="GTFS 2024-01",
            description="",
            url="https://example.com/g1.zip",
            format="ZIP",
            created="2024-01-01",
            last_modified="2024-01-01",
            snapshot_date=date(2024, 1, 1),
        ),
        SnapshotMeta(
            resource_id="new-one",
            name="GTFS 2024-02",
            description="",
            url="https://example.com/g2.zip",
            format="ZIP",
            created="2024-02-01",
            last_modified="2024-02-01",
            snapshot_date=date(2024, 2, 1),
        ),
    ]

    mock_result = MagicMock()
    mock_result.skipped = False

    with (
        patch.object(
            importer, "list_available_snapshots", new_callable=AsyncMock, return_value=snapshots
        ),
        patch.object(
            importer, "import_snapshot", new_callable=AsyncMock, return_value=mock_result
        ) as mock_import,
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_imported_resource_ids",
            new_callable=AsyncMock,
            return_value={"already-done"},
        ),
        patch("app.transit.historical_gtfs_importer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        progress = await importer.backfill()

    assert progress.skipped_duplicate == 1
    assert progress.imported == 1
    mock_import.assert_called_once_with(snapshots[1])
    await importer.close()


# --- error handling ---


@pytest.mark.asyncio
async def test_backfill_continues_on_single_failure() -> None:
    """A single failing snapshot does not abort the entire backfill."""
    importer = HistoricalGtfsImporter(_make_settings())
    snapshots = [
        SnapshotMeta(
            resource_id=f"r{i}",
            name=f"GTFS 2024-0{i}",
            description="",
            url=f"https://example.com/g{i}.zip",
            format="ZIP",
            created=f"2024-0{i}-01",
            last_modified=f"2024-0{i}-01",
            snapshot_date=date(2024, i, 1),
        )
        for i in range(1, 4)
    ]

    call_count = 0

    async def import_with_failure(meta: SnapshotMeta) -> MagicMock:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            msg = "connection error"
            raise httpx.ConnectError(msg)
        result = MagicMock()
        result.skipped = False
        return result

    with (
        patch.object(
            importer, "list_available_snapshots", new_callable=AsyncMock, return_value=snapshots
        ),
        patch.object(importer, "import_snapshot", side_effect=import_with_failure),
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_imported_resource_ids",
            new_callable=AsyncMock,
            return_value=set(),
        ),
        patch("app.transit.historical_gtfs_importer.asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        progress = await importer.backfill()

    assert progress.imported == 2
    assert progress.failed == 1
    await importer.close()


@pytest.mark.asyncio
async def test_corrupt_zip_marks_failed() -> None:
    """Invalid ZIP bytes result in failure, not crash."""
    importer = HistoricalGtfsImporter(_make_settings())
    meta = SnapshotMeta(
        resource_id="bad-zip",
        name="GTFS 2024-01",
        description="",
        url="https://example.com/bad.zip",
        format="ZIP",
        created="2024-01-01",
        last_modified="2024-01-01",
        snapshot_date=date(2024, 1, 1),
    )

    mock_snapshot = MagicMock()
    mock_snapshot.id = 5

    with (
        patch("app.transit.historical_gtfs_importer.get_db_context") as mock_ctx,
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_resource_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.get_snapshot_by_sha256",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.transit.historical_gtfs_importer.repo.create_snapshot",
            new_callable=AsyncMock,
            return_value=mock_snapshot,
        ),
        patch.object(
            importer, "download_snapshot", new_callable=AsyncMock, return_value=b"not-a-zip"
        ),
    ):
        mock_session = AsyncMock()
        mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        # Should raise (will be caught by backfill loop)
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            await importer.import_snapshot(meta)

    await importer.close()


# --- dry run ---


@pytest.mark.asyncio
async def test_backfill_dry_run_no_writes() -> None:
    """dry_run=True lists snapshots but does not import."""
    importer = HistoricalGtfsImporter(_make_settings())
    snapshots = [
        SnapshotMeta(
            resource_id="r1",
            name="GTFS 2024-01",
            description="",
            url="https://example.com/g1.zip",
            format="ZIP",
            created="2024-01-01",
            last_modified="2024-01-01",
            snapshot_date=date(2024, 1, 1),
        ),
    ]

    with (
        patch.object(
            importer, "list_available_snapshots", new_callable=AsyncMock, return_value=snapshots
        ),
        patch.object(importer, "import_snapshot", new_callable=AsyncMock) as mock_import,
    ):
        progress = await importer.backfill(dry_run=True)

    assert progress.total_available == 1
    assert progress.imported == 0
    mock_import.assert_not_called()
    await importer.close()


# --- download ---


@pytest.mark.asyncio
async def test_download_respects_size_limit() -> None:
    """Oversized downloads raise ValueError."""
    importer = HistoricalGtfsImporter(_make_settings())

    # Create a mock streaming response that exceeds the limit
    large_chunk = b"x" * (51 * 1024 * 1024)  # 51 MB

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()

    async def fake_aiter_bytes(chunk_size: int = 8192) -> object:
        yield large_chunk

    mock_response.aiter_bytes = fake_aiter_bytes

    with patch.object(importer._client, "stream") as mock_stream:
        mock_stream.return_value.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream.return_value.__aexit__ = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="exceeds"):
            await importer.download_snapshot("https://example.com/large.zip")

    await importer.close()


# --- date extraction ---


def test_extract_date_from_yyyy_mm_dd() -> None:
    """Full date in name is extracted."""
    assert _extract_date("GTFS 2024-03-15 update", "") == date(2024, 3, 15)


def test_extract_date_from_yyyy_mm() -> None:
    """Month-only date defaults to first of month."""
    assert _extract_date("GTFS 2024-03", "") == date(2024, 3, 1)


def test_extract_date_falls_back_to_created() -> None:
    """When name has no date, created timestamp is used."""
    assert _extract_date("some feed", "2024-06-15T10:00:00") == date(2024, 6, 15)
