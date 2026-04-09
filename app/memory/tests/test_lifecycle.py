"""Tests for memory lifecycle background tasks."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.lifecycle import (
    _run_compaction,
    _run_promotion,
    start_memory_tasks,
    stop_memory_tasks,
)


@pytest.mark.asyncio
async def test_start_memory_tasks_creates_tasks_when_enabled() -> None:
    with patch("app.memory.lifecycle.get_settings") as mock_settings:
        mock_settings.return_value.memory_enabled = True
        mock_settings.return_value.memory_compaction_cron_hour = 3
        mock_settings.return_value.memory_promotion_cron_hour = 3

        with patch("app.memory.lifecycle.asyncio.create_task") as mock_create:
            mock_create.return_value = MagicMock()
            await start_memory_tasks()

    assert mock_create.call_count == 2

    # Clean up module state
    await stop_memory_tasks()


@pytest.mark.asyncio
async def test_start_memory_tasks_skips_when_disabled() -> None:
    with patch("app.memory.lifecycle.get_settings") as mock_settings:
        mock_settings.return_value.memory_enabled = False

        with patch("app.memory.lifecycle.asyncio.create_task") as mock_create:
            await start_memory_tasks()

    mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_stop_memory_tasks_cancels_running_tasks() -> None:
    mock_task_1 = AsyncMock()
    mock_task_1.cancel = MagicMock()
    mock_task_2 = AsyncMock()
    mock_task_2.cancel = MagicMock()

    with patch("app.memory.lifecycle.get_settings") as mock_settings:
        mock_settings.return_value.memory_enabled = True
        mock_settings.return_value.memory_compaction_cron_hour = 3
        mock_settings.return_value.memory_promotion_cron_hour = 3

        with patch(
            "app.memory.lifecycle.asyncio.create_task", side_effect=[mock_task_1, mock_task_2]
        ):
            await start_memory_tasks()

    await stop_memory_tasks()

    mock_task_1.cancel.assert_called_once()
    mock_task_2.cancel.assert_called_once()


@pytest.mark.asyncio
async def test_run_compaction_calls_service() -> None:
    mock_service = AsyncMock()
    mock_result = MagicMock()
    mock_result.decayed_deleted = 2
    mock_result.merged = 1
    mock_result.promoted = 0
    mock_service.compact.return_value = mock_result

    with patch("app.memory.lifecycle.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.memory.lifecycle.MemoryService", return_value=mock_service):
            await _run_compaction()

    mock_service.compact.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_promotion_calls_service() -> None:
    mock_service = AsyncMock()
    mock_service.promote_episodes.return_value = 3

    with patch("app.memory.lifecycle.get_db_context") as mock_db_ctx:
        mock_db = AsyncMock()
        mock_db_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("app.memory.lifecycle.MemoryService", return_value=mock_service):
            await _run_promotion()

    mock_service.promote_episodes.assert_awaited_once()
