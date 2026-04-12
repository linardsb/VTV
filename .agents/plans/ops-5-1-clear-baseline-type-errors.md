# Plan: OPS-5.1 Clear Baseline Type Errors in Agent Tools + Pipeline

## Context

"Strict type safety" is contradicted by blanket suppression directives in `app/core/agents/tools/transit/client.py`. The file carries **5 pyright file-level suppressions** (lines 1-3) and **6 `# type: ignore[return-value]`** comments that mask an unknown number of actual type errors. Removing these suppressions and fixing the underlying types resets the baseline to zero so CI can fail on any regression.

`static_store.py` and `pipeline.py` are already clean (0 errors, 0 suppressions) and only need post-fix verification.

## Security Context Assessment

**No security contexts apply.** This is a pure type-safety refactoring — no new endpoints, no file handling, no auth changes, no infrastructure modifications.

## Research Summary

### Target Files

| File | Suppressions | Root Cause |
|------|-------------|------------|
| `client.py:1-3` | 5 pyright file-level directives (`reportUnknownVariableType`, `reportUnknownMemberType`, `reportUnknownParameterType`, `reportUnknownArgumentType`, `reportAttributeAccessIssue`) | `google.transit.gtfs_realtime_pb2` has no type stubs — protobuf-generated code is entirely untyped |
| `client.py:223,235,290,302,370,382` | 6 `# type: ignore[return-value]` (mypy) | `_CacheEntry.data` is `list[VehiclePositionData] \| list[TripUpdateData] \| list[AlertData]` — union can't narrow to return type |
| `static_store.py` | None | Clean |
| `pipeline.py` | None | Clean |

### Protobuf Types Used in `client.py`

The file accesses these protobuf message types from `google.transit.gtfs_realtime_pb2`:

- **`FeedMessage`**: `.header.timestamp`, `.entity` (repeated `FeedEntity`)
- **`FeedEntity`**: `.HasField("vehicle"|"trip_update"|"alert")`, `.vehicle`, `.trip_update`, `.alert`
- **`VehiclePosition`**: `.vehicle.id`, `.vehicle.label`, `.trip.trip_id`, `.trip.route_id`, `.position.latitude/.longitude/.bearing/.speed`, `.current_stop_sequence`, `.current_status`, `.stop_id`, `.timestamp`, `.HasField("vehicle"|"trip"|"position")`
- **`TripUpdate`**: `.trip.trip_id`, `.trip.route_id`, `.vehicle.id`, `.stop_time_update` (repeated), `.timestamp`, `.HasField("vehicle")`
- **`StopTimeUpdate`**: `.stop_sequence`, `.stop_id`, `.arrival.delay`, `.arrival.time`, `.departure.delay`, `.departure.time`, `.HasField("arrival"|"departure")`
- **`Alert`**: `.header_text.translation[0].text`, `.description_text.translation[0].text`, `.cause`, `.effect`, `.informed_entity` (repeated)
- **`EntitySelector`**: `.route_id`, `.stop_id`
- **`TranslatedString`**: `.translation` (repeated `Translation`)
- **`Translation`**: `.text`
- **`FeedHeader`**: `.timestamp`

### Cache Pattern (Root Cause of `type: ignore`)

```python
# Current: single union type for all cache entries
@dataclass
class _CacheEntry:
    data: list[VehiclePositionData] | list[TripUpdateData] | list[AlertData]

# Each method returns a specific list type but cache.data is the broad union
async def fetch_vehicle_positions(self) -> list[VehiclePositionData]:
    return self._vehicle_cache.data  # type: ignore[return-value]
```

### Pyright Global Config (pyproject.toml)

Already configured:
- `typeCheckingMode = "strict"`
- `reportMissingTypeStubs = "none"` (for protobuf)
- `reportUnknownLambdaType = "none"` (for protobuf lambdas)
- Pyright auto-discovers stubs in `typings/` at project root

### Existing mypy Config

- `[[tool.mypy.overrides]]` for `google.transit.*`: `ignore_missing_imports = true`

## Test Landscape

### Relevant Test Files

- `app/core/agents/tools/transit/tests/test_client.py` — GTFSRealtimeClient unit tests (HTTP mocking, cache TTL, error handling)
- `app/core/agents/tools/transit/tests/test_static_cache.py` — GTFSStaticCache in-memory tests
- `app/core/agents/tests/test_service.py` — AgentService orchestration
- `app/core/agents/tests/test_base.py` — BaseAgentService pipeline hooks

### Mock Patterns

- `AsyncMock(spec=httpx.AsyncClient)` for HTTP clients
- `MagicMock()` for settings (flexible property access)
- File-level pyright directives in test files (these are expected and acceptable for test code)

### Test Fixtures

- `_make_settings()` in `test_client.py` — creates mock settings with GTFS-RT URLs
- `_make_cache_with_calendar()` in `test_static_cache.py` — creates populated cache
- `conftest.py`: `make_agent_result()`, `make_skill_meta()`, `ManualClock`, `make_breaker_config()`

## Type Check Baseline

| Scope | Pyright | Mypy |
|-------|---------|------|
| 3 target files | 0 (suppressed) | 0 (suppressed) |
| `app/core/agents/` | 0 | 0 |

**Important:** The 0 count is artificial — `client.py` silences errors via file-level directives and inline ignores. The actual error count after removing suppressions is unknown and must be captured in Step 1.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `typings/google/__init__.pyi` | Namespace package stub |
| CREATE | `typings/google/transit/__init__.pyi` | Namespace package stub |
| CREATE | `typings/google/transit/gtfs_realtime_pb2.pyi` | Type stubs for protobuf messages used by `client.py` |
| UPDATE | `app/core/agents/tools/transit/client.py` | Remove suppressions, make `_CacheEntry` generic, fix any remaining type issues |

## Implementation Steps

### Step 1: Remove all suppressions and capture actual errors

**Goal:** Discover the true error count before fixing anything.

1. In `client.py`, **delete lines 1-3** (the 3 pyright file-level directive lines)
2. In `client.py`, **remove all 6 `# type: ignore[return-value]`** suffixes (lines 223, 235, 290, 302, 370, 382) — keep the code, just strip the comment
3. Run `uv run pyright app/core/agents/tools/transit/client.py 2>&1` and record every error
4. Run `uv run mypy app/core/agents/tools/transit/client.py 2>&1` and record every error
5. Document the exact error list — this becomes the checklist for Steps 2-3

**Validation:** No validation yet — errors are expected. Just capture them.

### Step 2: Create protobuf type stubs

**Goal:** Give pyright typed definitions for the `google.transit.gtfs_realtime_pb2` protobuf messages that `client.py` uses.

Create `typings/google/__init__.pyi`:
```python
# Namespace package
```

Create `typings/google/transit/__init__.pyi`:
```python
# Namespace package
```

Create `typings/google/transit/gtfs_realtime_pb2.pyi` with stub classes covering **only** the attributes `client.py` actually accesses. Use the protobuf types listed in the Research Summary above. Key design:

- All message classes inherit from `google.protobuf.message.Message` (which provides `HasField`)
- Repeated fields use `google.protobuf.internal.containers.RepeatedCompositeFieldContainer[T]`
- Scalar fields typed as `str`, `int`, `float` per GTFS-RT proto spec
- Optional sub-messages typed as their class (protobuf default: always present, but may be "unset" — `HasField` checks presence)

**Stub structure:**
```python
from google.protobuf.message import Message
from google.protobuf.internal.containers import RepeatedCompositeFieldContainer

class FeedHeader(Message):
    timestamp: int

class Translation(Message):
    text: str

class TranslatedString(Message):
    translation: RepeatedCompositeFieldContainer[Translation]

class Position(Message):
    latitude: float
    longitude: float
    bearing: float
    speed: float

class VehicleDescriptor(Message):
    id: str
    label: str

class TripDescriptor(Message):
    trip_id: str
    route_id: str

class StopTimeEvent(Message):
    delay: int
    time: int

class StopTimeUpdate(Message):
    stop_sequence: int
    stop_id: str
    arrival: StopTimeEvent
    departure: StopTimeEvent

class VehiclePosition(Message):
    vehicle: VehicleDescriptor
    trip: TripDescriptor
    position: Position
    current_stop_sequence: int
    current_status: int
    stop_id: str
    timestamp: int

class TripUpdate(Message):
    trip: TripDescriptor
    vehicle: VehicleDescriptor
    stop_time_update: RepeatedCompositeFieldContainer[StopTimeUpdate]
    timestamp: int

class EntitySelector(Message):
    route_id: str
    stop_id: str

class Alert(Message):
    header_text: TranslatedString
    description_text: TranslatedString
    cause: int
    effect: int
    informed_entity: RepeatedCompositeFieldContainer[EntitySelector]

class FeedEntity(Message):
    vehicle: VehiclePosition
    trip_update: TripUpdate
    alert: Alert

class FeedMessage(Message):
    header: FeedHeader
    entity: RepeatedCompositeFieldContainer[FeedEntity]
```

**Note:** `HasField()` is inherited from `google.protobuf.message.Message` which already has a typed signature in protobuf's own stubs. `google-protobuf` ships type stubs, so `Message.HasField(field_name: str) -> bool` is already typed.

**Validation:** `uv run pyright app/core/agents/tools/transit/client.py` — protobuf-related errors should resolve.

### Step 3: Make `_CacheEntry` generic

**Goal:** Eliminate the 6 `# type: ignore[return-value]` by making each cache field store a precisely typed list.

Replace the current `_CacheEntry` with a generic version:

```python
from typing import Generic, TypeVar

_T = TypeVar("_T")

@dataclass
class _CacheEntry(Generic[_T]):
    """In-memory cache entry with timestamp."""
    data: list[_T]
    fetched_at: float = field(default_factory=time.monotonic)
```

Update the `GTFSRealtimeClient.__init__` cache fields:
```python
self._vehicle_cache: _CacheEntry[VehiclePositionData] | None = None
self._trip_update_cache: _CacheEntry[TripUpdateData] | None = None
self._alerts_cache: _CacheEntry[AlertData] | None = None
```

Update `_is_cache_fresh` signature — it takes `_CacheEntry[object]` or just stay with `_CacheEntry[Any]`... Actually, keep it simple:
```python
def _is_cache_fresh(self, cache: _CacheEntry[object] | None) -> bool:
```

The cache assignment lines (`self._vehicle_cache = _CacheEntry(data=vehicles)`) will now infer the correct generic parameter from the list type. The return lines (`return self._vehicle_cache.data`) will now return the correctly narrowed `list[VehiclePositionData]` etc.

**Validation:** `uv run mypy app/core/agents/tools/transit/client.py` — return-value errors should resolve.

### Step 4: Fix any remaining errors

After Steps 2-3, re-run both type checkers on `client.py`. Address any remaining errors:

- If pyright still flags attribute access on protobuf types: extend the stub with missing attributes
- If mypy flags `_is_cache_fresh` generic parameter: adjust the bound (try `_CacheEntry[object]` → `Any` if needed)
- If either checker flags the `_parse_feed` return type: ensure stub's `FeedMessage` matches usage

**Validation per fix:**
```bash
uv run pyright app/core/agents/tools/transit/client.py
uv run mypy app/core/agents/tools/transit/client.py
```

### Step 5: Full verification

Run the complete type-checking suite to confirm zero errors and no regressions:

```bash
uv run pyright                                    # Full repo — 0 errors
uv run mypy app/                                  # Full app — 0 errors
uv run pytest app/core/agents/tools/transit/tests/ -x -q  # Transit tool tests pass
uv run pytest app/core/agents/tests/ -x -q        # Agent tests pass
```

Also verify `static_store.py` and `pipeline.py` remain clean:
```bash
uv run pyright app/core/agents/tools/transit/static_store.py app/core/agents/pipeline.py
uv run mypy app/core/agents/tools/transit/static_store.py app/core/agents/pipeline.py
```

## Preflight Warnings

- **Blanket suppression removal may reveal more errors than expected.** The 5 pyright directives silence *categories* of errors, not individual occurrences. Step 1 captures the real count before any fixes.
- **Protobuf stubs must match actual protobuf runtime behavior.** The GTFS-RT proto spec defines field presence rules (proto2 vs proto3) — stub types should use non-optional scalars since protobuf always returns default values for unset fields (0 for int, "" for str, 0.0 for float).
- **`RepeatedCompositeFieldContainer` import path.** Verify the exact import path works with the installed `protobuf` version: `from google.protobuf.internal.containers import RepeatedCompositeFieldContainer`. If the version differs, may need `from google.protobuf.internal.containers import RepeatedCompositeContainer` or similar.
- **`_is_cache_fresh` generic bound.** Using `_CacheEntry[object]` for the parameter type enables covariance (accepting `_CacheEntry[VehiclePositionData]` etc.) since it only reads, never writes. If pyright complains about invariance, switch to a `@overload` or use `_CacheEntry[Any]`.

## Security Checklist

N/A — no new endpoints, no user input changes, no auth modifications.

## Verification

- [ ] `uv run pyright` → 0 errors repo-wide
- [ ] `uv run mypy app/` → 0 errors
- [ ] `uv run pytest app/core/agents/tools/transit/tests/ -x -q` → all pass
- [ ] `uv run pytest app/core/agents/tests/ -x -q` → all pass
- [ ] `client.py` has zero `# type: ignore` comments
- [ ] `client.py` has zero `# pyright:` file-level directives
- [ ] `static_store.py` and `pipeline.py` remain at 0 errors
- [ ] `make check` passes (lint + types + tests)
