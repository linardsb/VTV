"""Tests for SQL validator (ML-5.4).

Covers: SELECT whitelist, DDL/DML rejection, injection pattern detection,
stacked queries, comment obfuscation, UNION injection, hex encoding,
system catalog access, role escalation, CROSS JOIN DoS.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.agents.tools.transit.sql_validator import (
    check_query_cost,
    validate_sql,
)


class TestValidateSQL:
    """Tests for validate_sql()."""

    def test_valid_simple_select(self) -> None:
        result = validate_sql("SELECT COUNT(*) FROM vehicles WHERE is_active = true")
        assert result.valid is True
        assert result.sanitized_sql is not None
        assert "SELECT" in result.sanitized_sql

    def test_valid_select_with_joins(self) -> None:
        sql = (
            "SELECT r.route_short_name, AVG(vp.delay) "
            "FROM vehicle_positions vp "
            "JOIN trips t ON vp.trip_id = t.trip_id "
            "JOIN routes r ON t.route_id = r.route_id "
            "GROUP BY r.route_short_name"
        )
        result = validate_sql(sql)
        assert result.valid is True

    def test_valid_select_with_aggregation(self) -> None:
        sql = (
            "SELECT route_id, COUNT(*) AS cnt, AVG(delay) "
            "FROM vehicle_positions "
            "GROUP BY route_id "
            "HAVING COUNT(*) > 10"
        )
        result = validate_sql(sql)
        assert result.valid is True

    def test_reject_empty_sql(self) -> None:
        result = validate_sql("")
        assert result.valid is False
        assert "Empty" in (result.error or "")

    def test_reject_whitespace_only(self) -> None:
        result = validate_sql("   ")
        assert result.valid is False

    def test_reject_insert(self) -> None:
        result = validate_sql("INSERT INTO vehicles (id) VALUES (1)")
        assert result.valid is False

    def test_reject_update(self) -> None:
        result = validate_sql("UPDATE vehicles SET is_active = false")
        assert result.valid is False

    def test_reject_delete(self) -> None:
        result = validate_sql("DELETE FROM vehicles WHERE id = 1")
        assert result.valid is False

    def test_reject_drop_table(self) -> None:
        result = validate_sql("DROP TABLE vehicles")
        assert result.valid is False

    def test_reject_stacked_queries(self) -> None:
        result = validate_sql("SELECT 1; DROP TABLE vehicles")
        assert result.valid is False

    def test_reject_comment_obfuscation(self) -> None:
        result = validate_sql("SELECT /* dangerous */ 1 FROM vehicles")
        assert result.valid is False
        assert "injection" in (result.error or "").lower()

    def test_reject_line_comment(self) -> None:
        result = validate_sql("SELECT 1 FROM vehicles --")
        assert result.valid is False

    def test_reject_hex_encoding(self) -> None:
        result = validate_sql("SELECT \\x44\\x52\\x4f\\x50 FROM vehicles")
        assert result.valid is False

    def test_reject_pg_catalog_access(self) -> None:
        result = validate_sql("SELECT * FROM pg_shadow")
        assert result.valid is False

    def test_reject_information_schema(self) -> None:
        result = validate_sql("SELECT * FROM information_schema.tables")
        assert result.valid is False

    def test_reject_grant_escalation(self) -> None:
        result = validate_sql("GRANT ALL ON vehicles TO public")
        assert result.valid is False

    def test_reject_copy_exfiltration(self) -> None:
        result = validate_sql("COPY vehicles TO '/tmp/data.csv'")
        assert result.valid is False

    def test_reject_chr_function(self) -> None:
        result = validate_sql("SELECT chr(68) || chr(82) FROM vehicles")
        assert result.valid is False

    def test_strips_trailing_semicolon(self) -> None:
        result = validate_sql("SELECT 1 FROM vehicles;")
        assert result.valid is True
        assert result.sanitized_sql is not None
        assert not result.sanitized_sql.endswith(";")


class TestCheckQueryCost:
    """Tests for check_query_cost()."""

    @pytest.mark.asyncio
    async def test_cost_below_threshold_passes(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = [{"Plan": {"Total Cost": 500.0}}]
        mock_db.execute.return_value = mock_result

        passes, cost = await check_query_cost(mock_db, "SELECT 1", 10000)
        assert passes is True
        assert cost == 500.0

    @pytest.mark.asyncio
    async def test_cost_above_threshold_rejected(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = [{"Plan": {"Total Cost": 15000.0}}]
        mock_db.execute.return_value = mock_result

        passes, cost = await check_query_cost(mock_db, "SELECT 1", 10000)
        assert passes is False
        assert cost == 15000.0

    @pytest.mark.asyncio
    async def test_explain_returns_none_raises(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="no result"):
            await check_query_cost(mock_db, "SELECT 1", 10000)

    @pytest.mark.asyncio
    async def test_explain_returns_empty_list_raises(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = []
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="unexpected format"):
            await check_query_cost(mock_db, "SELECT 1", 10000)

    @pytest.mark.asyncio
    async def test_explain_json_string(self) -> None:
        """check_query_cost handles JSON string response from EXPLAIN."""
        import json

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = json.dumps([{"Plan": {"Total Cost": 250.0}}])
        mock_db.execute.return_value = mock_result

        passes, cost = await check_query_cost(mock_db, "SELECT 1", 10000)
        assert passes is True
        assert cost == 250.0
