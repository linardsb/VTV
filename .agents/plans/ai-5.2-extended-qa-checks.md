# Plan: AI-5.2 — Extended QA Checks for Agent Self-Correction

## Context

AI-5.1 (commit `997a425`) wired a bounded self-correction loop around the standard-tier `agent.run()`. It currently consumes 4 deterministic validators in `app/core/agents/validation.py` (route range, delay range, stale data, Latvian diacritics) and retries when any "retryable" warning fires.

AI-5.2 adds **6 new deterministic QA checks** that catch the most common factual failures dispatchers report:

1. `check_route_existence` — mentioned route number must exist in GTFS static data
2. `check_stop_existence` — mentioned stop name must exist in GTFS static data
3. `check_time_consistency` — no impossible times (25:30, departures before "now" for future queries)
4. `check_citation_grounding` — every `[title](/lv|en/documents/{id})` link refers to a doc that was actually returned by `search_knowledge`
5. `check_language_match` — response language matches the user-message language (lv/en)
6. `check_stale_data` — extends the current module-level flag with per-response inspection of GTFS-RT timestamps in tool results

Each new check returns `Issue(check_name, description, severity)` where `severity ∈ {"error", "warning"}`. **Errors** flow through the AI-5.1 correction loop and trigger one retry. **Warnings** become footnotes only (same UX as today's stale-data warning).

The current `ValidationResult` model uses a flat `warnings: list[str]`. AI-5.2 introduces an `Issue` dataclass and an `issues: list[Issue]` field. `warnings` stays as a derived view for backward compatibility with `service.py` footnote rendering — no churn there.

## Security Context Assessment

- **CTX-AGENT** (active) — `app/core/agents/` is core agent infra. No new endpoint, no new user input surface, no new tool, no new credentials. The validators only *read* response text and *read* the in-memory GTFS cache. Tool results are inspected as plain Python objects already produced by registered tools — no new external I/O. Validator exceptions must continue to fail-open (matches `correction.py:_safe_validate`); a crashing validator must NEVER block dispatchers.
- **CTX-INPUT** (marginal) — Regex extraction from agent text. All regexes already use `re.IGNORECASE` + `finditer`; no eval, no shell, no SQL. Add max-iteration guards on `finditer` loops to defend against pathological agent outputs (e.g., 10k route mentions).
- **CTX-AUTH / CTX-RBAC / CTX-FILE / CTX-INFRA** — not applicable.

## Research Summary

### Existing validation architecture (`app/core/agents/validation.py:1-160`)

```python
@dataclass
class ValidationResult:                       # validation.py:65-77
    is_valid: bool = True
    warnings: list[str] = field(default_factory=list)
    sanitized_response: str = ""

def validate_transit_response(response: str) -> ValidationResult:   # :80-105
    # calls 4 _check_* helpers, sets is_valid = bool(no warnings)

# Module-level state
last_stale_data_timestamp: float = 0.0        # :20  set by circuit breaker
_STALE_DATA_THRESHOLD: float = 300.0           # :23  5 minutes

# Regexes
_ROUTE_PATTERN = re.compile(                   # :53
    r"(?:route|mar[sš]rut[sa]?|#|nr\.?\s*)\s*(\d+)", re.IGNORECASE
)
_DELAY_PATTERN = re.compile(                   # :59
    r"(\-?\d+(?:\.\d+)?)\s*(?:min[uū]t|minut|second|sekund)", re.IGNORECASE
)

# Existing checks — all signature (response, result) -> None, mutate result.warnings
_check_route_plausibility(response, result)    # :108  range 1-999
_check_delay_plausibility(response, result)    # :116  negative + >1440min
_check_stale_data(result)                       # :137  module-level flag
_check_latvian_diacritics(response, result)    # :149  ASCII vs diacritic forms
```

### Self-correction loop integration (`app/core/agents/correction.py`)

- `SelfCorrectionLoop.run_with_correction()` — calls `_safe_validate()` then `_retryable_warnings(warnings)`. Today the filter is prefix-based:
  ```python
  _NON_RETRYABLE_PREFIXES: tuple[str, ...] = ("This response may be based on cached data",)  # :41
  def _retryable_warnings(warnings: list[str]) -> list[str]:                                  # :68
      return [w for w in warnings if not w.startswith(_NON_RETRYABLE_PREFIXES)]
  ```
- `_safe_validate(response)` is the only call site (`correction.py:157`, `service.py:268`). Both are sync calls — validation must stay synchronous.
- The retry corrective prompt is built from the warning *strings*, not Issue objects (`correction.py:198, 234`). Bullet list is `f"- {w}"`.

### Service-side validation (`app/core/agents/service.py:201-280`)

- `correction_warnings` is `list[str] | None`. Loop populates it from `corrected.warnings`. The `else` branch (loop disabled) calls `validate_transit_response(response_content)` directly and reads `validation.warnings`.
- Footnote rendering (`service.py:273-280`) iterates `warnings_to_render` strings — no Issue field is touched.
- Complex tier (`service.py:203-221`) does NOT go through validation today. AI-5.2 stays out of scope for the complex pipeline; that lands in AI-5.3.

### GTFS static cache (`app/core/agents/tools/transit/static_cache.py`)

```python
class GTFSStaticCache:                         # static_cache.py:116
    routes: dict[str, RouteInfo]                # route_id -> RouteInfo
    stops:  dict[str, StopInfo]                 # stop_id  -> StopInfo
    stop_routes: dict[str, list[str]]           # stop_id  -> [route_short_name, ...]

@dataclass
class RouteInfo:                                # static_cache.py:25
    route_id: str
    route_short_name: str                       # the user-visible "22", "3", "1A"
    route_long_name: str
    route_type: int

@dataclass
class StopInfo:                                 # static_cache.py:35
    stop_id: str
    stop_name: str
    stop_lat: float
    stop_lon: float
```

- Loaded via async `get_static_store()` (`static_store.py:199`) — singleton, ttl-bounded.
- For validation we need a SYNC handle. The cache lives behind `UnifiedDeps.db_session_factory`, but the cache object itself is plain Python after load. Strategy: pass the *already-loaded* `GTFSStaticCache` instance into `validate_transit_response()` as an optional parameter; the loop fetches it once via `await get_static_store(...)` BEFORE calling `_safe_validate`.
- If the cache is `None` (not loaded yet, or transit feature disabled), the existence checks gracefully no-op. They never fail-closed.

### Tool result inspection

- The agent loop returns `result.all_messages()` (pydantic_ai). Tool returns surface as `ToolReturnPart` with `.content`. The correction loop already captures `result.all_messages()` into `last_messages` (`correction.py:155`).
- For `check_citation_grounding`: scan `ToolReturnPart` parts whose tool name is `search_knowledge`, parse the returned JSON, extract `document_id` values.
- For `check_stale_data` (per-response): scan `ToolReturnPart` parts from transit tools (`query_bus_status`, `get_route_schedule`, etc.), parse JSON, extract any `timestamp` field, compare to `time.time()`.
- A small helper `extract_tool_returns(messages) -> list[ToolReturnRecord]` lives in validation.py — pure-stdlib, returns `list[ToolReturnRecord(tool_name: str, payload: Any)]`.

### Knowledge citation format

- Agent system prompt (`agent.py:93-100`) instructs Markdown links: `[title](/lv/documents/{document_id})` or `/en/documents/{document_id}`.
- Citation regex: `r"\[[^\]]+\]\(/(?:lv|en)/documents/(\d+)\)"`.

### Language detection

No existing utility. Use a lightweight regex heuristic — count Latvian-only diacritics (`ā č ē ģ ī ķ ļ ņ š ū ž`) vs common English stopwords (`\bthe\b`, `\band\b`, `\bof\b`, `\bbus\b`, `\broute\b`). Tie-breaks default to `lv` (primary platform language). No third-party dependency.

## Test Landscape

- **No `test_validation.py` exists yet** — this plan creates it at `app/core/agents/tests/test_validation.py`.
- Closest precedent: `app/core/agents/tests/test_correction.py` — uses `pytest.mark.asyncio`, inline `_make_*` helpers, `MagicMock`/`AsyncMock`, no integration marker, no DB.
- Agent tests are pure unit tests; no `app/core/agents/tests/conftest.py` (fixtures inlined).
- Helper factory naming convention: `_make_<thing>() -> ReturnType` (e.g., `_make_static_cache() -> GTFSStaticCache`).
- Static cache fixtures used in `test_get_route_schedule.py` / `test_search_stops.py` build a `MagicMock` populated with real `RouteInfo` / `StopInfo` / `StopTimeEntry` dataclasses. We can copy that pattern for validation tests but should construct a *real* `GTFSStaticCache()` (not MagicMock) since validation reads `.routes` / `.stops` directly — clearer.
- Anti-patterns to honor: Rule 7 (test helpers need `-> ReturnType`), Rule 26 (parameterized tests need `-> None`), Rule 22/28 (annotate empty/dict literals), Rule 14 (no `type: ignore` in tests — use `# pyright:` directive at file head if needed).

## Type Check Baseline

| Check | Scope | Errors |
|---|---|---|
| pyright | `app/core/agents/validation.py` | **1** (`warnings: list[str]` empty literal warning at L76) |
| pyright | `app/core/agents/` | **6** total (1 in validation.py + 5 pre-existing in pipeline.py / client.py / static_store.py) |
| mypy | `app/core/agents/validation.py` | **0** |
| mypy | `app/core/agents/` | **3** (pre-existing in pipeline.py + static_store.py) |

**Acceptance:**
- `validation.py` must end at **pyright 0 / mypy 0** (the existing L76 warning is a free fix once we touch the file — annotate the empty list literal).
- `correction.py` must remain at **pyright 0 / mypy 0**.
- `service.py` must remain at its current (unchanged) baseline.
- `app/core/agents/` total must be **≤ pyright 5 / ≤ mypy 3** (one fewer pyright than baseline, since we fix the validation.py warning).

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| UPDATE | `app/core/agents/validation.py` | Add `Issue`, `Severity`, `ValidationContext`, `ToolReturnRecord`, `extract_tool_returns()`, 6 new check functions, refactor existing 4 checks to emit Issue objects, derive `warnings` from `issues` |
| UPDATE | `app/core/agents/correction.py` | Replace `_NON_RETRYABLE_PREFIXES`/`_retryable_warnings()` with severity-based `_retryable_issues()`. Pass `ValidationContext` (user_message, static_cache, tool_returns from `result.all_messages()`) into `_safe_validate()`. Build corrective prompt from error-severity issue descriptions. |
| UPDATE | `app/core/agents/service.py` | When loop is enabled, fetch static cache once before calling the loop and forward it. When loop is disabled (else branch), build the same `ValidationContext` (user_message + static_cache + tool returns from `result.all_messages()`) and pass it to `validate_transit_response`. No footnote-rendering changes. |
| CREATE | `app/core/agents/tests/test_validation.py` | 12+ unit tests covering each new check (positive + negative cases) and the severity-driven retry semantics |
| UPDATE | `app/core/agents/tests/test_correction.py` | Add 2-3 tests proving severity-based retry: error issues trigger retry, warning issues do not. Update existing tests if they hard-code `_NON_RETRYABLE_PREFIXES`. |

## Implementation Steps

### Step 1 — Refactor `validation.py`: introduce `Issue`, `Severity`, `ValidationContext`, helpers

`UPDATE app/core/agents/validation.py`:

1. Add types:
   ```python
   from typing import Any, Literal
   from pydantic_ai.messages import ModelMessage, ToolReturnPart  # for extract_tool_returns

   Severity = Literal["error", "warning"]

   @dataclass(frozen=True)
   class Issue:
       """A single validation finding.

       Attributes:
           check_name: Stable identifier of the producing check (e.g.
               "route_existence"). Used for metrics and tests.
           description: Human-readable message rendered in footnotes
               and corrective retry prompts.
           severity: "error" → triggers self-correction retry.
               "warning" → footnote only, no retry.
       """
       check_name: str
       description: str
       severity: Severity

   @dataclass
   class ToolReturnRecord:
       """A parsed tool return extracted from agent message history."""
       tool_name: str
       payload: Any  # parsed JSON or raw content

   @dataclass
   class ValidationContext:
       """Optional context passed into validate_transit_response.

       All fields are optional. Checks that need a missing field
       gracefully skip themselves (no false errors).
       """
       user_message: str | None = None
       static_cache: Any | None = None  # GTFSStaticCache | None — Any to avoid circular import
       tool_returns: list[ToolReturnRecord] = field(
           default_factory=lambda: list[ToolReturnRecord]()
       )
   ```

2. Update `ValidationResult`:
   ```python
   @dataclass
   class ValidationResult:
       is_valid: bool = True
       issues: list[Issue] = field(default_factory=lambda: list[Issue]())
       warnings: list[str] = field(default_factory=lambda: list[str]())  # derived view
       sanitized_response: str = ""
   ```
   `warnings` stays for backward compat with `service.py:273-280` footnote rendering — populated as `[issue.description for issue in result.issues]` at the end of `validate_transit_response`. **Annotate the empty list literal** (fixes the pre-existing pyright warning).

3. Add `extract_tool_returns(messages: list[ModelMessage]) -> list[ToolReturnRecord]`:
   - Iterate messages, find `ToolReturnPart` (or `ToolReturn` parts depending on pydantic_ai version), record `tool_name` + `content`.
   - Try `json.loads(content)` if it's a string; fall back to raw string.
   - Wrap the whole function in try/except → return `[]` on failure (fail-open).
   - **Pyright safety:** annotate with `list[ToolReturnRecord]`, narrow message parts via `isinstance`.

4. Refactor existing 4 checks to push `Issue` objects instead of plain strings. Severity assignment matches today's retry semantics:
   | Existing check | New severity |
   |---|---|
   | `_check_route_plausibility` | `error` (was retryable) |
   | `_check_delay_plausibility` | `error` (was retryable) |
   | `_check_latvian_diacritics` | `error` (was retryable) |
   | `_check_stale_data` (module flag branch) | `warning` (was non-retryable) |

5. Update orchestrator:
   ```python
   def validate_transit_response(
       response: str,
       context: ValidationContext | None = None,
   ) -> ValidationResult:
       result = ValidationResult(sanitized_response=response)
       ctx = context or ValidationContext()

       _check_route_plausibility(response, result)
       _check_delay_plausibility(response, result)
       _check_stale_data(result, ctx)               # extended (Step 6)
       _check_latvian_diacritics(response, result)

       _check_route_existence(response, result, ctx)        # Step 2
       _check_stop_existence(response, result, ctx)         # Step 3
       _check_time_consistency(response, result)            # Step 4
       _check_citation_grounding(response, result, ctx)     # Step 5
       _check_language_match(response, result, ctx)         # Step 7
       # _check_stale_data already done above with extended logic

       result.warnings = [i.description for i in result.issues]
       result.is_valid = not result.issues
       return result
   ```

6. **MAX_ITERATIONS guard:** when calling `finditer` add a `for idx, match in enumerate(... ): if idx > 200: break` cap. Defends against pathological output. Apply to all regex loops in this file.

**Validation:**
```bash
uv run ruff format app/core/agents/validation.py && \
uv run ruff check --fix app/core/agents/validation.py && \
uv run pyright app/core/agents/validation.py && \
uv run mypy app/core/agents/validation.py
```
Expect: pyright 0 / mypy 0.

---

### Step 2 — `check_route_existence`

`UPDATE app/core/agents/validation.py`:

```python
def _check_route_existence(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    """Verify mentioned route numbers exist in GTFS static data.

    No-op if static_cache is unavailable. Errors are retryable: the
    agent should re-answer using a route number that actually exists.
    """
    if ctx.static_cache is None:
        return
    known_short_names: set[str] = {
        info.route_short_name for info in ctx.static_cache.routes.values()
    }
    if not known_short_names:
        return  # cache loaded but empty — fail-open
    seen: set[str] = set()
    for idx, match in enumerate(_ROUTE_PATTERN.finditer(response)):
        if idx > 200:
            break
        route_token = match.group(1)
        if route_token in seen:
            continue
        seen.add(route_token)
        if route_token not in known_short_names:
            result.issues.append(
                Issue(
                    check_name="route_existence",
                    description=(
                        f"Route {route_token} not found in GTFS data. "
                        "Use a real route number."
                    ),
                    severity="error",
                )
            )
```

**Validation:** same per-file ruff/pyright/mypy loop.

---

### Step 3 — `check_stop_existence`

`UPDATE app/core/agents/validation.py`:

- Stop *names* in agent prose are fuzzy ("Brīvības", "Brīvības iela", "Brivibas"). Direct substring matching produces false positives.
- Strategy: extract proper-noun-looking tokens that follow the words `pietura`, `stop`, `at`, `pie pieturas` (Latvian for "at the stop"). Build a regex like:
  ```python
  _STOP_PATTERN = re.compile(
      r"(?:pietur[āai]|stop)\s+([A-ZĀČĒĢĪĶĻŅŠŪŽ][\w\-āčēģīķļņšūž]{2,40}(?:\s+[A-ZĀČĒĢĪĶĻŅŠŪŽ][\w\-āčēģīķļņšūž]{2,40})*)",
      re.IGNORECASE,
  )
  ```
- For each captured stop name, normalize (lowercase, strip diacritics via `_normalize_lv()` helper) and check against a normalized set built from `ctx.static_cache.stops.values()`.
- Severity: **`warning`** (NOT error). Stop name extraction is heuristic — false positives are likely. We surface the doubt as a footnote instead of forcing a retry.
- No-op if cache is None or empty. Cap finditer loop at 200.

```python
def _normalize_lv(text: str) -> str:
    """Lowercase + strip Latvian diacritics for fuzzy matching."""
    table = str.maketrans("āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ", "acegiklnsuzACEGIKLNSUZ")
    return text.translate(table).lower().strip()

def _check_stop_existence(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    if ctx.static_cache is None or not ctx.static_cache.stops:
        return
    known_names = {_normalize_lv(s.stop_name) for s in ctx.static_cache.stops.values()}
    seen_norms: set[str] = set()
    for idx, match in enumerate(_STOP_PATTERN.finditer(response)):
        if idx > 200:
            break
        candidate = match.group(1).strip()
        norm = _normalize_lv(candidate)
        if norm in seen_norms:
            continue
        seen_norms.add(norm)
        # Substring match either way — agent might say "Brīvības" but the
        # full stop is "Brīvības iela 12". Treat partial as found.
        if not any(norm in k or k in norm for k in known_names):
            result.issues.append(
                Issue(
                    check_name="stop_existence",
                    description=f"Stop '{candidate}' not found in GTFS data — verify name.",
                    severity="warning",
                )
            )
```

**Validation:** per-file checks.

---

### Step 4 — `check_time_consistency`

`UPDATE app/core/agents/validation.py`:

- Add `_TIME_PATTERN = re.compile(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b")`.
- For each match, parse hours/minutes/seconds. Flag:
  - hours > 23 (GTFS supports 24-47 for next-day trips, but agent text addressing dispatchers should normalize)
  - minutes ≥ 60
  - seconds ≥ 60
- **Severity: `error`** — agent can re-answer with normalized times.
- Cap iterations at 200.

```python
def _check_time_consistency(response: str, result: ValidationResult) -> None:
    for idx, match in enumerate(_TIME_PATTERN.finditer(response)):
        if idx > 200:
            break
        try:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = int(match.group(3)) if match.group(3) else 0
        except ValueError:
            continue
        problems: list[str] = []
        if hours > 23:
            problems.append(f"hours={hours}")
        if minutes >= 60:
            problems.append(f"minutes={minutes}")
        if seconds >= 60:
            problems.append(f"seconds={seconds}")
        if problems:
            result.issues.append(
                Issue(
                    check_name="time_consistency",
                    description=(
                        f"Impossible time '{match.group(0)}' "
                        f"({', '.join(problems)})."
                    ),
                    severity="error",
                )
            )
```

**Validation:** per-file checks.

---

### Step 5 — `check_citation_grounding`

`UPDATE app/core/agents/validation.py`:

- Citation regex: `_CITATION_PATTERN = re.compile(r"\[[^\]]+\]\(/(?:lv|en)/documents/(\d+)\)")`.
- Extract `document_id` ints from response.
- Pull the set of valid IDs from `ctx.tool_returns` for tools whose name starts with `search_knowledge`. The tool returns a JSON list of records each containing `document_id`.
- If ANY tool return is missing OR JSON parse fails → fail-open (skip the check) — we cannot prove an unground citation if we can't see the tool data.
- Flag any cited ID that's not in the union of search-knowledge result IDs.
- **Severity: `error`** — agent must remove fake citations.

```python
_CITATION_PATTERN = re.compile(r"\[[^\]]+\]\(/(?:lv|en)/documents/(\d+)\)")

def _check_citation_grounding(
    response: str,
    result: ValidationResult,
    ctx: ValidationContext,
) -> None:
    if not ctx.tool_returns:
        return
    valid_ids: set[int] = set()
    saw_search = False
    for record in ctx.tool_returns:
        if not record.tool_name.startswith("search_knowledge"):
            continue
        saw_search = True
        try:
            payload = record.payload
            # Tool returns a list of dicts or a dict with "results" key
            entries = payload if isinstance(payload, list) else payload.get("results", [])
            for entry in entries:
                if isinstance(entry, dict) and "document_id" in entry:
                    valid_ids.add(int(entry["document_id"]))
        except (AttributeError, TypeError, ValueError):
            return  # malformed payload — fail-open
    if not saw_search:
        return  # no knowledge tool calls → no citations expected
    seen: set[int] = set()
    for idx, match in enumerate(_CITATION_PATTERN.finditer(response)):
        if idx > 200:
            break
        try:
            doc_id = int(match.group(1))
        except ValueError:
            continue
        if doc_id in seen:
            continue
        seen.add(doc_id)
        if doc_id not in valid_ids:
            result.issues.append(
                Issue(
                    check_name="citation_grounding",
                    description=(
                        f"Citation references document {doc_id} which "
                        "was not returned by search_knowledge."
                    ),
                    severity="error",
                )
            )
```

**Validation:** per-file checks.

---

### Step 6 — `check_stale_data` extension

`UPDATE app/core/agents/validation.py`:

- Keep the existing module-level flag branch (warning severity).
- Add a per-response branch: if `ctx.tool_returns` contains transit tool returns with a `timestamp` field (POSIX seconds), compare to `time.time()`. If `now - timestamp > _STALE_DATA_THRESHOLD`, append a warning naming the stale tool.
- Both branches are **`warning`** severity (non-retryable — retrying won't refresh the upstream feed).

```python
_TRANSIT_TOOLS_WITH_TIMESTAMPS = (
    "query_bus_status",
    "get_route_schedule",
    "get_adherence_report",
)

def _check_stale_data(result: ValidationResult, ctx: ValidationContext) -> None:
    global last_stale_data_timestamp
    if last_stale_data_timestamp > 0:
        age = time.monotonic() - last_stale_data_timestamp
        if age < _STALE_DATA_THRESHOLD:
            result.issues.append(
                Issue(
                    check_name="stale_data",
                    description=(
                        "This response may be based on cached data. "
                        "Live feed was temporarily unavailable."
                    ),
                    severity="warning",
                )
            )
    now_ts = time.time()
    for record in ctx.tool_returns:
        if not any(record.tool_name.startswith(t) for t in _TRANSIT_TOOLS_WITH_TIMESTAMPS):
            continue
        try:
            payload = record.payload
            ts = payload.get("timestamp") if isinstance(payload, dict) else None
            if ts is None:
                continue
            age = now_ts - float(ts)
        except (AttributeError, TypeError, ValueError):
            continue
        if age > _STALE_DATA_THRESHOLD:
            result.issues.append(
                Issue(
                    check_name="stale_data",
                    description=(
                        f"GTFS-RT data from {record.tool_name} is "
                        f"{int(age)}s old (threshold {int(_STALE_DATA_THRESHOLD)}s)."
                    ),
                    severity="warning",
                )
            )
            return  # one warning is enough — avoid spam
```

**IMPORTANT:** `_NON_RETRYABLE_PREFIXES` in correction.py must keep matching the legacy stale-data string for the duration of Step 8 (severity-based filter). Once Step 8 lands the prefix list is removed entirely.

**Validation:** per-file checks.

---

### Step 7 — `check_language_match`

`UPDATE app/core/agents/validation.py`:

- Add `_detect_language(text: str) -> Literal["lv", "en"]`:
  - Count Latvian-only diacritics: `sum(1 for c in text if c in "āčēģīķļņšūžĀČĒĢĪĶĻŅŠŪŽ")`.
  - Count English stopword hits: `len(_EN_STOPWORD_PATTERN.findall(text))` where the pattern is `r"\b(?:the|and|of|to|is|are|with|bus|route|stop|schedule)\b"`.
  - If diacritic_count >= 2 → `"lv"`. Else if stopword_hits >= 2 → `"en"`. Else `"lv"` (default).
- `_check_language_match(response, result, ctx)`:
  - If `ctx.user_message` is None → skip.
  - Compare detected languages; if different, append `Issue(check_name="language_match", severity="error", description="Response language does not match the user's language ({lang_user} → {lang_resp}).")`.

**Validation:** per-file checks.

---

### Step 8 — Severity-based retry filter in `correction.py`

`UPDATE app/core/agents/correction.py`:

1. Replace `_NON_RETRYABLE_PREFIXES` and `_retryable_warnings()` with:
   ```python
   def _retryable_issues(issues: list[Issue]) -> list[Issue]:
       """Return only error-severity issues. Warnings are footnote-only."""
       return [i for i in issues if i.severity == "error"]
   ```
2. Change `_safe_validate` signature to accept and forward a `ValidationContext`:
   ```python
   @staticmethod
   def _safe_validate(response: str, ctx: ValidationContext) -> ValidationResult:
       try:
           return validate_transit_response(response, ctx)
       except Exception:
           logger.error("agent.correction.failed", exc_info=True)
           return ValidationResult(is_valid=True, issues=[], warnings=[], sanitized_response=response)
   ```
3. Add `static_cache: Any | None = None` parameter to `run_with_correction()`. Build a `ValidationContext` once per attempt with:
   - `user_message=prompt` (the *original* user prompt, not the corrective retry prompt)
   - `static_cache=static_cache`
   - `tool_returns=extract_tool_returns(last_messages)`
4. Replace the call sites:
   ```python
   ctx = ValidationContext(
       user_message=prompt,
       static_cache=static_cache,
       tool_returns=extract_tool_returns(last_messages),
   )
   validation = self._safe_validate(last_output, ctx)
   issues = list(validation.issues)
   retryable = _retryable_issues(issues)
   ```
5. Update `CorrectedResult` to optionally carry `issues: list[Issue]` alongside `warnings: list[str]` (for downstream metrics in AI-5.3). Keep `warnings` populated as the description list to avoid breaking `service.py`.
6. `_build_correction_prompt_text(failed_response, retryable_issues)` builds the bullet list from `i.description for i in retryable_issues`. Update its signature accordingly.
7. Imports: `from app.core.agents.validation import Issue, ValidationContext, ValidationResult, extract_tool_returns, validate_transit_response`.

**Validation:**
```bash
uv run ruff format app/core/agents/correction.py && \
uv run ruff check --fix app/core/agents/correction.py && \
uv run pyright app/core/agents/correction.py && \
uv run mypy app/core/agents/correction.py
```

---

### Step 9 — Service-side wiring (`service.py`)

`UPDATE app/core/agents/service.py`:

1. Before calling the correction loop, fetch the static cache once:
   ```python
   from app.core.agents.tools.transit.static_store import get_static_store
   try:
       static_cache = await get_static_store(self._deps.db_session_factory, settings)
   except Exception:
       static_cache = None  # fail-open: validation gracefully degrades
   ```
2. Pass `static_cache=static_cache` into `self._correction_loop.run_with_correction(...)`.
3. In the **else** branch (loop disabled, `service.py:240-256`), build the same `ValidationContext` from `result.all_messages()` and pass it:
   ```python
   ctx = ValidationContext(
       user_message=current_prompt,
       static_cache=static_cache,
       tool_returns=extract_tool_returns(list(result.all_messages())),
   )
   ```
4. Update the post-call validation block (`service.py:267-271`):
   ```python
   if correction_warnings is None:
       validation = validate_transit_response(response_content, ctx)
       warnings_to_render = list(validation.warnings)
   else:
       warnings_to_render = correction_warnings
   ```
5. Footnote rendering (`service.py:273-280`) is **unchanged** — it iterates `warnings_to_render: list[str]`.
6. Complex tier (`service.py:203-221`) is unchanged. AI-5.2 does not extend pipeline validation; that's AI-5.3 scope.

**Validation:**
```bash
uv run ruff format app/core/agents/service.py && \
uv run ruff check --fix app/core/agents/service.py && \
uv run pyright app/core/agents/service.py && \
uv run mypy app/core/agents/service.py
```

---

### Step 10 — Tests: `test_validation.py` (new file, 12+ tests)

`CREATE app/core/agents/tests/test_validation.py`:

File header (anti-pattern compliance):
```python
"""Unit tests for app/core/agents/validation.py extended QA checks (AI-5.2)."""
from __future__ import annotations

from app.core.agents.tools.transit.static_cache import (
    GTFSStaticCache,
    RouteInfo,
    StopInfo,
)
from app.core.agents.validation import (
    Issue,
    ToolReturnRecord,
    ValidationContext,
    ValidationResult,
    validate_transit_response,
)
```

Helpers:
```python
def _make_static_cache() -> GTFSStaticCache:
    cache = GTFSStaticCache()
    cache.routes = {
        "bus_22": RouteInfo(route_id="bus_22", route_short_name="22",
                            route_long_name="Centrs - Jugla", route_type=3),
        "bus_3": RouteInfo(route_id="bus_3", route_short_name="3",
                           route_long_name="Imanta - Centrs", route_type=3),
    }
    cache.stops = {
        "s1": StopInfo(stop_id="s1", stop_name="Brīvības iela",
                       stop_lat=56.95, stop_lon=24.10),
        "s2": StopInfo(stop_id="s2", stop_name="Stacijas laukums",
                       stop_lat=56.94, stop_lon=24.12),
    }
    return cache

def _ctx(**kwargs: object) -> ValidationContext:
    return ValidationContext(**kwargs)  # type-checker via dataclass init
```

Test cases (each `def test_*() -> None`):

| # | Test name | Asserts |
|---|---|---|
| 1 | `test_route_existence_known_route_no_issue` | "Route 22 leaves at 8:00" + cache → no issues |
| 2 | `test_route_existence_unknown_route_emits_error` | "Route 999 leaves at 8:00" + cache → 1 issue, `check_name="route_existence"`, `severity="error"` |
| 3 | `test_route_existence_no_cache_skips_check` | "Route 999 leaves" with `ctx.static_cache=None` → no route_existence issue |
| 4 | `test_stop_existence_known_stop_no_issue` | "pietura Brīvības iela" + cache → no issue |
| 5 | `test_stop_existence_unknown_stop_emits_warning` | "pietura Vecpilsēta" + cache → 1 issue, `severity="warning"` |
| 6 | `test_time_consistency_valid_time_no_issue` | "Departs at 14:30" → no issue |
| 7 | `test_time_consistency_impossible_minute_emits_error` | "Arrives at 14:75" → 1 issue, error |
| 8 | `test_time_consistency_overflow_hour_emits_error` | "Departs at 25:30" → 1 issue, error |
| 9 | `test_citation_grounding_valid_citation_no_issue` | response cites doc 42, tool_returns include `[{"document_id": 42}]` → no issue |
| 10 | `test_citation_grounding_unground_citation_emits_error` | response cites doc 99, tool_returns include `[{"document_id": 42}]` → 1 issue, error |
| 11 | `test_citation_grounding_no_search_tool_skips_check` | response cites doc 99, no search_knowledge tool returns → no issue (fail-open) |
| 12 | `test_language_match_lv_to_lv_no_issue` | user "Kad pienāk autobuss?" → response "Maršruts 22 pienāk plkst. 08:00" → no issue |
| 13 | `test_language_match_lv_to_en_emits_error` | user "Kad pienāk autobuss?" → response "Bus route 22 arrives at 08:00" → 1 issue, error |
| 14 | `test_stale_data_per_response_old_timestamp_emits_warning` | tool_return `{"timestamp": time.time() - 600}` for `query_bus_status` → 1 issue, warning |
| 15 | `test_stale_data_per_response_fresh_timestamp_no_issue` | tool_return `{"timestamp": time.time() - 30}` → no stale_data issue |
| 16 | `test_existing_route_plausibility_now_returns_error_severity` | "Route 1500 status" → issue with `severity="error"`, `check_name="route_plausibility"` |
| 17 | `test_validation_result_is_valid_false_when_any_issue` | any error issue → `result.is_valid is False` |
| 18 | `test_warnings_field_mirrors_issue_descriptions` | confirm `result.warnings == [i.description for i in result.issues]` (backward compat) |

All tests are `-> None`, all helper functions are `-> ReturnType`. No `type: ignore` (use `# pyright: reportPrivateUsage=false` only at file head if introspecting `_check_*` privates — prefer the public `validate_transit_response` for orchestration).

**Validation:**
```bash
uv run ruff format app/core/agents/tests/test_validation.py && \
uv run ruff check --fix app/core/agents/tests/test_validation.py && \
uv run pyright app/core/agents/tests/test_validation.py && \
uv run mypy app/core/agents/tests/test_validation.py && \
uv run pytest app/core/agents/tests/test_validation.py -v
```

---

### Step 11 — Tests: severity-based retry semantics in `test_correction.py`

`UPDATE app/core/agents/tests/test_correction.py`:

Add 3 tests:
1. `test_error_severity_issue_triggers_retry` — fake validator returns one `Issue(severity="error")` on first call, clean on second → `rounds_used == 2`, `corrected is True`.
2. `test_warning_severity_issue_does_not_retry` — fake validator returns one `Issue(severity="warning")` → `rounds_used == 1`, `corrected is False`, warning preserved in `corrected.warnings`.
3. `test_mixed_severity_only_errors_block` — fake validator returns one error + one warning on first call, clean on second → `rounds_used == 2`, both descriptions persisted on first attempt's residual.

Existing tests that hard-code `_NON_RETRYABLE_PREFIXES` or assert on warning string prefixes must be updated to assert on severity instead. Verify by greping for `_NON_RETRYABLE_PREFIXES` and `cached data` in the test file.

**Validation:**
```bash
uv run pytest app/core/agents/tests/test_correction.py -v
```

---

### Step 12 — Full quality gate

```bash
uv run ruff format app/core/agents/ && \
uv run ruff check --fix app/core/agents/ && \
uv run pyright app/core/agents/ && \
uv run mypy app/core/agents/ && \
uv run pytest app/core/agents/tests/ -v && \
make security-audit-quick
```

Expect:
- `pyright app/core/agents/` → ≤ 5 errors (one fewer than baseline 6, since validation.py L76 was fixed)
- `mypy app/core/agents/` → ≤ 3 errors (unchanged baseline)
- `pytest app/core/agents/tests/` → all green, including the new ~18 validation tests + 3 correction tests

## Preflight Warnings

1. **`from app.core.agents.tools.transit.static_cache import GTFSStaticCache`** in `validation.py` would create a circular-import risk if static_cache.py ever imports from validation.py. Mitigation: type-only import via `if TYPE_CHECKING:` and use `Any` in the runtime dataclass field annotation. Already specified in Step 1.
2. **`pydantic_ai.messages.ToolReturnPart`** — confirm exact import path during Step 1; pydantic_ai has shifted these between minor versions. If unavailable, fall back to duck-typing on `hasattr(part, "tool_name")` and `hasattr(part, "content")`.
3. **`extract_tool_returns()` JSON parsing** — agent tools return JSON-encoded strings. Wrap parse in `try/except (json.JSONDecodeError, TypeError)` → return raw content. No KeyError tolerance assumptions in downstream check_*.
4. **Module-level state pollution in tests** — `last_stale_data_timestamp` is global. Tests touching stale data must reset it in a fixture (`monkeypatch.setattr(validation, "last_stale_data_timestamp", 0.0)`).
5. **`_LATVIAN_DIACRITICS` map** — many entries currently map `"x" → "x"` (no-op). Don't refactor that map in this plan; it would scope-creep into AI-5.4. Skip-noop branch in `_check_latvian_diacritics` already handles it.
6. **Anti-pattern Rule 28**: every empty list literal in the new dataclasses MUST be annotated. Use `field(default_factory=lambda: list[Issue]())`, NOT `field(default_factory=list)`.
7. **Anti-pattern Rule 7**: every test helper function in `test_validation.py` MUST have a return type annotation, even simple ones (`def _make_static_cache() -> GTFSStaticCache`).
8. **Anti-pattern Rule 26**: every test function MUST have `-> None`.
9. **Anti-pattern Rule 14**: NO `# type: ignore` in test files. Use `# pyright: reportPrivateUsage=false` at file head only if introspecting private names.

## Security Checklist (CTX-AGENT)

- [x] No new endpoint, no new credential, no new external I/O
- [x] All validators are READ-ONLY (no DB writes, no HTTP calls, no file I/O)
- [x] Validator exceptions caught fail-open in `_safe_validate` (matches AI-5.1) — never blocks dispatcher
- [x] Tool result parsing wrapped in `try/except` — malformed payload skips the check, never raises
- [x] Regex iterations bounded to 200 per check (defense against pathological output)
- [x] No credential exposure in Issue descriptions (we only echo back the agent's own text)
- [x] Citation grounding does NOT cross-reference the actual `documents` table — it only verifies the citation appeared in the agent's own tool calls (no IDOR risk)
- [x] Static cache passed by reference; validators only read `.routes` / `.stops` dicts

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `pyright app/core/agents/` ≤ 5 errors (was 6 — validation.py L76 fixed)
- [ ] `mypy app/core/agents/` ≤ 3 errors (unchanged)
- [ ] New file `app/core/agents/tests/test_validation.py` exists with ≥ 12 tests passing
- [ ] `app/core/agents/tests/test_correction.py` updated with severity-based assertions; all tests green
- [ ] `app/core/agents/correction.py` no longer references `_NON_RETRYABLE_PREFIXES`
- [ ] `validate_transit_response()` accepts optional `ValidationContext` and is backward compatible (`validate_transit_response(text)` still works without context — graceful skip on existence/citation/language checks)
- [ ] `service.py` footnote rendering UNCHANGED (warnings_to_render is still `list[str]`)
- [ ] Self-correction loop confirmed: error issue → retry; warning issue → footnote only
- [ ] No `# type: ignore` introduced anywhere
