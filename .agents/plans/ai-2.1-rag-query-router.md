# Plan: AI-2.1 RAG Query Router + Markdown Document Conversion

## Context

~60% of VTV agent queries are transit operations ("which routes are delayed?", "schedule for route 3") that never need document retrieval. Skipping RAG for these saves embedding API calls and reduces latency by 200-400ms per query.

Additionally, the current document pipeline extracts plain text from PDFs, Word, Excel, and images — losing all structure (headings, tables, lists). Converting to markdown at ingestion time produces better chunks for the agent to present in chat, without any runtime token overhead.

## Security Context Assessment

- **CTX-AGENT** — modifies agent tool pipeline routing (tool availability per request)
- **CTX-INPUT** — query router processes user input (needs safe string handling)

CTX-AUTH, CTX-RBAC, CTX-FILE, CTX-INFRA: not affected (no new endpoints, no file upload changes, no infra changes).

## Research Summary

### Current Architecture

**Agent pipeline** (`app/core/agents/service.py:98-222`):
```
Request → extract prompt → injection check → classify_prompt(tier) → resolve_model
→ load skills → agent.run(11 tools) → validate response → return
```
Integration point for RAG router: **between `classify_prompt()` (line 122) and skills loading (line 136)**.

**Existing routing** (`app/core/agents/routing.py`): `classify_prompt()` returns `fast`/`standard`/`complex` based on pattern matching. Same architecture — signal-based scoring, zero latency. The RAG router is a complementary classifier (orthogonal to tier routing).

**Knowledge search tool** (`app/core/agents/tools/knowledge/search_knowledge.py:30-162`): `search_knowledge_base()` — hybrid vector+fulltext, reranking, confidence threshold. Returns JSON with document_id, content (truncated 1500 chars), source, domain, score.

**Document extraction** (`app/knowledge/processing.py`): 7 extractors (PDF/DOCX/XLSX/CSV/email/image/text). All return plain text. PDF has OCR fallback. DOCX loses heading structure. XLSX outputs tab-separated rows.

**Document model** (`app/knowledge/models.py`): `Document` (metadata) → `DocumentChunk` (content + pgvector embedding). No `markdown_content` column — chunks store plain text.

### Key Insight: Markdown Conversion Strategy

**Problem**: Documents lose structure during extraction. A PDF with headers, tables, and numbered lists becomes flat text. When the agent retrieves a chunk, it gets an unstructured blob — hard to present in chat.

**Solution**: Convert to markdown **during extraction, before chunking**. This means:
1. The markdown IS the text that gets chunked and embedded
2. No separate column or duplicate storage needed
3. Chunks inherit markdown structure (headers, lists, tables)
4. Agent naturally presents structured content in chat (it's already markdown)
5. Zero runtime cost — conversion happens once at upload time

**Why NOT store a separate .md copy**:
- Double storage for every document
- Two columns to maintain in sync
- No benefit: the agent reads chunks, not full documents
- Chunks from markdown text ARE markdown chunks

**Format-specific strategies**:
| Format | Current | Improved |
|--------|---------|----------|
| PDF | Flat page text | `# Page N` headers, detect bold→`**`, detect lists→`- `, detect tables→`\|` |
| DOCX | Joined paragraphs | Map `Heading 1-6` → `#-######`, preserve lists, extract tables |
| XLSX | Tab-separated rows | Markdown tables with `\| header \| header \|` format |
| CSV | Tab-separated rows | Markdown tables (same as XLSX) |
| Image | OCR text | `> [OCR from: filename]\n\n{text}` (blockquote context) |
| Email | Headers + body | YAML-style frontmatter headers + body |
| Text | Raw content | Passthrough (may already be markdown) |

## Test Landscape

**Knowledge tests** (11 files): `test_processing.py`, `test_chunking.py`, `test_embedding.py`, `test_reranker.py`, `test_autotag.py`, `test_dms.py`, `test_repository.py`, `test_routes.py`, `test_tags.py`, conftest with `sample_upload`, `sample_latvian_text`, `sample_english_text` fixtures.

**Agent routing tests** (`app/core/agents/tests/test_routing.py`): 28 tests covering `classify_prompt()` — fast/standard/complex tier patterns. Direct template for RAG router tests.

**Mock patterns**: MagicMock for services, AsyncMock for async methods, `@patch` for external deps. No factory functions for knowledge.

## Type Check Baseline

| Scope | Pyright | Mypy |
|-------|---------|------|
| `app/knowledge/` | **0 errors** | **0 errors** |
| `app/core/agents/` | **6 errors** | **3 errors** |

Pre-existing agent errors (not introduced by this task):
- `pipeline.py` — `phase_details` list[Unknown], model arg type
- `tools/transit/client.py` — `response` possibly unbound
- `validation.py` — `warnings` list[Unknown]
- `tools/transit/static_store.py` — AsyncResult vs Result

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/knowledge/router.py` | RAG query router — signal-based classifier |
| CREATE | `app/knowledge/tests/test_router.py` | Unit tests for RAG router |
| UPDATE | `app/core/agents/service.py` | Integrate router after classify_prompt() |
| UPDATE | `app/core/agents/tests/test_service.py` | Test router integration in chat flow |
| UPDATE | `app/core/config.py` | Add `KNOWLEDGE__ROUTER_ENABLED` flag |
| UPDATE | `app/knowledge/processing.py` | Markdown-aware extraction for PDF, DOCX, XLSX, CSV, email, image |
| UPDATE | `app/knowledge/tests/test_processing.py` | Tests for markdown extraction |

## Implementation Steps

### Step 1: Create RAG Query Router (`app/knowledge/router.py`)

CREATE `app/knowledge/router.py`:

```python
"""RAG query router — determines if a query needs knowledge base retrieval.

Signal-based scoring with zero latency overhead (no LLM calls).
Transit, schedule, vault, and real-time queries skip RAG entirely.
Knowledge, policy, SOP, and document queries trigger RAG.
"""
import hashlib
import re
from typing import NamedTuple

from app.core.logging import get_logger

logger = get_logger(__name__)


class RoutingDecision(NamedTuple):
    """Result of RAG routing classification."""
    needs_rag: bool
    rag_score: int
    skip_score: int


# Signals that indicate the query needs document retrieval
_RAG_SIGNALS: list[re.Pattern[str]] = [
    # Policy / regulation / compliance
    re.compile(r"\b(policy|politic|politi[kc]a|regulation|regulēj|noteikum|likum)\b", re.I),
    # Procedures and SOPs
    re.compile(r"\b(procedure|procedūr|protocol|protokol|SOP|instrukcij|kārtīb|kartib)\b", re.I),
    # Documents and manuals
    re.compile(r"\b(document|dokument|manual|rokasgrāmat|handbook|guidelines)\b", re.I),
    # Training and HR
    re.compile(r"\b(training|apmācīb|apmacib|onboarding|certification|sertifik)\b", re.I),
    # Safety and compliance
    re.compile(r"\b(safety|drošīb|drosib|compliance|atbilstīb|audit|pārbaud)\b", re.I),
    # Knowledge lookups
    re.compile(r"\b(find.*document|atrast.*dokument|search.*knowledge|meklē)\b", re.I),
    # "What does the X say about Y" pattern
    re.compile(r"\bwhat\s+(does|do)\s+the\b.*\b(say|state|require|specify)\b", re.I),
    # "How to" procedural queries
    re.compile(r"\bhow\s+to\s+\w+", re.I),
    # "Kā" (Latvian "how") + procedural context
    re.compile(r"\bkā\s+(rīkoties|rikoties|veikt|pieteikt|noformēt|noformet)\b", re.I),
]

# Signals that the query does NOT need RAG (transit/schedule/vault operations)
_SKIP_SIGNALS: list[re.Pattern[str]] = [
    # Route/transit queries
    re.compile(r"\b(route|maršrut|marsrut|bus|autobus|trolleybus|trolejbus|tram)\b", re.I),
    # Delay/status
    re.compile(r"\b(delay|kavēj|kavej|late|on.?time|laik[aā])\b", re.I),
    # Schedule lookups
    re.compile(r"\b(schedule|grafik|timetable|sarakst|next bus|nākos|nakos)\b", re.I),
    # Stops
    re.compile(r"\b(stop|pietura|pieturā|nearest|tuvāk|tuv[aā]k)\b", re.I),
    # Real-time status
    re.compile(r"\b(active|aktīv|aktiv|current|pašlaik|paslaik|right now|tagad)\b", re.I),
    # Vault/Obsidian
    re.compile(r"\b(vault|note|piezīm|piezim|obsidian|folder|mape)\b", re.I),
    # Driver/vehicle lookup (operational, not knowledge)
    re.compile(r"\b(driver|vadītāj|vaditaj|vehicle|transportlīdzekl|transportlidzekl)\b", re.I),
    # Counting/status queries
    re.compile(r"\b(how many|cik|count|status|statuss)\b", re.I),
]


def needs_rag(query: str) -> RoutingDecision:
    """Classify whether a query needs RAG knowledge base retrieval.

    Uses signal-based scoring: counts matches against RAG and SKIP
    pattern lists. RAG wins when rag_score > skip_score.

    Args:
        query: The user's natural language query.

    Returns:
        RoutingDecision with needs_rag flag and both scores.
    """
    text = query.strip()
    rag_score = sum(1 for p in _RAG_SIGNALS if p.search(text))
    skip_score = sum(1 for p in _SKIP_SIGNALS if p.search(text))

    decision = RoutingDecision(
        needs_rag=rag_score > skip_score,
        rag_score=rag_score,
        skip_score=skip_score,
    )

    query_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
    logger.info(
        "knowledge.router.decision",
        query_hash=query_hash,
        needs_rag=decision.needs_rag,
        rag_score=rag_score,
        skip_score=skip_score,
    )

    return decision
```

**Validation:** `uv run ruff format app/knowledge/router.py && uv run ruff check --fix app/knowledge/router.py && uv run pyright app/knowledge/router.py`

### Step 2: Add config flag (`app/core/config.py`)

UPDATE `app/core/config.py` — add to the knowledge section (near other `knowledge_*` settings):

```python
# RAG query router
knowledge_router_enabled: bool = True
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 3: Integrate router into agent service (`app/core/agents/service.py`)

UPDATE `app/core/agents/service.py`:

1. Add imports:
```python
from app.core.agents.tools.knowledge.search_knowledge import search_knowledge_base
from app.knowledge.router import needs_rag
```

2. After `classify_prompt()` (line 122), before skills loading (line 136), add RAG routing:
```python
# RAG query router — skip knowledge search for transit/schedule/vault queries
settings = get_settings()
rag_decision = None
if settings.knowledge_router_enabled:
    rag_decision = needs_rag(current_prompt)
    logger.info(
        "agent.rag_routing",
        needs_rag=rag_decision.needs_rag,
        rag_score=rag_decision.rag_score,
        skip_score=rag_decision.skip_score,
        tier=tier,
    )
```

3. When calling `agent.run()`, if RAG is skipped, pass `tool_choice` or override to exclude knowledge tool. The cleanest approach: use Pydantic AI's `run()` with a dynamic tool filter. Check if `agent.run()` supports `tools=` override — if not, the router decision should be stored in `UnifiedDeps` so `search_knowledge_base` can short-circuit:

```python
# In UnifiedDeps (or as a field on it):
# rag_enabled: bool = True

# In search_knowledge_base(), at the top:
if not ctx.deps.rag_enabled:
    return "RAG retrieval skipped for this query type. Use transit or vault tools instead."
```

**Implementation approach**: Add `rag_enabled: bool = True` to `UnifiedDeps` dataclass. Set `self._deps.rag_enabled = rag_decision.needs_rag` before agent.run(). In `search_knowledge_base()`, check `ctx.deps.rag_enabled` and short-circuit if False.

**Validation:** `uv run ruff check app/core/agents/service.py && uv run pyright app/core/agents/service.py && uv run mypy app/core/agents/service.py`

### Step 4: Add `rag_enabled` to UnifiedDeps

UPDATE `app/core/agents/tools/transit/deps.py`:

Add `rag_enabled: bool = True` field to the `UnifiedDeps` dataclass. Set default `True` so existing code paths work without changes.

UPDATE `app/core/agents/tools/knowledge/search_knowledge.py`:

Add short-circuit at the top of `search_knowledge_base()`:
```python
if not ctx.deps.rag_enabled:
    logger.info("agent.knowledge.search_skipped", reason="rag_router_skip")
    return (
        "Knowledge base search was skipped by the query router. "
        "This query is better answered using transit or vault tools."
    )
```

**Validation:** `uv run pyright app/core/agents/tools/transit/deps.py app/core/agents/tools/knowledge/search_knowledge.py`

### Step 5: Write RAG router tests (`app/knowledge/tests/test_router.py`)

CREATE `app/knowledge/tests/test_router.py`:

Test structure (following `test_routing.py` pattern):

```python
class TestNeedsRagTransitQueries:
    """Transit/schedule queries should skip RAG."""
    # "Kuri maršruti kavējas?" → skip
    # "Which routes are delayed?" → skip
    # "Next bus at Brīvības iela stop" → skip
    # "Is route 3 on time?" → skip
    # "How many buses are active right now?" → skip
    # "Cik autobusu ir aktīvi?" → skip

class TestNeedsRagKnowledgeQueries:
    """Knowledge/policy/SOP queries should use RAG."""
    # "Kāda ir procedūra, ja autobuss sabojājas?" → needs RAG
    # "What is the overtime policy?" → needs RAG
    # "Find driver safety guidelines" → needs RAG
    # "What does the compliance manual say about X?" → needs RAG
    # "Kā rīkoties, ja ir avārija?" → needs RAG
    # "Show me the training SOP" → needs RAG

class TestNeedsRagMixedQueries:
    """Ambiguous queries — test tie-breaking behavior."""
    # "Tell me about route 3 safety procedures" → has both signals
    # Short/generic queries → skip (no RAG signals)

class TestNeedsRagLogging:
    """Verify structured logging of routing decisions."""
    # Check logger.info called with correct event name and fields
```

Target: ~25 tests covering LV/EN, transit skip, knowledge use, mixed signals, edge cases.

**Validation:** `uv run pytest app/knowledge/tests/test_router.py -v && uv run pyright app/knowledge/tests/test_router.py`

### Step 6: Update agent service tests

UPDATE `app/core/agents/tests/test_service.py`:

Add tests:
- `test_rag_router_skips_for_transit_query` — mock `needs_rag` to return skip, verify `rag_enabled=False` on deps
- `test_rag_router_enables_for_knowledge_query` — mock `needs_rag` to return use, verify `rag_enabled=True`
- `test_rag_router_disabled_by_config` — set `knowledge_router_enabled=False`, verify `needs_rag` not called

**Validation:** `uv run pytest app/core/agents/tests/test_service.py -v`

### Step 7: Markdown-aware document extraction (`app/knowledge/processing.py`)

UPDATE `app/knowledge/processing.py`:

Replace extraction functions with markdown-aware versions. The key changes:

**PDF** (`_extract_pdf_sync`):
```python
def _extract_pdf_sync(file_path: str) -> tuple[str, bool]:
    """Extract text from PDF with markdown structure preservation."""
    import fitz
    doc = fitz.open(file_path)
    pages: list[str] = []
    for page_num, page in enumerate(doc, 1):
        blocks = page.get_text("dict")["blocks"]
        page_lines: list[str] = []
        for block in blocks:
            if block["type"] == 0:  # text block
                for line in block["lines"]:
                    text = "".join(span["text"] for span in line["spans"])
                    if not text.strip():
                        continue
                    # Detect headings by font size (largest spans = headings)
                    max_size = max(span["size"] for span in line["spans"])
                    is_bold = any(
                        "bold" in span.get("font", "").lower() for span in line["spans"]
                    )
                    if max_size >= 16 and is_bold:
                        page_lines.append(f"## {text.strip()}")
                    elif max_size >= 14 and is_bold:
                        page_lines.append(f"### {text.strip()}")
                    elif is_bold and len(text.strip()) < 100:
                        page_lines.append(f"**{text.strip()}**")
                    else:
                        page_lines.append(text.strip())
        if page_lines:
            pages.append(f"# Page {page_num}\n\n" + "\n\n".join(page_lines))
    # ... OCR fallback unchanged ...
```

**DOCX** (`_extract_docx_sync`):
```python
def _extract_docx_sync(file_path: str) -> str:
    """Extract text from Word document with markdown structure."""
    from docx import Document as DocxDocument
    doc = DocxDocument(file_path)
    lines: list[str] = []
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        style = para.style.name if para.style else ""
        if style.startswith("Heading 1"):
            lines.append(f"# {para.text}")
        elif style.startswith("Heading 2"):
            lines.append(f"## {para.text}")
        elif style.startswith("Heading 3"):
            lines.append(f"### {para.text}")
        elif style.startswith("Heading"):
            level = min(int(style.split()[-1]) if style.split()[-1].isdigit() else 4, 6)
            lines.append(f"{'#' * level} {para.text}")
        elif style.startswith("List"):
            lines.append(f"- {para.text}")
        else:
            lines.append(para.text)
    # Extract tables
    for table in doc.tables:
        if not table.rows:
            continue
        headers = [cell.text.strip() for cell in table.rows[0].cells]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in table.rows[1:]:
            cells = [cell.text.strip() for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
    return "\n\n".join(lines)
```

**XLSX** (`_extract_excel_sync`):
```python
def _extract_excel_sync(file_path: str) -> str:
    """Extract Excel data as markdown tables."""
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    sheets: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows())
        if not rows:
            continue
        # First row as headers
        headers = [str(c.value) if c.value is not None else "" for c in rows[0]]
        lines = [f"## {sheet_name}", ""]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for row in rows[1:]:
            cells = [str(c.value) if c.value is not None else "" for c in row]
            lines.append("| " + " | ".join(cells) + " |")
        sheets.append("\n".join(lines))
    wb.close()
    return "\n\n".join(sheets)
```

**CSV** (`_extract_csv_sync`): Same markdown table approach as XLSX.

**Image** (`_extract_image_sync`):
```python
def _extract_image_sync(file_path: str) -> str:
    """Extract text from image via OCR, wrapped in markdown."""
    import pytesseract
    from PIL import Image
    image = Image.open(file_path)
    raw = str(pytesseract.image_to_string(image, lang="lav+eng"))
    filename = Path(file_path).name
    return f"> OCR extracted from: {filename}\n\n{raw}"
```

**Email** (`_extract_email_sync`): Add markdown formatting to headers:
```python
# Format as markdown
parts.append(f"**From:** {from_val}")
parts.append(f"**To:** {to_val}")
# etc.
```

**Validation:** `uv run pytest app/knowledge/tests/test_processing.py -v && uv run pyright app/knowledge/processing.py`

### Step 8: Update processing tests

UPDATE `app/knowledge/tests/test_processing.py`:

Add tests verifying markdown output:
- `test_docx_headings_to_markdown` — Heading 1/2/3 → `#`/`##`/`###`
- `test_docx_tables_to_markdown` — Word tables → markdown tables
- `test_excel_to_markdown_tables` — XLSX sheets → `## SheetName` + markdown tables
- `test_csv_to_markdown_table` — CSV rows → markdown table with header
- `test_image_ocr_markdown_wrapper` — OCR text wrapped in blockquote
- `test_email_markdown_headers` — Email headers formatted as bold markdown

**Validation:** `uv run pytest app/knowledge/tests/test_processing.py -v`

## Preflight Warnings

- `app/core/agents/tools/transit/deps.py` — adding `rag_enabled` field to `UnifiedDeps` dataclass. Check all constructors of `UnifiedDeps` (grep for `UnifiedDeps(` and `create_unified_deps`).
- `app/knowledge/processing.py` — changing extraction output format affects ALL existing tests that assert on extracted text. Run full test suite after changes.
- PyMuPDF `page.get_text("dict")` returns a different structure than `page.get_text()` — needs careful handling of the dict format.
- `python-docx` `para.style` can be `None` — always check before accessing `.name`.
- Markdown table cells must not contain `|` characters — escape with `\|` in cell content.

## Security Checklist

No new endpoints added. Existing security unchanged.

- [x] RAG router only processes the user query string (already validated by ChatMessage schema, max 4000 chars)
- [x] No SQL queries, no file access, no external API calls in router
- [x] Router logs query hash (SHA-256), not raw query text — prevents PII in logs
- [x] Markdown conversion runs on already-uploaded files (no new file handling)
- [x] `escape_like()` not needed (no ILIKE queries added)

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] Pyright errors <= baseline (0 for knowledge, 6 for agents)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] RAG router test: "Kuri maršruti kavējas?" → `needs_rag=False`
- [ ] RAG router test: "Kāda ir procedūra, ja autobuss sabojājas?" → `needs_rag=True`
- [ ] Markdown extraction test: DOCX headings → `#` headers in output
- [ ] Markdown extraction test: XLSX data → markdown tables in output
- [ ] Agent integration test: transit query → `rag_enabled=False` on deps
