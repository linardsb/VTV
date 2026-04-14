"""Shared fixtures for transit tool tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest
import structlog

import app.core.agents.tools.transit.predict_eta as predict_eta_mod
import app.core.agents.tools.transit.predict_passenger_load as predict_load_mod


@pytest.fixture(autouse=True)
def _reset_structlog_proxy_cache() -> Generator[None, None, None]:
    """Reset cached structlog bound loggers so capture_logs() works reliably.

    When setup_logging() is called multiple times (e.g., in test_logging.py),
    each call creates a new processor list via structlog.configure().  Cached
    loggers may still reference an older list, so capture_logs() — which
    mutates the *current* list in-place — misses their events.  Replacing
    module loggers with fresh proxies ensures they pick up the current
    processor chain.
    """
    yield
    # Restore fresh proxies after each test so no stale cache leaks forward.
    predict_eta_mod.logger = structlog.get_logger(predict_eta_mod.__name__)
    predict_load_mod.logger = structlog.get_logger(predict_load_mod.__name__)
