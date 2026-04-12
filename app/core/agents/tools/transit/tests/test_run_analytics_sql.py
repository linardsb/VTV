"""Tests for run_analytics_sql agent tool (ML-5.4).

Covers: embedding, retrieval, SQL generation, validation gate,
cost gate, execution, result truncation, feature flag, input validation.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import models

from app.core.agents.tools.transit.run_analytics_sql import run_analytics_sql
from app.core.agents.tools.transit.sql_validator import ValidationResult

models.ALLOW_MODEL_REQUESTS = False

# --- Helpers ---

MOCK_EXAMPLES: list[dict[str, Any]] = [
    {"question": "How many vehicles?", "sql": "SELECT COUNT(*) FROM vehicles", "similarity": 0.95},
    {
        "question": "Average delay?",
        "sql": "SELECT AVG(delay) FROM vehicle_positions",
        "similarity": 0.88,
    },
]


def _make_settings(**overrides: Any) -> MagicMock:
    """Create a mock Settings with ML-5.4 fields."""
    s = MagicMock()
    s.analytics_sql_enabled = True
    s.analytics_sql_statement_timeout_ms = 5000
    s.analytics_sql_max_query_cost = 10000
    s.analytics_sql_max_result_rows = 100
    s.analytics_sql_example_retrieval_k = 5
    s.analytics_sql_readonly_dsn = None
    s.embedding_cache_enabled = False
    s.embedding_provider = "openai"
    s.embedding_model = "text-embedding-3-large"
    s.llm_fast_provider = None
    s.llm_fast_model = None
    s.llm_provider = "test"
    s.llm_model = "test-model"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def _make_ctx(settings: MagicMock | None = None) -> MagicMock:
    """Create a mock RunContext with UnifiedDeps."""
    ctx = MagicMock()
    ctx.deps.settings = settings or _make_settings()

    # Create an async context manager factory for db_session_factory
    mock_db = AsyncMock()

    @asynccontextmanager
    async def db_factory():
        yield mock_db

    ctx.deps.db_session_factory = db_factory
    ctx._mock_db = mock_db
    return ctx


# --- Tests ---


class TestRunAnalyticsSQL:
    """Tests for the run_analytics_sql tool function."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled(self) -> None:
        settings = _make_settings(analytics_sql_enabled=False)
        ctx = _make_ctx(settings)
        result = await run_analytics_sql(ctx, "How many buses?")
        assert "disabled" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_question_rejected(self) -> None:
        ctx = _make_ctx()
        result = await run_analytics_sql(ctx, "")
        assert "1-500 characters" in result

    @pytest.mark.asyncio
    async def test_question_too_long_rejected(self) -> None:
        ctx = _make_ctx()
        result = await run_analytics_sql(ctx, "x" * 501)
        assert "1-500 characters" in result

    @pytest.mark.asyncio
    async def test_whitespace_only_rejected(self) -> None:
        ctx = _make_ctx()
        result = await run_analytics_sql(ctx, "   ")
        assert "1-500 characters" in result

    @pytest.mark.asyncio
    async def test_no_db_session_factory(self) -> None:
        ctx = _make_ctx()
        ctx.deps.db_session_factory = None
        with patch(
            "app.core.agents.tools.transit.run_analytics_sql._embed_question",
            return_value=[0.1] * 1024,
        ):
            result = await run_analytics_sql(ctx, "How many buses?")
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_no_examples_found(self) -> None:
        ctx = _make_ctx()
        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=[],
            ),
        ):
            result = await run_analytics_sql(ctx, "How many buses?")
        assert "seeding" in result.lower()

    @pytest.mark.asyncio
    async def test_validation_rejects_unsafe_sql(self) -> None:
        ctx = _make_ctx()
        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="DROP TABLE vehicles",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(valid=False, error="Blocked keyword: DROP"),
            ),
        ):
            result = await run_analytics_sql(ctx, "How many buses?")
        assert "safety validation" in result.lower()

    @pytest.mark.asyncio
    async def test_cost_gate_rejects_expensive(self) -> None:
        ctx = _make_ctx()
        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="SELECT * FROM vehicles",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(valid=True, sanitized_sql="SELECT * FROM vehicles"),
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.check_query_cost",
                return_value=(False, 50000.0),
            ),
        ):
            result = await run_analytics_sql(ctx, "How many buses?")
        assert "expensive" in result.lower()

    @pytest.mark.asyncio
    async def test_successful_query_execution(self) -> None:
        ctx = _make_ctx()
        mock_db = ctx._mock_db
        # Mock execute for SET LOCAL and the actual query
        mock_result = MagicMock()
        mock_result.keys.return_value = ["count"]
        mock_result.fetchmany.return_value = [(42,)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="SELECT COUNT(*) AS count FROM vehicles",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(
                    valid=True,
                    sanitized_sql="SELECT COUNT(*) AS count FROM vehicles",
                ),
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.check_query_cost",
                return_value=(True, 500.0),
            ),
        ):
            result = await run_analytics_sql(ctx, "How many vehicles?")

        data = json.loads(result)
        assert data["row_count"] == 1
        assert data["columns"] == ["count"]
        assert len(data["examples_used"]) == 2

    @pytest.mark.asyncio
    async def test_result_truncation_at_max_rows(self) -> None:
        ctx = _make_ctx(_make_settings(analytics_sql_max_result_rows=2))
        mock_db = ctx._mock_db
        mock_result = MagicMock()
        mock_result.keys.return_value = ["id"]
        mock_result.fetchmany.return_value = [(1,), (2,)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="SELECT id FROM vehicles",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(valid=True, sanitized_sql="SELECT id FROM vehicles"),
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.check_query_cost",
                return_value=(True, 100.0),
            ),
        ):
            result = await run_analytics_sql(ctx, "List vehicles")

        data = json.loads(result)
        assert data["truncated"] is True

    @pytest.mark.asyncio
    async def test_result_json_serialization(self) -> None:
        ctx = _make_ctx()
        mock_db = ctx._mock_db
        mock_result = MagicMock()
        mock_result.keys.return_value = ["name", "count"]
        mock_result.fetchmany.return_value = [("Route 1", 10)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="SELECT name, count FROM routes",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(
                    valid=True, sanitized_sql="SELECT name, count FROM routes"
                ),
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.check_query_cost",
                return_value=(True, 200.0),
            ),
        ):
            result = await run_analytics_sql(ctx, "Route counts")

        # Must be valid JSON
        data = json.loads(result)
        assert "query" in data
        assert "columns" in data
        assert "rows" in data
        assert "execution_time_ms" in data

    @pytest.mark.asyncio
    async def test_exception_handling(self) -> None:
        ctx = _make_ctx()
        with patch(
            "app.core.agents.tools.transit.run_analytics_sql._embed_question",
            side_effect=RuntimeError("embedding failure"),
        ):
            result = await run_analytics_sql(ctx, "How many buses?")
        assert "RuntimeError" in result
        assert "rephrase" in result.lower()

    @pytest.mark.asyncio
    async def test_examples_used_in_response(self) -> None:
        ctx = _make_ctx()
        mock_db = ctx._mock_db
        mock_result = MagicMock()
        mock_result.keys.return_value = ["n"]
        mock_result.fetchmany.return_value = [(1,)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        with (
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._embed_question",
                return_value=[0.1] * 1024,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._retrieve_examples",
                return_value=MOCK_EXAMPLES,
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql._generate_sql",
                return_value="SELECT 1 AS n",
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.validate_sql",
                return_value=ValidationResult(valid=True, sanitized_sql="SELECT 1 AS n"),
            ),
            patch(
                "app.core.agents.tools.transit.run_analytics_sql.check_query_cost",
                return_value=(True, 50.0),
            ),
        ):
            result = await run_analytics_sql(ctx, "Test query")

        data = json.loads(result)
        assert len(data["examples_used"]) == 2
        assert data["examples_used"][0]["question"] == "How many vehicles?"
        assert data["examples_used"][0]["similarity"] == 0.95
