# Plan: AI-7.2 — Eval Runner + Trace Collection

## Context

AI-7.1 (commit `06e0a1b`) landed 30 synthetic `EvalCase` fixtures plus a fail-open YAML
loader under `app/core/agents/evals/`. **There is no runner yet** — the cases are
parsed and validated, but nothing executes them against the live agent.

AI-7.2 builds the runner: a CLI that loads cases for one or more domains, invokes
the matching per-domain `BaseAgentService` subclass, captures the full interaction
(prompt, response, tool calls, tool results, latency, errors), and writes JSONL
trace files under `evals/traces/`. These traces are the input artifact for
AI-7.3 (binary LLM judges) and for manual regression review, so the schema must be
stable and grep-friendly.

**Key design constraints:**
1. The runner must **not** break when the agent or one of its tools raises — an
   individual case failure is written as a trace with `error` populated and the
   suite continues. Fail-open matches AI-7.1 loader semantics.
2. Traces must capture tool calls and tool results — these already exist inside
   the `_PipelineOutcome.messages` list but are **not** exposed through the public
   `chat()` response. A small, non-behavioral refactor of `BaseAgentService` is
   required to surface them cleanly.
3. The runner is a script, not an endpoint. No HTTP layer, no rate limiting, no
   quota — but it must instantiate a real `UnifiedDeps` through the existing
   per-agent singleton so DB-backed and HTTP-backed tools work end-to-end.

## Security Context Assessment

Triggered contexts from `_shared/security-contexts.md`:

- **CTX-AGENT** (primary) — feature calls agent tools. Requirements:
  - No raw prompts in INFO/WARNING logs — only `case_id` + counts, mirroring
    `evals/loader.py` and `router.py` (uses 12-char `prompt_hash`).
  - Tool responses may include PII from the transit DB. Traces are written to
    `evals/traces/` which is **git-ignored** (new `.gitignore` entry).
  - No credential exposure — the runner must not log settings, DB URLs, API keys.
- **CTX-INPUT** (secondary) — CLI `--suite` flag. Requirements:
  - `--suite` must be validated against the closed set `{transit, knowledge, vault, all}`;
    `argparse.ArgumentParser.add_argument(choices=...)` handles this.
  - Output directory must be path-sandboxed (`Path.resolve().is_relative_to()`)
    the same way `loader.py` sandboxes `cases_root`.
- **CTX-INFRA** (low) — new `make eval` target. No secrets, uses `uv run` per
  existing pattern (`make rechunk` @ `Makefile:95`).

**Not triggered:** CTX-AUTH, CTX-RBAC, CTX-FILE (no upload), CTX-INFRA at a
Docker/CORS level.

## Research Summary

### Existing `app/core/agents/evals/` — already in place from AI-7.1

| File | Role | Lines |
|---|---|---|
| `app/core/agents/evals/schemas.py` | `EvalCase`, `QualityCriterion`, `KNOWN_TOOLS`, `VALID_DOMAINS`, `REQUIRED_CRITERIA_COUNT` — all frozen dataclasses | 1–120 |
| `app/core/agents/evals/loader.py` | `load_eval_cases(domain)`, `load_all_cases()` — fail-open, path-sandboxed, returns lists of `EvalCase` | 1–287 |
| `app/core/agents/evals/cases/{transit,knowledge,vault}.yaml` | 15 + 10 + 5 = 30 synthetic cases | — |
| `app/core/agents/evals/__init__.py` | Currently just a docstring — runner re-exports go here | 1–2 |

### Agent invocation — how to actually run a case

**Per-domain agent singletons** live in `app/core/agents/agents/registry.py:27–56`:

```python
def get_agent_by_name(name: AgentName) -> BaseAgentService:
    # name ∈ {"unified", "transit", "knowledge", "vault"}
    # unified → get_agent_service() (existing AgentService)
    # others → lazy-instantiated TransitAgent/KnowledgeAgent/VaultAgent
```

The runner **must** route each case to `get_agent_by_name(case.expected_domain)`
— that is the ground-truth domain for eval purposes. Using the heuristic router
would conflate "did the router classify correctly?" with "did the agent answer
correctly?".

**Public API** — `BaseAgentService.chat(request: ChatCompletionRequest) -> ChatCompletionResponse`
at `app/core/agents/base.py:158–315`. This already computes an `AgentResult`
(AI-6.5) internally for the confidence re-route gate at lines 238–302, but
**discards it after building the response envelope at line 305**. The trace
runner needs the discarded metadata: `confidence`, `tools_used`, `warnings`.

**Non-behavioral refactor required** — add a new public method:

```python
async def chat_with_trace(
    self, request: ChatCompletionRequest
) -> tuple[ChatCompletionResponse, AgentResult]:
    """Like chat() but also returns the internal AgentResult (AI-7.2)."""
```

and have `chat()` delegate to it (`response, _ = await self.chat_with_trace(request); return response`).
This is a pure refactor — no observable change for existing HTTP callers and no
new dependencies.

### Tool call / tool return extraction

`app/core/agents/validation.py:195–230` already provides `extract_tool_returns()`
that walks `_PipelineOutcome.messages` and returns `[ToolReturnRecord(tool_name, payload)]`.
The runner re-uses this. Tool **call** names are already aggregated in
`_PipelineOutcome.tools_used: tuple[str, ...]` at `base.py:116–137`; the runner
captures both.

### Logging taxonomy (follow `docs/logging-standard.md`, `domain.component.action_state`)

New events:
- `agent.evals.runner.suite_started` — `{suite, total_cases, output_path}`
- `agent.evals.runner.case_started` — `{case_id, domain}`
- `agent.evals.runner.case_completed` — `{case_id, latency_ms, tools_count, had_warnings}`
- `agent.evals.runner.case_failed` — `{case_id, error_type}` (never the raw exception string if it could contain prompt echo)
- `agent.evals.runner.suite_completed` — `{suite, passed, failed, total_latency_ms, trace_path}`
- `agent.evals.runner.path_escaped` — if output dir escapes its root (CTX-INPUT)

Never log `prompt` or `response` content — only lengths and IDs.

### CLI / Makefile precedent

- `scripts/seed_fleet_data.py` — standalone script pattern, `if __name__ == "__main__": ...`.
- `Makefile:95–99` — `rechunk` target uses `uv run python scripts/rechunk_documents.py`.
- The task spec asks for `python -m app.core.agents.evals.runner --suite transit` which
  works if `runner.py` has a module-level `if __name__ == "__main__":` block (no
  `__main__.py` needed — `python -m pkg.mod` runs `pkg/mod.py` as `__main__` directly).

### Database / deps access

Per-domain agents already carry a `UnifiedDeps` via their singletons — the runner
does **not** need to create its own `get_db_context()` session. Calling
`get_agent_by_name("transit")` returns an agent with a live HTTP client and DB
session factory, exactly as if it were serving an HTTP request. The runner
must still call `await close_all_agents()` (from `registry.py:59`) in a `try/finally`
so the lifespan-style HTTP clients are closed cleanly on exit.

### `evals/` directory convention

No top-level `evals/` folder exists yet. The spec calls for
`evals/traces/{suite}_{timestamp}.jsonl`, which the runner will create relative
to the repo root (resolved via `Path(__file__).parents[5]` → verified at plan
time, or via `Path.cwd()`). Add `evals/traces/` to `.gitignore` so trace runs
don't pollute git status.

## Test Landscape

Templates and fixtures:

| File | Use for | Key pattern |
|---|---|---|
| `app/core/agents/tests/conftest.py:84–104` | `make_eval_case()` factory, `tmp_eval_dir` fixture | Build synthetic cases for runner tests |
| `app/core/agents/tests/test_eval_loader.py:1–325` | Path-sandboxing + fail-open semantics | Mirror for runner argparse + `--output-dir` validation |
| `app/core/agents/tests/test_agent_result.py:94–264` | `_FakeBudgetAgent(BaseAgentService)` subclass test pattern | Mock `_execute` to return a fixed `_PipelineOutcome` so the runner drives the full pipeline without an LLM |
| `app/core/agents/tests/test_correction.py:18–30` | `_fake_run_result(output)` + `AsyncMock` agent | Useful for any test that needs a real pydantic-ai `RunResult`-shaped object |

**conftest layout for the new test file:**
- Import `make_eval_case` and the `_FakeBudgetAgent`-style helper directly.
- Use `tmp_path / "traces"` for all JSONL output — never write to the real
  `evals/traces/`.
- `@pytest.mark.asyncio` — `pyproject.toml` sets `asyncio_mode = "auto"` so
  plain `async def test_*` would also work, but explicit marker is the local
  convention.

**No integration marker.** All runner unit tests mock the agent pipeline via a
concrete `BaseAgentService` test-double; no DB, no HTTP, no Docker needed.

## Type Check Baseline

From the pyright/mypy baseline agent (target = `app/core/agents/evals/`):

- `app/core/agents/evals/` — **pyright 0 errors, mypy 0 errors** (clean module).
- `app/core/agents/` wider — pyright 5 errors (pre-existing, `tools/transit/client.py:193`,
  `tools/transit/static_store.py:149–150`, `pipeline.py:136`), mypy 3 errors in the
  same files. **These are not related to AI-7.2 and must not be addressed here.**

**New acceptance bar:** `uv run pyright app/core/agents/evals/` must remain at
**0 errors, 0 warnings** after the runner lands. `uv run mypy app/core/agents/evals/`
must remain at **0 errors**. The wider `app/core/agents/` baseline must not
regress: ≤5 pyright errors, ≤3 mypy errors.

## Files to Create / Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/evals/runner.py` | `EvalTrace` dataclass, `EvalRunner` class, CLI entrypoint |
| UPDATE | `app/core/agents/evals/__init__.py` | Re-export `EvalRunner`, `EvalTrace` |
| UPDATE | `app/core/agents/base.py` | Add `chat_with_trace()`; have `chat()` delegate to it |
| CREATE | `app/core/agents/tests/test_eval_runner.py` | Unit tests for runner (fake agent, tmp_path traces) |
| UPDATE | `app/core/agents/tests/test_base.py` | Add one test asserting `chat_with_trace()` returns `(ChatCompletionResponse, AgentResult)` and `chat()` still returns only the response |
| UPDATE | `Makefile` | Add `eval` target mirroring `rechunk` (line 95) |
| UPDATE | `.gitignore` | Ignore `evals/traces/*.jsonl` so runs don't pollute git status |
| UPDATE | `app/core/agents/CLAUDE.md` | One-line mention of `runner.py` in the `evals/` bullet |

No new files outside the evals module. No DB migration. No dependency changes
(`yaml` already present from loader; `argparse`, `json`, `dataclasses`, `asyncio`
are stdlib).

## Implementation Steps

### Step 1 — Refactor `BaseAgentService.chat()` to expose trace metadata

**File:** `app/core/agents/base.py`

Split the current `chat()` (lines 158–315) into two methods:

```python
async def chat_with_trace(
    self, request: ChatCompletionRequest
) -> tuple[ChatCompletionResponse, AgentResult]:
    """Run the full chat pipeline and return both the envelope and metadata.

    Identical semantics to :meth:`chat` — this is the implementation that
    ``chat`` delegates to. Returning the internal ``AgentResult`` exposes
    ``confidence``, ``warnings``, and ``tools_used`` to observability
    consumers (AI-7.2 eval runner, future audit tooling).

    Args:
        request: Parsed ``ChatCompletionRequest`` from the HTTP layer or a
            script.

    Returns:
        ``(response, result)`` — the OpenAI-compatible envelope and the
        frozen ``AgentResult`` built after any confidence re-route.
    """
    # <... move the existing body of chat() here, but instead of
    #  `return response`, do `return response, result` ...>

async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
    """Run the full chat pipeline for one request.

    Returns only the OpenAI-compatible envelope. For pipeline metadata
    (confidence, tools_used, warnings) call :meth:`chat_with_trace`.
    """
    response, _result = await self.chat_with_trace(request)
    return response
```

**Critical detail — anti-pattern #5/#9:** do NOT leave the unused local variable
named `_result` without the underscore, Ruff F841 will flag it. The leading `_`
is required. Alternatively use `response, _ = await self.chat_with_trace(request)`.

**Do not touch:**
- The `agent.chat_started` / `agent.chat_completed` log calls — they stay inside
  `chat_with_trace` because that is where the pipeline runs.
- The `AgentExecutionError` wrapping — same, stays in `chat_with_trace`.
- The confidence re-route gate logic — stays put, untouched.

**Validation:**
```bash
uv run ruff format app/core/agents/base.py
uv run ruff check --fix app/core/agents/base.py
uv run pyright app/core/agents/base.py
uv run mypy app/core/agents/base.py
uv run pytest app/core/agents/tests/test_base.py app/core/agents/tests/test_agent_result.py -x -q
```

All existing base/agent_result tests must pass unchanged — this is a pure
refactor.

### Step 2 — Add `chat_with_trace` regression test in `test_base.py`

**File:** `app/core/agents/tests/test_base.py`

Append one test (use whatever minimal `BaseAgentService` test double already exists
in that file — a fresh subclass is fine if there isn't one):

```python
@pytest.mark.asyncio
async def test_chat_with_trace_returns_response_and_agent_result() -> None:
    """chat_with_trace exposes the AgentResult chat() discards."""
    svc = _FakeAgent(outcomes=[_make_outcome(text="ok", tools_used=("query_bus_status",))])
    request = _make_request("hello")

    response, result = await svc.chat_with_trace(request)

    assert response.choices[0].message.content == "ok"
    assert isinstance(result, AgentResult)
    assert result.tools_used == ("query_bus_status",)
    assert result.domain in VALID_DOMAINS
```

Also confirm the backward-compat shim: `response = await svc.chat(request)` still
works and returns only the response object.

**Validation:**
```bash
uv run pytest app/core/agents/tests/test_base.py::test_chat_with_trace_returns_response_and_agent_result -x -q
```

### Step 3 — Create `EvalTrace` dataclass + JSONL serializer

**File:** `app/core/agents/evals/runner.py`

```python
"""Eval runner + trace collection (AI-7.2).

CLI that runs synthetic EvalCases against the live per-domain agents and
writes one JSONL trace file per suite under ``evals/traces/``. The runner
is fail-open: one case raising never aborts the suite, and the runner
never logs prompt/response content — only case IDs and counts.
"""
# pyright: reportUnknownMemberType=false
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import time
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

from app.core.agents.agent_result import AgentResult
from app.core.agents.agents.registry import close_all_agents, get_agent_by_name
from app.core.agents.evals.loader import load_eval_cases
from app.core.agents.evals.schemas import VALID_DOMAINS, EvalCase
from app.core.agents.schemas import (
    AgentName,
    ChatCompletionRequest,
    ChatMessage,
)
from app.core.agents.validation import ToolReturnRecord, extract_tool_returns
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_OUTPUT_DIR: Final[Path] = Path("evals/traces")
_SUITE_CHOICES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault", "all")


@dataclass(frozen=True, slots=True)
class EvalTrace:
    """One line of the JSONL trace output for one EvalCase run.

    Attributes:
        case_id: Stable ID from ``EvalCase.id`` (e.g. ``transit_001``).
        domain: The domain the case was routed to (``transit``/``knowledge``/``vault``).
        prompt: The exact prompt fed to the agent.
        response: Final rendered response text (post ``_post_process``).
            Empty string on error.
        tools_used: Tool function names the agent invoked.
        tool_returns: Per-tool JSON-serializable payloads from
            ``extract_tool_returns``. Non-serializable payloads are coerced
            to ``str``.
        confidence: ``AgentResult.confidence`` or ``None`` when unmeasured.
        warnings: QA warnings from validation; empty tuple on clean runs.
        latency_ms: Wall-clock time from request start to response ready.
        error: ``None`` on success, otherwise ``"<ExcType>: <str(exc)>"``.
        timestamp: ISO-8601 UTC timestamp captured at case start.
    """

    case_id: str
    domain: str
    prompt: str
    response: str
    tools_used: tuple[str, ...]
    tool_returns: tuple[dict[str, Any], ...]
    confidence: float | None
    warnings: tuple[str, ...]
    latency_ms: float
    error: str | None
    timestamp: str


def _coerce_tool_return(record: ToolReturnRecord) -> dict[str, Any]:
    """Return a JSON-serializable dict for one tool return.

    ``record.payload`` may be an arbitrary object graph from the tool.
    We try ``json.dumps`` first, falling back to ``str()`` so the trace
    never dies on a non-serializable payload.
    """
    try:
        json.dumps(record.payload, ensure_ascii=False, default=str)
        payload: Any = record.payload
    except (TypeError, ValueError):
        payload = str(record.payload)
    return {"tool_name": record.tool_name, "payload": payload}


def _trace_to_jsonl_line(trace: EvalTrace) -> str:
    """Serialize one EvalTrace as a single-line JSON string (no trailing newline)."""
    data = asdict(trace)
    # asdict turns tuples into lists, which is correct for JSONL.
    return json.dumps(data, ensure_ascii=False, default=str)
```

**Anti-pattern callouts:**
- **#23 / pyright file-level directive** — `reportUnknownMemberType=false` at top.
  `extract_tool_returns` uses `getattr(message, "parts", None)` which pyright
  flags with `Unknown` types from pydantic-ai. The directive is scoped to this
  one file.
- **#1** — never `assert` — frozen dataclass + `__post_init__` OR `if ... raise ValueError`
  (not applicable here; `EvalTrace` has no invariants beyond shape).
- **#8** — no EN DASH in strings, only `-`.
- **#33** — `tool_returns` uses `dict[str, Any]` not `dict[str, object]` because
  downstream consumers (`json.dumps`) need `Any`.
- **#44** — no URL logging (runner never touches URLs anyway).

**Validation:**
```bash
uv run ruff format app/core/agents/evals/runner.py
uv run ruff check --fix app/core/agents/evals/runner.py
uv run pyright app/core/agents/evals/runner.py
uv run mypy app/core/agents/evals/runner.py
```

### Step 4 — Implement `EvalRunner` class

**File:** `app/core/agents/evals/runner.py` (append to Step 3)

```python
@dataclass(slots=True)
class _SuiteSummary:
    """In-memory counters for the human-readable end-of-run summary."""

    suite: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    trace_path: Path | None = None


class EvalRunner:
    """Runs EvalCases through the live per-domain agents and writes JSONL traces.

    The runner is fail-open: an exception inside ``_run_case`` produces an
    ``EvalTrace`` with ``error`` populated and the suite continues. Only
    infrastructure-level problems (e.g. unable to create the output
    directory) will abort the run.

    Example:
        >>> runner = EvalRunner(output_dir=Path("evals/traces"))
        >>> traces = await runner.run_suite("transit")
        >>> len(traces)
        15
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize the runner.

        Args:
            output_dir: Where to write JSONL trace files. Defaults to
                ``evals/traces`` relative to CWD. The directory is created
                if missing; path is sandboxed to its resolved self to
                reject symlink escapes.
        """
        self._output_dir = (output_dir or _DEFAULT_OUTPUT_DIR).resolve()

    async def run_suite(self, suite: str) -> list[EvalTrace]:
        """Run one suite (``transit``/``knowledge``/``vault``) or all three.

        Args:
            suite: One of ``_SUITE_CHOICES``. ``all`` runs the three domain
                suites sequentially and writes one JSONL file per domain.

        Returns:
            Flat list of all traces produced in this invocation.

        Raises:
            ValueError: If ``suite`` is not in ``_SUITE_CHOICES``.
            OSError: If the output directory cannot be created.
        """
        if suite not in _SUITE_CHOICES:
            msg = f"suite must be one of {_SUITE_CHOICES}; got {suite!r}"
            raise ValueError(msg)

        self._output_dir.mkdir(parents=True, exist_ok=True)

        domains = ("transit", "knowledge", "vault") if suite == "all" else (suite,)
        all_traces: list[EvalTrace] = []
        summaries: list[_SuiteSummary] = []

        try:
            for domain in domains:
                summary = _SuiteSummary(suite=domain)
                cases = load_eval_cases(domain)
                summary.total = len(cases)

                logger.info(
                    "agent.evals.runner.suite_started",
                    suite=domain,
                    total_cases=summary.total,
                    output_dir=str(self._output_dir),
                )

                traces = await self._run_cases(cases, domain)
                trace_path = self._write_traces(traces, suite_name=domain)
                summary.trace_path = trace_path

                for trace in traces:
                    summary.total_latency_ms += trace.latency_ms
                    if trace.error is None:
                        summary.passed += 1
                    else:
                        summary.failed += 1

                logger.info(
                    "agent.evals.runner.suite_completed",
                    suite=domain,
                    passed=summary.passed,
                    failed=summary.failed,
                    total_latency_ms=summary.total_latency_ms,
                    trace_path=str(trace_path),
                )

                all_traces.extend(traces)
                summaries.append(summary)
        finally:
            # AI-6.2: close per-domain HTTP clients. The unified AgentService
            # is closed by close_agent_service() in app.main lifespan; here we
            # only own the three domain singletons spun up inside the runner.
            await close_all_agents()

        self._print_summary(summaries)
        return all_traces

    async def _run_cases(
        self, cases: list[EvalCase], domain: str
    ) -> list[EvalTrace]:
        traces: list[EvalTrace] = []
        for case in cases:
            trace = await self._run_case(case, domain)
            traces.append(trace)
        return traces

    async def _run_case(self, case: EvalCase, domain: str) -> EvalTrace:
        """Execute one case through the matching domain agent (fail-open)."""
        agent = get_agent_by_name(_as_agent_name(domain))
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content=case.prompt)],
            agent=_as_agent_name(domain),
        )

        timestamp = _dt.datetime.now(_dt.UTC).isoformat()
        logger.info("agent.evals.runner.case_started", case_id=case.id, domain=domain)

        start = time.perf_counter()
        try:
            response, result = await agent.chat_with_trace(request)
        except Exception as exc:  # noqa: BLE001 — fail-open by design
            latency_ms = (time.perf_counter() - start) * 1000.0
            logger.warning(
                "agent.evals.runner.case_failed",
                case_id=case.id,
                error_type=type(exc).__name__,
            )
            return EvalTrace(
                case_id=case.id,
                domain=domain,
                prompt=case.prompt,
                response="",
                tools_used=(),
                tool_returns=(),
                confidence=None,
                warnings=(),
                latency_ms=latency_ms,
                error=f"{type(exc).__name__}: {exc}",
                timestamp=timestamp,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0

        # Tool returns live in the pipeline outcome messages; the AgentResult
        # wrapper does not carry them, so re-extract from response envelope's
        # last pipeline hop via the agent's internals.
        # AgentResult.tools_used is the canonical tool-call name list; to
        # capture tool payloads we re-run extraction on `response` by pulling
        # the messages from the internal `_last_messages` slot — BUT that does
        # not exist yet. Simpler: extend chat_with_trace return to a 3-tuple
        # including raw messages, OR have _execute stash them on the AgentResult
        # via a new field. We choose the former — see Step 1 refinement.
        tool_returns = _collect_tool_returns(result)

        logger.info(
            "agent.evals.runner.case_completed",
            case_id=case.id,
            latency_ms=round(latency_ms, 2),
            tools_count=len(result.tools_used),
            had_warnings=bool(result.warnings),
        )

        return EvalTrace(
            case_id=case.id,
            domain=domain,
            prompt=case.prompt,
            response=response.choices[0].message.content,
            tools_used=result.tools_used,
            tool_returns=tool_returns,
            confidence=result.confidence,
            warnings=result.warnings,
            latency_ms=latency_ms,
            error=None,
            timestamp=timestamp,
        )
```

**IMPORTANT refinement:** `AgentResult` does **not** currently carry the raw
`messages: list[ModelMessage]` — so we cannot call `extract_tool_returns()` from
the runner. Two clean options:

**Option A (chosen)** — extend the `chat_with_trace` return to a **3-tuple**
`(ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...])` and have
`chat_with_trace` call `extract_tool_returns(outcome.messages)` at the end.
This keeps `AgentResult` unchanged and scope-limits the new data to the runner
path.

**Option B (rejected)** — add `tool_returns: tuple[ToolReturnRecord, ...]` to
`AgentResult`. Rejected because `AgentResult` is a public interface used by the
reroute gate and possibly future audit tooling; expanding it for one consumer
is overreach, and `ToolReturnRecord` isn't currently exported from `validation.py`.

**Revised Step 1 signature:**

```python
async def chat_with_trace(
    self, request: ChatCompletionRequest
) -> tuple[ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...]]:
```

And in the revised body, after the (possibly retried) `_post_process` call:

```python
tool_returns = tuple(extract_tool_returns(outcome.messages))
# ... build response, build result ...
return response, result, tool_returns
```

The backward-compat `chat()` becomes:

```python
async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
    response, _result, _returns = await self.chat_with_trace(request)
    return response
```

Update the Step 3 test to unpack 3 values. Update `_collect_tool_returns()` below
to operate on the third element instead of the result:

```python
def _collect_tool_returns(
    records: tuple[ToolReturnRecord, ...],
) -> tuple[dict[str, Any], ...]:
    return tuple(_coerce_tool_return(r) for r in records)
```

And `_run_case` unpacks:

```python
response, result, tool_return_records = await agent.chat_with_trace(request)
...
tool_returns=_collect_tool_returns(tool_return_records),
```

**Continue `EvalRunner` class:**

```python
    def _write_traces(self, traces: list[EvalTrace], *, suite_name: str) -> Path:
        """Serialize traces as JSONL under ``<output_dir>/<suite>_<ts>.jsonl``.

        Path-sandboxed: after resolving, the output file must still be
        under ``self._output_dir`` or the method raises ``ValueError``.
        """
        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        out_path = (self._output_dir / f"{suite_name}_{stamp}.jsonl").resolve()
        if not out_path.is_relative_to(self._output_dir):
            logger.warning(
                "agent.evals.runner.path_escaped",
                path=str(out_path),
                root=str(self._output_dir),
            )
            msg = "output path escaped sandbox root"
            raise ValueError(msg)

        with out_path.open("w", encoding="utf-8") as fh:
            for trace in traces:
                fh.write(_trace_to_jsonl_line(trace))
                fh.write("\n")
        return out_path

    def _print_summary(self, summaries: list[_SuiteSummary]) -> None:
        """Print a human-readable summary to stdout (CLI UX only)."""
        for s in summaries:
            avg = (s.total_latency_ms / s.total) if s.total else 0.0
            print(
                f"[{s.suite}] {s.passed}/{s.total} passed, "
                f"{s.failed} failed, avg {avg:.0f}ms, "
                f"trace={s.trace_path}"
            )


def _as_agent_name(domain: str) -> AgentName:
    """Narrow a validated domain string to the ``AgentName`` literal type."""
    if domain not in ("transit", "knowledge", "vault"):
        msg = f"unexpected domain {domain!r}"
        raise ValueError(msg)
    return domain  # type: ignore[return-value]
```

**Anti-pattern #32** — the `type: ignore[return-value]` on `_as_agent_name` is
justified because `AgentName` is `Literal["unified","transit","knowledge","vault"]`
and pyright cannot narrow a `str` to a literal without runtime isinstance.
Validate by running pyright first to confirm the exact code is `return-value`
before committing the ignore.

**Validation:**
```bash
uv run ruff format app/core/agents/evals/runner.py
uv run ruff check --fix app/core/agents/evals/runner.py
uv run pyright app/core/agents/evals/runner.py
uv run mypy app/core/agents/evals/runner.py
```

### Step 5 — CLI entrypoint

**File:** `app/core/agents/evals/runner.py` (append)

```python
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.core.agents.evals.runner",
        description="Run synthetic EvalCases against the live VTV agents.",
    )
    parser.add_argument(
        "--suite",
        required=True,
        choices=_SUITE_CHOICES,
        help="Suite to run: transit, knowledge, vault, or all.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Directory to write JSONL trace files. Defaults to {_DEFAULT_OUTPUT_DIR}.",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    runner = EvalRunner(output_dir=args.output_dir)
    try:
        traces = await runner.run_suite(args.suite)
    except (OSError, ValueError) as exc:
        logger.error(
            "agent.evals.runner.aborted",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 2
    failed = sum(1 for t in traces if t.error is not None)
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["EvalRunner", "EvalTrace", "main"]
```

**Anti-pattern callouts:**
- **#5** — do not import `sys` for `sys.argv`; `argparse.parse_args(None)` already
  uses `sys.argv[1:]` by default.
- **#18 ARG001** — `argv` is used in both `_amain` and `main`, no unused args.
- **#42 / #43** — no file upload, no user-provided filenames in this path.
- **#37** — `except (OSError, ValueError)` is specific; no bare `except`.

**Validation:**
```bash
uv run python -m app.core.agents.evals.runner --help
# Must print the argparse help without importing the full agent stack twice
```

### Step 6 — Re-export from `__init__.py`

**File:** `app/core/agents/evals/__init__.py`

Replace the one-line docstring body with:

```python
"""Agent eval framework (AI-7.x)."""

from app.core.agents.evals.runner import EvalRunner, EvalTrace

__all__ = ["EvalRunner", "EvalTrace"]
```

**Validation:**
```bash
uv run python -c "from app.core.agents.evals import EvalRunner, EvalTrace; print('ok')"
```

### Step 7 — Unit tests for the runner

**File:** `app/core/agents/tests/test_eval_runner.py` (new)

Test cases (each `@pytest.mark.asyncio`, keep under 12 tests total, unit-only):

1. **`test_eval_runner_writes_jsonl_per_suite`** — patch `get_agent_by_name` to
   return a fake agent whose `chat_with_trace` returns `(fake_response, fake_result, ())`.
   Run `EvalRunner(output_dir=tmp_path).run_suite("transit")`. Assert:
   - One `transit_<ts>.jsonl` file exists under `tmp_path`.
   - Line count matches `load_eval_cases("transit")` count.
   - Each line parses as JSON and matches the `EvalTrace` shape.

2. **`test_eval_runner_records_tool_returns`** — the fake agent's
   `chat_with_trace` returns a `ToolReturnRecord("query_bus_status", {"delays": 2})`.
   Assert the JSONL line's `tool_returns[0]["tool_name"] == "query_bus_status"`
   and `payload == {"delays": 2}`.

3. **`test_eval_runner_captures_exceptions_as_error_traces`** — the fake agent
   raises `RuntimeError("boom")`. Assert `trace.error == "RuntimeError: boom"`,
   `trace.response == ""`, and the suite continues (no re-raise).

4. **`test_eval_runner_handles_non_json_tool_payload`** — fake tool return
   with `payload=object()`. Assert `_coerce_tool_return` coerces to `str` and
   the JSONL line is still valid JSON.

5. **`test_eval_runner_sandboxes_output_path`** — construct a runner with
   `output_dir=tmp_path`, then monkey-patch `_write_traces` to force a resolved
   path outside the sandbox (or use a symlink pointing outside). Assert the
   `path_escaped` log is emitted and `ValueError` is raised.

6. **`test_eval_runner_rejects_unknown_suite`** — `await runner.run_suite("foobar")`
   raises `ValueError` before any agent is instantiated.

7. **`test_eval_runner_suite_all_runs_three_domains`** — with a fake agent,
   `run_suite("all")` produces three JSONL files and the returned list covers
   all 30 cases.

8. **`test_eval_runner_calls_close_all_agents_in_finally`** — patch
   `close_all_agents` with `AsyncMock`. Run a successful suite and a failing
   suite (tempting `OSError` on mkdir by pointing at a file-not-dir). Assert
   `close_all_agents` is called in both branches.

9. **`test_cli_help_exits_zero`** — `main(["--help"])` — argparse raises
   `SystemExit(0)`, wrap in `pytest.raises(SystemExit)` and assert `exc.value.code == 0`.

10. **`test_cli_unknown_suite_exits_two`** — `main(["--suite", "foo"])` —
    argparse raises `SystemExit(2)`.

11. **`test_trace_to_jsonl_line_roundtrip`** — build an `EvalTrace`, serialize,
    re-parse with `json.loads`, assert key-level equality (tuples become lists).

**Test-side fake agent template** (using the `_FakeBudgetAgent` pattern from
`test_agent_result.py:94–135`):

```python
class _FakeEvalAgent(BaseAgentService):
    agent_name = "transit_agent_v2"

    def __init__(
        self,
        *,
        tools_used: tuple[str, ...] = (),
        tool_returns: tuple[ToolReturnRecord, ...] = (),
        raise_exc: BaseException | None = None,
    ) -> None:
        self._tools_used = tools_used
        self._tool_returns = tool_returns
        self._raise_exc = raise_exc

    async def chat_with_trace(  # type: ignore[override]
        self, request: ChatCompletionRequest
    ) -> tuple[ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...]]:
        if self._raise_exc is not None:
            raise self._raise_exc
        response = ChatCompletionResponse(
            model="fake-model",
            choices=[ChatCompletionChoice(message=ChatMessage(role="assistant", content="ok"))],
        )
        result = AgentResult(
            content="ok",
            confidence=0.9,
            warnings=(),
            tools_used=self._tools_used,
            domain="transit",
        )
        return response, result, self._tool_returns
```

**Anti-pattern #14** — the `# type: ignore[override]` on `chat_with_trace` is
needed because the fake skips the base implementation entirely. **Validate**
the exact error code with pyright before adding the comment (pattern #32):
run `uv run pyright app/core/agents/tests/test_eval_runner.py` first, read
the exact error code, then add the matching `type: ignore[...]`.

**Anti-pattern #26** — every test helper/test function must have a
`-> None` return annotation.

**Anti-pattern #30** — these new tests must not change existing tests'
assertions about `BaseAgentService` return types (the old `chat()` signature
is preserved; only `chat_with_trace` is new).

**Validation:**
```bash
uv run ruff format app/core/agents/tests/test_eval_runner.py
uv run ruff check --fix app/core/agents/tests/test_eval_runner.py
uv run pyright app/core/agents/tests/test_eval_runner.py
uv run pytest app/core/agents/tests/test_eval_runner.py -x -q
```

### Step 8 — Makefile target

**File:** `Makefile` — append a new section under `# === Knowledge base operations ===`
or next to `rechunk`:

```makefile
# === Agent evals (AI-7.x) ===

eval: ## Run eval suite (usage: make eval SUITE=transit|knowledge|vault|all)
	uv run python -m app.core.agents.evals.runner --suite $(or $(SUITE),transit)

eval-all: ## Run all three eval suites sequentially
	uv run python -m app.core.agents.evals.runner --suite all
```

**Validation:**
```bash
make help | grep -E "^(eval|eval-all)"
# Two lines output, descriptions present
```

Do **not** run `make eval` as part of validation — the live agents need settings
(Claude API key, DB) that may not be present in the dev shell. The `--help`
smoke test above plus the unit tests cover the runner code paths.

### Step 9 — `.gitignore`

**File:** `.gitignore` — add under an existing "generated" or "local state"
section (or append):

```
# AI-7.2 eval runs
evals/traces/*.jsonl
```

Use `*.jsonl` not `evals/traces/` so future non-JSONL artifacts (e.g. summary
TSVs in AI-7.3) are still tracked if desired.

### Step 10 — Docs touch-ups

**File:** `app/core/agents/CLAUDE.md`

Update the `evals/` bullet (currently reads `AI-7.1: synthetic eval cases ...`)
to append `AI-7.2: `runner.py` CLI + EvalTrace JSONL writer under evals/traces/`.
One sentence. Do not expand the document.

## Preflight Warnings

- **`base.py` test coverage** — `test_base.py` has 23 hook-point tests (per
  `app/core/agents/CLAUDE.md`). The `chat()` → `chat_with_trace()` refactor is
  subtle because it moves Phase 1–12 into a different method. Run
  `uv run pytest app/core/agents/tests/test_base.py app/core/agents/tests/test_agent_result.py -x -q`
  first to capture the baseline before editing. **Expected: all pass.**
- **`confidence re-route` path** — `test_agent_result.py` contains explicit
  tests for the re-route gate at low confidence. The refactor must keep that
  branch inside `chat_with_trace` intact — including the second `_post_process`
  call on the retry path. Do not factor the re-route block out.
- **Tuple unpacking fragility** — changing `chat_with_trace` to a 3-tuple means
  any hypothetical caller doing `response, result = await ...` would break.
  **Grep first**: `Grep(pattern="chat_with_trace", glob="**/*.py")` — this method
  is brand new in this plan, so there will be zero pre-existing callers. Safe.
- **`extract_tool_returns` import** — already exported from `app.core.agents.validation`.
  Confirm with `Grep` before writing the import line.
- **`ToolReturnRecord` export** — needs to be importable from
  `app.core.agents.validation`. Verify it is in `__all__`; if not, add it to
  `__all__` in Step 3 as a one-line `validation.py` edit.
- **`datetime.UTC` vs `datetime.timezone.utc`** — anti-pattern #39 warns about
  shadowing `date`. Use `import datetime as _dt` and reference `_dt.UTC` (or
  `_dt.datetime.now(_dt.UTC)`), which works on 3.11+. VTV is Python 3.12+.

## Security Checklist

Apply CTX-AGENT + CTX-INPUT requirements:

- [ ] Runner never logs `case.prompt` or agent response content — only case IDs,
      domains, counts, and latencies.
- [ ] `--suite` uses `argparse choices=_SUITE_CHOICES` (closed set).
- [ ] `--output-dir` path is resolved and sandboxed via `is_relative_to()`
      before any file write; emits `agent.evals.runner.path_escaped` warning
      on violation and raises `ValueError`.
- [ ] Tool return payloads may contain PII (driver names, vehicle IDs) — the
      JSONL is gitignored (`evals/traces/*.jsonl`). Document this in the
      Makefile help text comment.
- [ ] No credential exposure — runner never imports or logs `settings.database_url`,
      API keys, JWT secrets.
- [ ] Fail-open per-case — one exception in `_run_case` writes an error trace
      and continues the suite. Infrastructure-level OSError aborts with exit
      code 2 (not 1, which is reserved for "suite ran, N failed").
- [ ] `close_all_agents()` in `finally` — HTTP clients closed on error paths.
- [ ] No hardcoded secrets in Makefile (uses `uv run`, no env vars set inline).

## Verification

Run in order. Each must pass before moving to the next.

**Step-scoped:**
```bash
# Baseline (before any edits)
uv run pytest app/core/agents/tests/test_base.py app/core/agents/tests/test_agent_result.py -x -q

# After step 1 (base.py refactor)
uv run ruff format app/core/agents/base.py
uv run ruff check --fix app/core/agents/base.py
uv run pyright app/core/agents/base.py
uv run mypy app/core/agents/base.py
uv run pytest app/core/agents/tests/test_base.py app/core/agents/tests/test_agent_result.py -x -q

# After steps 3-6 (runner + init)
uv run ruff format app/core/agents/evals/
uv run ruff check --fix app/core/agents/evals/
uv run pyright app/core/agents/evals/
uv run mypy app/core/agents/evals/
uv run python -c "from app.core.agents.evals import EvalRunner, EvalTrace; print('ok')"
uv run python -m app.core.agents.evals.runner --help

# After step 7 (runner tests)
uv run pytest app/core/agents/tests/test_eval_runner.py -x -q

# After step 8 (Makefile)
make help | grep -E "^(eval|eval-all)"
```

**Full quality gate (before commit):**
```bash
uv run ruff format app/
uv run ruff check --fix app/
uv run pyright app/core/agents/
uv run mypy app/core/agents/
uv run pytest app/core/agents/tests/ -x -q
uv run pytest -m "not integration" -q              # full unit suite (~30s)
make security-audit-quick                            # <10s security check
```

**Baseline preservation:**
- [ ] `uv run pyright app/core/agents/evals/` — must stay at **0 errors**.
- [ ] `uv run mypy app/core/agents/evals/` — must stay at **0 errors**.
- [ ] `uv run pyright app/core/agents/` — must stay ≤ **5 errors** (same files
      as baseline: `tools/transit/client.py:193`, `tools/transit/static_store.py:149–150`,
      `pipeline.py:136`). **No new pyright errors in `base.py` or any file we touched.**
- [ ] `uv run mypy app/core/agents/` — must stay ≤ **3 errors** (same files).
- [ ] Full agent test suite `uv run pytest app/core/agents/tests/ -q` — total count
      must grow by ≥ 11 (new runner tests) + 1 (new `chat_with_trace` base test).
      No pre-existing tests may fail.

**Acceptance criteria:**
- [ ] `make eval SUITE=transit` **in a dev shell with real settings** produces a
      file at `evals/traces/transit_<ts>.jsonl` with 15 lines (one per AI-7.1 case).
      Each line is valid JSON with the full `EvalTrace` shape.
- [ ] When a tool in one case raises, that one line has `error=<type>: <msg>` and
      subsequent cases still run.
- [ ] `make eval-all` produces three files and exits 0 if all cases succeed.
- [ ] Stdout summary matches `"[transit] 15/15 passed, 0 failed, avg <ms>ms, trace=<path>"`.

## Out of Scope

- **LLM judges / pass-fail scoring per case.** That is AI-7.3. This runner only
  captures traces; the `error` field is the only "pass/fail" signal, and it
  reflects runtime exceptions, not quality.
- **Regression baselines / CI gating.** Also AI-7.3.
- **Touching the `AgentResult` public surface.** Intentionally kept frozen.
- **Fixing pre-existing pyright/mypy errors in `tools/transit/client.py`,
  `tools/transit/static_store.py`, `pipeline.py`.** These are unrelated to
  AI-7.2 and must not be bundled in.
