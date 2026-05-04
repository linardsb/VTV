"""CKAN Datastore SQL API client for ATD intercity transit data.

Queries data.gov.lv CKAN Datastore SQL API with Redis caching (5 min TTL),
automatic pagination (>32K rows), and rate limiting (1 req/s).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from typing import Any

import httpx

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

# ATD intercity GTFS dataset resource IDs (data.gov.lv)
#
# WARNING (T-003 — known broken; gated by ``Settings.intercity_search_enabled``,
# default ``False``). These IDs are placeholders. The original TODO assumed each
# GTFS table is published as a separate Datastore-enabled CKAN resource, but
# verification against data.gov.lv (dataset slug ``atd-gtfs``) shows the ATD
# publishes the full GTFS feed as a single ZIP file (``gtfs-latvia-lv.zip``,
# resource ``b0a020e4-1ee6-4e1a-9a94-63b1f8defd6d``) — there is no per-table
# Datastore SQL surface. The ``search_intercity_*`` agent tools therefore
# cannot work as written until the pipeline imports that ZIP into local tables
# (similar to ``historical_gtfs_importer.py``). Until that redesign lands, the
# feature flag in ``app/core/config.py`` keeps ``UnifiedDeps.ckan_http_client``
# unset, so ``_get_ckan_client()`` raises a clear ``TransitDataError``.
#
# DO NOT enable ``intercity_search_enabled`` in production without first
# replacing this dict with real Datastore-enabled resource IDs from a CKAN
# dataset that exposes GTFS tables individually.
CKAN_RESOURCES: dict[str, str] = {
    "agency": "b6884e21-0f28-4f98-a182-a673a2ce6270",
    "stops": "a17a6ee2-14ca-4a78-8e35-e82ccbc0e1f6",
    "routes": "0c3a4e00-f8f6-4f4e-9b6b-5bf5b1c5e3a1",
    "trips": "d4e5f6a7-b8c9-4d0e-a1f2-3b4c5d6e7f80",
    "stop_times": "e5f6a7b8-c9d0-4e1f-a2b3-4c5d6e7f8091",
    "calendar": "f6a7b8c9-d0e1-4f2a-b3c4-5d6e7f809102",
    "calendar_dates": "a7b8c9d0-e1f2-4a3b-c4d5-6e7f80910213",
    "shapes": "b8c9d0e1-f2a3-4b4c-d5e6-7f8091021324",
}

_CKAN_PAGE_SIZE = 32000
_MAX_PAGES = 100
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _escape_ckan_value(val: str) -> str:
    """Escape a user-provided value for safe embedding in CKAN SQL.

    Strips control characters, escapes backslashes, doubles single quotes,
    and escapes LIKE wildcards (%, _).

    Args:
        val: Raw user input string.

    Returns:
        Sanitized string safe for SQL LIKE embedding.
    """
    cleaned = _CONTROL_CHAR_RE.sub("", val)
    # Backslash first (before other replacements that introduce backslashes)
    cleaned = cleaned.replace("\\", "\\\\")
    # Single-quote escaping for SQL strings
    cleaned = cleaned.replace("'", "''")
    # LIKE wildcard escaping (anti-pattern #41)
    cleaned = cleaned.replace("%", "\\%")
    cleaned = cleaned.replace("_", "\\_")
    return cleaned


class CKANClient:
    """Async client for CKAN Datastore SQL API with caching and rate limiting.

    Args:
        http_client: Connection-pooled async HTTP client.
        settings: Application settings with CKAN configuration.
    """

    def __init__(self, http_client: httpx.AsyncClient, settings: Settings) -> None:
        self._http = http_client
        self._settings = settings
        self._rate_lock = asyncio.Lock()
        self._last_request_time: float = 0.0

    def _cache_key(self, sql: str) -> str:
        """Generate a deterministic Redis cache key from SQL.

        Args:
            sql: The SQL query string.

        Returns:
            Cache key in format ``ckan:{sha256_prefix}``.
        """
        sql_hash = hashlib.sha256(sql.encode()).hexdigest()[:16]
        return f"ckan:{sql_hash}"

    async def _get_cached(self, cache_key: str) -> list[dict[str, Any]] | None:
        """Attempt to retrieve cached query results from Redis.

        Args:
            cache_key: The Redis key to look up.

        Returns:
            Cached records list, or None on cache miss/error.
        """
        try:
            redis = await get_redis()
            raw = await redis.get(cache_key)
            if raw is not None:
                result: list[dict[str, Any]] = json.loads(raw)
                return result
        except Exception as exc:
            logger.debug(
                "transit.ckan.cache_error",
                cache_key=cache_key,
                error=str(exc),
                error_type=type(exc).__name__,
            )
        return None

    async def _set_cache(self, cache_key: str, data: list[dict[str, Any]]) -> None:
        """Store query results in Redis with configured TTL.

        Args:
            cache_key: The Redis key.
            data: Records to cache.
        """
        try:
            redis = await get_redis()
            await redis.set(
                cache_key,
                json.dumps(data, ensure_ascii=False),
                ex=self._settings.ckan_cache_ttl_s,
            )
        except Exception as exc:
            logger.debug(
                "transit.ckan.cache_set_error",
                cache_key=cache_key,
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async def _rate_limit(self) -> None:
        """Enforce minimum delay between requests to data.gov.lv."""
        async with self._rate_lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            delay = self._settings.ckan_rate_limit_delay_s
            if elapsed < delay:
                wait_s = delay - elapsed
                logger.debug("transit.ckan.rate_limited", wait_s=round(wait_s, 3))
                await asyncio.sleep(wait_s)
            self._last_request_time = time.monotonic()

    async def query_sql(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SQL query against the CKAN Datastore SQL API.

        Handles Redis caching, rate limiting, and automatic pagination
        for result sets exceeding 32K rows (the CKAN default page size).

        The caller's SQL should include its own LIMIT clause for bounded queries.
        Pagination only activates when CKAN returns a full 32K-row page, indicating
        more data is available (used for unbounded queries like all-stops fetch).

        Args:
            sql: SQL SELECT query to execute. May include LIMIT/ORDER BY.

        Returns:
            List of record dictionaries.

        Raises:
            TransitDataError: On HTTP errors, timeouts, or malformed responses.
        """
        cache_key = self._cache_key(sql)
        sql_hash = cache_key.split(":")[1]

        # Check cache first
        cached = await self._get_cached(cache_key)
        if cached is not None:
            logger.debug(
                "transit.ckan.cache_hit",
                sql_hash=sql_hash,
                record_count=len(cached),
            )
            return cached

        logger.debug("transit.ckan.cache_miss", sql_hash=sql_hash)
        logger.info("transit.ckan.query_started", sql_hash=sql_hash, cached=False)

        start = time.monotonic()
        all_records: list[dict[str, Any]] = []
        page = 0

        try:
            while page < _MAX_PAGES:
                page += 1

                await self._rate_limit()

                response = await self._http.post(
                    self._settings.ckan_datastore_sql_url,
                    json={"sql": sql},
                )
                response.raise_for_status()

                body = response.json()
                if not body.get("success"):
                    error_msg = body.get("error", {}).get("message", "Unknown CKAN error")
                    msg = f"CKAN API error: {error_msg}"
                    raise TransitDataError(msg)

                records: list[dict[str, Any]] = body.get("result", {}).get("records", [])
                all_records.extend(records)

                if len(records) < _CKAN_PAGE_SIZE:
                    break

                logger.info(
                    "transit.ckan.pagination_needed",
                    sql_hash=sql_hash,
                    total_fetched=len(all_records),
                    page_count=page,
                )

        except httpx.TimeoutException as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "transit.ckan.query_failed",
                sql_hash=sql_hash,
                error=str(exc),
                error_type="timeout",
                elapsed_ms=elapsed_ms,
            )
            msg = "CKAN API request timed out. Try again in a few seconds."
            raise TransitDataError(msg) from exc
        except httpx.HTTPError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "transit.ckan.query_failed",
                sql_hash=sql_hash,
                error=str(exc),
                error_type="http_error",
                elapsed_ms=elapsed_ms,
            )
            msg = "CKAN API request failed. The data.gov.lv service may be temporarily unavailable."
            raise TransitDataError(msg) from exc
        except TransitDataError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "transit.ckan.query_failed",
                sql_hash=sql_hash,
                error=str(exc),
                error_type=type(exc).__name__,
                elapsed_ms=elapsed_ms,
            )
            msg = f"Unexpected error querying CKAN: {type(exc).__name__}"
            raise TransitDataError(msg) from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "transit.ckan.query_completed",
            sql_hash=sql_hash,
            record_count=len(all_records),
            elapsed_ms=elapsed_ms,
            cached=False,
        )

        # Cache the results
        await self._set_cache(cache_key, all_records)

        return all_records
