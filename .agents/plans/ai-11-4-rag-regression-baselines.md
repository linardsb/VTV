# Plan: AI-11.4 RAG Regression Baselines + CI Integration

## Context

The RAG retrieval pipeline has many tunable components (chunker version, reranker model, RRF weights, embedding provider, HyDE toggle). Any change can silently degrade retrieval quality. This feature generates regression baselines from eval runs and adds a CI gate that exits non-zero when any metric drops more than 3 percentage points.

## Security Context Assessment

- **CTX-INPUT**: Not active — no new API endpoints or user-facing input.
- **CTX-RBAC**: Not active — CLI-only, no REST endpoints.
- **CTX-FILE**: Active (light) — reads/writes JSON baseline file. Path sandboxing required.
- **CTX-AGENT**: Not active — no LLM interaction.
- **CTX-INFRA**: Active (light) — Makefile changes.
- **CTX-AUTH**: Not active.

## Research Summary

### Existing RAG Eval Infrastructure

| File | Purpose | Key Types |
|------|---------|-----------|
| `app/knowledge/evals/schemas.py` | Frozen dataclasses | `QAPair`, `PairMetrics`, `RetrievalMetrics`, `RunReport`, `CaseResult`, `FaithfulnessResult` |
| `app/knowledge/evals/runner.py` | Orchestrator + CLI | `RAGEvalRunner.run() -> RunReport`, `_write_report()`, `_load_qa_pairs()` |
| `app/knowledge/evals/metrics.py` | Metric computation | `compute_pair_metrics()`, `aggregate_metrics()` |
| `app/knowledge/evals/faithfulness.py` | LLM judge | `FaithfulnessJudge.judge() -> FaithfulnessResult` |

### Key Type: `RunReport` (the regression module's input)

```python
@dataclass(frozen=True, slots=True)
class RunReport:
    run_id: str
    timestamp: str  # ISO-8601
    qa_file: str
    total_pairs: int
    retrieval_metrics: RetrievalMetrics  # recall@1/3/5/10, mrr, mean_completeness
    mean_faithfulness: float
    faithfulness_errors: int
    case_results: tuple[CaseResult, ...]
```

### Key Type: `RetrievalMetrics`

```python
@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    total_pairs: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float
    mean_completeness: float
```

### Reference Pattern: Agent Evals Regression (`app/core/agents/evals/regression.py`)

The agent eval module has an identical feature (AI-7.4). Key patterns to mirror:
- Frozen dataclasses for `RAGBaseline` / `RegressionReport` / `RegressionFinding`
- `generate_baseline(report) -> RAGBaseline` extracts metric values
- `check_regression(current, baseline, tolerance_pct) -> RegressionReport` with `report.passed` property
- `write_baseline()` / `read_baseline()` with path sandboxing via `Path.is_relative_to()`
- CLI with `baseline` and `check` subcommands, exit codes 0/1/2
- JSON serialization with `ensure_ascii=False`, `indent=2`, `sort_keys=True`
- Structured logging: `knowledge.evals.regression.*` events (never raw content)

### Makefile Pattern (lines 104-127)

Existing targets: `rag-eval-generate`, `rag-eval-run`, `rag-eval`. New targets follow the agent eval pattern (`eval-baseline`, `eval-check`).

### Corpus Checksum Design

The user spec requests a `corpus_checksum` field that invalidates the baseline when the chunk corpus changes materially. Implementation: SHA-256 of sorted `(chunk_id, chunk_index)` tuples from the QA file's source chunks. This is lightweight (no DB query) and changes when QA pairs are regenerated against a different corpus.

## Test Landscape

### Existing Fixtures (`app/knowledge/evals/tests/conftest.py`)

- `make_qa_pair(**overrides) -> QAPair` — safe defaults, Latvian transit context
- `make_search_result(**overrides) -> SearchResult` — score=0.85, language="lv"
- `make_mock_chunk(**overrides) -> MagicMock` — DocumentChunk mock
- `make_mock_document(**overrides) -> MagicMock` — Document mock

### Test Patterns

- `@pytest.mark.anyio` for async tests
- `pytest.approx()` for float assertions
- `tmp_path` for filesystem tests
- Path sandboxing: `pytest.raises(ValueError, match="escaped sandbox")`
- JSON round-trip via `json.loads(path.read_text())`
- No `type: ignore` in test files

## Type Check Baseline

- **Pyright** on `app/knowledge/evals/`: 0 errors, 0 warnings
- **Mypy** on `app/knowledge/evals/`: 0 errors (13 source files)
- **Pyright** on `app/knowledge/schemas.py`: 0 errors

Target: maintain zero errors after adding `regression.py` + tests.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/knowledge/evals/schemas.py` | Add `RAGBaseline`, `RegressionFinding`, `RegressionReport` frozen dataclasses |
| CREATE | `app/knowledge/evals/regression.py` | `generate_baseline()`, `check_regression()`, `write_baseline()`, `read_baseline()`, CLI |
| CREATE | `app/knowledge/evals/tests/test_regression.py` | 12+ unit tests |
| UPDATE | `Makefile` | Add `rag-eval-check` and `rag-eval-update-baseline` targets |

## Implementation Steps

### Step 1: Add schema types to `app/knowledge/evals/schemas.py`

Append three frozen dataclasses after the existing `RunReport`:

```python
@dataclass(frozen=True, slots=True)
class RAGBaseline:
    """Stored baseline from a known-good RAG eval run."""
    recall_at_1: float
    recall_at_3: float
    recall_at_10: float
    mrr: float
    mean_completeness: float
    mean_faithfulness: float
    total_pairs: int
    generated_at: str  # ISO-8601
    corpus_checksum: str  # SHA-256 of sorted source chunk IDs from QA file

@dataclass(frozen=True, slots=True)
class RegressionFinding:
    """One metric that regressed beyond tolerance."""
    metric_name: str
    baseline_value: float
    current_value: float
    delta: float  # current - baseline (negative = regression)
    tolerance: float

@dataclass(frozen=True, slots=True)
class RegressionReport:
    """Result of comparing current metrics against a stored baseline."""
    passed: bool
    tolerance: float
    findings: tuple[RegressionFinding, ...]
    corpus_checksum_match: bool  # False = baseline may be stale
    generated_at: str
```

**Validation:** `uv run ruff check app/knowledge/evals/schemas.py && uv run pyright app/knowledge/evals/schemas.py`

### Step 2: Create `app/knowledge/evals/regression.py`

Core functions (mirror `app/core/agents/evals/regression.py` pattern):

```python
"""RAG regression baselines (AI-11.4).

Extracts metric baselines from RunReport, persists as JSON under
evals/rag/baseline.json (committed, not gitignored), and compares
fresh runs against stored numbers with configurable tolerance.

CLI: python -m app.knowledge.evals.regression baseline --report <path>
     python -m app.knowledge.evals.regression check --report <path>
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
```

**Functions to implement:**

1. `compute_corpus_checksum(qa_pairs: list[QAPair]) -> str`
   - SHA-256 of `"|".join(str(p.source_chunk_id) for p in sorted(qa_pairs, key=lambda p: p.source_chunk_id))`
   - Deterministic: sorted by source_chunk_id

2. `generate_baseline(report: RunReport, *, qa_pairs: list[QAPair], now: datetime | None = None) -> RAGBaseline`
   - Extract metrics from `report.retrieval_metrics` + `report.mean_faithfulness`
   - Compute corpus checksum from qa_pairs
   - Return frozen `RAGBaseline`

3. `check_regression(current: RunReport, baseline: RAGBaseline, *, qa_pairs: list[QAPair], tolerance: float = 0.03) -> RegressionReport`
   - Compare 6 metrics: `recall_at_1`, `recall_at_3`, `recall_at_10`, `mrr`, `mean_completeness`, `mean_faithfulness`
   - Finding when `current - baseline < -tolerance` (negative delta beyond tolerance)
   - Compute corpus_checksum_match from qa_pairs vs baseline
   - Log warning if checksum mismatch
   - Return `RegressionReport(passed=len(findings)==0, ...)`

4. `_baseline_to_json(baseline: RAGBaseline) -> dict[str, Any]` — serialize

5. `_baseline_from_json(data: dict[str, Any]) -> RAGBaseline` — deserialize defensively

6. `write_baseline(baseline: RAGBaseline, *, baseline_path: Path) -> Path`
   - Path-sandboxed via `is_relative_to()`
   - Default: `evals/rag/baseline.json`
   - `json.dump(..., ensure_ascii=False, indent=2, sort_keys=True)` + trailing newline

7. `read_baseline(*, baseline_path: Path) -> RAGBaseline | None`
   - Return None if file doesn't exist
   - Path-sandboxed

8. CLI: `_build_parser()` with `baseline` and `check` subcommands
   - `baseline --report <path> [--qa-file <path>] [--force]`
   - `check --report <path> [--qa-file <path>] [--tolerance <float>]`
   - Both load the RunReport JSON + QA pairs
   - Exit codes: 0=pass, 1=regression, 2=infra error
   - `check` prints regression findings to stdout (matches agent eval format)
   - `check` prints corpus checksum warning if mismatch

9. `main(argv: list[str] | None = None) -> int` + `if __name__ == "__main__": raise SystemExit(main())`

**Key details:**
- Use `from app.core.logging import get_logger` with `logger = get_logger(__name__)`
- Log events: `knowledge.evals.regression.baseline_generated`, `.baseline_written`, `.check_passed`, `.regression_detected`, `.corpus_checksum_mismatch`, `.aborted`, `.path_escaped`
- `_DEFAULT_BASELINE_PATH: Final[Path] = Path("evals/rag/baseline.json")`
- `_DEFAULT_QA_DIR: Final[Path] = Path("evals/rag")`
- `_METRIC_NAMES: Final[tuple[str, ...]] = ("recall_at_1", "recall_at_3", "recall_at_10", "mrr", "mean_completeness", "mean_faithfulness")`
- `__all__` exports: `generate_baseline`, `check_regression`, `write_baseline`, `read_baseline`, `compute_corpus_checksum`, `main`

**Validation:** `uv run ruff format app/knowledge/evals/regression.py && uv run ruff check --fix app/knowledge/evals/regression.py && uv run pyright app/knowledge/evals/regression.py && uv run mypy app/knowledge/evals/regression.py`

### Step 3: Create `app/knowledge/evals/tests/test_regression.py`

12+ tests organized in test classes:

```python
"""Tests for RAG regression baselines (AI-11.4)."""
```

**TestComputeCorpusChecksum (2 tests):**
1. `test_deterministic_same_order` — same pairs → same hash
2. `test_deterministic_different_order` — reordered pairs → same hash (sorted internally)

**TestGenerateBaseline (2 tests):**
3. `test_extracts_all_metrics` — verify all 6 metrics + total_pairs + corpus_checksum + generated_at
4. `test_injectable_timestamp` — `now=` parameter produces expected ISO timestamp

**TestCheckRegression (5 tests):**
5. `test_no_regression_within_tolerance` — small drop < 3pp → `passed=True`, empty findings
6. `test_regression_detected_beyond_tolerance` — drop > 3pp on recall_at_3 → `passed=False`, finding with correct delta
7. `test_multiple_regressions` — drop on 2 metrics → 2 findings
8. `test_custom_tolerance` — tolerance=0.10 allows larger drops
9. `test_corpus_checksum_mismatch` — different qa_pairs → `corpus_checksum_match=False`

**TestWriteReadBaseline (2 tests):**
10. `test_round_trip` — write then read, values match (use `tmp_path`)
11. `test_read_missing_returns_none` — nonexistent file → None

**TestCLI (2 tests):**
12. `test_baseline_subcommand` — mock `_load_report` + `_load_qa_pairs`, verify exit 0 and file written
13. `test_check_subcommand_regression` — mock inputs with degraded metrics, verify exit 1

**Factories to add to conftest.py or inline:**
- `make_run_report(**overrides) -> RunReport` — construct with `make_retrieval_metrics()` defaults
- `make_retrieval_metrics(**overrides) -> RetrievalMetrics` — good defaults (recall_at_3=0.85, mrr=0.80, etc.)

Use existing `make_qa_pair` from conftest.

**Validation:** `uv run pytest app/knowledge/evals/tests/test_regression.py -v && uv run pyright app/knowledge/evals/tests/test_regression.py`

### Step 4: Update `Makefile`

Add two targets after the existing `rag-eval:` target (line ~127):

```makefile
rag-eval-update-baseline: ## Update RAG eval baseline from latest report (usage: make rag-eval-update-baseline REPORT=evals/rag/eval_report_*.json)
	uv run python -m app.knowledge.evals.regression baseline --report $(or $(REPORT),$(shell ls -t evals/rag/eval_report_*.json 2>/dev/null | head -1)) --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl) --force

rag-eval-check: ## Run RAG eval and check for regressions against baseline (CI gate)
	uv run python -m app.knowledge.evals.regression check --report $(or $(REPORT),$(shell ls -t evals/rag/eval_report_*.json 2>/dev/null | head -1)) --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl)
```

**Validation:** `make help | grep rag-eval`

## Preflight Warnings

None — all target files are either new (`regression.py`, `test_regression.py`) or append-only (`schemas.py`, `Makefile`). No fragile patterns at risk.

## Security Checklist

No new endpoints. File I/O checklist:
- [x] Path sandboxing via `Path.is_relative_to()` on write and read
- [x] No raw content logging — only metric names, values, checksums
- [x] No new env vars or secrets
- [x] JSON input parsed defensively (type checks before casting)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `uv run pytest app/knowledge/evals/tests/test_regression.py -v` — 12+ tests green
- [ ] Pyright errors = 0 (baseline: 0)
- [ ] Mypy errors = 0 (baseline: 0)
- [ ] `make help | grep rag-eval` shows all 5 targets (generate, run, eval, update-baseline, check)
- [ ] `make security-audit-quick` passes
