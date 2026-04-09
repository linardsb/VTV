# Plan: AI-4.1 Heading-Aware Semantic Chunker

## Context

Replace the fixed 512-char recursive splitter in `chunking.py` with a heading-aware chunker that respects document structure. Fixed-size splitting breaks mid-sentence, mid-paragraph, and mid-SOP-step. A "What to do when bus breaks down" SOP gets split into fragments that individually make no sense. Heading-aware chunking keeps each section coherent by splitting at heading/section boundaries with adaptive sizing.

## Security Context Assessment

**Active contexts:** None. This feature modifies internal chunking logic only — no new endpoints, no user input handling, no file uploads, no auth changes. The existing upload pipeline (CTX-FILE) is unchanged.

## Research Summary

### Current Implementation

**`app/knowledge/chunking.py`** (155 lines):
- `ChunkResult` dataclass: `content`, `chunk_index`, `metadata` (stores `char_start`/`char_end`)
- `chunk_text()`: Main entry, splits by separators `["\n\n", "\n", ". ", " "]`, builds overlapping chunks
- `_split_by_separators()`: Recursive hierarchical splitting
- `_build_chunks()`: Merges segments with overlap

### Pipeline Integration

**`app/knowledge/service.py:250-274`** — `ingest_document()`:
```
text extraction → chunk_text(text, chunk_size, chunk_overlap) → embed → build DocumentChunk objects → bulk_create_chunks
```

`metadata_json` on `DocumentChunk` is always `None` currently — available for `heading_path` storage.

### Key Insight

**Extraction already produces markdown headings.** `app/knowledge/processing.py`:
- PDF: PyMuPDF detects font size/bold → `## Header` / `### Header`
- DOCX: Maps Word heading styles → `# Heading 1`, `## Heading 2`
- Excel: Sheet names as headings
- Email: Headers as bold markdown

So the semantic chunker just needs to parse markdown `#` headings from the already-extracted text.

### Config Pattern

`app/core/config.py:190-221` — existing `knowledge_*` settings:
- `knowledge_chunk_size: int = 512`
- `knowledge_chunk_overlap: int = 100`
- `knowledge_search_limit: int = 50`
- `knowledge_hyde_enabled: bool = False`

### Model

`app/knowledge/models.py` — `DocumentChunk`:
- `metadata_json: Mapped[str | None]` — Text column, currently always None
- No schema changes needed; heading metadata goes into this existing field as JSON

## Test Landscape

**`app/knowledge/tests/test_chunking.py`** (70 lines, 7 tests):
- Tests: short text, empty text, paragraph splitting, overlap, Latvian diacritics, char offsets
- Pure unit tests, no mocks needed, no DB

**Fixtures available** (`conftest.py`):
- `sample_latvian_text`, `sample_english_text`, `sample_upload`

**Factories** (`test_repository.py`):
- `make_document()`, `make_chunk()` — for integration tests

## Type Check Baseline

- **Pyright:** 0 errors on `app/knowledge/` (clean)
- **Mypy:** 0 errors in knowledge/ (3 pre-existing errors in `app/core/agents/` pulled transitively)

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/knowledge/chunking.py` | Add `SemanticChunker` class, `chunk_text_semantic()` function |
| UPDATE | `app/knowledge/service.py` | Call semantic chunker when enabled, store heading metadata |
| UPDATE | `app/core/config.py` | Add 4 new `knowledge_*` settings |
| UPDATE | `app/knowledge/tests/test_chunking.py` | Add tests for semantic chunker |

## Implementation Steps

### Step 1: Add config settings

**File:** `app/core/config.py`
**Action:** Add after line 221 (after `knowledge_hyde_max_tokens`):

```python
# Semantic chunking (heading-aware, replaces fixed-size for structured docs)
knowledge_semantic_chunking_enabled: bool = True
knowledge_chunk_target_size: int = 800
knowledge_chunk_min_size: int = 256
knowledge_chunk_max_size: int = 1500
```

**Validation:** `uv run pyright app/core/config.py`

### Step 2: Implement SemanticChunker in chunking.py

**File:** `app/knowledge/chunking.py`
**Action:** Add `chunk_text_semantic()` function and helpers. Keep all existing code intact.

**Design:**

1. `_extract_sections(text) -> list[Section]` — Parse markdown headings with regex `^(#{1,6})\s+(.+)$` (multiline). Each section = heading level + heading text + body text. Track heading path hierarchy.

2. `_merge_small_sections(sections, min_size, target_size) -> list[Section]` — Merge consecutive same-level or child sections if combined < target_size.

3. `_split_large_sections(sections, max_size, chunk_overlap) -> list[Section]` — If a section body exceeds max_size, split at paragraph boundaries (`\n\n`), then sentence boundaries (`. `). Each sub-chunk inherits the parent's heading_path.

4. `chunk_text_semantic(text, target_size=800, min_size=256, max_size=1500, chunk_overlap=100) -> list[ChunkResult]`:
   - Extract sections
   - If no headings found (< 2 sections), fall back to `chunk_text()` with `chunk_size=target_size`
   - Merge small sections
   - Split large sections
   - Build `ChunkResult` list with metadata: `heading_path` (str, e.g. "Safety > Emergency Procedures"), `heading_level` (int), `char_start`, `char_end`

**Key rules:**
- `Section` is a simple dataclass: `heading_level: int`, `heading_text: str`, `heading_path: str`, `content: str`
- Heading path built as stack: when encountering `## Sub`, pop to level 2 in stack, push "Sub"
- Metadata dict type: `dict[str, str | int | None]` (matches existing `ChunkResult.metadata`)
- No new dependencies — regex only
- Fallback: if text has no markdown headings, delegate to existing `chunk_text()`

**Validation:** `uv run ruff format app/knowledge/chunking.py && uv run ruff check --fix app/knowledge/chunking.py && uv run pyright app/knowledge/chunking.py`

### Step 3: Integrate into service.py

**File:** `app/knowledge/service.py`
**Action:** Update `ingest_document()` at lines 249-274.

Replace the chunking call:
```python
# Before (line 250-254):
chunks = chunking.chunk_text(
    text,
    chunk_size=settings.knowledge_chunk_size,
    chunk_overlap=settings.knowledge_chunk_overlap,
)

# After:
if settings.knowledge_semantic_chunking_enabled:
    chunks = chunking.chunk_text_semantic(
        text,
        target_size=settings.knowledge_chunk_target_size,
        min_size=settings.knowledge_chunk_min_size,
        max_size=settings.knowledge_chunk_max_size,
        chunk_overlap=settings.knowledge_chunk_overlap,
    )
else:
    chunks = chunking.chunk_text(
        text,
        chunk_size=settings.knowledge_chunk_size,
        chunk_overlap=settings.knowledge_chunk_overlap,
    )
```

Update chunk object creation (lines 265-274) — store metadata as JSON:
```python
import json

chunk_objects = [
    DocumentChunk(
        document_id=doc.id,
        content=chunks[i].content,
        chunk_index=chunks[i].chunk_index,
        embedding=embeddings[i],
        metadata_json=json.dumps(chunks[i].metadata) if chunks[i].metadata else None,
    )
    for i in range(len(chunks))
]
```

Add import at top: `import json` (if not already imported).

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py`

### Step 4: Add tests for semantic chunker

**File:** `app/knowledge/tests/test_chunking.py`
**Action:** Add tests after existing tests. Import `chunk_text_semantic`.

**Tests to add:**

1. `test_semantic_single_section_no_headings` — Text without headings falls back to recursive chunker. Verify chunks produced.

2. `test_semantic_heading_detection` — Markdown with `# Title\n\n## Section 1\n\nBody 1\n\n## Section 2\n\nBody 2`. Verify 2+ chunks, each starting near a heading boundary.

3. `test_semantic_heading_path_metadata` — Verify `heading_path` in metadata: `"Title > Section 1"`.

4. `test_semantic_heading_level_metadata` — Verify `heading_level` is int matching the `#` count.

5. `test_semantic_nested_headings` — `# A\n## B\n### C\ntext\n## D\ntext`. Verify heading paths: `"A > B > C"` and `"A > D"`.

6. `test_semantic_large_section_split` — Section with 3000 chars body. Verify it splits into 2+ chunks, each ≤ max_size. Each sub-chunk inherits heading_path.

7. `test_semantic_small_sections_merged` — Multiple headings with tiny bodies (50 chars each). Verify adjacent sections merged up to target_size.

8. `test_semantic_latvian_headings` — `# Drošības noteikumi\n\n## Ārkārtas procedūras\n\nSaturs`. Verify diacritics preserved in heading_path.

9. `test_semantic_empty_text` — Returns empty list.

10. `test_semantic_char_offsets` — Verify `char_start`/`char_end` metadata present on all chunks.

11. `test_semantic_adaptive_sizing` — Verify no chunk < min_size (except last), no chunk > max_size.

**Validation:** `uv run pytest app/knowledge/tests/test_chunking.py -v`

## Preflight Warnings

- `service.py:250-274` — Chunk creation loop uses index-based access (`chunks[i]`). The new function must return `list[ChunkResult]` with same interface.
- `metadata_json` is `str | None` in the model — must pass `json.dumps()` output, not a dict.
- Existing tests in `test_chunking.py` use `conftest.py` fixture `sample_latvian_text` — ensure it stays compatible.

## Security Checklist

No new endpoints, no user input changes. N/A.

## Verification

- [ ] `uv run ruff format app/knowledge/ && uv run ruff check --fix app/knowledge/`
- [ ] `uv run pyright app/knowledge/chunking.py app/knowledge/service.py`
- [ ] `uv run mypy app/knowledge/chunking.py app/knowledge/service.py`
- [ ] `uv run pytest app/knowledge/tests/test_chunking.py -v` — all tests pass
- [ ] `uv run pytest app/knowledge/tests/ -v` — no regressions in other knowledge tests
- [ ] `make check` passes (lint + types + tests)
- [ ] Pyright errors ≤ baseline (0 errors before)
