"""Tests for the Arq worker settings and job functions."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, patch

import pytest

from app.core.jobs.worker import (
    WorkerSettings,
    run_compaction,
    run_daily_adherence,
    run_promotion,
    run_rrf_recompute,
)


def test_worker_has_cron_jobs() -> None:
    assert len(WorkerSettings.cron_jobs) == 4


def test_worker_has_functions() -> None:
    assert run_compaction in WorkerSettings.functions
    assert run_promotion in WorkerSettings.functions
    assert run_daily_adherence in WorkerSettings.functions
    assert run_rrf_recompute in WorkerSettings.functions


@pytest.mark.asyncio
async def test_run_compaction_calls_lifecycle() -> None:
    with patch("app.core.jobs.worker._run_compaction", new_callable=AsyncMock) as mock_compact:
        result = await run_compaction({})

    mock_compact.assert_awaited_once()
    assert result == {"status": "completed"}


@pytest.mark.asyncio
async def test_run_promotion_calls_lifecycle() -> None:
    with patch("app.core.jobs.worker._run_promotion", new_callable=AsyncMock) as mock_promote:
        result = await run_promotion({})

    mock_promote.assert_awaited_once()
    assert result == {"status": "completed"}


@pytest.mark.asyncio
async def test_run_compaction_reraises_on_failure() -> None:
    with (
        patch(
            "app.core.jobs.worker._run_compaction",
            new_callable=AsyncMock,
            side_effect=RuntimeError("db down"),
        ),
        pytest.raises(RuntimeError, match="db down"),
    ):
        await run_compaction({})
