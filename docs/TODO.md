# VTV TODO

Planned features and improvements. Each item links to its detailed planning document.

## Planned Features

### Knowledge Base

- [ ] **RAG Knowledge Base Improvements** — Expand document type support (Excel/CSV, HTML, PPTX), add Latvian lemmatizer, parent-child chunking, temporal metadata, auto-domain tagging, cross-lingual search, document versioning, search feedback loop, and knowledge graph overlay. ~14-16 days total effort, ~$0.65/month added cost.
  - Plan: [docs/PLANNING/rag-improvements.md](PLANNING/rag-improvements.md)

- [ ] **SOP & File Automation** — Automated document ingestion (folder watcher, email monitor, web scraper, GTFS sync) and LLM-powered SOP generation (incident-to-SOP pipeline, regulation change detection, shift handover notes, template scaffolding). ~13 days total effort, ~$4.50/month LLM cost, saves ~47 hrs/month human time.
  - Plan: [docs/PLANNING/sop-file-automation.md](PLANNING/sop-file-automation.md)

## Completed

- [x] **RAG Knowledge Base** — Hybrid search (pgvector + fulltext + RRF), multi-format ingestion (PDF, DOCX, email, image OCR, text), configurable embeddings (OpenAI/Jina/local), cross-encoder reranking, agent tool integration. 337 tests passing.
