# RAG Knowledge Base Improvements Plan

## Status (2026-04-11)

Items from this plan that have already shipped via Agent Intelligence phases AI-1..AI-7 and earlier DMS work:

| Improvement | Status | Shipped by |
|-------------|--------|------------|
| Excel/CSV extraction | ✅ Done | DMS Backend — `_extract_excel_sync` / `_extract_csv_sync` in `app/knowledge/processing.py` |
| Auto-domain tagging | ✅ Done | DMS Enhancements — `_auto_tag_document` in `app/knowledge/service.py`, `auto_tag_enabled` config |
| Parent-child chunking | ✅ Done | AI-4.2/4.3/4.4 — `parent_chunk_id`, `heading_path`, `section_type` columns + retrieval-time parent expansion |
| Temporal metadata | ✅ Covered | AI-1.2 `created_after`/`created_before` filtering + AI-1.3 temporal boost + `evergreen` flag (plan's speculative `content_date`/`valid_from`/`valid_until` fields deferred as unneeded) |
| Cross-lingual search | ✅ Covered | Multilingual embeddings (Jina v3 / BGE-M3) + AI-2.2 HyDE + AI-7.1 cross-lingual eval cases |

**Still pending** (~9.5 days, ~$0.55/month): PPTX support, Latvian UDPipe lemmatizer, document versioning, search feedback loop, knowledge graph overlay. HTML support dropped — no concrete use case.

## Current State

The RAG knowledge base is fully implemented with:
- **Document ingestion**: PDF, DOCX, email (.eml), image (OCR via pytesseract), plain text, Excel (.xlsx), CSV
- **Hybrid search**: pgvector cosine similarity + PostgreSQL fulltext (RRF fusion, k=60)
- **Cross-encoder reranking**: Local BGE-Reranker-v2-m3 or noop, always-on (AI-1.1)
- **Configurable embeddings**: OpenAI, Jina, or local sentence-transformers (BGE-M3)
- **Semantic chunking**: Heading-aware parent-child hierarchy (AI-4.1/4.2), target 800 chars, min 256, max 1500
- **Query router**: Skip RAG for transit queries (AI-2.1), HyDE query expansion for Latvian (AI-2.2), Redis embedding cache (AI-2.3)
- **Temporal awareness**: Recency boost with evergreen flag (AI-1.3), confidence threshold filter (AI-1.4), `created_after`/`created_before` filtering
- **Parent-context expansion**: Matched child chunks return full parent section in agent context (AI-4.3)
- **Auto-domain tagging**: LLM classifies `domain` on upload
- **Agent tool**: `search_knowledge_base` with 1500-char per-hit truncation, parent-context markers
- **REST API**: 14 endpoints for upload, list, get, delete, search, tags, rechunk

## Phase 1: High-Value Document Types

### Operational Documents (Priority: Critical)
These are the core knowledge a transit dispatcher needs daily.

| Document Type | Format | Example Content | Search Value |
|---------------|--------|----------------|--------------|
| SOPs (Standard Operating Procedures) | PDF/DOCX | "If bus breaks down on route 22, contact depot X, reroute via Y" | Dispatchers ask "what do I do when..." |
| Incident reports | PDF/DOCX | Past incident logs with root cause and resolution | Pattern matching for recurring issues |
| Route deviation protocols | PDF | Approved detour maps and trigger conditions | "What's the detour for route 15 during construction?" |
| Emergency contact sheets | DOCX/PDF | Depot contacts, police liaison, hospital routes | Quick reference during emergencies |
| Shift handover notes | TXT/DOCX | "Route 3 has roadwork at Brivibas, expect 5-min delays" | Continuity between shifts |
| Maintenance bulletins | PDF | "Bus #4521 restricted to routes under 40km/day" | Vehicle assignment decisions |

### Regulatory & Compliance (Priority: High)
Legal requirements that dispatchers must follow.

| Document Type | Format | Example Content | Search Value |
|---------------|--------|----------------|--------------|
| EU Regulation 1370/2007 | PDF | Public service obligations for transit operators | Compliance questions |
| Latvian Road Transport Law | PDF | National regulations for public transit | Legal requirements |
| Driver hour regulations (EU 561/2006) | PDF | Maximum driving hours, mandatory breaks | Shift planning compliance |
| Municipal service contracts | PDF | Route obligations, frequency minimums, penalty clauses | "What's our SLA for route 22?" |
| Safety audit reports | PDF | Annual safety compliance findings | Audit preparation |
| GDPR data handling procedures | DOCX | Passenger data, CCTV footage retention policies | Privacy compliance |

### HR & Workforce (Priority: Medium)
Staff management knowledge.

| Document Type | Format | Example Content | Search Value |
|---------------|--------|----------------|--------------|
| Driver qualification records | XLSX/CSV | License types, certifications, expiry dates | "Which drivers can operate articulated buses?" |
| Training materials | PDF/DOCX | New driver onboarding, route familiarization | Training program queries |
| Union agreements | PDF | Working conditions, overtime rules, grievance procedures | Labor relations questions |
| Absence & leave policies | DOCX | Sick leave procedures, holiday scheduling | Staffing decisions |
| Performance metrics | XLSX | Driver punctuality scores, complaint records | Performance reviews |

### Historical & Analytics (Priority: Medium)
Past data for trend analysis and decision support.

| Document Type | Format | Example Content | Search Value |
|---------------|--------|----------------|--------------|
| Ridership reports | XLSX/CSV/PDF | Monthly passenger counts by route, peak hours | "What's the busiest route on weekdays?" |
| Seasonal patterns | XLSX | Holiday schedules, school-term adjustments | Planning for known demand changes |
| Weather impact logs | CSV/DOCX | Historical delays during snow/ice/flooding | "How does snow affect route 7?" |
| Construction impact reports | PDF | Past roadwork and its effect on schedules | Predicting future construction impact |
| Complaint summaries | XLSX/PDF | Categorized passenger complaints with trends | Service improvement decisions |

### Technical & Infrastructure (Priority: Lower)
System and fleet documentation.

| Document Type | Format | Example Content | Search Value |
|---------------|--------|----------------|--------------|
| Fleet specifications | PDF | Bus models, capacities, accessibility features | "Which buses have wheelchair ramps?" |
| Depot layout maps | PDF/Image | Parking assignments, fueling stations, wash bays | Logistics planning |
| GTFS feed documentation | MD/TXT | Data dictionary, update schedules, known issues | Technical reference |
| IT system manuals | PDF | CMS user guide, radio system operations | System troubleshooting |
| Network topology maps | PDF/Image | Route network, transfer points, coverage gaps | Network planning |

## Phase 2: File Format Expansion

### Excel/CSV Support (Priority: High) ✅ DONE
Shipped in DMS Backend. See `_extract_excel_sync` and `_extract_csv_sync` in `app/knowledge/processing.py`.

**Why**: Spreadsheets are the #1 format for operational data in transit agencies.

**Implementation approach**:
- Add `openpyxl` dependency for `.xlsx` processing
- Add `csv` stdlib for `.csv` processing
- Extract cell values row-by-row, preserve header context
- For multi-sheet workbooks: prefix chunks with sheet name
- Handle merged cells, formulas (extract computed values)

**Estimated effort**: 1 day (extraction + tests)

```python
# Processing addition in app/knowledge/processing.py
async def _extract_xlsx(file_path: str) -> str:
    """Extract text from Excel files, sheet by sheet."""
    return await asyncio.to_thread(_extract_xlsx_sync, file_path)

def _extract_xlsx_sync(file_path: str) -> str:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    text_parts: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        text_parts.append(f"## {sheet_name}")
        for row in ws.iter_rows(values_only=True):
            row_text = " | ".join(str(cell) for cell in row if cell is not None)
            if row_text.strip():
                text_parts.append(row_text)
    return "\n".join(text_parts)
```

### HTML Support — DROPPED
Not needed. Transit operational documents arrive as PDF/DOCX/XLSX; no concrete use case for web-scraped HTML ingestion has surfaced.

### PowerPoint Support (Priority: Low)
**Why**: Training presentations, board reports.

**Implementation approach**:
- Add `python-pptx` dependency
- Extract slide text, notes, and table content
- Prefix chunks with slide number for context

**Estimated effort**: 0.5 days

### Audio/Video Transcription Support (Priority: Future)
**Why**: Radio communications, training videos, council meeting recordings.

**Implementation approach**:
- Use Whisper API or local whisper.cpp
- Generate timestamps for chunk boundaries
- Language detection for Latvian/Russian/English content

**Estimated effort**: 2-3 days (requires model hosting decisions)

## Phase 3: Search & Retrieval Improvements

### 1. Auto-Domain Tagging ✅ DONE
Shipped in DMS Enhancements. See `_auto_tag_document` in `app/knowledge/service.py:960`, gated by `auto_tag_enabled` config.

**Current**: Users manually set `domain` on upload (transit, hr, legal).
**Improved**: LLM classifies domain automatically from content.

```python
async def auto_classify_domain(text_preview: str) -> str:
    """Use LLM to classify document domain from first 500 chars."""
    # Zero-shot classification via Claude/local model
    # Returns: transit | hr | legal | safety | operations | technical
```

**Cost**: ~$0.001 per document (500 tokens input)
**Benefit**: Enables domain-filtered search without manual tagging

### 2. Parent-Child Chunking (Hierarchical) ✅ DONE
Shipped in AI-4.2 (model), AI-4.3 (search-time parent-context expansion), AI-4.4 (re-chunk migration script). Heading-aware semantic chunking from AI-4.1 underpins it. See `parent_chunk_id`, `heading_path`, `section_type` on `DocumentChunk`; parent expansion in `KnowledgeService.search()`.

**Current**: Flat recursive chunking - each chunk is independent.
**Improved**: Two-level hierarchy - parent chunks (2048 chars) contain child chunks (512 chars).

**How it works**:
- Search matches on child chunks (fine-grained relevance)
- Return parent chunks (broader context for LLM reasoning)
- Same embedding cost, better context quality

**Implementation**:
- Add `parent_chunk_id` nullable FK to `document_chunks` table
- Store parent chunks with `is_parent=True` flag
- Search child chunks, return parent content

### 3. Temporal Metadata ✅ COVERED (partial build, remainder deferred)
Core intent shipped in AI-1.2 + AI-1.3: `created_after`/`created_before` filtering on `SearchRequest` (repository, service, agent tool), age-weighted temporal boost (today 1.5x / week 1.2x / month 1.0x / older 0.8x), and an `evergreen` boolean on `Document` to skip decay. The plan's speculative `content_date` / `valid_from` / `valid_until` fields are **deferred** — no concrete transit use case has surfaced for content-validity windows distinct from document creation time.

**Current**: Documents have `created_at` but no content date awareness.
**Improved**: Extract and store document dates for time-aware search.

```python
class DocumentChunk(Base):
    # ... existing fields
    content_date: Mapped[datetime | None]  # Date the content refers to
    valid_from: Mapped[datetime | None]    # When this info becomes valid
    valid_until: Mapped[datetime | None]   # When this info expires
```

**Benefit**: "What was the snow procedure last winter?" filters to correct time range.
**Benefit**: Automatically deprioritize expired procedures.

### 4. Latvian Language Preprocessing
**Current**: Using PostgreSQL `simple` text search config (no stemming).
**Improved**: Custom Latvian lemmatizer for better fulltext matching.

**Options**:
- **UDPipe Latvian model** (free, local): Lemmatization + POS tagging
- **Custom pg_trgm index**: Trigram matching handles Latvian diacritics better
- **Latvian dictionary for hunspell**: PostgreSQL fulltext with Latvian stemmer

**Impact on search quality**:
- "autobuss" (bus, nominative) matches "autobusu" (bus, genitive) and "autobusam" (bus, dative)
- "marsruts" (route) matches "marsruta", "marsrutiem", "marsrutos"
- Estimated 20-30% improvement in Latvian query recall

**Estimated effort**: 2-3 days for UDPipe integration
**Cost**: Free (UDPipe is MIT licensed, runs locally)

### 5. Document Versioning
**Current**: Re-uploading replaces the document entirely.
**Improved**: Version tracking with diff-aware search.

```python
class Document(Base):
    # ... existing fields
    version: Mapped[int] = mapped_column(default=1)
    parent_document_id: Mapped[int | None]  # Previous version
    is_latest: Mapped[bool] = mapped_column(default=True)
```

**Benefit**: "What changed in the snow protocol this year?" returns diff between versions.
**Benefit**: Audit trail for regulated documents.

### 6. Search Feedback Loop
**Current**: No learning from search quality.
**Improved**: Track which results agents/users find useful.

```python
class SearchFeedback(Base):
    query: Mapped[str]
    chunk_id: Mapped[int]  # FK to document_chunks
    relevance_score: Mapped[float]  # 0.0 to 1.0, from user/agent feedback
    source: Mapped[str]  # "agent" or "user"
```

**How it works**:
- Agent reports which chunks it actually used in its response
- Users can thumbs-up/down search results in CMS
- Feedback adjusts RRF weights and reranker fine-tuning over time

**Estimated effort**: 2 days
**Cost**: Storage only (tiny - just feedback rows)

### 7. Knowledge Graph Overlay
**Current**: Documents are isolated - no relationship awareness.
**Improved**: Extract entities and relationships for graph-enhanced search.

**Entities**: Routes, stops, drivers, vehicles, regulations, procedures
**Relationships**: "Route 22 serves Stop Brivibas" "Driver X certified for Bus Model Y"

**Implementation approach**:
- Use LLM to extract entities during ingestion
- Store in a simple `entity_mentions` table (entity_type, entity_name, chunk_id)
- At search time: find related entities and boost chunks mentioning them

**Cost**: ~$0.01 per document for entity extraction
**Estimated effort**: 3-4 days

### 8. Cross-Lingual Search ✅ COVERED
The multilingual embedding path (Jina v3 / BGE-M3) already makes LV queries match EN chunks on the vector side, as this plan anticipated. AI-2.2 HyDE further improves Latvian retrieval by generating a hypothetical answer and embedding that. AI-7.1 synthetic eval cases explicitly cover cross-lingual retrieval (LV question → EN document) and are part of the regression baseline. The residual fulltext-side query-translation idea is **dropped** — marginal lift over the above, and query translation latency contradicts the sub-500ms target.

**Current**: Queries in language X only match documents in language X well.
**Improved**: Latvian query matches English documents and vice versa.

**How**: BGE-M3 (our default local model) already supports multilingual embeddings natively. Vector search already works cross-lingually. The gap is in fulltext search.

**Fix**: Add query translation step before fulltext search:
- Translate Latvian query to English (and vice versa) using LLM
- Run fulltext search with both original and translated query
- Merge results via RRF

**Cost**: ~$0.001 per query for translation
**Estimated effort**: 1 day

## Cost Analysis

### Current System Costs (Monthly)

| Component | OpenAI Embeddings | Jina Embeddings | Local Embeddings |
|-----------|-------------------|-----------------|------------------|
| Embedding (1000 docs) | $0.10 | $0.02 | $0.00 |
| Storage (pgvector) | $0.00 (included in PostgreSQL) | $0.00 | $0.00 |
| Reranking (local) | $0.00 | $0.00 | $0.00 |
| Per-query cost | $0.006/mo (50 queries/day) | $0.001/mo | $0.00 |
| **Total monthly** | **~$0.11** | **~$0.02** | **~$0.00** |

### Improvement Cost Impact

| Improvement | One-Time Cost | Monthly Cost | Effort |
|-------------|---------------|--------------|--------|
| Excel/CSV/HTML/PPTX support | $0 | $0 | 2 days |
| Auto-domain tagging | $0 | ~$0.10 (LLM calls) | 1 day |
| Parent-child chunking | $0 | $0 (same embedding count) | 1.5 days |
| Temporal metadata | $0 | $0 | 1 day |
| Latvian lemmatizer | $0 | $0 (local UDPipe) | 2-3 days |
| Document versioning | $0 | $0 | 1.5 days |
| Search feedback loop | $0 | $0 | 2 days |
| Knowledge graph overlay | $0 | ~$0.50 (entity extraction) | 3-4 days |
| Cross-lingual search | $0 | ~$0.05 (query translation) | 1 day |
| **Total** | **$0** | **~$0.65** | **~14-16 days** |

### Storage Projections

| Scale | Documents | Chunks (~50/doc) | Vector Storage | Total DB Size |
|-------|-----------|-------------------|----------------|---------------|
| Current | 0 | 0 | 0 MB | ~50 MB (schema) |
| 6 months | 200 | 10,000 | ~40 MB | ~100 MB |
| 1 year | 500 | 25,000 | ~100 MB | ~200 MB |
| 2 years | 1,000 | 50,000 | ~200 MB | ~400 MB |

All fits comfortably in the existing PostgreSQL instance with no additional infrastructure.

## Recommended Build Order — Remaining Work Only

Items already shipped (Excel/CSV, auto-domain tagging, parent-child chunking, temporal metadata, cross-lingual search) are excluded. See the Status table at the top of this doc.

| Priority | Improvement | Impact | Effort | Dependencies |
|----------|-------------|--------|--------|-------------|
| 1 | Latvian UDPipe lemmatizer | High (distinct BM25 channel, 20-30% fulltext recall lift on top of existing multilingual embeddings) | 2-3 days | UDPipe model download |
| 2 | PPTX support | Low (training decks, board reports) | 0.5 days | python-pptx |
| 3 | Document versioning | Low-Medium (audit trail on regulated docs) | 1.5 days | Alembic migration |
| 4 | Search feedback loop | Low-Medium (long-term quality — note partial overlap with AI-11 synthetic-QA retrieval evals, but feedback loop is a production-signal channel AI-11 does not replace) | 2 days | Alembic migration |
| 5 | Knowledge graph overlay | Low (advanced; future) | 3-4 days | Entity extraction pipeline |

Total remaining: ~9.5 days.

## Success Metrics

- **Search recall**: % of relevant chunks in top-10 results (target: >80%)
- **Query latency**: p95 search response time (target: <500ms)
- **Ingestion throughput**: Documents processed per minute (target: >10/min)
- **User satisfaction**: Agent response quality ratings (target: >4/5)
- **Coverage**: % of dispatcher questions answerable from knowledge base (target: >70%)
