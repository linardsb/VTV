# Plan: AI-11.1 Synthetic QA Pair Generation from Documents

## Context

Hand-writing retrieval test cases doesn't scale and can't cover corpus drift. This feature generates synthetic QA pairs from the actual knowledge base corpus so ground truth stays in sync as the KB grows. A fast-tier LLM generates plausible dispatcher questions for sampled chunks, recording `(question, source_chunk_id, source_heading_path, language)` as ground truth for RAG evaluation.

## Security Context Assessment

- **CTX-AGENT** — Uses LLM (fast tier) to generate questions; must not expose credentials in prompts/logs, output must be sanitized
- **CTX-INPUT** — CLI accepts `--count`, `--output` params; validate ranges and path safety
- **CTX-INFRA** — Output path must be sandboxed to prevent directory traversal

No new REST endpoints → CTX-RBAC/CTX-AUTH not triggered. No file uploads → CTX-FILE not triggered.

## Research Summary

### Key Files

| File | Purpose |
|------|---------|
| `app/knowledge/models.py:71-100` | `DocumentChunk` model — `id`, `document_id`, `content`, `chunk_index`, `embedding`, `parent_chunk_id`, `heading_path`, `section_type` |
| `app/knowledge/models.py:30-56` | `Document` model — `id`, `filename`, `domain`, `language`, `status`, `chunk_count`, `evergreen` |
| `app/knowledge/repository.py:246-260` | `get_chunks_by_document(document_id)` — fetch all chunks for a doc |
| `app/knowledge/repository.py:87-123` | `list_documents(offset, limit, domain, status, language, tag)` — paginated doc listing |
| `app/knowledge/hyde.py:1-96` | HyDE pattern — `pydantic_ai.Agent` with `resolve_model()` → fast tier, `agent.run(query)`, `str(result.response).strip()` |
| `app/core/agents/evals/runner.py:48-110` | `EvalTrace` frozen dataclass + JSONL writing pattern with path sandboxing |
| `app/core/agents/evals/runner.py:350-391` | CLI pattern: `_build_parser()` → `_amain()` → `main()` → `if __name__ == "__main__"` |
| `app/core/config.py:59-72` | LLM tier settings: `llm_fast_provider`, `llm_fast_model` |
| `Makefile:101-117` | Existing eval targets to place new target after |

### Reference Pattern: hyde.py

The QA generator follows the same LLM invocation pattern as `hyde.py`:
1. Resolve model string via fast tier settings
2. Create `pydantic_ai.Agent(model_str, system_prompt=...)`
3. `result = await agent.run(chunk_content)`
4. Extract text: `str(result.response).strip()`
5. Graceful degradation on error (skip pair, don't crash)

### JSONL Output Convention

From `app/core/agents/evals/runner.py`:
- Default output dir: `evals/traces/` (git-ignored)
- Filename: `{suite_name}_{timestamp}.jsonl`
- Path sandboxing: `out_path.resolve().is_relative_to(output_dir)`
- One JSON line per record via `json.dumps(asdict(trace), ensure_ascii=False, default=str)`

New QA pairs will go to `evals/rag/` (git-ignored).

## Test Landscape

### Existing Fixtures (app/knowledge/tests/)

| Fixture/Factory | Location | Purpose |
|----------------|----------|---------|
| `make_document(**overrides)` | `test_repository.py:15-37` | Document ORM instance with defaults |
| `make_chunk(**overrides)` | `test_repository.py:40-57` | DocumentChunk ORM instance with defaults |
| `sample_latvian_text` | `conftest.py:16-26` | Multi-paragraph Latvian text |
| `sample_english_text` | `conftest.py:29-38` | Multi-paragraph English text |

### LLM Mock Pattern (from test_hyde.py)

```python
with patch("pydantic_ai.Agent") as mock_agent_cls:
    mock_agent = AsyncMock()
    mock_agent.run = AsyncMock(return_value=mock_result)
    mock_agent_cls.return_value = mock_agent
```

### CLI Test Pattern (from test_eval_runner.py:370-383)

```python
def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
```

### Eval Path Sandboxing Test Pattern

```python
def test_sandboxes_output_path(tmp_path):
    with pytest.raises(ValueError, match="output path escaped sandbox root"):
        _write_output([], output_dir=tmp_path, filename="../escape/x")
```

## Type Check Baseline

| Tool | Errors in `app/knowledge/` |
|------|---------------------------|
| Pyright | **0** (clean) |
| Mypy | **0** direct, 3 transitive (in `app/core/agents/`) |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/knowledge/evals/__init__.py` | Package init |
| CREATE | `app/knowledge/evals/schemas.py` | `QAPair`, `RetrievalMetrics`, `EvalReport` frozen dataclasses |
| CREATE | `app/knowledge/evals/qa_generator.py` | Sampler + LLM question generation + CLI + JSONL writer |
| CREATE | `app/knowledge/evals/__main__.py` | `python -m app.knowledge.evals.generate` entry point |
| CREATE | `app/knowledge/evals/tests/__init__.py` | Test package init |
| CREATE | `app/knowledge/evals/tests/conftest.py` | Factories: `make_qa_pair`, `make_mock_chunk`, `tmp_output_dir` |
| CREATE | `app/knowledge/evals/tests/test_qa_generator.py` | 12+ unit tests |
| UPDATE | `Makefile` | Add `rag-eval-generate` target |
| UPDATE | `.gitignore` | Add `evals/rag/` to ignored paths |

## Implementation Steps

### Step 1: Create package structure + schemas

**Files:** `app/knowledge/evals/__init__.py`, `app/knowledge/evals/schemas.py`

`__init__.py` — empty file.

`schemas.py` — three frozen dataclasses:

```python
@dataclass(frozen=True, slots=True)
class QAPair:
    """One synthetic QA pair for RAG retrieval evaluation."""
    question: str
    source_chunk_id: int
    source_document_id: int
    source_heading_path: str | None
    language: str
    generated_at: str  # ISO-8601
    model_used: str

@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Aggregate retrieval metrics from one eval run."""
    total_pairs: int
    recall_at_1: float
    recall_at_5: float
    mrr: float  # Mean Reciprocal Rank

@dataclass(frozen=True, slots=True)
class EvalReport:
    """Summary of a retrieval evaluation run."""
    run_id: str
    timestamp: str
    qa_file: str
    metrics: RetrievalMetrics
    errors: int
```

**Validation:** `uv run ruff format app/knowledge/evals/schemas.py && uv run ruff check --fix app/knowledge/evals/schemas.py && uv run pyright app/knowledge/evals/schemas.py`

### Step 2: Create qa_generator.py — core sampler + LLM generation

**File:** `app/knowledge/evals/qa_generator.py`

**Imports:**
- `from __future__ import annotations`
- `argparse`, `asyncio`, `datetime`, `json`, `random`, `time` from stdlib
- `from dataclasses import asdict`
- `from pathlib import Path`
- `from typing import Final`
- `from app.core.config import Settings, get_settings`
- `from app.core.database import get_db_context`
- `from app.core.logging import get_logger`
- `from app.knowledge.evals.schemas import QAPair`
- `from app.knowledge.models import Document, DocumentChunk`

**Constants:**
- `_DEFAULT_OUTPUT_DIR: Final[Path] = Path("evals/rag")`
- `_MIN_CHUNK_LENGTH: Final[int] = 200`
- `_EXCLUDED_SECTION_TYPES: Final[frozenset[str]] = frozenset({"list", "table"})`

**System prompt for QA generation:**
```
_QA_SYSTEM_PROMPT = (
    "Given the following passage from a transit operations document, "
    "write one specific factual question that a dispatcher might ask, "
    "where this passage would be the ideal answer. "
    "Respond in {language}. Question only, no preamble."
)
```

**Key functions:**

1. `_resolve_model(settings: Settings) -> str` — Same pattern as `hyde.py:_resolve_model`. Priority: `llm_fast > primary model`.

2. `async def _fetch_eligible_chunks(n: int, language_mix: dict[str, float], settings: Settings | None = None) -> list[DocumentChunk]` — Uses `get_db_context()` to open a session, queries `DocumentChunk` with SQLAlchemy `select()`:
   - Filter: `len(content) >= _MIN_CHUNK_LENGTH`
   - Filter: `section_type NOT IN _EXCLUDED_SECTION_TYPES` (or `section_type IS NULL`)
   - Filter: `heading_path IS NOT NULL` (preferred but not required — use `order_by(heading_path.isnot(None).desc())` to prefer chunks with headings)
   - Join `Document` to get `language`, filter `status = 'completed'`
   - Stratify by language using `language_mix` weights — compute target count per language, query each separately
   - Randomize via `func.random()` or Python `random.sample()` after fetch
   - Return sampled list

3. `async def _generate_question(chunk: DocumentChunk, language: str, model_str: str) -> str | None` — Lazy imports `pydantic_ai.Agent`, creates agent with formatted system prompt, runs against chunk content, returns question string or `None` on error. Pattern from `hyde.py:expand_query`. Truncate chunk content to 2000 chars for the prompt. Log `knowledge.qa_generator.question_generated` or `knowledge.qa_generator.question_failed`.

4. `async def generate_qa_pairs(n: int = 100, language_mix: dict[str, float] | None = None, settings: Settings | None = None) -> list[QAPair]` — Main entry point:
   - Default `language_mix = {"lv": 0.7, "en": 0.3}`
   - Fetch eligible chunks
   - For each chunk, call `_generate_question`, build `QAPair` with `generated_at=datetime.datetime.now(datetime.UTC).isoformat()`, `model_used=model_str`
   - Skip on LLM failure (log warning, continue)
   - Return list of successfully generated pairs
   - Log `knowledge.qa_generator.batch_completed` with `total_requested`, `total_generated`, `elapsed_ms`

5. `def _write_jsonl(pairs: list[QAPair], output_dir: Path) -> Path` — Path-sandboxed JSONL writer:
   - `output_dir.mkdir(parents=True, exist_ok=True)`
   - Filename: `qa_pairs_{timestamp}.jsonl` where timestamp = `%Y%m%d_%H%M%S`
   - Sandbox check: `out_path.resolve().is_relative_to(output_dir.resolve())`
   - Write one `json.dumps(asdict(pair), ensure_ascii=False, default=str)` per line
   - Return `out_path`

6. **CLI:** `_build_parser() -> argparse.ArgumentParser` with:
   - `--count` (int, default 100)
   - `--output-dir` (Path, default `evals/rag`)
   - `--lv-ratio` (float, default 0.7, range 0.0-1.0)

7. `async def _amain(argv: list[str] | None = None) -> int` — Parse args, call `generate_qa_pairs`, write JSONL, print summary, return 0 on success, 1 on error.

8. `def main(argv: list[str] | None = None) -> int` — `return asyncio.run(_amain(argv))`

9. `if __name__ == "__main__": raise SystemExit(main())`

**Logging events:**
- `knowledge.qa_generator.fetch_started` — n, language_mix
- `knowledge.qa_generator.fetch_completed` — eligible_count, elapsed_ms
- `knowledge.qa_generator.question_generated` — chunk_id, language, elapsed_ms
- `knowledge.qa_generator.question_failed` — chunk_id, error_type, error
- `knowledge.qa_generator.batch_completed` — total_requested, total_generated, skipped, elapsed_ms
- `knowledge.qa_generator.output_written` — path, pair_count

**Validation:** `uv run ruff format app/knowledge/evals/qa_generator.py && uv run ruff check --fix app/knowledge/evals/qa_generator.py && uv run pyright app/knowledge/evals/qa_generator.py`

### Step 3: Create __main__.py entry point

**File:** `app/knowledge/evals/__main__.py`

```python
"""CLI entry point: python -m app.knowledge.evals.generate"""
from app.knowledge.evals.qa_generator import main

raise SystemExit(main())
```

Wait — the spec says `python -m app.knowledge.evals.generate`. That means the entry point should be at `app/knowledge/evals/generate.py` as a module with `__main__` block, OR we use `app/knowledge/evals/__main__.py` for `python -m app.knowledge.evals`.

Use `__main__.py` so the CLI is `python -m app.knowledge.evals` (simpler). The Makefile target wraps it.

**Validation:** `uv run python -m app.knowledge.evals --help`

### Step 4: Create test infrastructure

**Files:** `app/knowledge/evals/tests/__init__.py`, `app/knowledge/evals/tests/conftest.py`

`conftest.py` — factories and fixtures:

```python
from unittest.mock import MagicMock
from app.knowledge.evals.schemas import QAPair
from app.knowledge.models import Document, DocumentChunk

def make_mock_chunk(**overrides: ...) -> MagicMock:
    """Return a MagicMock mimicking DocumentChunk with safe defaults."""
    chunk = MagicMock(spec=DocumentChunk)
    chunk.id = overrides.get("id", 1)
    chunk.document_id = overrides.get("document_id", 1)
    chunk.content = overrides.get("content", "A" * 300)  # > _MIN_CHUNK_LENGTH
    chunk.chunk_index = overrides.get("chunk_index", 0)
    chunk.heading_path = overrides.get("heading_path", "Section > Subsection")
    chunk.section_type = overrides.get("section_type", "heading")
    chunk.parent_chunk_id = overrides.get("parent_chunk_id", None)
    return chunk

def make_mock_document(**overrides: ...) -> MagicMock:
    """Return a MagicMock mimicking Document with safe defaults."""
    doc = MagicMock(spec=Document)
    doc.id = overrides.get("id", 1)
    doc.language = overrides.get("language", "lv")
    doc.status = overrides.get("status", "completed")
    doc.domain = overrides.get("domain", "transit")
    return doc

def make_qa_pair(**overrides: ...) -> QAPair:
    """Return a QAPair with safe defaults."""
    defaults = {
        "question": "Kāds ir maršruta 22 grafiks?",
        "source_chunk_id": 1,
        "source_document_id": 1,
        "source_heading_path": "Maršruti > Maršruts 22",
        "language": "lv",
        "generated_at": "2026-04-12T10:00:00+00:00",
        "model_used": "test:test-model",
    }
    defaults.update(overrides)
    return QAPair(**defaults)
```

Note: Use `Any` for `**overrides` parameter type — actually use explicit typed params or `**overrides: Any` with `# noqa: ANN401`.

**Validation:** `uv run ruff check app/knowledge/evals/tests/conftest.py`

### Step 5: Create unit tests

**File:** `app/knowledge/evals/tests/test_qa_generator.py`

12+ tests organized in groups:

**Schema tests (2):**
1. `test_qa_pair_is_frozen` — Verify `QAPair` is immutable
2. `test_qa_pair_serialization` — `asdict(pair)` produces expected dict, `json.dumps` succeeds

**Chunk filtering tests (3):**
3. `test_short_chunks_excluded` — Chunks < 200 chars filtered out
4. `test_table_section_type_excluded` — `section_type="table"` excluded
5. `test_list_section_type_excluded` — `section_type="list"` excluded

**Sampling stratification tests (2):**
6. `test_language_mix_respected` — With `{"lv": 0.7, "en": 0.3}` and n=10, result has ~7 lv + ~3 en
7. `test_language_mix_all_latvian` — With `{"lv": 1.0}`, all results are Latvian

**LLM interaction tests (2):**
8. `test_generate_question_success` — Mock `pydantic_ai.Agent`, verify question returned
9. `test_generate_question_failure_returns_none` — Mock agent raising exception, verify None returned and error logged

**JSONL output tests (2):**
10. `test_write_jsonl_creates_file` — Verify file created in `tmp_path` with correct line count
11. `test_write_jsonl_path_sandboxing` — Verify `ValueError` on path traversal attempt (`../escape`)

**CLI tests (1):**
12. `test_cli_help_exits_zero` — `main(["--help"])` exits 0

**Mock patterns:**
- LLM: `patch("app.knowledge.evals.qa_generator.Agent")` (patch at import site per anti-pattern #36)
- DB: `patch("app.knowledge.evals.qa_generator.get_db_context")` with `AsyncMock`
- Use `tmp_path` fixture for output directory

**Validation:** `uv run pytest app/knowledge/evals/tests/test_qa_generator.py -v`

### Step 6: Update Makefile

**File:** `Makefile`

Add after line 117 (`eval-check` target):

```makefile

# === RAG retrieval evals (AI-11.x) ===

rag-eval-generate: ## Generate synthetic QA pairs from knowledge base (usage: make rag-eval-generate COUNT=100)
	uv run python -m app.knowledge.evals --count $(or $(COUNT),100)
```

**Validation:** `make help | grep rag-eval`

### Step 7: Update .gitignore

**File:** `.gitignore`

Add after the existing `evals/verdicts/` line:

```
evals/rag/
```

**Validation:** `grep "evals/rag" .gitignore`

## Anti-Pattern Checklist

| # | Rule | How Addressed |
|---|------|---------------|
| 1 | No `assert` in production | Use `if`/`raise ValueError` for sandbox check |
| 5 | No unused imports | Only import what's used; lazy import `pydantic_ai.Agent` inside function |
| 7 | Test helpers need return types | All conftest factories have `-> QAPair`, `-> MagicMock` |
| 9 | `ctx` parameter must be referenced | N/A — no agent tools added |
| 12 | Untyped lib 3-layer fix | `pydantic_ai` already configured in `pyproject.toml` |
| 36 | Lazy imports break `@patch` | Patch at the qa_generator module level, not pydantic_ai directly |
| 37 | Bare `except: pass` | Always log in except blocks |
| 43 | Filename sanitization | Output filename uses timestamp format only, no user input |

## Security Checklist

- [x] No credentials in prompts or logs (only chunk_id, language, elapsed_ms)
- [x] Output path sandboxed via `Path.resolve().is_relative_to()`
- [x] Chunk content truncated before sending to LLM (2000 char cap)
- [x] LLM failures fail-open (skip pair, don't crash)
- [x] CLI `--count` validated as positive integer
- [x] No raw chunk content logged (only lengths and IDs)
- [x] `json.dumps(ensure_ascii=False)` for Latvian text preservation

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (0 errors before)
- [ ] `uv run pytest app/knowledge/evals/tests/ -v` — all 12+ tests pass
- [ ] `make rag-eval-generate COUNT=5` runs without error (requires DB + LLM config)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
