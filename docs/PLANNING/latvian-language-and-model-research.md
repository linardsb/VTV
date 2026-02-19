# Latvian Language & Model Stack Research

## Context

Research conducted 2026-02-19 to improve Latvian language quality across the VTV AI agent, RAG knowledge base, and frontend UI.

## Problem Statement

The VTV agent was producing poor Latvian output:
- System prompt was 100% English - agent had no Latvian language guidance
- Frontend i18n (lv.json) had all diacritics stripped from chat namespace
- LLM model (Claude Haiku 4.5) generated pseudo-Latvian words ("pietures" instead of "pieturas", "Distanse" instead of "attālums")
- Hardcoded English fallback string in chat hook

## Changes Made

### 1. System Prompt (app/core/agents/agent.py)
- Added LANGUAGE RULES section (respond in Latvian by default, proper diacritics)
- Added LATVIAN TRANSIT GLOSSARY (30+ transit terms with correct Latvian)
- Added LATVIAN INPUT UNDERSTANDING (diacriticless input mapping for dispatchers)
- Added RESPONSE FORMAT RULES (translate tool outputs, use markdown)

### 2. Frontend i18n (cms/apps/web/messages/lv.json)
- Fixed all 17 chat namespace keys with proper Latvian diacritics
- Key fix: "Kuri marsruti sodiena kave?" -> "Kuri maršruti šodien kavējas?"

### 3. Chat Hook (cms/apps/web/src/hooks/use-chat-agent.ts)
- Replaced hardcoded `"No response received."` with language-neutral `"..."`

### 4. Model Upgrade
- LLM: Claude Haiku 4.5 -> Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`)
- Embedding: OpenAI `text-embedding-3-large` -> Jina v3 (`jina-embeddings-v3`)
- Reranker: BGE-reranker-v2-m3 (kept, already multilingual)

## LLM Model Research for Latvian

### LAG-MMLU Benchmark (Latvian Academic General Knowledge)

| Model | Latvian Score | Notes |
|-------|--------------|-------|
| OpenAI o1 | 88.8% | Best overall for Latvian |
| GPT-4o | ~85% | Strong Latvian, good cost/quality |
| Claude Sonnet 4.5 | Good | Proper grammar, correct terms |
| Claude Haiku 4.5 | Poor | Generates pseudo-Latvian words |
| Mistral-Large | 35.6% | Surprisingly bad for Latvian |
| TildeOpen-30B | Purpose-built | Latvian-specific, self-hosted only |

### Key Finding
Baltic languages (Latvian, Lithuanian, Estonian) have small speaker bases and are under-represented in training data. Models lose more accuracy under quantization for Latvian than for English (0.12 vs 0.01 accuracy points for Llama 3.1 70B).

Source: "Localizing AI: Evaluating Open-Weight Language Models for Languages of Baltic States" (arXiv:2501.03952)

## Embedding Model Research for Latvian RAG

### Comparison

| Model | MTEB Score | Latvian Support | Dimensions | Type | Price/1M tokens |
|-------|-----------|-----------------|------------|------|----------------|
| **Qwen3-Embedding-8B** | **70.58** | General (100+ langs) | 1024 | Open-source | Free (self-host) |
| **Cohere Embed v4** | **65.2** | General (100+ langs) | 768 | API | ~$0.10 |
| OpenAI text-embedding-3-large | 64.6 | General (100+ langs) | 1024 | API | $0.13 |
| **BGE-M3** | 63.0 | General (100+ langs) | 1024 | Open-source | Free (self-host) |
| **Jina v3** | Top sub-1B | **Explicit top-30** | 1024 | API | $0.02 |
| **Jina v4** | Newer | 30+ langs, multimodal | Flexible | API | TBD |
| EmbeddingGemma-300M | Competitive | General (100+ langs) | Varies | Open-source | Free |

### Decision: Jina v3

Selected Jina v3 because:
- **Only model with explicit Latvian evaluation** - Latvian is in their top-30 languages with dedicated benchmarking
- **Cheapest API option** - $0.02/1M tokens vs $0.10-0.13 for alternatives
- **Already supported** in codebase - `embedding_provider: "jina"` requires only .env change
- **Same 1024 dimensions** as previous setup - no schema migration needed
- Free tier: 10M tokens, no credit card required

### Why not others?
- **Qwen3-Embedding-8B**: Best MTEB score but requires GPU self-hosting
- **Cohere Embed v4**: 5x more expensive than Jina, Latvian not explicitly tested
- **BGE-M3**: Good open-source option but requires local GPU for production scale
- **OpenAI**: Already using it, Latvian not explicitly optimized

## Monthly Cost Estimates (30-50 users)

### Assumptions
- 30-50 dispatchers, ~70% daily active
- ~15 queries/active user/day, 22 working days/month
- ~35% of queries hit knowledge base RAG
- ~2000 input tokens/query, ~400 output tokens/query

### Cost Breakdown

| Component | 30 users | 50 users |
|-----------|----------|----------|
| Jina v3 embeddings | < $0.01 | < $0.01 |
| Claude Sonnet 4.5 | ~$63 | ~$111 |
| BGE reranker (local) | $0 | $0 |
| **Total** | **~$63** | **~$111** |

~95% of cost is the LLM, not embeddings or RAG.

## Knowledge Base Storage Architecture

### Structured Data (50+ GB) -> PostgreSQL (NOT document store)

| Dataset | Size | Format | Storage |
|---------|------|--------|---------|
| E-ticket validations | ~6.5 GB | ZIPs | PostgreSQL (SQL queries) |
| Historical GTFS schedules | ~64 ZIPs | GTFS | PostgreSQL (SQL joins) |
| Weather observations | CSV | CSV | PostgreSQL + time-series |
| Road weather stations | REST API | Live | Redis cache |
| Traffic counts | CSV | CSV | PostgreSQL |
| Traffic accidents | CSV | CSV | PostgreSQL |
| Vehicle positions | Real-time | Protobuf | TimescaleDB |

**Key insight**: Traditional vector RAG is wrong for structured transit data. Embedding GPS coordinates and schedule tables into vectors destroys their relational structure. Use typed SQL tools instead.

### Unstructured Docs (SOPs, policies) -> RAG Pipeline

The existing `app/knowledge/` pipeline handles this:
- Upload via REST API -> chunk -> embed with Jina v3 -> store in PostgreSQL + pgvector
- Hybrid search: vector cosine + fulltext with RRF fusion
- Cross-encoder reranking with BGE-reranker-v2-m3

### Security: Local-First Architecture

All data stays on own infrastructure. Two deployment options:

**Option A: Everything on own server (most secure)**
```
Your server (office/datacenter)
  ├── FastAPI app
  ├── PostgreSQL + pgvector
  ├── Knowledge base docs
  └── Document management (optional)
```

**Option B: App on cloud, data local (hybrid)**
```
Cloudflare (app) <--VPN/tunnel--> Your server (PostgreSQL, docs)
```

### Document Management Alternatives to Obsidian

Obsidian is limited to ~5 GB / ~50K files. For larger scale:

| Tool | Max Scale | API | License | Cost |
|------|----------|-----|---------|------|
| Outline | 50+ GB | REST | BSL/Apache | Free |
| BookStack | 100+ GB | REST | MIT | Free |
| Paperless-ngx | 100+ GB | REST | GPL | Free |
| WikiJS | 100+ GB | GraphQL | AGPL | Free |
| PostgreSQL RAG | Unlimited | Own API | PostgreSQL | Free |

All self-hosted, open-source, zero licensing costs.

**Recommendation**: Use existing PostgreSQL RAG pipeline for document storage. Add Outline only if dispatchers need a browsing/editing UI for documents.

## Configuration (Current State)

```env
# LLM
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5-20250929

# Embedding
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v3
EMBEDDING_DIMENSION=1024
EMBEDDING_BASE_URL=https://api.jina.ai/v1

# Reranker (unchanged)
RERANKER_PROVIDER=local
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
```

## Document Viewer UX Decision

**Decision**: Option B - CMS document viewer page

When the agent returns knowledge base results, it includes links to a dedicated document viewer page in the CMS. Clicking opens the full document in a new tab.

### Required Components

**Backend:**
- `GET /api/v1/knowledge/documents/{id}/content` - returns full extracted text + metadata
- Agent formats links as `[document-title](/lv/documents/{id})` in responses

**Frontend:**
- New page: `cms/apps/web/src/app/[locale]/(dashboard)/documents/[id]/page.tsx`
- Renders: document title, metadata (upload date, domain, format), full content with markdown
- Highlighted search context (if arrived from chat link with query param)
- Download original file button
- i18n keys in `lv.json` and `en.json`
- Sidebar nav entry (optional - may not need standalone browsing)

**Agent prompt update:**
- Instruct agent to include document links in responses when citing knowledge base results
- Format: `[Dokumenta nosaukums](/lv/documents/{id})` with source attribution

## Unified DMS (replacing Paperless-ngx with built-in solution)

**Decision**: Build document management directly into CMS instead of adding Paperless-ngx as a separate service. Single app, single login, seamless UX.

**Rationale**: Paperless-ngx would require a separate UI, separate login, and separate Docker service. The existing `app/knowledge/` RAG pipeline already handles ~60% of what Paperless-ngx does. Building the remaining features into the existing stack is ~11 days of work and results in a unified experience.

**Does NOT affect**: Latvian language agent capability, system prompt, Sonnet 4.5 model, Jina v3 embeddings, or any existing agent tools. The agent's `search_knowledge_base` tool continues to work as-is — this adds UI and better ingestion around it.

### What already exists (app/knowledge/)

- Document upload via REST API (5 endpoints)
- Text extraction: PDF (PyMuPDF), DOCX, email (.eml), image OCR (pytesseract), plain text
- Recursive chunking (512 chars, 50 overlap)
- Jina v3 embedding + pgvector storage
- Hybrid search (vector cosine + fulltext with RRF fusion)
- Cross-encoder reranking (BGE-reranker-v2-m3)
- Agent tool: `search_knowledge_base`

### Backend additions (~4 days)

| Task | Effort | Details |
|------|--------|---------|
| Scanned PDF detection + OCR | 1 day | If PyMuPDF returns empty text -> run Tesseract OCR on pages |
| Excel/CSV extraction | 0.5 day | `openpyxl` + stdlib `csv` |
| LLM auto-tagging on upload | 1 day | Send first 500 chars to Claude -> classify domain/tags |
| Tag CRUD endpoints | 0.5 day | `/api/v1/knowledge/tags` - list, create, delete |
| Document download endpoint | 0.5 day | `/api/v1/knowledge/documents/{id}/download` - serve original file |
| Document content endpoint | 0.5 day | `/api/v1/knowledge/documents/{id}/content` - full extracted text |

### Frontend CMS pages (~6 days)

| Page | Route | Effort | Features |
|------|-------|--------|----------|
| Document upload | `/documents/upload` | 2 days | Drag & drop, progress bar, metadata form, auto-tag preview |
| Document list | `/documents` | 2 days | Table with filters (domain, tags, date, type), search, pagination |
| Document viewer | `/documents/[id]` | 1.5 days | Rendered content, metadata sidebar, download button, highlighted search matches |
| Tag management | Inline on list/viewer | 0.5 day | Tag chips, filter by tag |

### i18n + testing (~1 day)

- All new pages need `lv.json` + `en.json` keys
- Unit tests for new backend endpoints
- Frontend component tests

### Agent integration

- Agent prompt update: include document links in knowledge base responses
- Format: `[Dokumenta nosaukums](/lv/documents/{id})` with source attribution
- No changes to existing tool logic — just adds links to the response format

### Unified architecture

```
CMS (localhost:3000)
├── /dashboard          — metrics, calendar
├── /routes             — route management + map
├── /documents          — browse, search, filter        [NEW]
├── /documents/upload   — drag & drop upload             [NEW]
├── /documents/[id]     — view document + metadata       [NEW]
├── /stops              — stop management
└── /chat               — AI assistant
        │
        ├── "Kāda ir sniega procedūra?"
        │    → search_knowledge_base → answer + link
        │    → [Skatīt dokumentu](/lv/documents/42)    → opens viewer
        │
        └── All powered by ONE PostgreSQL instance
```

### Build order

1. Backend: scanned PDF OCR + Excel/CSV extraction
2. Backend: document download + content endpoints
3. Backend: tag CRUD + LLM auto-tagging
4. Frontend: document list page
5. Frontend: document upload page
6. Frontend: document viewer page
7. Agent: prompt update for document links
8. i18n + testing

### Total: ~11 days

## Sources

- [LAG-MMLU Baltic Language Benchmark](https://arxiv.org/html/2501.03952v1)
- [TildeLM - Baltic Language LLM](https://tech.eu/2025/07/31/most-llms-ignores-baltic-and-eastern-european-languages-tildelm-is-the-solution/)
- [Jina Embeddings v3](https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/)
- [MTEB Embedding Benchmark](https://huggingface.co/spaces/mteb/leaderboard)
- [Cohere Embed v4](https://app.ailog.fr/en/blog/news/cohere-embed-v4)
- [MMTEB Multilingual Benchmark](https://arxiv.org/abs/2502.13595)
- [Best Embedding Models 2026](https://www.openxcell.com/blog/best-embedding-models/)
