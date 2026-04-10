# Plan: AI-4.4 — Re-Chunk Existing Documents

## Context

AI-4.1/4.2/4.3 introduced heading-aware semantic chunking with parent-child structure
and search-time parent expansion. Documents ingested before those changes still use
the old 512-char recursive splitter and have no `parent_chunk_id`, `heading_path`,
or `section_type` set on their chunks. They cannot benefit from the new retrieval
quality without being re-chunked.

This task adds a one-shot migration script that walks every document in the DB,
deletes its existing chunks, and re-runs the modern ingestion pipeline (extract →
semantic chunk → embed → two-phase parent/child store) against the file already
on disk. A `--dry-run` mode lets ops preview the change before committing.

## Security Context Assessment

| Context | Active? | Reason |
|---|---|---|
| CTX-AUTH | No | No auth flow touched |
| CTX-RBAC | No | CLI script only — no HTTP surface added |
| CTX-FILE | Partial | Re-reads files on disk via existing `processing.extract_text`; no new upload path. Reuse existing path validation in `processing.py`. |
| CTX-AGENT | No | Not an agent tool |
| CTX-INFRA | Yes | New script must read `DATABASE_URL` from env (not hardcoded), and Makefile target must not leak credentials. Document **risk** in script docstring: this script mutates production data. |
| CTX-INPUT | Partial | CLI args (`--dry-run`, `--batch-size`, `--document-id`) parsed by argparse — no SQL injection vector, but still bound `int` and validate ranges. |

**Plan-derived requirements:**
- Use `os.environ["DATABASE_URL"]` via the existing `app.core.config.get_settings()`; do not duplicate URL parsing.
- Script docstring must warn that this is a destructive, irreversible operation (chunk rows are deleted before re-creation).
- `--batch-size` must be `int` with a sane default (10) and floor of 1.
- Add `--document-id` for targeted re-chunking of a single document during testing.

## Research Summary

### Knowledge module entry points
- **Semantic chunker:** `chunk_text_semantic(text, target_size, min_size, max_size, chunk_overlap) -> list[ChunkResult]` — `app/knowledge/chunking.py:364`
- **`ChunkResult` dataclass:** `app/knowledge/chunking.py:12` — fields `content`, `chunk_index`, `metadata`, `heading_path`, `section_type`, `is_parent`, `parent_index`
- **Text extraction (stateless):** `processing.extract_text(file_path: str, source_type: str) -> tuple[str, bool]` — `app/knowledge/processing.py:21`. Returns `(text, ocr_applied)`. No DB dependency.
- **Embedding provider factory:** `get_embedding_provider(settings) -> EmbeddingProvider` — `app/knowledge/embedding.py:161`. Wrapped by `CachedEmbeddingProvider`.
- **Embed method:** `EmbeddingProvider.embed(texts: list[str]) -> list[list[float]]` (async) — `app/knowledge/embedding.py:22`

### Repository methods (already exist)
- `list_documents(*, offset, limit, domain, status, language, tag)` — `app/knowledge/repository.py:86`
- `count_documents(...)` — line 124
- `get_document(document_id)` — line 74
- `get_chunks_by_document(document_id)` — line 226
- `bulk_create_chunks(chunks, flush_only=False)` — line 247 (the existing two-phase parent flush helper)
- `update_document_status(document_id, status, error_message, chunk_count)` — line 153
- `delete_document(document_id)` — line 176 (CASCADE-deletes chunks **and** the Document — too aggressive; we only want chunks gone)

### Models
- `Document` (`app/knowledge/models.py:30`): has `id`, `filename`, `file_path` (nullable str — set by `update_document_file_path`), `source_type`, `status`, `chunk_count`, `evergreen`, `metadata_json`, etc. Raw extracted text is **not** persisted — we must re-extract from `file_path`.
- `DocumentChunk` (`app/knowledge/models.py:71`): `parent_chunk_id` (self-FK, nullable), `heading_path`, `section_type`, `embedding` (Vector(1024)), `metadata_json`.
- Foreign key on `DocumentChunk.document_id` is `ON DELETE CASCADE`, but we are intentionally **not** deleting the document — only its chunks. We need a new repository helper.

### Reference ingestion code
- The two-phase parent/child write pattern lives in `KnowledgeService.ingest_document` at `app/knowledge/service.py:251–342`. The script must use the **same algorithm** to preserve invariants (parent ids resolved before children write). Refactoring this into a private helper on the service is the cleanest path so the script and the live ingestion stay in sync.

### Standalone script pattern
- Reference: `scripts/docker-migrate.py:1–60` — uses `asyncio.run(main())`, prints with `[migrate]` prefix, exits with non-zero code on failure, derives `DATABASE_URL` from env.
- Existing scripts use `print()` (allowed by `[per-file-ignores] "scripts/**/*.py" = ["T201"]` in pyproject.toml).
- DB session for non-request code: `async with get_db_context() as session:` — `app/core/database.py:46`.

### Settings (already in place)
- `knowledge_semantic_chunking_enabled`, `knowledge_chunk_target_size`, `knowledge_chunk_min_size`, `knowledge_chunk_max_size`, `knowledge_chunk_overlap` — `app/core/config.py:223`. Reuse via `get_settings()`.

## Test Landscape

### Existing test infrastructure (reuse, do not duplicate)
- `app/knowledge/tests/conftest.py` — `sample_upload`, `sample_latvian_text`, `sample_english_text` fixtures.
- `app/knowledge/tests/test_repository.py:15-57` — `make_document(**overrides)` and `make_chunk(**overrides)` factories. Marked `@pytest.mark.integration` (line 75-76).
- `app/knowledge/tests/test_chunking.py` — patterns for asserting semantic chunker output (parent/child relationships, heading paths, section types).
- `app/knowledge/tests/test_embedding.py:52-69` — `MagicMock` + `AsyncMock` patterns for mocking the embedding provider; `side_effect` for batch responses.

### Test gaps to fill
- No `scripts/tests/` exists. Migration scripts in this repo have historically been smoke-tested manually.
- For AI-4.4 we add **unit tests for the rechunk service helper** (where the real logic lives) using mocks for embedding + DB. The script itself becomes a thin CLI wrapper around the service helper and is exercised via a single happy-path integration test if Docker is available.

### Patterns to avoid
- `test_chunking.py:56-57` uses substring `.find()` for char offset assertions — brittle for repeated text. We will assert structural shape (counts, parent links) instead.
- Mock `side_effect=[...]` ordering breaks under retry loops — keep retry logic out of the helper for testability.

## Type Check Baseline

| Path | pyright | mypy |
|---|---|---|
| `app/knowledge/` | **0 errors** | 0 errors (3 unrelated errors in `app/core/agents/` follow-imports) |
| `scripts/` (9 .py files) | 187 errors | 22 errors |

**Implications:**
- `pyproject.toml` `[tool.pyright]` has `include = ["app"]` — `scripts/` is **not** in default pyright scope. The new script must be validated by passing it explicitly: `uv run pyright scripts/rechunk_documents.py`.
- Same for mypy: `uv run mypy scripts/rechunk_documents.py` (no project-wide regression possible because scripts/ baseline is already dirty).
- Ruff lints scripts/ globally and `T201` (print) is allow-listed for `scripts/**/*.py`.
- Goal: `scripts/rechunk_documents.py` passes pyright + mypy + ruff with **0 errors** as a single file.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| UPDATE | `app/knowledge/repository.py` | Add `delete_chunks_by_document(document_id)` (deletes chunks but keeps Document row) |
| UPDATE | `app/knowledge/service.py` | Extract two-phase store algo into private helper `_chunk_embed_store(doc, text)` and add public `rechunk_document(document_id)`; reuse helper from `ingest_document` and from the script |
| CREATE | `scripts/rechunk_documents.py` | CLI entry point: argparse, batch loop, dry-run, progress prints |
| UPDATE | `Makefile` | Add `rechunk` and `rechunk-dry-run` targets and list them in `.PHONY` + `help` |
| CREATE | `app/knowledge/tests/test_rechunk.py` | Unit tests for `KnowledgeService.rechunk_document` with mocked embedding + extraction; one integration-marked happy-path test |

No new schemas, models, routes, migrations, exceptions, or middleware. No new dependencies.

## Implementation Steps

### Step 1 — Add `delete_chunks_by_document` to repository

In `app/knowledge/repository.py`, append (after `delete_document` at line 186) a new method that issues a bulk DELETE on `DocumentChunk` rows for a given document id, **without** deleting the parent `Document`. Use `sqlalchemy.delete(DocumentChunk).where(DocumentChunk.document_id == document_id)`. Commit at the end.

```python
async def delete_chunks_by_document(self, document_id: int) -> int:
    """Delete all chunks for a document, keeping the Document row.

    Used by the AI-4.4 re-chunk migration to wipe stale chunks before
    re-running the ingestion pipeline against the existing file.

    Args:
        document_id: The document's database ID.

    Returns:
        Number of chunk rows deleted.
    """
    from sqlalchemy import delete as sql_delete

    result = await self.db.execute(
        sql_delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )
    await self.db.commit()
    return int(result.rowcount or 0)
```

Move the `from sqlalchemy import delete as sql_delete` to module-top imports if any other method already needs it — otherwise inline import is acceptable to avoid disturbing the existing file. Prefer top-of-file import alongside the existing `from sqlalchemy import select, distinct, func` line.

**Validation:** `uv run ruff format app/knowledge/repository.py && uv run ruff check --fix app/knowledge/repository.py && uv run pyright app/knowledge/repository.py && uv run mypy app/knowledge/repository.py`

### Step 2 — Refactor service two-phase store into a reusable helper

In `app/knowledge/service.py`, extract lines 251–343 of `ingest_document` into a new private async method:

```python
async def _chunk_embed_store(
    self,
    *,
    document_id: int,
    text: str,
) -> int:
    """Chunk + embed + two-phase parent/child store for a document.

    Returns the number of chunks created. Used by both fresh ingestion
    and the AI-4.4 re-chunk migration.

    Caller is responsible for setting document status before/after.
    """
```

Then update `ingest_document` to call `chunk_count = await self._chunk_embed_store(document_id=doc.id, text=text)` and pass that to the existing `update_document_status` call. Make sure the early-empty-text branch (`if not chunks: ...`) and the return path still work — push that empty-chunk handling into the helper too (return 0).

Add the new public method:

```python
async def rechunk_document(self, document_id: int) -> int:
    """Re-chunk a single document using the current chunking config.

    Deletes existing chunks, re-extracts text from the stored file,
    re-runs the chunk → embed → store pipeline, and updates the
    document chunk_count. Returns the new chunk count.

    Raises:
        NotFoundError: Document does not exist.
        ProcessingError: file_path is missing or extraction fails.
    """
    doc = await self.repository.get_document(document_id)
    if doc is None:
        raise NotFoundError(f"Document {document_id} not found")
    if not doc.file_path:
        raise ProcessingError(
            f"Document {document_id} has no stored file_path; cannot re-extract"
        )
    text, ocr_applied = await processing.extract_text(doc.file_path, doc.source_type)
    await self.repository.delete_chunks_by_document(document_id)
    chunk_count = await self._chunk_embed_store(document_id=document_id, text=text)
    await self.repository.update_document_status(document_id, "completed", None, chunk_count)
    if ocr_applied:
        await self.repository.update_document_ocr_applied(document_id, ocr_applied=True)
    return chunk_count
```

**Critical invariants:**
- Use the **existing** `_get_embedding()` singleton from the module (line 57 of service.py) — do not instantiate a fresh provider per call.
- Preserve the parent-then-children flush ordering exactly as in the original `ingest_document` block.
- Do **not** touch `Document.metadata_json`, `evergreen`, `domain`, `language`, or `title` — only chunks change.
- Do **not** call `_auto_tag_document` from `rechunk_document` — auto-tagging already ran when the document was first ingested; re-running it would overwrite human-curated tags.

**Anti-patterns to honor (from `_shared/python-anti-patterns.md`):**
- #5: don't import or assign anything you don't use in the new helper.
- #11: this changes how `ingest_document` builds chunks but does not add a required field — still `Grep` for `_chunk_embed_store(` and `rechunk_document(` to confirm zero unintended call sites once implemented.
- #29: no schema field additions to existing Pydantic models.
- #50: cleanup-on-failure — if `delete_chunks_by_document` succeeds but `_chunk_embed_store` raises, the document is left with zero chunks. Catch broad `Exception` in `rechunk_document`, mark the document `status="failed"` with the error message via `update_document_status`, and re-raise so the script's outer loop can record + skip.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py && uv run mypy app/knowledge/service.py`

### Step 3 — Create `scripts/rechunk_documents.py`

```python
"""Re-chunk all existing knowledge documents using the new SemanticChunker.

ONE-SHOT MIGRATION (AI-4.4): walks every Document row, deletes its existing
chunks, and re-runs the ingestion pipeline (extract → semantic chunk → embed →
two-phase parent/child store) against the file on disk. Documents whose
file_path is missing are skipped with a warning.

DESTRUCTIVE: chunk rows are deleted before re-creation. Run with --dry-run
first to preview impact. Document metadata, tags, and embeddings cache are
NOT touched.

Usage:
    uv run python scripts/rechunk_documents.py --dry-run
    uv run python scripts/rechunk_documents.py
    uv run python scripts/rechunk_documents.py --document-id 42
    uv run python scripts/rechunk_documents.py --batch-size 5
"""
```

Structure:

1. **CLI:** `argparse` with `--dry-run` (bool), `--batch-size` (int, default 10, validate `>= 1`), `--document-id` (int | None), `--limit` (int | None for testing).
2. **Async main:**
   ```python
   async def main(args: argparse.Namespace) -> int:
       async with get_db_context() as session:
           repo = KnowledgeRepository(session)
           service = KnowledgeService(session)
           if args.document_id is not None:
               doc_ids = [args.document_id]
           else:
               doc_ids = await _collect_doc_ids(repo, limit=args.limit)
           # Process in batches; per-doc try/except; track stats
   ```
3. **Per-document loop:**
   - Skip if `doc.file_path is None` → counted as `skipped_no_file`.
   - In dry-run, log: `[rechunk] DRY-RUN doc {id} ({filename}) would re-chunk: {existing_chunk_count} chunks → unknown` and continue.
   - In real run, call `await service.rechunk_document(doc_id)` and log `[rechunk] doc {id} ({filename}) {old} → {new} chunks ({elapsed_ms}ms)`.
   - Catch `Exception` per doc, log + record under `failed`, continue to next.
4. **Batching:** process in groups of `batch_size`, awaiting each group sequentially (not concurrently — embedding provider is rate-limited and DB session is single).
5. **Summary at end:** total processed, succeeded, skipped (no file), failed (with first 5 doc ids), wall-clock time. Exit `1` if any failed, `0` otherwise.
6. **Logging:** plain `print("[rechunk] ...")` to stdout (per existing `scripts/docker-migrate.py` convention; T201 is allow-listed for scripts/).
7. **DB URL:** rely on `app.core.config.get_settings()` and `get_db_context()` — do **not** parse `DATABASE_URL` directly.

**`sys.path` shim:** mirror `scripts/docker-migrate.py` — `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))` so `from app.core.database import get_db_context` resolves when run via `uv run python scripts/...`.

**Anti-patterns to honor:**
- #5: no unused imports.
- #38: this is not a long-running background task — no `CancelledError` handling needed, but the per-doc `try/except Exception` must log the exception with traceback (`traceback.format_exc()` or `logger.exception` style print).
- #44: never log the `DATABASE_URL` (even masked) — the script doesn't need to print it.
- Do not log file paths that include the document storage root if it could include user-uploaded filenames containing secrets. Log only `doc.id` and `doc.filename`.

**Validation:** `uv run ruff format scripts/rechunk_documents.py && uv run ruff check --fix scripts/rechunk_documents.py && uv run pyright scripts/rechunk_documents.py && uv run mypy scripts/rechunk_documents.py`

The new file must end at **0 pyright + 0 mypy errors** even though the rest of `scripts/` is dirty.

### Step 4 — Add Makefile targets

Edit `Makefile`:

1. Append `rechunk rechunk-dry-run` to the `.PHONY:` line at the top.
2. Add (after the existing `db-restore` target around line 95):

```makefile
rechunk: ## Re-chunk all documents with the new SemanticChunker (one-shot AI-4.4 migration)
	uv run python scripts/rechunk_documents.py

rechunk-dry-run: ## Preview re-chunking without modifying the database
	uv run python scripts/rechunk_documents.py --dry-run
```

3. The `## ` doc comments are picked up by `make help` automatically (see line 149 of Makefile).

**Validation:** `make help | grep rechunk` should show both targets. `make rechunk-dry-run` should run end-to-end against a dev DB.

### Step 5 — Tests

Create `app/knowledge/tests/test_rechunk.py`:

```python
"""Tests for the AI-4.4 re-chunk pipeline (KnowledgeService.rechunk_document)."""
```

**Unit tests (no `@pytest.mark.integration`, mock everything):**

1. `test_rechunk_document_happy_path` — mock repo `get_document` to return a document with `file_path="/tmp/foo.md"`, mock `processing.extract_text` to return `("# Heading\n\npara1\n\npara2", False)`, mock `_get_embedding` to return a fixture vector, call `service.rechunk_document(1)`, assert:
   - `repo.delete_chunks_by_document` called with `1`
   - `repo.bulk_create_chunks` called at least once
   - `repo.update_document_status` called with `(1, "completed", None, <int>)`
   - Return value is the new chunk count

2. `test_rechunk_document_missing_file_path_raises` — mock `get_document` to return doc with `file_path=None`, assert `ProcessingError` is raised, assert `delete_chunks_by_document` was **not** called.

3. `test_rechunk_document_not_found_raises` — mock `get_document` returns `None`, assert `NotFoundError` is raised.

4. `test_rechunk_document_marks_failed_on_chunk_error` — mock extraction to succeed, mock `bulk_create_chunks` to raise `RuntimeError`, assert `update_document_status` called with `("failed", error_message, 0)`, assert the original exception re-raises.

5. `test_rechunk_document_preserves_metadata` — assert that no calls to `update_document` or `update_document_file_path` happen (regression guard for metadata-mutation bugs).

**Mock patterns:** follow `app/knowledge/tests/test_embedding.py:52-69`. Use `MagicMock` for sync objects, `AsyncMock` for async DB and embedding methods. Patch `app.knowledge.service._get_embedding` (not the importing module — see anti-pattern #36).

**Test helper return types** must be annotated `-> None` (anti-pattern #7).

**Optional integration test (gated by `@pytest.mark.integration`):** create a real document via `make_document`, write a small markdown file to a temp dir, set `file_path`, call `rechunk_document`, assert `get_chunks_by_document` returns chunks with `heading_path` populated. Skip if `LocalEmbeddingProvider` model isn't downloaded.

**Validation:** `uv run pytest app/knowledge/tests/test_rechunk.py -v -m "not integration"`

### Step 6 — Full validation pyramid

After all steps:

1. `uv run ruff format app/knowledge/ scripts/rechunk_documents.py`
2. `uv run ruff check --fix app/knowledge/ scripts/rechunk_documents.py`
3. `uv run pyright app/knowledge/ scripts/rechunk_documents.py`
4. `uv run mypy app/knowledge/ scripts/rechunk_documents.py`
5. `uv run pytest app/knowledge/tests/ -v -m "not integration"`
6. `make security-audit-quick`
7. `uv run pytest app/tests/test_security.py -v` — confirm no convention regression (script doesn't add an HTTP endpoint, so this should remain green by construction)
8. `make rechunk-dry-run` against a local dev DB with at least one document

## Preflight Warnings

- **`service.ingest_document` refactor risk:** lines 251–343 are the heart of the existing test suite for ingestion. Run `uv run pytest app/knowledge/tests/test_routes.py app/knowledge/tests/test_repository.py -v` after Step 2 — these are the most likely consumers to break.
- **Substring-based offset asserts in `test_chunking.py:56-57`** are unrelated to this work but very fragile; do not rely on similar patterns in the new tests.
- **Embedding provider singleton** is module-level cached; if a test file imports the service and sets up `_get_embedding`, leaks across tests are possible. Use `monkeypatch` to patch + restore rather than module-level reassignment.
- **`bulk_create_chunks` flush ordering** is non-obvious — the parent flush relies on `flush_only=True` then session.flush() so children get real ids in the same transaction. Reuse the helper, do not re-implement.
- **`Document.file_path` may legitimately be `None`** for documents that failed during initial ingestion (status="failed" before line 243 of service.py executed). The script must skip these gracefully, not crash.

## Security Checklist

This task adds **zero new HTTP endpoints**. The script-specific checklist:

- [ ] No hardcoded credentials — script reads `DATABASE_URL` via `get_settings()`/`get_db_context()` only
- [ ] `argparse` int args are bounded (`batch_size >= 1`)
- [ ] No `--force` flag without `--dry-run` first being communicated in `--help` text
- [ ] Script docstring contains a destructive-operation warning
- [ ] Per-doc errors logged but never raise the underlying `DATABASE_URL`, file system root, or stack frames containing secrets
- [ ] Convention test suite (`app/tests/test_security.py`) remains green — no new endpoints to register

For the unchanged `ingest_document` path:

- [ ] Existing rate limits, auth, and `escape_like` usage remain untouched
- [ ] `update_document_ocr_applied` is still called only when OCR was actually applied

## Verification

- [ ] `make check` passes (lint + types + unit tests)
- [ ] `uv run pyright scripts/rechunk_documents.py` → 0 errors
- [ ] `uv run mypy scripts/rechunk_documents.py` → 0 errors
- [ ] `uv run pytest app/knowledge/tests/test_rechunk.py -v` → all green
- [ ] `uv run pytest app/knowledge/tests/test_repository.py app/knowledge/tests/test_routes.py -v -m "not integration"` → no regression from service refactor
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors on `app/knowledge/` ≤ baseline (**0 before**)
- [ ] Mypy errors on `app/knowledge/` ≤ baseline (**0 in module; 3 unrelated in `app/core/agents/`**)
- [ ] `make help | grep rechunk` shows both new targets
- [ ] `make rechunk-dry-run` against dev DB prints a per-document preview, exits 0, and does not mutate the chunks table (verify with `SELECT count(*) FROM document_chunks` before/after)
- [ ] Search quality spot-check (manual): pick 5 production queries, run `make rechunk` on a staging copy, and confirm parent-context expansion now activates for the migrated documents
