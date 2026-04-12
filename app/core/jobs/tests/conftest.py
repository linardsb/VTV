"""Fixtures for job queue tests."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_arq_pool() -> MagicMock:
    """Mock ArqRedis pool with async enqueue_job."""
    pool = MagicMock()
    pool.enqueue_job = AsyncMock()
    pool.all_job_results = AsyncMock(return_value=[])
    pool.aclose = AsyncMock()
    return pool


@pytest.fixture
def mock_settings_queue_enabled() -> MagicMock:
    """Settings mock with background queue enabled."""
    s = MagicMock()
    s.background_queue_enabled = True
    s.redis_url = "redis://:devpassword@localhost:6379/0"
    s.arq_max_jobs = 10
    s.arq_job_timeout_seconds = 3600
    s.arq_retry_count = 3
    s.arq_compaction_interval_hours = 6
    s.arq_promotion_cron_hour = 3
    s.log_level = "INFO"
    return s


@pytest.fixture
def mock_settings_queue_disabled() -> MagicMock:
    """Settings mock with background queue disabled."""
    s = MagicMock()
    s.background_queue_enabled = False
    s.redis_url = "redis://:devpassword@localhost:6379/0"
    s.memory_enabled = True
    s.memory_compaction_cron_hour = 3
    s.memory_promotion_cron_hour = 3
    s.log_level = "INFO"
    return s
