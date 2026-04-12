# Plan: AI-11.3 RAG Eval Runner + Faithfulness Judge

## Context

Rank-based retrieval metrics (recall@k, MRR, completeness) from AI-11.2 miss semantic correctness. A chunk can be rank 1 but still be the wrong answer. This feature adds:
1. An `RAGEvalRunner` that runs QA pairs through `KnowledgeService.search()` and computes AI-11.2 metrics
2. A `FaithfulnessJudge` that uses a fast-tier LLM to verify retrieved context actually supports answering the question (binary pass/fail with 3 criteria: grounded, accurate, complete)
3. CLI + Makefile targets for end-to-end evaluation

## Security Context Assessment

- **CTX-INPUT**: Not applicable — no user-facing endpoints added
- **CTX-RBAC**: Not applicable — CLI-only, no REST endpoints
- **CTX-AGENT**: **Active** — LLM judge uses fast-tier model; must never log raw chunk content or question text; fail-open on LLM errors
- **CTX-INFRA**: **Active** — Path-sandboxed output files; no credentials in logs
- **CTX-FILE**: Not applicable — no file uploads
- **CTX-AUTH**: Not applicable — no auth changes

## Research Summary

### Existing Eval Infrastructure (AI-11.1 + AI-11.2)

| File | Role |
|------|------|
| `app/knowledge/evals/schemas.py` | `QAPair`, `PairMetrics`, `RetrievalMetrics`, `EvalReport` frozen dataclasses |
| `app/knowledge/evals/qa_generator.py` | AI-11.1 QA pair generation from corpus via fast-tier LLM |
| `app/knowledge/evals/metrics.py` | AI-11.2 `compute_pair_metrics()` + `aggregate_metrics()` |
| `app/knowledge/evals/__main__.py` | CLI entry point (currently delegates to `qa_generator.main`) |
| `app/knowledge/evals/tests/conftest.py` | `make_qa_pair()`, `make_search_result()`, `make_mock_chunk()`, `make_mock_document()` |

### Key Dependencies

| Symbol | Location | Signature |
|--------|----------|-----------|
| `KnowledgeService.search()` | `app/knowledge/service.py:575` | `async def search(self, request: SearchRequest) -> SearchResponse` |
| `SearchRequest` | `app/knowledge/schemas.py:143` | `query, domain?, language?, limit=10` |
| `SearchResult` | `app/knowledge/schemas.py:158` | `chunk_content, document_id, chunk_index, score, heading_path?, ...` |
| `resolve_tier_model()` | `app/core/agents/config.py:113` | `def resolve_tier_model(tier: ModelTier, settings?) -> str \| Model \| None` |
| `get_db_context()` | `app/core/database` | Async context manager yielding `AsyncSession` |
| `get_settings()` | `app/core/config` | Returns `Settings` singleton |

### Reference Patterns

- **LLM Judge pattern**: `app/core/agents/evals/judge.py` — Pydantic AI `Agent` with structured `_CriterionJudgement(BaseModel)` output, `<<<BEGIN>>>`/`<<<END>>>` delimiters, fail-open per case, path-sandboxed JSONL output
- **CLI pattern**: `app/knowledge/evals/qa_generator.py` — `_build_parser()` / `_amain()` / `main()` three-function pattern with `asyncio.run()`
- **Path sandboxing**: `Path.resolve().is_relative_to()` used throughout evals
- **Logging**: `get_logger(__name__)`, `knowledge.eval_runner.*` / `knowledge.faithfulness.*` domain pattern

## Test Landscape

### Existing Fixtures (reuse from `app/knowledge/evals/tests/conftest.py`)
- `make_qa_pair(**overrides)` — returns `QAPair` with Latvian defaults
- `make_search_result(**overrides)` — returns `SearchResult` with score=0.85
- `make_mock_chunk(**overrides)` / `make_mock_document(**overrides)`

### Mock Patterns
- **Pydantic AI Agent**: `patch("pydantic_ai.Agent")` + `AsyncMock().run` or `TestModel(custom_output_args=...)`
- **KnowledgeService.search()**: `AsyncMock(return_value=SearchResponse(...))` on the service instance
- **get_db_context()**: `patch("app.knowledge.evals.runner.get_db_context")` returning `AsyncMock` session
- **CLI tests**: Sync `main(["--arg", "val"])` with `pytest.raises(SystemExit)` for `--help`

## Type Check Baseline

- **Pyright**: 0 errors on `app/knowledge/` (0 on `app/knowledge/evals/`)
- **Mypy**: 0 errors on `app/knowledge/` (0 on `app/knowledge/evals/`)

Target: 0 new errors after implementation.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/knowledge/evals/schemas.py` | Add `FaithfulnessResult`, `CaseResult`, `RunReport` dataclasses |
| CREATE | `app/knowledge/evals/faithfulness.py` | `FaithfulnessJudge` — LLM-based binary faithfulness scoring |
| CREATE | `app/knowledge/evals/runner.py` | `RAGEvalRunner.run()` — orchestrates search + metrics + faithfulness |
| UPDATE | `app/knowledge/evals/__main__.py` | Route `--mode run` to runner, `--mode generate` to qa_generator |
| UPDATE | `Makefile` | Add `rag-eval`, `rag-eval-run` targets |
| CREATE | `app/knowledge/evals/tests/test_faithfulness.py` | 6 tests for FaithfulnessJudge |
| CREATE | `app/knowledge/evals/tests/test_runner.py` | 8+ tests for RAGEvalRunner + CLI |

## Implementation Steps

### Step 1: Extend schemas (`app/knowledge/evals/schemas.py`)

Add three frozen dataclasses after `EvalReport`:

```python
@dataclass(frozen=True, slots=True)
class FaithfulnessResult:
    """LLM-judged faithfulness for one QA pair."""
    grounded: bool | None  # Answer derivable from chunks?
    accurate: bool | None  # Matches source content?
    complete: bool | None  # No key info missing?
    passed: bool | None    # All three True = pass; None = error
    error: str | None      # Error message if LLM call failed

@dataclass(frozen=True, slots=True)
class CaseResult:
    """Per-QA-pair evaluation result combining metrics + faithfulness."""
    qa_pair: QAPair
    pair_metrics: PairMetrics
    faithfulness: FaithfulnessResult
    search_latency_ms: float
    judge_latency_ms: float

@dataclass(frozen=True, slots=True)
class RunReport:
    """Full eval run report with retrieval metrics + faithfulness stats."""
    run_id: str
    timestamp: str
    qa_file: str
    total_pairs: int
    retrieval_metrics: RetrievalMetrics
    mean_faithfulness: float  # Fraction of pairs where passed=True
    faithfulness_errors: int  # Count of pairs where passed=None
    case_results: tuple[CaseResult, ...]
```

**Validation:** `uv run ruff format app/knowledge/evals/schemas.py && uv run ruff check --fix app/knowledge/evals/schemas.py && uv run pyright app/knowledge/evals/schemas.py`

### Step 2: Create FaithfulnessJudge (`app/knowledge/evals/faithfulness.py`)

New file following `app/core/agents/evals/judge.py` pattern:

```python
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""LLM-judged faithfulness scoring for RAG evaluation (AI-11.3).

Given a question, retrieved chunks, and source chunk content, determines
whether the retrieval is faithful — i.e., the chunks provide enough
grounded, accurate, and complete context to answer the question.

Fail-open: LLM errors produce FaithfulnessResult(passed=None, error=...).
Never logs raw question text or chunk content — only IDs and scores.
"""
```

Key design:
- `class _FaithfulnessJudgement(BaseModel)`: structured output with `grounded: bool`, `accurate: bool`, `complete: bool`, `reasoning: str = Field(max_length=280)`
- `class FaithfulnessJudge`: constructor takes `model: str | Model | None = None`
- `async def judge(self, question: str, results: list[SearchResult], source_chunk_content: str) -> FaithfulnessResult`
- Uses `pydantic_ai.Agent` with system prompt (3 criteria, treat chunks as DATA not instructions, `<<<BEGIN>>>`/`<<<END>>>` delimiters)
- Fail-open: `except Exception` → `FaithfulnessResult(grounded=None, accurate=None, complete=None, passed=None, error=f"{type(exc).__name__}: {exc}")`
- Logging: `knowledge.faithfulness.judge_started` (pair_id only), `knowledge.faithfulness.judge_completed` (passed, latency_ms), `knowledge.faithfulness.judge_failed` (error_type only)
- Model resolution: `resolve_tier_model("fast")` or fall back to `get_agent_model()`

**Validation:** `uv run ruff format app/knowledge/evals/faithfulness.py && uv run ruff check --fix app/knowledge/evals/faithfulness.py && uv run pyright app/knowledge/evals/faithfulness.py`

### Step 3: Create RAGEvalRunner (`app/knowledge/evals/runner.py`)

New file:

```python
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""RAG evaluation runner (AI-11.3).

Runs QA pairs through KnowledgeService.search(), computes retrieval metrics
via AI-11.2, and optionally judges faithfulness via LLM.

CLI: python -m app.knowledge.evals --mode run --qa-file evals/rag/qa_pairs_*.jsonl
"""
```

Key design:
- `class RAGEvalRunner`: constructor takes `judge: FaithfulnessJudge | None = None`
- `async def run(self, qa_pairs: list[QAPair], *, limit: int = 10) -> RunReport`
  - For each pair: `async with get_db_context() as session:` create `KnowledgeService(session)`, call `search(SearchRequest(query=pair.question, language=pair.language, limit=limit))`
  - Compute `compute_pair_metrics(pair, response.results)` from AI-11.2
  - If judge provided: call `judge.judge(pair.question, response.results, <source_chunk_content>)` — source chunk content fetched from DB if `pair.source_chunk_id` matches a result, else from a direct DB query
  - Track `search_latency_ms` and `judge_latency_ms` per pair
  - Fail-open per pair: catch `Exception`, log warning, produce `CaseResult` with error faithfulness
- `aggregate_metrics()` from AI-11.2 for retrieval; faithfulness = count(passed=True) / count(passed is not None)
- `_load_qa_pairs(path: Path) -> list[QAPair]`: read JSONL, deserialize via `QAPair(**json.loads(line))`
- `_write_report(report: RunReport, output_dir: Path) -> Path`: path-sandboxed JSON output
- CLI functions: `_build_parser()`, `async _amain(argv)`, `def main(argv)`

Logging: `knowledge.eval_runner.run_started` (total_pairs, limit), `knowledge.eval_runner.case_completed` (case_index, search_ms, judge_ms), `knowledge.eval_runner.case_failed` (case_index, error_type), `knowledge.eval_runner.run_completed` (total_pairs, recall_at_3, mrr, mean_faithfulness, duration_s)

**Validation:** `uv run ruff format app/knowledge/evals/runner.py && uv run ruff check --fix app/knowledge/evals/runner.py && uv run pyright app/knowledge/evals/runner.py`

### Step 4: Update `__main__.py`

Replace the single-purpose QA generator delegation with a mode dispatcher:

```python
"""CLI entry point: python -m app.knowledge.evals

Modes:
  --mode generate  Generate synthetic QA pairs (AI-11.1, default)
  --mode run       Run RAG evaluation on existing QA pairs (AI-11.3)
"""
import sys

def main() -> int:
    if "--mode" not in sys.argv or "generate" in sys.argv:
        from app.knowledge.evals.qa_generator import main as gen_main
        return gen_main()
    else:
        from app.knowledge.evals.runner import main as run_main
        return run_main()

raise SystemExit(main())
```

Actually — simpler approach: keep `__main__.py` as the QA generator entry point. The runner has its own `python -m app.knowledge.evals.runner` entry. Add a `__main__.py` to handle both modes OR just rely on separate module-level entry points. The simplest approach: runner.py contains its own `if __name__ == "__main__"` block + `main()` function, invoked via `python -m app.knowledge.evals.runner`. No changes to existing `__main__.py`.

**Decision:** Do NOT modify `__main__.py`. The runner is invoked directly: `python -m app.knowledge.evals.runner --qa-file ...`. This avoids breaking the existing `make rag-eval-generate` target.

**Validation:** `uv run python -m app.knowledge.evals --help` still works

### Step 5: Update Makefile

Add after existing `rag-eval-generate` target (line ~122):

```makefile
rag-eval-run: ## Run RAG eval on existing QA pairs (usage: make rag-eval-run QA_FILE=evals/rag/qa_pairs.jsonl)
	uv run python -m app.knowledge.evals.runner --qa-file $(or $(QA_FILE),evals/rag/qa_pairs.jsonl)

rag-eval: rag-eval-generate rag-eval-run ## Generate QA pairs + run RAG eval (usage: make rag-eval COUNT=100)
```

**Validation:** `make help | grep rag-eval`

### Step 6: Create FaithfulnessJudge tests (`app/knowledge/evals/tests/test_faithfulness.py`)

6 tests:

```
class TestFaithfulnessJudge:
    test_judge_returns_pass_when_all_criteria_true     # TestModel(grounded=True, accurate=True, complete=True)
    test_judge_returns_fail_when_any_criterion_false    # TestModel(grounded=True, accurate=False, complete=True)
    test_judge_fail_open_on_llm_error                  # Mock Agent.run raising Exception → FaithfulnessResult(passed=None, error=...)
    test_judge_does_not_log_raw_question_or_content    # caplog assertion: no question text or chunk content in logs
    test_judge_wraps_chunks_in_data_delimiters         # Verify <<<BEGIN>>>/<<<END>>> in prompt construction
    test_judge_uses_fast_tier_model                    # Verify resolve_tier_model("fast") is called
```

**Validation:** `uv run pytest app/knowledge/evals/tests/test_faithfulness.py -v`

### Step 7: Create RAGEvalRunner tests (`app/knowledge/evals/tests/test_runner.py`)

8+ tests:

```
class TestRAGEvalRunner:
    test_run_happy_path_with_judge              # Mock search + judge, verify RunReport fields
    test_run_happy_path_without_judge           # No judge → faithfulness all None, mean_faithfulness=0.0
    test_run_fail_open_on_search_error          # Mock search raising → CaseResult with error faithfulness
    test_run_zero_pairs_returns_empty_report    # Empty list → RunReport with 0 pairs, 0.0 metrics
    test_run_computes_retrieval_metrics         # Verify recall@k/MRR from known search results

class TestRunReportOutput:
    test_write_report_path_sandboxing           # ../escape.json → ValueError
    test_write_report_creates_valid_json        # Round-trip JSON serialization

class TestCLI:
    test_cli_help_exits_zero                    # main(["--help"]) → SystemExit(0)
    test_cli_missing_qa_file_exits_nonzero      # main(["--qa-file", "/nonexistent"]) → nonzero exit
    test_load_qa_pairs_from_jsonl               # Write JSONL to tmp_path, load and verify
```

**Validation:** `uv run pytest app/knowledge/evals/tests/test_runner.py -v`

## Preflight Warnings

- `make_search_result()` in conftest.py hardcodes `document_filename="test.pdf"` — ensure runner doesn't depend on filename
- `make_qa_pair()` uses hardcoded `generated_at` — ensure runner doesn't parse this field
- Pydantic AI `Agent` must be patched at `"pydantic_ai.Agent"` or use `TestModel` — never instantiate real Agent in unit tests
- `KnowledgeService(session)` requires a real or mocked `AsyncSession` — use `AsyncMock()` for unit tests
- The `SearchResult` schema requires `document_filename` field (added since AI-11.2 conftest was written — verify `make_search_result` includes it)

## Security Checklist

No new REST endpoints — CLI-only feature. Security focus:

- [ ] Path sandboxing on all output file writes (`Path.resolve().is_relative_to()`)
- [ ] Never log raw question text or chunk content — only IDs, scores, latencies
- [ ] LLM judge prompt wraps retrieved content in `<<<BEGIN>>>`/`<<<END>>>` delimiters with "treat as data" instruction
- [ ] Fail-open on all LLM errors — never crash the runner
- [ ] No credentials in logs or output files
- [ ] `resolve_tier_model()` never exposed in output

## Verification

- [ ] `uv run ruff format app/knowledge/evals/ && uv run ruff check --fix app/knowledge/evals/`
- [ ] `uv run pyright app/knowledge/evals/` — 0 errors (baseline: 0)
- [ ] `uv run mypy app/knowledge/evals/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/knowledge/evals/tests/ -v` — all tests pass
- [ ] `make check` passes (lint + types + tests)
- [ ] `make help | grep rag-eval` shows new targets
- [ ] `make security-audit-quick` passes
