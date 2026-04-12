# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""SQL validation for text-to-sql agent tool (ML-5.4).

Three-layer defense: sqlparse whitelist, keyword blocklist, EXPLAIN cost gate.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import sqlparse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger

logger = get_logger(__name__)


# Tables the LLM is allowed to reference
ALLOWED_TABLES: frozenset[str] = frozenset(
    {
        "vehicles",
        "vehicle_positions",
        "routes",
        "trips",
        "stops",
        "stop_times",
        "drivers",
        "schedules",
        "calendar",
        "calendar_dates",
        "shapes",
        "agencies",
        "feed_info",
        "fleet_devices",
        "geofences",
        "geofence_events",
        "alerts",
        "alert_rules",
        "events",
        "documents",
        "document_chunks",
        "weather_observations",
        "traffic_counts",
    }
)

# Keywords that MUST NOT appear in generated SQL (case-insensitive)
_BLOCKED_KEYWORDS: frozenset[str] = frozenset(
    {
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "CREATE",
        "ALTER",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "COPY",
        "EXECUTE",
        "CALL",
        "DO",
        "SET",
        "RESET",
        "LOAD",
        "VACUUM",
        "CLUSTER",
        "REINDEX",
        "COMMENT",
        "SECURITY",
        "OWNER",
    }
)

# Patterns that indicate injection attempts
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r";\s*\w", re.IGNORECASE),  # Stacked queries
    re.compile(r"--\s*$", re.MULTILINE),  # Line comments at end
    re.compile(r"/\*.*?\*/", re.DOTALL),  # Block comments
    re.compile(r"\\x[0-9a-f]{2}", re.IGNORECASE),  # Hex-encoded chars
    re.compile(r"chr\s*\(", re.IGNORECASE),  # CHR() function
    re.compile(r"pg_\w+", re.IGNORECASE),  # System catalog access
    re.compile(r"information_schema", re.IGNORECASE),  # Schema introspection
]


@dataclass(frozen=True)
class ValidationResult:
    """Result of SQL validation."""

    valid: bool
    error: str | None = None
    sanitized_sql: str | None = None


def validate_sql(sql: str) -> ValidationResult:
    """Validate SQL is a safe, read-only SELECT statement.

    Three checks:
    1. sqlparse parse - must be exactly one SELECT statement
    2. Keyword blocklist - no DDL/DML tokens
    3. Injection pattern scan - no stacked queries, comments, hex encoding

    Args:
        sql: The SQL string to validate.

    Returns:
        ValidationResult with valid=True and sanitized SQL, or valid=False with error.
    """
    if not sql or not sql.strip():
        return ValidationResult(valid=False, error="Empty SQL statement")

    # Parse with sqlparse
    statements = sqlparse.parse(sql.strip())
    if len(statements) != 1:
        logger.warning(
            "agent.analytics_sql.validation_failed",
            reason="multiple_statements",
            statement_count=len(statements),
        )
        return ValidationResult(valid=False, error="Only single SELECT statements are allowed")

    stmt = statements[0]
    stmt_type: str = str(stmt.get_type() or "").upper()  # type: ignore[no-untyped-call]

    if stmt_type != "SELECT":
        logger.warning(
            "agent.analytics_sql.validation_failed",
            reason="not_select",
            statement_type=stmt_type,
        )
        return ValidationResult(
            valid=False, error=f"Only SELECT statements are allowed, got {stmt_type}"
        )

    # Flatten tokens and check against blocked keywords
    sql_upper = sql.upper()
    for keyword in _BLOCKED_KEYWORDS:
        # Match whole words only to avoid false positives (e.g., "RESET" in "PRESET")
        keyword_pat = rf"\b{keyword}\b"
        if re.search(keyword_pat, sql_upper):
            logger.warning(
                "agent.analytics_sql.validation_failed",
                reason="blocked_keyword",
                keyword=keyword,
            )
            return ValidationResult(valid=False, error=f"Blocked keyword detected: {keyword}")

    # Injection pattern scan
    for inj_pattern in _INJECTION_PATTERNS:
        if inj_pattern.search(sql):
            logger.warning(
                "agent.analytics_sql.validation_failed",
                reason="injection_pattern",
                pattern_name=inj_pattern.pattern,
            )
            return ValidationResult(
                valid=False,
                error="Potential SQL injection pattern detected",
            )

    # Sanitize: strip trailing whitespace and semicolons
    sanitized = sql.strip().rstrip(";").strip()

    return ValidationResult(valid=True, sanitized_sql=sanitized)


async def check_query_cost(
    db: AsyncSession,
    sql: str,
    max_cost: int,
) -> tuple[bool, float]:
    """Run EXPLAIN to estimate query cost.

    Args:
        db: Async database session.
        sql: Validated SELECT statement.
        max_cost: Maximum allowed Total Cost from EXPLAIN.

    Returns:
        Tuple of (passes_cost_gate, estimated_cost).

    Raises:
        ValueError: If EXPLAIN fails to parse.
    """
    explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
    result = await db.execute(text(explain_sql))
    row = result.scalar()

    if row is None:
        msg = "EXPLAIN returned no result"
        raise ValueError(msg)

    # Parse the JSON plan
    if isinstance(row, str):
        plan_data = json.loads(row)
    else:
        plan_data = row

    if not isinstance(plan_data, list) or len(plan_data) == 0:
        msg = "EXPLAIN returned unexpected format"
        raise ValueError(msg)

    total_cost = float(plan_data[0]["Plan"]["Total Cost"])

    if total_cost > max_cost:
        logger.warning(
            "agent.analytics_sql.cost_exceeded",
            estimated_cost=total_cost,
            max_cost=max_cost,
        )
        return (False, total_cost)

    return (True, total_cost)
