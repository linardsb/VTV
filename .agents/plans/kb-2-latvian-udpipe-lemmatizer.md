# Plan: KB-2 Latvian UDPipe Lemmatizer for BM25

## Context

Knowledge base BM25 search currently uses `to_tsvector('simple', ...)` in `app/knowledge/repository.py:385-387`, treating Latvian as unstemmed tokens. Latvian has 7 noun cases × 6 verb conjugations, so inflected forms (`autobuss`/`autobusam`/`autobusu`) never match. Integrate UDPipe (Universal Dependencies lemmatizer, C++ bindings via `ufal.udpipe`) to lemmatize both indexed chunks and queries. Fall back to `simple` tsvector for non-Latvian docs via `Document.language`.

Target: 15–20% recall@3 improvement on Latvian QA pairs after HyDE.

## Security Context Assessment

Relevant contexts from `_shared/security-contexts.md`:

- **CTX-INPUT** — Query text is user-supplied. Lemmatizing is CPU-bound; enforce input length cap (already validated at search endpoint via `KnowledgeSearchRequest` — confirm cap in Step 10) and wrap UDPipe call in timeout/thread offload so slow queries can't block the event loop. Use parameterized SQL (`text("'simple'")` + bind params); do not interpolate lemmatized output into SQL strings.
- **CTX-INFRA** — New C++ dependency (`ufal.udpipe`) + ~50MB model file. Model path is filesystem-local, configurable, never user-controlled. Ship model via `scripts/download_udpipe_model.sh`, keep artifact out of git (add to `.gitignore`), document in `docs/runbooks/`.

Not applicable: CTX-AUTH (no auth code touched), CTX-RBAC (no new endpoints), CTX-FILE (no uploads), CTX-AGENT (agent tools already route to knowledge service, no new tool).

## Research Summary

**Current BM25 path** (`app/knowledge/repository.py:371-409`, `search_fulltext`):
- `func.plainto_tsquery(text("'simple'"), query_text)` at L385
- `func.to_tsvector(text("'simple'"), DocumentChunk.content)` at L386
- Ranked with `func.ts_rank(...)` L387, ordered desc L394
- Comment at L371 explicitly notes "cross-language support" as rationale for `'simple'`

**Model:** `app/knowledge/models.py:71-101` — `DocumentChunk` has `content`, `embedding`, `metadata_json`, `parent_chunk_id`, `heading_path`, `section_type`. No existing tsvector column. `Document.language` at L46 defaults to `"lv"`.

**Chunking:** `app/knowledge/chunking.py` — `chunk_text()` and `chunk_text_semantic()` both return `ChunkResult(content, chunk_index, metadata, heading_path, section_type)`. Consumed in `service.py:304-349` (`_chunk_embed_store`).

**Singleton pattern to mirror** (`app/knowledge/service.py:52-80`):
```python
_reranker_provider: RerankerProvider | None = None
def _get_reranker() -> RerankerProvider:
    global _reranker_provider
    if _reranker_provider is None:
        _reranker_provider = get_reranker_provider(get_settings())
    return _reranker_provider
```
Warm-up called from `app/main.py` on lifespan startup (reranker pattern).

**Reranker reference file:** `app/knowledge/reranker.py` — `Protocol` + `LocalRerankerProvider` with lazy `_get_model()`, `NoopRerankerProvider` factory via `get_reranker_provider(settings)`. Our lemmatizer should mirror this exactly.

**Config** (`app/core/config.py:220-291`) — Pydantic BaseSettings. Add fields next to reranker block:
```python
latvian_lemmatizer_enabled: bool = True
udpipe_model_path: str = "models/latvian-ud-2.5.udpipe"
```

**Alembic pattern** (most recent: `alembic/versions/g5h6i7j8k9l0_add_parent_child_to_chunks.py`): `revision: str`, `down_revision: str | None`, `upgrade()` + `downgrade()` with `op.add_column` / `op.drop_column`.

**Rechunk script:** `scripts/rechunk_documents.py` — `--dry-run`, `--batch-size`, `--document-id`, `--limit`. Calls `service.rechunk_document(doc_id)` which invokes `_chunk_embed_store`. A backfill of `lemmatized_content` requires either (a) re-running full rechunk (re-embeds, expensive) or (b) a dedicated lemmatization-only backfill script that reads existing chunks and updates `lemmatized_content` in place. Plan uses (b) — cheap, no re-embedding.

**Search flow:** `routes.py:357-367` → `service.search()` (L575-696) → `repository.search_vector()` + `repository.search_fulltext()` → RRF + reranker + parent expansion.

## Test Landscape

**Test files** (`app/knowledge/tests/`): `test_repository.py` (BM25 at L289-315), `test_chunking.py`, `test_embedding.py`, `test_reranker.py` (singleton/warm-up patterns at L62-94), `test_service.py`, `test_routes.py`, `conftest.py` (fixtures `sample_latvian_text`, `sample_english_text`, factories `make_document()`, `make_chunk()`).

**Fulltext test pattern** (`test_repository.py:289-315`): mock `mock_db.execute()` to return tuples `(chunk, document, rank)`; no real SQL. Our tests will mock at same layer for `_build_tsvector` / `_build_tsquery` helpers.

**Singleton mocking pattern** (`test_reranker.py:62-94`):
```python
with patch.object(provider, "_get_model", return_value=mock_model):
    await provider.warm_up()
# or direct: provider._model = mock_model
```
Mirror for `UDPipeLemmatizer._model`.

**Type stubs pattern** (`pyproject.toml:146-328`) — need `[[tool.mypy.overrides]] module = "ufal.udpipe.*" ignore_missing_imports = true` + file-level pyright directives on `lemmatizer.py`. This is anti-pattern #3 and #12 — all three layers must be added in the same commit.

**Config flag test** (`app/core/tests/test_config.py:10-80`): `patch.dict(os.environ, {"LATVIAN_LEMMATIZER_ENABLED": "false"})` + `Settings()`.

## Type Check Baseline

Clean starting state — all new errors attributable to this change:

| Target | Pyright | Mypy |
|---|---|---|
| `app/knowledge/` | 0 errors, 0 warnings | 0 errors (43 files) |
| `app/core/config.py` | 0 errors | 0 errors |

## Preflight Warnings

Fragile patterns in existing tests that our change may trip:

| File:line | Pattern | Risk |
|---|---|---|
| `app/knowledge/tests/test_chunking.py:213` | `assert len(children) == 3` | Won't break — lemmatizer doesn't touch chunk count; chunks are stored as raw `content`, lemmatization is a *separate* column. But verify by re-running chunking tests after changes. |
| `app/knowledge/tests/test_chunking.py:281` | `child_count == 3` metadata | Same as above. |
| `app/knowledge/tests/test_repository.py:223-232` | `make_chunk(id=i ... for i in range(5))` with `assert len(chunks) == 5` | Won't break — chunk CRUD doesn't change. |

**Design guard:** `lemmatized_content` is an *additional* column, not a replacement for `content`. Raw `content` still feeds chunking tests and display. No chunk-count semantics change.

**Pydantic `Field` constructor risk (anti-pattern #11, #29):** `DocumentChunk` model gains `lemmatized_content: Mapped[str | None]` as nullable to avoid breaking existing `DocumentChunk(...)` callers. Grep post-change for `DocumentChunk(` / `make_chunk(` to confirm nothing requires the new field.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/knowledge/lemmatizer.py` | `LemmaTokenizer` Protocol + `UDPipeLemmatizer` + `NoopLemmatizer` + `get_lemmatizer_provider()` |
| UPDATE | `app/knowledge/models.py` | Add `lemmatized_content: Mapped[str \| None]` to `DocumentChunk` |
| UPDATE | `app/knowledge/repository.py` | Branch `search_fulltext` by `Document.language`; add `_build_ts_config()` helper; query lemmatization |
| UPDATE | `app/knowledge/chunking.py` | Accept optional `lemmatizer` arg; store `lemmatized_content` in `ChunkResult` |
| UPDATE | `app/knowledge/schemas.py` | Add `lemmatized_content` to `ChunkResult` dataclass (if present there) |
| UPDATE | `app/knowledge/service.py` | `_get_lemmatizer()` singleton; pass into `_chunk_embed_store`; lemmatize queries in `search()` |
| UPDATE | `app/main.py` | Call `warm_up_lemmatizer()` in lifespan (conditional on `latvian_lemmatizer_enabled`) |
| UPDATE | `app/core/config.py` | Add `latvian_lemmatizer_enabled: bool = True`, `udpipe_model_path: str = "models/latvian-ud-2.5.udpipe"` |
| UPDATE | `pyproject.toml` | Add `ufal.udpipe ^1.3` dep; mypy override for `ufal.udpipe.*`; mypy override allowing `disallow_untyped_calls = false` on `app.knowledge.lemmatizer` |
| UPDATE | `.gitignore` | Add `models/*.udpipe` |
| CREATE | `alembic/versions/{rev}_add_lemmatized_content_to_chunks.py` | `op.add_column("document_chunks", sa.Column("lemmatized_content", sa.Text(), nullable=True))` |
| CREATE | `scripts/backfill_lemmatized_content.py` | Iterate existing chunks for `language="lv"` docs, lemmatize and write; no re-embedding |
| CREATE | `scripts/download_udpipe_model.sh` | Fetch Latvian UD 2.5 model to `models/` |
| UPDATE | `Makefile` | `make lemmatize-backfill`, `make download-udpipe-model` |
| CREATE | `app/knowledge/tests/test_lemmatizer.py` | 12+ unit tests (see Testing Strategy) |
| UPDATE | `app/knowledge/tests/test_repository.py` | New tests: BM25 uses lemmatized column for `language=lv`, simple for `language=en` |
| UPDATE | `docs/logging-standard.md` | Document new events: `knowledge.lemmatizer.loaded`, `knowledge.lemmatizer.failed`, `knowledge.lemmatizer.skipped` |
| UPDATE | `app/knowledge/CLAUDE.md` (if exists) | Note lemmatization pipeline |

## Implementation Steps

Order strictly: schemas → models → migration → lemmatizer → repository → chunking → service → main → config/deps → scripts → tests → docs.

### 1. Dependency + type-stub plumbing (anti-pattern #12 — do all 3 layers up front)

**UPDATE** `pyproject.toml`:
- Add `"ufal.udpipe >=1.3.1,<2.0"` to dependencies.
- Add to `[[tool.mypy.overrides]]`:
  ```toml
  [[tool.mypy.overrides]]
  module = "ufal.udpipe.*"
  ignore_missing_imports = true

  [[tool.mypy.overrides]]
  module = "app.knowledge.lemmatizer"
  disallow_untyped_calls = false
  ```

**UPDATE** `.gitignore`: append `models/*.udpipe`.

**Validation:** `uv sync && uv run ruff check pyproject.toml` (TOML parse only).

### 2. Config fields

**UPDATE** `app/core/config.py` — add near the reranker block (around L250):
```python
latvian_lemmatizer_enabled: bool = True
udpipe_model_path: str = "models/latvian-ud-2.5.udpipe"
```

**Validation:** `uv run ruff format app/core/config.py && uv run pyright app/core/config.py && uv run mypy app/core/config.py`.

### 3. Model column

**UPDATE** `app/knowledge/models.py` (`DocumentChunk`, ~L71):
```python
lemmatized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**Validation:** `uv run pyright app/knowledge/models.py`.

### 4. Alembic migration

**CREATE** `alembic/versions/{rev}_add_lemmatized_content_to_chunks.py` using `alembic revision --autogenerate -m "add lemmatized_content to chunks"`, then hand-trim to minimal diff:
```python
def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("lemmatized_content", sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column("document_chunks", "lemmatized_content")
```
Set `down_revision` to latest knowledge migration (`g5h6i7j8k9l0` unless something newer was added).

**Validation:** `uv run alembic upgrade head --sql` (renders SQL, doesn't execute) and then against a live DB: `make db-migrate`.

### 5. Lemmatizer module (Protocol + impls) — mirrors `reranker.py`

**CREATE** `app/knowledge/lemmatizer.py`:
```python
"""Latvian UDPipe lemmatization for BM25 fulltext search."""
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false

from __future__ import annotations
import asyncio
from pathlib import Path
from typing import Protocol, runtime_checkable

import structlog

from app.core.config import Settings

logger = structlog.get_logger(__name__)


@runtime_checkable
class LemmaTokenizer(Protocol):
    async def warm_up(self) -> None: ...
    def lemmatize(self, text: str, language: str) -> str: ...


class UDPipeLemmatizer:
    def __init__(self, model_path: str) -> None:
        self._model_path = model_path
        self._model: object | None = None
        self._pipeline: object | None = None

    async def warm_up(self) -> None:
        if self._model is not None:
            return
        await asyncio.to_thread(self._load)

    def _load(self) -> None:
        from ufal.udpipe import Model, Pipeline  # noqa: PLC0415
        path = Path(self._model_path)
        if not path.exists():
            logger.error("knowledge.lemmatizer.failed", reason="model_missing", path=str(path))
            raise FileNotFoundError(f"UDPipe model not found: {path}")
        model = Model.load(str(path))
        if model is None:
            logger.error("knowledge.lemmatizer.failed", reason="load_returned_none", path=str(path))
            raise RuntimeError(f"UDPipe Model.load returned None for {path}")
        self._model = model
        self._pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, "conllu")
        logger.info("knowledge.lemmatizer.loaded", path=str(path))

    def lemmatize(self, text: str, language: str) -> str:
        if language != "lv":
            return text
        if self._pipeline is None:
            self._load()
        assert self._pipeline is not None  # noqa: S101  -- replace with if block: see anti-pattern #1
        # ANTI-PATTERN FIX: no assert in prod code. Use explicit check.
        processed = self._pipeline.process(text)  # type: ignore[attr-defined]
        return _extract_lemmas(processed)


def _extract_lemmas(conllu: str) -> str:
    """Parse CoNLL-U output, extract column 3 (LEMMA)."""
    lemmas: list[str] = []
    for line in conllu.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) >= 3:
            lemmas.append(fields[2].lower())
    return " ".join(lemmas)


class NoopLemmatizer:
    async def warm_up(self) -> None:
        return
    def lemmatize(self, text: str, language: str) -> str:
        return text


def get_lemmatizer_provider(settings: Settings) -> LemmaTokenizer:
    if not settings.latvian_lemmatizer_enabled:
        logger.info("knowledge.lemmatizer.skipped", reason="disabled_in_config")
        return NoopLemmatizer()
    return UDPipeLemmatizer(settings.udpipe_model_path)
```

**Fix the assert** (anti-pattern #1) — replace `assert self._pipeline is not None` with `if self._pipeline is None: raise RuntimeError("pipeline not initialized")`. Keep file free of `assert` statements.

**Validation:** `uv run ruff format app/knowledge/lemmatizer.py && uv run ruff check app/knowledge/lemmatizer.py && uv run pyright app/knowledge/lemmatizer.py && uv run mypy app/knowledge/lemmatizer.py`.

### 6. Repository — branch BM25 by language

**UPDATE** `app/knowledge/repository.py:371-409` (`search_fulltext`).

Current: single tsvector/tsquery with `'simple'` against `DocumentChunk.content`.

New behavior:
- Accept optional `lemmatized_query: str | None` param (service will pre-lemmatize if Latvian).
- Build two branches via SQL `CASE`: when `Document.language = 'lv'` AND `DocumentChunk.lemmatized_content IS NOT NULL`, use `to_tsvector('simple', DocumentChunk.lemmatized_content)` with `plainto_tsquery('simple', :lemmatized_query)`. Else fall back to `to_tsvector('simple', DocumentChunk.content)` with `plainto_tsquery('simple', :raw_query)`.

Sketch (keeping parameterized SQL — no string interpolation):
```python
async def search_fulltext(
    self,
    query_text: str,
    limit: int,
    *,
    lemmatized_query: str | None = None,
    ...
) -> list[tuple[DocumentChunk, Document, float]]:
    # Use COALESCE(lemmatized_content, content) with a dynamically-chosen query.
    chunk_text_expr = func.coalesce(DocumentChunk.lemmatized_content, DocumentChunk.content)
    # Prefer lemmatized query when provided; otherwise raw.
    query_param = lemmatized_query if lemmatized_query else query_text
    ts_query = func.plainto_tsquery(text("'simple'"), query_param)
    ts_vector = func.to_tsvector(text("'simple'"), chunk_text_expr)
    rank = func.ts_rank(ts_vector, ts_query).label("rank")
    ...
```
Simpler than branching on language in SQL — `COALESCE` handles English docs (where `lemmatized_content IS NULL`) by falling through to `content`. Service layer decides whether to pass `lemmatized_query`.

**Validation:** `uv run ruff format app/knowledge/repository.py && uv run pyright app/knowledge/repository.py`.

### 7. Chunking — compute lemmatized_content

**UPDATE** `app/knowledge/chunking.py`:
- Add `lemmatized_content: str | None = None` to `ChunkResult` dataclass.
- `chunk_text()` / `chunk_text_semantic()` do NOT call UDPipe directly (keep chunking pure / synchronous / testable without the C++ dep). Instead, add a post-processing helper `apply_lemmatization(chunks: list[ChunkResult], lemmatizer, language) -> list[ChunkResult]` called from the service layer.

**Validation:** `uv run pyright app/knowledge/chunking.py && uv run pytest app/knowledge/tests/test_chunking.py -x`.

### 8. Service — wire singleton + orchestrate

**UPDATE** `app/knowledge/service.py`:

- Add singleton around L52-80:
  ```python
  _lemmatizer_provider: LemmaTokenizer | None = None
  def _get_lemmatizer() -> LemmaTokenizer:
      global _lemmatizer_provider
      if _lemmatizer_provider is None:
          _lemmatizer_provider = get_lemmatizer_provider(get_settings())
      return _lemmatizer_provider

  async def warm_up_lemmatizer() -> None:
      await _get_lemmatizer().warm_up()
  ```
- In `_chunk_embed_store` (~L304-349): after chunking, call `apply_lemmatization(chunks, _get_lemmatizer(), document.language)` and set `DocumentChunk.lemmatized_content=chunk.lemmatized_content` on create.
- In `search()` (~L575-696): before calling `repository.search_fulltext(...)`, compute `lemmatized_query = _get_lemmatizer().lemmatize(query_text, "lv") if settings.latvian_lemmatizer_enabled else None`. Pass via new kwarg.
- Fail-safe: wrap `lemmatize()` in `try/except Exception` with `logger.error("knowledge.lemmatizer.failed", ...)`, fall back to `None` so search still runs.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py`.

### 9. Main — lifespan warm-up

**UPDATE** `app/main.py` — in the lifespan `async with` block, next to `warm_up_reranker()`:
```python
if settings.latvian_lemmatizer_enabled:
    try:
        await warm_up_lemmatizer()
    except Exception:
        logger.exception("knowledge.lemmatizer.failed", stage="startup_warmup")
```
Startup must not hard-fail if the model file is missing; log and continue (fall back behavior: `lemmatize()` returns raw text on exception).

**Validation:** `uv run ruff format app/main.py && uv run pyright app/main.py`.

### 10. Input length guard (CTX-INPUT)

Confirm `KnowledgeSearchRequest.query` in `app/knowledge/schemas.py` has `max_length` (typical cap: 1000). If missing, add `Field(..., max_length=1000, min_length=1)`. UDPipe cost is linear in text length; cap prevents DoS via 10MB queries.

**Validation:** `uv run pytest app/knowledge/tests/test_routes.py -x`.

### 11. Logging taxonomy

**UPDATE** `docs/logging-standard.md` (under `knowledge` domain):
```
knowledge.lemmatizer.loaded      | info  | UDPipe model loaded, includes path
knowledge.lemmatizer.failed      | error | Model load or lemmatize error, includes reason
knowledge.lemmatizer.skipped     | info  | Disabled via config
```

**Validation:** `make audit-log-taxonomy`.

### 12. Backfill script + make target

**CREATE** `scripts/backfill_lemmatized_content.py`:
- Async script mirroring `scripts/rechunk_documents.py` skeleton
- For each `Document` where `language="lv"`: stream chunks in batches, lemmatize each chunk's `content`, `UPDATE document_chunks SET lemmatized_content = :val WHERE id = :id` — no re-embedding, no re-chunking.
- Flags: `--dry-run`, `--document-id`, `--batch-size`, `--limit`.
- Structured logging: `knowledge.lemmatizer.backfill_started`, `knowledge.lemmatizer.backfill_completed` with counts.

**CREATE** `scripts/download_udpipe_model.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p models
curl -fL -o models/latvian-ud-2.5.udpipe \
  https://lindat.mff.cuni.cz/repository/xmlui/bitstream/handle/11234/1-3131/latvian-lvtb-ud-2.5-191206.udpipe
```
(Confirm LINDAT URL before running; if it 404s, ask user for the canonical source rather than guess.)

**UPDATE** `Makefile`:
```make
download-udpipe-model:
	bash scripts/download_udpipe_model.sh

lemmatize-backfill:
	uv run python scripts/backfill_lemmatized_content.py

lemmatize-backfill-dry-run:
	uv run python scripts/backfill_lemmatized_content.py --dry-run
```

**Validation:** `bash -n scripts/download_udpipe_model.sh` (syntax only; don't fetch in planning).

### 13. Tests

**CREATE** `app/knowledge/tests/test_lemmatizer.py` — 12+ tests:

| # | Test | Mock strategy |
|---|---|---|
| 1 | `test_noop_lemmatizer_returns_text_unchanged` | Direct — no mock |
| 2 | `test_udpipe_lemmatizer_disabled_returns_noop` | `Settings(latvian_lemmatizer_enabled=False)` |
| 3 | `test_udpipe_lemmatizer_non_latvian_passthrough` | Direct: `lemmatize("hello world", "en") == "hello world"` (early return) |
| 4 | `test_udpipe_noun_cases_collapsed` | Patch `_load` to install a fake pipeline returning canned CoNLL-U |
| 5 | `test_udpipe_verb_conjugations_collapsed` | Same patch strategy |
| 6 | `test_udpipe_compound_word` | Same |
| 7 | `test_udpipe_mixed_latvian_english_input` | Same — assert lemmas preserved for lv tokens |
| 8 | `test_extract_lemmas_parses_conllu_columns` | Pure unit on `_extract_lemmas` |
| 9 | `test_extract_lemmas_skips_comments_and_blanks` | Pure unit |
| 10 | `test_warm_up_idempotent` | Patch `_load` with `Mock` counter, call twice, assert called once |
| 11 | `test_warm_up_missing_model_raises` | Mock `Path.exists` False, expect `FileNotFoundError` |
| 12 | `test_lemmatize_without_warmup_auto_loads` | `_model is None`, call `lemmatize`, assert `_load` called |
| 13 | `test_get_lemmatizer_provider_enabled_returns_udpipe` | `Settings(latvian_lemmatizer_enabled=True)` |

**UPDATE** `app/knowledge/tests/test_repository.py`:
- New test: `test_search_fulltext_uses_lemmatized_query` — mock `execute`, assert SQL bind params include lemmatized form.
- New test: `test_search_fulltext_falls_back_to_content_when_lemmatized_null` — assert `COALESCE` behavior (smoke via SQL compilation).

Type-annotate every test helper (`-> None`) per anti-pattern #7, #26.

**Validation per step:** `uv run pytest app/knowledge/tests/test_lemmatizer.py -x`, then `uv run pytest app/knowledge/tests/ -x`.

### 14. Integration verify (manual, post-validation)

1. `make db && make download-udpipe-model && make db-migrate`
2. `make dev-be`
3. Ingest a Latvian doc containing "autobuss" and "apkopē".
4. `make lemmatize-backfill`
5. `POST /api/v1/knowledge/search` with `{"query": "autobusu apkope"}`.
6. Expect the Latvian doc in results at rank ≥ 1.
7. Compare recall@3 on 20 Latvian QA pairs with/without `latvian_lemmatizer_enabled`. Target: +15-20% recall.

## Testing Strategy

- **Unit (fast, no Docker):** lemmatizer module tests with patched UDPipe; `_extract_lemmas` parser tests; config flag tests.
- **Integration (`@pytest.mark.integration`):** repository SQL-compilation tests verifying `COALESCE` + bind param; alembic migration up/down.
- **End-to-end verify:** Manual `/health` + search round-trip per Step 14 — not automated until we have a reproducible Latvian seed fixture.

## Logging Events

| Event | Level | Fields |
|---|---|---|
| `knowledge.lemmatizer.loaded` | info | `path` |
| `knowledge.lemmatizer.failed` | error | `reason`, `path?`, `stage?` |
| `knowledge.lemmatizer.skipped` | info | `reason` |
| `knowledge.lemmatizer.backfill_started` | info | `total_docs`, `dry_run` |
| `knowledge.lemmatizer.backfill_completed` | info | `updated_chunks`, `elapsed_ms` |

## Acceptance Criteria

- [ ] `app/knowledge/lemmatizer.py` exists, mirrors reranker Protocol+impls+factory pattern
- [ ] `document_chunks.lemmatized_content` column present via alembic migration with both `upgrade()` and `downgrade()`
- [ ] `search_fulltext` uses `COALESCE(lemmatized_content, content)` for tsvector
- [ ] Service passes lemmatized query to repository when `latvian_lemmatizer_enabled` and raw query is Latvian
- [ ] Lemmatizer failures are logged and non-fatal (search still runs with raw query)
- [ ] Warm-up called in lifespan; startup continues even if model file missing
- [ ] 12+ lemmatizer unit tests pass
- [ ] All pre-existing knowledge tests still pass
- [ ] Pyright errors ≤ baseline (0) on `app/knowledge/` and `app/core/config.py`
- [ ] Mypy errors ≤ baseline (0) on `app/knowledge/` and `app/core/config.py`
- [ ] `make audit-log-taxonomy` passes with new events documented
- [ ] `make security-audit-quick` passes
- [ ] Backfill script runs dry-run cleanly on a seeded DB

## Security Checklist

- [ ] CTX-INPUT: `KnowledgeSearchRequest.query` has `max_length` cap (1000); lemmatize CPU-bound but bounded
- [ ] CTX-INPUT: All SQL uses SQLAlchemy `text()` + bind params; no string interpolation of lemmatized output
- [ ] CTX-INFRA: `udpipe_model_path` is filesystem path, never user-controlled
- [ ] CTX-INFRA: Model file in `.gitignore`, fetched via `scripts/download_udpipe_model.sh`
- [ ] CTX-INFRA: Mypy `[[overrides]]` + pyright file-level directives present for `ufal.udpipe` (anti-pattern #3, #12)
- [ ] No `assert` in production code (anti-pattern #1)
- [ ] Bare `except` avoided; every lemmatize failure logs at `error` (anti-pattern #37)
- [ ] Fail-open for lemmatizer exceptions — search degrades to raw-text BM25 (documented fallback)

## Verification (final)

```bash
make check                              # ruff + mypy + pyright + unit tests
uv run pytest app/knowledge/tests/ -v   # full knowledge suite
uv run pytest app/tests/test_security.py -v
make audit-log-taxonomy
make security-audit-quick
```

Pyright errors must remain at 0 for `app/knowledge/` and `app/core/config.py`.
