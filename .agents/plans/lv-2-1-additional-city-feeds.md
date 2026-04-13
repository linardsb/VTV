# Plan: LV-2.1 Additional City GTFS-RT Feeds

## Context

Extend VTV from Riga-only to 4+ cities by adding GTFS-RT feeds for Jurmala and Pieriga (standard protobuf), a scraper for Daugavpils (`satiksme.daugavpils.lv`), and GPS text parsers for Liepaja/Rezekne (`marsruti.lv/*/gps.txt`). The existing multi-feed architecture (per-feed Redis keys, Pub/Sub channels, WebSocket subscriber) handles everything downstream — the work is config entries for standard feeds and pluggable fetch clients for non-standard sources.

## Security Context Assessment

- **CTX-INPUT** — GPS text and scraped HTML/JSON are untrusted external input. Validate lat/lon ranges (Latvia bounding box: 55.5-58.1 N, 20.5-28.3 E), sanitize vehicle_id strings, validate timestamps (reject future > 5min or stale > 24h).
- **CTX-INFRA** — New env var entries in `TRANSIT_FEEDS_JSON`. No new secrets. SSL verification stays enabled (all sources are HTTPS).

## Research Summary

### Key files

| File | Role | Lines |
|------|------|-------|
| `app/core/config.py:18-28` | `TransitFeedConfig` dataclass — 7 fields | Add `feed_type` discriminator |
| `app/transit/poller.py:52-100` | `FeedPoller.__init__` + `poll_once` — hardwired to `GTFSRealtimeClient` | Refactor to pluggable `_feed_client` |
| `app/transit/poller.py:348-408` | `start_pollers()` — iterates `settings.transit_feeds`, creates `FeedPoller` | No changes needed |
| `app/transit/poller.py:210-279` | `_enrich_vehicle()` — route/stop resolution with fallbacks | Works for feeds without static GTFS (falls back to vehicle_label parsing) |
| `app/transit/poller.py:31-49` | `EnrichedVehicle` TypedDict | No changes needed |
| `app/core/agents/tools/transit/client.py:32-47` | `VehiclePositionData` dataclass (12 fields) | Target output for all feed clients |
| `app/core/agents/tools/transit/client.py:50-59` | `TripUpdateData` / `StopTimeUpdateData` | Non-GTFS-RT clients return `[]` |
| `app/main.py:124` | `await start_pollers()` in lifespan | No changes needed |
| `app/transit/ckan_client.py` | Reference pattern for HTTP client with Redis caching | Template for scraper/GPS client |

### Architecture: pluggable feed client

Current: `FeedPoller.__init__` creates `GTFSRealtimeClient` and stores as `self._rt_client`. `poll_once` calls `self._rt_client.fetch_vehicle_positions()` / `fetch_trip_updates()`.

Change: Add `feed_type: Literal["gtfs_rt", "scraper", "gps_text"]` to `TransitFeedConfig`. In `FeedPoller.__init__`, dispatch on `feed_type` to create the right client (GTFS-RT / Daugavpils scraper / GPS text parser). Store as `self._feed_client`. All clients implement the same two-method interface returning `list[VehiclePositionData]` and `list[TripUpdateData]`. Downstream pipeline (enrich → Redis → TimescaleDB → Pub/Sub) is unchanged.

### Static GTFS data for non-standard feeds

`_enrich_vehicle()` calls `get_static_store()` for route/stop name resolution. Jurmala/Pieriga have GTFS static feeds (set `static_url`). Daugavpils and GPS-text feeds don't — enrichment falls back to vehicle_label parsing and empty strings. No crash risk — all fallback paths are already coded (lines 238-260).

## Test Landscape

- **15 transit test files** in `app/transit/tests/`
- **Key template**: `test_poller.py` — `_make_vehicle_position()` factory, `_make_feed_config()`, `_make_mock_settings()`, `_make_static_cache()` mock helpers, `_make_mock_redis()` (sync pipeline + async execute)
- **VehiclePositionData construction**: `VehiclePositionData(vehicle_id="4521", trip_id="trip_1", route_id="22", latitude=56.9496, longitude=24.1052, bearing=180.0, speed=10.0, current_stop_sequence=5, current_status="IN_TRANSIT_TO", stop_id="stop_100", timestamp=1700000000)`
- **Mock patterns**: `MagicMock()` for Redis pipeline methods (sync), `AsyncMock()` for `execute()` and `publish()`; `AsyncMock(spec=httpx.AsyncClient)` for HTTP clients
- **Anti-pattern #35**: `redis.pipeline()` is SYNC, not async — mock with `MagicMock()`, only `execute()` is async

## Type Check Baseline

| Tool | Errors | Notes |
|------|--------|-------|
| Pyright | 0 | Clean |
| MyPy | 0 | Clean |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add `feed_type: Literal["gtfs_rt", "scraper", "gps_text"]` to `TransitFeedConfig` |
| CREATE | `app/transit/feed_client.py` | `FeedClient` Protocol + `DaugavpilsScraper` + `GpsTextClient` + factory function |
| UPDATE | `app/transit/poller.py` | Replace `self._rt_client` with pluggable `self._feed_client` via factory dispatch |
| CREATE | `app/transit/tests/test_feed_client.py` | Tests for DaugavpilsScraper and GpsTextClient |
| UPDATE | `app/transit/tests/test_poller.py` | Update mocks from `_rt_client` to `_feed_client` |
| UPDATE | `.env.example` | Add example multi-feed JSON with new cities |

## Implementation Steps

### Step 1: Add `feed_type` to TransitFeedConfig

**File:** `app/core/config.py:18-28`

Add `feed_type` field with `Literal` type and default `"gtfs_rt"`:

```python
from typing import Literal

class TransitFeedConfig(BaseModel):
    """Configuration for a single GTFS-RT transit feed."""
    feed_id: str
    operator_name: str
    rt_vehicle_positions_url: str
    rt_trip_updates_url: str = ""  # empty for non-GTFS-RT feeds
    static_url: str = ""           # empty for feeds without static GTFS
    poll_interval_seconds: int = 10
    enabled: bool = True
    feed_type: Literal["gtfs_rt", "scraper", "gps_text"] = "gtfs_rt"
```

Make `rt_trip_updates_url` and `static_url` default to `""` so non-GTFS-RT feeds don't need to specify them.

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

---

### Step 2: Create feed client module

**File:** `app/transit/feed_client.py` (CREATE)

Define the `FeedClient` Protocol and two concrete implementations:

```python
"""Pluggable feed clients for non-GTFS-RT transit data sources.

Provides DaugavpilsScraper (HTML/JSON scraper) and GpsTextClient (CSV-like
GPS text parser). Both normalize to VehiclePositionData, matching the
GTFSRealtimeClient interface so FeedPoller can use them interchangeably.
"""
from __future__ import annotations

import re
import time
from typing import Protocol, runtime_checkable

import httpx

from app.core.agents.tools.transit.client import (
    TripUpdateData,
    VehiclePositionData,
)
from app.core.config import Settings, TransitFeedConfig
from app.core.logging import get_logger

logger = get_logger(__name__)

# Latvia bounding box for input validation
_LAT_MIN, _LAT_MAX = 55.5, 58.1
_LON_MIN, _LON_MAX = 20.5, 28.3
_MAX_FUTURE_SECONDS = 300       # 5 minutes
_MAX_STALE_SECONDS = 86400      # 24 hours
_VEHICLE_ID_RE = re.compile(r"^[\w\-.:]{1,64}$")


@runtime_checkable
class FeedClient(Protocol):
    """Interface for feed data fetchers."""

    async def fetch_vehicle_positions(self) -> list[VehiclePositionData]: ...
    async def fetch_trip_updates(self) -> list[TripUpdateData]: ...
```

**DaugavpilsScraper**: Fetches from `satiksme.daugavpils.lv/transports/karte` (expected JSON API endpoint returning vehicle objects with lat/lon/route/vehicle_id). Normalizes each entry to `VehiclePositionData`. Returns `[]` for `fetch_trip_updates()`.

Key implementation points:
- HTTP GET with 10s timeout
- Parse JSON response (expected: list of objects with `lat`, `lng`, `route`, `id`, `bearing`, `speed` fields)
- Validate each vehicle: lat/lon within Latvia bounding box, vehicle_id matches `_VEHICLE_ID_RE`, timestamp within stale/future bounds
- Skip invalid vehicles with warning log, don't fail the whole batch
- Log `transit.scraper.fetch_completed` with `feed_id`, `raw_count`, `valid_count`, `duration_ms`
- Log `transit.scraper.vehicle_invalid` for skipped vehicles (no PII, just reason + field name)

**GpsTextClient**: Fetches from `marsruti.lv/{city}/gps.txt` (expected CSV-like format: `vehicle_id;lat;lon;bearing;speed;route_id;timestamp`). Parses line by line. Same validation as scraper.

Key implementation points:
- HTTP GET with 10s timeout, expect `text/plain` response
- Split by newlines, split each line by `;` delimiter
- Parse fields positionally (7 fields per line)
- Skip malformed lines with warning log
- Log `transit.gps_text.fetch_completed` with `feed_id`, `raw_lines`, `valid_count`, `duration_ms`

**Factory function**:
```python
def create_feed_client(
    feed_config: TransitFeedConfig,
    http_client: httpx.AsyncClient,
    settings: Settings,
) -> FeedClient:
    """Create the appropriate feed client based on feed_type."""
    if feed_config.feed_type == "scraper":
        return DaugavpilsScraper(feed_config=feed_config, http_client=http_client)
    elif feed_config.feed_type == "gps_text":
        return GpsTextClient(feed_config=feed_config, http_client=http_client)
    else:
        from app.core.agents.tools.transit.client import GTFSRealtimeClient
        return GTFSRealtimeClient(http_client=http_client, settings=settings)
```

**Validation:** `uv run ruff format app/transit/feed_client.py && uv run ruff check --fix app/transit/feed_client.py && uv run pyright app/transit/feed_client.py`

---

### Step 3: Refactor FeedPoller to use pluggable client

**File:** `app/transit/poller.py`

Changes:
1. Import `create_feed_client` from `app.transit.feed_client`
2. In `__init__` (line 60-74): replace `self._rt_client = GTFSRealtimeClient(...)` with `self._feed_client = create_feed_client(feed_config, self._http_client, settings)`
3. In `poll_once` (line 88-89): replace `self._rt_client.fetch_vehicle_positions()` with `self._feed_client.fetch_vehicle_positions()` and same for `fetch_trip_updates()`
4. Remove direct `GTFSRealtimeClient` import (now imported via factory)

Exact changes in `__init__`:
```python
# OLD:
self._rt_client = GTFSRealtimeClient(http_client=self._http_client, settings=settings)

# NEW:
from app.transit.feed_client import create_feed_client
self._feed_client = create_feed_client(feed_config, self._http_client, settings)
```

Exact changes in `poll_once`:
```python
# OLD:
raw_vehicles = await self._rt_client.fetch_vehicle_positions()
trip_updates = await self._rt_client.fetch_trip_updates()

# NEW:
raw_vehicles = await self._feed_client.fetch_vehicle_positions()
trip_updates = await self._feed_client.fetch_trip_updates()
```

**Validation:** `uv run ruff format app/transit/poller.py && uv run ruff check --fix app/transit/poller.py && uv run pyright app/transit/poller.py`

---

### Step 4: Create tests for feed clients

**File:** `app/transit/tests/test_feed_client.py` (CREATE)

**DaugavpilsScraper tests (5 tests):**
1. `test_scraper_success` — mock HTTP response with valid JSON, verify VehiclePositionData output
2. `test_scraper_invalid_coordinates` — lat/lon outside Latvia bbox → vehicle skipped, no crash
3. `test_scraper_invalid_vehicle_id` — vehicle_id with special chars → skipped
4. `test_scraper_http_error` — `httpx.ConnectError` → raises `TransitDataError`
5. `test_scraper_empty_response` — empty JSON array → returns `[]`

**GpsTextClient tests (5 tests):**
6. `test_gps_text_success` — mock response with valid CSV lines, verify output
7. `test_gps_text_malformed_line` — line with wrong field count → skipped, others parsed
8. `test_gps_text_invalid_coordinates` — out-of-range lat/lon → skipped
9. `test_gps_text_http_error` — `httpx.ConnectError` → raises `TransitDataError`
10. `test_gps_text_empty_response` — empty body → returns `[]`

**Factory tests (2 tests):**
11. `test_create_feed_client_gtfs_rt` — `feed_type="gtfs_rt"` → returns `GTFSRealtimeClient`
12. `test_create_feed_client_scraper` — `feed_type="scraper"` → returns `DaugavpilsScraper`

Use `_make_feed_config()` pattern from `test_poller.py`, with `feed_type` override.
Mock `httpx.AsyncClient` with `AsyncMock(spec=httpx.AsyncClient)`.
Use `httpx.ConnectError` (not `Exception`) for error mocks — anti-pattern #4.

**Validation:** `uv run pytest app/transit/tests/test_feed_client.py -v`

---

### Step 5: Update existing poller tests

**File:** `app/transit/tests/test_poller.py`

Update all `patch.object(poller, "_rt_client")` to `patch.object(poller, "_feed_client")`. The mock interface is the same (`fetch_vehicle_positions`, `fetch_trip_updates`), just the attribute name changes.

Search for `_rt_client` in the file and replace with `_feed_client`.

**Validation:** `uv run pytest app/transit/tests/test_poller.py -v`

---

### Step 6: Update `.env.example` with multi-city feed config

**File:** `.env.example`

Add example `TRANSIT_FEEDS_JSON` showing all feed types:

```bash
# Multi-city transit feeds (LV-2.1)
# TRANSIT_FEEDS_JSON='[
#   {"feed_id":"riga","operator_name":"Rigas Satiksme","rt_vehicle_positions_url":"https://saraksti.rigassatiksme.lv/vehicle_positions.pb","rt_trip_updates_url":"https://saraksti.rigassatiksme.lv/trip_updates.pb","static_url":"https://saraksti.rigassatiksme.lv/gtfs.zip","poll_interval_seconds":10},
#   {"feed_id":"jurmala","operator_name":"Jurmala Transit","rt_vehicle_positions_url":"https://marsruti.lv/jurmala/gtfs_realtime.pb","rt_trip_updates_url":"","static_url":"https://marsruti.lv/jurmala/gtfs.zip","poll_interval_seconds":15},
#   {"feed_id":"pieriga","operator_name":"Pieriga Transit","rt_vehicle_positions_url":"https://marsruti.lv/pieriga/gtfs_realtime.pb","rt_trip_updates_url":"","static_url":"https://marsruti.lv/pieriga/gtfs.zip","poll_interval_seconds":15},
#   {"feed_id":"daugavpils","operator_name":"Daugavpils Satiksme","rt_vehicle_positions_url":"https://satiksme.daugavpils.lv/transports/karte","feed_type":"scraper","poll_interval_seconds":15},
#   {"feed_id":"liepaja","operator_name":"Liepaja Transport","rt_vehicle_positions_url":"https://marsruti.lv/liepaja/gps.txt","feed_type":"gps_text","poll_interval_seconds":15}
# ]'
```

**Validation:** Visual review only.

---

## Preflight Warnings

- **`_rt_client` references in test_poller.py** — must all be renamed to `_feed_client` (Step 5). Grep count before editing.
- **GTFSRealtimeClient import in poller.py** — remove direct import after factory handles it (Step 3). Ruff F401 will catch unused import.
- **TransitFeedConfig constructor calls in tests** — adding `feed_type` with a default value means existing constructors won't break.
- **`rt_trip_updates_url` and `static_url` defaults** — changing from required to optional (default `""`) may affect existing test `_make_feed_config()` calls that pass them explicitly. These will still work — just redundant.

## Security Checklist

For the scraper and GPS text clients:
- [x] Input validation: lat/lon within Latvia bounding box (55.5-58.1 N, 20.5-28.3 E)
- [x] Input validation: vehicle_id matches `^[\w\-.:]{1,64}$` regex
- [x] Input validation: timestamp within stale/future bounds
- [x] No user-provided data in log messages beyond feed_id and field names
- [x] `httpx.AsyncClient` uses SSL verification (default `verify=True`)
- [x] Error responses use `TransitDataError` (not internal type leakage)
- [x] No hardcoded credentials — URLs come from `TRANSIT_FEEDS_JSON` config

No new REST endpoints → CTX-RBAC not applicable.
No file uploads → CTX-FILE not applicable.

## Verification

- [ ] `make lint` passes (ruff format + check)
- [ ] `make types` passes (mypy + pyright)
- [ ] `uv run pytest app/transit/tests/ -v` — all transit tests pass
- [ ] `uv run pytest app/transit/tests/test_feed_client.py -v` — 12 new tests pass
- [ ] `uv run pytest app/transit/tests/test_poller.py -v` — existing poller tests pass with `_feed_client` rename
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] `make security-audit-quick` passes

## Notes

- **Daugavpils API format is provisional** — the scraper parsing logic assumes JSON with `{lat, lng, route, id, bearing, speed}` fields. Must be verified against the actual `satiksme.daugavpils.lv/transports/karte` API response. If the format differs, update `DaugavpilsScraper._parse_vehicle()` accordingly.
- **GPS text format is provisional** — assumes `vehicle_id;lat;lon;bearing;speed;route_id;timestamp` semicolon-delimited. Verify against `marsruti.lv/liepaja/gps.txt` response. The parser should handle minor variations (extra whitespace, missing trailing fields).
- **No frontend changes** — the CMS map already renders vehicles from all feeds via the `feed_id` field. Adding new feeds is config-only for the frontend.
- **Rezekne and LSA** — not included in this plan's config entries since their data source URLs need discovery. Can be added later as additional `gps_text` feed entries once URLs are confirmed.
