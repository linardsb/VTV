"""Tests for job result persistence."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, patch

import pytest

from app.core.jobs.worker import run_compaction, run_promotion


@pytest.mark.asyncio
async def test_compaction_result_has_status() -> None:
    with patch("app.core.jobs.worker._run_compaction", new_callable=AsyncMock):
        result = await run_compaction({})

    assert "status" in result
    assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_promotion_result_has_status() -> None:
    with patch("app.core.jobs.worker._run_promotion", new_callable=AsyncMock):
        result = await run_promotion({})

    assert "status" in result
    assert result["status"] == "completed"
