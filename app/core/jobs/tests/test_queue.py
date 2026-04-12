"""Tests for the Arq job queue wrapper."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.jobs.queue import _parse_redis_settings, enqueue


def test_parse_redis_settings_full_url() -> None:
    rs = _parse_redis_settings("redis://:secret@myhost:6380/2")
    assert rs.host == "myhost"
    assert rs.port == 6380
    assert rs.password == "secret"
    assert rs.database == 2


def test_parse_redis_settings_defaults() -> None:
    rs = _parse_redis_settings("redis://localhost")
    assert rs.host == "localhost"
    assert rs.port == 6379
    assert rs.database == 0


@pytest.mark.asyncio
async def test_enqueue_calls_pool(mock_arq_pool: MagicMock) -> None:
    mock_job = MagicMock()
    mock_arq_pool.enqueue_job.return_value = mock_job

    with (
        patch("app.core.jobs.queue.get_settings") as mock_gs,
        patch(
            "app.core.jobs.queue.get_arq_pool", new_callable=AsyncMock, return_value=mock_arq_pool
        ),
    ):
        mock_gs.return_value.background_queue_enabled = True
        result = await enqueue("run_compaction", _job_id="test-123")

    mock_arq_pool.enqueue_job.assert_awaited_once_with(
        "run_compaction",
        _defer_until=None,
        _job_id="test-123",
    )
    assert result is mock_job


@pytest.mark.asyncio
async def test_enqueue_returns_job_reference(mock_arq_pool: MagicMock) -> None:
    mock_job = MagicMock()
    mock_job.job_id = "abc-123"
    mock_arq_pool.enqueue_job.return_value = mock_job

    with (
        patch("app.core.jobs.queue.get_settings") as mock_gs,
        patch(
            "app.core.jobs.queue.get_arq_pool", new_callable=AsyncMock, return_value=mock_arq_pool
        ),
    ):
        mock_gs.return_value.background_queue_enabled = True
        result = await enqueue("run_compaction")

    assert result is not None
    assert result.job_id == "abc-123"


@pytest.mark.asyncio
async def test_enqueue_noop_when_disabled() -> None:
    with patch("app.core.jobs.queue.get_settings") as mock_gs:
        mock_gs.return_value.background_queue_enabled = False
        result = await enqueue("run_compaction")

    assert result is None


@pytest.mark.asyncio
async def test_enqueue_with_defer_until(mock_arq_pool: MagicMock) -> None:
    import datetime

    defer_time = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.UTC)
    mock_arq_pool.enqueue_job.return_value = MagicMock()

    with (
        patch("app.core.jobs.queue.get_settings") as mock_gs,
        patch(
            "app.core.jobs.queue.get_arq_pool", new_callable=AsyncMock, return_value=mock_arq_pool
        ),
    ):
        mock_gs.return_value.background_queue_enabled = True
        await enqueue("run_promotion", _defer_until=defer_time)

    mock_arq_pool.enqueue_job.assert_awaited_once_with(
        "run_promotion",
        _defer_until=defer_time,
        _job_id=None,
    )
