"""Tests for feature flag gating of the background queue."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import MagicMock, patch

import pytest

from app.memory.lifecycle import start_memory_tasks, stop_memory_tasks


@pytest.mark.asyncio
async def test_queue_disabled_preserves_asyncio_tasks() -> None:
    with patch("app.memory.lifecycle.get_settings") as mock_gs:
        mock_gs.return_value.memory_enabled = True
        mock_gs.return_value.background_queue_enabled = False
        mock_gs.return_value.memory_compaction_cron_hour = 3
        mock_gs.return_value.memory_promotion_cron_hour = 3

        with patch("app.memory.lifecycle.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()
            await start_memory_tasks()

    assert mock_create.call_count == 2
    await stop_memory_tasks()


@pytest.mark.asyncio
async def test_queue_enabled_skips_asyncio_tasks() -> None:
    with patch("app.memory.lifecycle.get_settings") as mock_gs:
        mock_gs.return_value.memory_enabled = True
        mock_gs.return_value.background_queue_enabled = True

        with patch("app.memory.lifecycle.asyncio.create_task") as mock_create:
            await start_memory_tasks()

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_noop_when_disabled() -> None:
    from app.core.jobs.queue import enqueue

    with patch("app.core.jobs.queue.get_settings") as mock_gs:
        mock_gs.return_value.background_queue_enabled = False
        result = await enqueue("run_compaction")

    assert result is None
