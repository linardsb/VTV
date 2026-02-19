# RAG Knowledge Base Improvements Plan

## Current State

The RAG knowledge base is fully implemented with:
- **Document ingestion**: PDF, DOCX, email (.eml), image (OCR via pytesseract), plain text
- **Hybrid search**: pgvector cosine similarity + PostgreSQL fulltext (RRF fusion, k=60)
- **Cross-encoder reranking**: Local BGE-Reranker-v2-m3 or noop
- **Configurable embeddings**: OpenAI, Jina, or local sentence-transformers (BGE-M3)
- **Recursive chunking**: Paragraphs -> lines -> sentences -> words (512 chars, 50 overlap)
- **Agent tool**: `search_knowledge_base` with 500-char truncation for token efficiency
- **REST API**: 5 endpoints for upload, list, get, delete, search

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

### Excel/CSV Support (Priority: High)
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

### HTML Support (Priority: Medium)
**Why**: Web-scraped regulations, municipal announcements, CKAN dataset descriptions.

**Implementation approach**:
- Add `beautifulsoup4` + `lxml` dependencies
- Strip scripts/styles, extract semantic text
- Preserve heading hierarchy for chunk boundaries

**Estimated effort**: 0.5 days

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

### 1. Auto-Domain Tagging
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

### 2. Parent-Child Chunking (Hierarchical)
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

### 3. Temporal Metadata
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

### 8. Cross-Lingual Search
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

## Recommended Build Order

| Priority | Improvement | Impact | Effort | Dependencies |
|----------|-------------|--------|--------|-------------|
| 1 | Excel/CSV support | High (most operational data) | 1 day | openpyxl dependency |
| 2 | Auto-domain tagging | Medium (reduces upload friction) | 1 day | LLM provider configured |
| 3 | Latvian lemmatizer | High (20-30% recall improvement) | 2-3 days | UDPipe model download |
| 4 | Temporal metadata | Medium (time-aware search) | 1 day | Alembic migration |
| 5 | Parent-child chunking | Medium (better context quality) | 1.5 days | Alembic migration |
| 6 | Cross-lingual search | Medium (LV/EN interop) | 1 day | LLM provider |
| 7 | Document versioning | Low-Medium (audit trail) | 1.5 days | Alembic migration |
| 8 | HTML/PPTX support | Low (occasional use) | 1 day | beautifulsoup4, python-pptx |
| 9 | Search feedback loop | Low-Medium (long-term quality) | 2 days | Alembic migration |
| 10 | Knowledge graph | Low (advanced, future) | 3-4 days | Entity extraction pipeline |

## Success Metrics

- **Search recall**: % of relevant chunks in top-10 results (target: >80%)
- **Query latency**: p95 search response time (target: <500ms)
- **Ingestion throughput**: Documents processed per minute (target: >10/min)
- **User satisfaction**: Agent response quality ratings (target: >4/5)
- **Coverage**: % of dispatcher questions answerable from knowledge base (target: >70%)
