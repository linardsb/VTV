# RAG PDF Extraction Fix

## TL;DR

VTV's RAG stack is mature: hybrid search (pgvector + Postgres FTS with RRF), cross-encoder reranker, HyDE, heading-aware semantic chunking with parent/child hierarchy. The **one unambiguous gap** is upstream of all of that: `_extract_pdf_sync` silently drops content before it's ever indexed. No amount of retrieval tuning can find text that was never extracted.

This plan fixes only that gap. One file touched, one migration run, one dependency added.

## The bug

`app/knowledge/processing.py:97`

```python
for block in blocks:
    if block["type"] != 0:  # skip non-text blocks
        continue
```

Also, within text blocks, lines are concatenated in PyMuPDF's default block order, not reading order, and tables are flattened into prose.

### What's actually being lost

1. **Tables lose structure.** PyMuPDF dict mode returns table cells as text spans. Current code joins them line-by-line, so a fare table becomes `"Route Adult Child Senior\n1 1.50 0.80 1.00\n..."` — columns collapse into a flat stream. The semantic chunker's `section_type="table"` classifier (`chunking.py:347`) never fires because the markdown table syntax is never produced.
2. **Multi-column reading order.** EU regulations and municipal contracts are two-column. PyMuPDF block order can interleave left/right columns, producing garbled text that embeddings and FTS both handle badly.
3. **Images, drawings, figure captions** (`block["type"] != 0`) are dropped entirely. Diagrams with labels, depot maps, workflow charts, figure captions — gone.

### Why this matters for transit ops

VTV's target corpus (per `docs/PLANNING/rag-improvements.md`): SOPs, fare tables, driver hour regulations (EU 561/2006), municipal service contracts with SLA tables, maintenance bulletins, fleet specs. These are **table-dense, often multi-column** government/regulatory PDFs. Table content is usually the answer to the query ("what's the fare for route 22?", "max driving hours before break?", "SLA penalty for late bus?").

## Fix

Replace `_extract_pdf_sync` with a pdfplumber-based implementation that:

1. Extracts tables per page via `page.extract_tables()` and emits them as markdown tables.
2. Extracts prose via `page.extract_text(layout=False)` — pdfplumber's reading order handles multi-column better than raw PyMuPDF blocks.
3. Emits text and tables in document order using bounding-box y-coordinates.
4. Keeps the existing heading heuristic (font size/bold via PyMuPDF) as an optional second pass, or drops it — pdfplumber doesn't expose font size cleanly. Acceptable tradeoff: pdfplumber outputs clean paragraph text, the chunker still works, headings just become plain paragraphs instead of `##`. **Validate on sample docs whether this regresses chunking quality; if so, keep the PyMuPDF heading pass for pages with no detected tables.**
5. Keeps the existing scanned-PDF fallback path untouched (`if len(total_text.strip()) < 50`) — tesseract `lav+eng` stays.

### Dependency

Add `pdfplumber>=0.11.9` to `pyproject.toml` (already a transitive dep of other things in the ecosystem, small addition). Keep `pymupdf` — it's still used for the OCR rasterization path and possibly for heading detection.

### File changes

- `app/knowledge/processing.py` — rewrite `_extract_pdf_sync` only. Function signature and return type stay identical: `(file_path: str) -> tuple[str, bool]`. No caller changes anywhere.
- `pyproject.toml` — add `pdfplumber>=0.11.9`.
- `app/knowledge/tests/test_processing.py` (or equivalent) — add fixtures for: single-column PDF with a table, two-column regulation PDF, scanned PDF (confirm OCR fallback still triggers).

No schema changes. No migration. No new settings. No feature flag.

## Validation before merging

One-off script, throwaway, do not commit:

```python
# scripts/diff_pdf_extraction.py
# Loads every pdf document from VTV's existing corpus, runs both
# the old and new _extract_pdf_sync, writes a side-by-side diff.
# Spot-check 10-20 real docs for:
#   - tables present in new output that were missing in old
#   - reading order improved on multi-column docs
#   - no regression on simple single-column docs
#   - char count delta (expect new > old when tables exist)
```

Run it against `documents/` (local dev corpus) or a snapshot of the prod DB's uploaded files.

**Do not rechunk production until the diff shows consistent improvement on real VTV docs.** If the diff shows regressions, either fix them or abandon the change — the current extractor is working well enough for non-table content.

## Rollout

1. Branch, implement, unit tests pass.
2. Run diff script on local corpus. Eyeball ~15 PDFs. Confirm tables appear, reading order looks sane.
3. Open PR. Include 2-3 before/after snippets in the PR description.
4. Merge.
5. Run `make rechunk` (VTV already has the rechunk migration mechanism from AI-4.4). This re-extracts every existing PDF through the new path, rechunks, re-embeds.
6. Smoke-test search on 5-10 queries you know should hit table content in the corpus. Confirm those chunks now appear in top-k.

## Explicitly out of scope

- **markitdown migration** — nice architecturally, not worth 350 LOC of churn and a feature flag for the same underlying pdfplumber result.
- **DOCX improvements** — `python-docx` already handles headings/lists/tables correctly. No gap observed.
- **Excel/CSV changes** — structured extraction already works.
- **Image OCR changes** — tesseract `lav+eng` offline path is the right call; LLM vision OCR is a cost decision, not a quality one, and not relevant to this fix.
- **New file formats (PPTX, EPUB, .msg)** — speculative unless the corpus demands it.
- **Retrieval layer changes** — hybrid search, HyDE, reranker, chunker are all in good shape.

## Estimated effort

- Implementation + unit tests: half a day.
- Diff validation on real corpus: half a day.
- Rechunk + smoke test: 1-2 hours depending on corpus size.

Total: ~1 day of focused work, single PR.

## Success criteria

- Tables from at least one real VTV PDF appear as markdown tables in `DocumentChunk.content` after rechunking.
- At least one query that previously returned only prose chunks now returns a table chunk in top-k.
- No regression on existing test suite (1128 unit + 81 e2e).
- Scanned-PDF OCR fallback still triggers on a known scanned test fixture.
