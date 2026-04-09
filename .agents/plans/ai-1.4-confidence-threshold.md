# Plan: AI-1.4 Confidence Threshold + "No Results" Response

## Context
Currently the knowledge search tool returns all reranked results regardless of score. When the KB lacks relevant content, the agent receives low-relevance chunks and hallucinates answers grounded in irrelevant material. Dispatchers need to know when the system genuinely lacks information. This adds a configurable confidence threshold (default 0.3) — results below it are filtered, and when nothing passes, the tool returns "No relevant documents found."

## Security Context Assessment
- **CTX-AGENT** — Modifies agent tool behavior and system prompt. Must ensure tool doesn't expose internal scoring details to end users.
- **CTX-INPUT** — Threshold is config-only (not user-supplied), no input validation needed.

## Research Summary

### Score Flow
1. **Repository** → `search_vector()` returns cosine distance, `search_fulltext()` returns ts_rank
2. **Service** → RRF fusion + temporal boost + reranking via `BAAI/bge-reranker-v2-m3`
3. **Final score** → `RerankResult.score` (0–1 range from cross-encoder) stored in `SearchResult.score`
4. **Tool** → Mapped to `KnowledgeSearchResult.relevance_score` (rounded to 4 decimals)

### Key Files
| File | Lines | Role |
|------|-------|------|
| `app/core/config.py` | 170–201 | `Settings` — KnowledgeConfig fields (chunk, reranker, RRF, temporal) |
| `app/knowledge/service.py` | 400–530 | `search()` — orchestrates vector+fulltext, RRF, reranking, builds results |
| `app/core/agents/tools/knowledge/search_knowledge.py` | 30–156 | `search_knowledge_base()` — agent tool, calls service, formats JSON |
| `app/core/agents/tools/knowledge/schemas.py` | 1–23 | `KnowledgeSearchResult`, `KnowledgeSearchResponse` |
| `app/core/agents/agent.py` | 28–99 | `SYSTEM_PROMPT` string |

### Existing Patterns
- Config: env-var-backed floats follow `knowledge_*` / `temporal_boost_*` / `rrf_*` naming
- Service: results built in loop at ~lines 497–514 from `reranked` list
- Tool: returns `json.dumps(result.model_dump())` or plain error string
- Empty results: tool currently returns `"No documents found."` for errors only

## Test Landscape

### Existing Test Files
| File | Tests | Key Patterns |
|------|-------|--------------|
| `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` | 7 | AsyncMock service, MagicMock results with `.score`, patched `AsyncSessionLocal` |
| `app/knowledge/tests/test_repository.py` | 13 | `make_document()`, `make_chunk()` factories |
| `app/knowledge/tests/test_reranker.py` | 6+ | Score ordering assertions |

### Mock Pattern for Tool Tests
```python
with patch("...KnowledgeService") as mock_svc_cls:
    mock_svc = AsyncMock()
    mock_svc.search.return_value = mock_response
    mock_svc_cls.return_value = mock_svc
```

### Fixtures Available
- `conftest.py` (knowledge): `sample_upload`, `sample_latvian_text`, `sample_english_text`
- `test_repository.py`: `make_document(**overrides)`, `make_chunk(**overrides)`

## Type Check Baseline
| Target | Pyright | Mypy |
|--------|---------|------|
| `app/core/agents/tools/knowledge/` | 0 errors | 0 errors |
| `app/core/agents/service.py` | 0 errors | 3 pre-existing (transitive imports, not in service.py) |
| `app/core/config.py` | 0 errors | 0 errors |

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| UPDATE | `app/core/config.py` | Add `knowledge_confidence_threshold: float = 0.3` |
| UPDATE | `app/knowledge/service.py` | Filter reranked results by threshold, add logging |
| UPDATE | `app/core/agents/tools/knowledge/search_knowledge.py` | Return "No relevant documents found" when empty after filtering |
| UPDATE | `app/core/agents/agent.py` | Add SYSTEM_PROMPT guidance for no-results behavior |
| UPDATE | `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` | Add threshold filtering + no-results tests |

## Implementation Steps

### Step 1: Add config setting
**File:** `app/core/config.py`
**Action:** Add `knowledge_confidence_threshold: float = 0.3` after the existing reranker settings (~line 174).
Env var: `KNOWLEDGE__CONFIDENCE_THRESHOLD`.

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py`

### Step 2: Filter results in service layer
**File:** `app/knowledge/service.py`
**Action:** In the `search()` method, after the reranking loop builds results (~lines 497–514), filter by confidence threshold. Since reranked results are sorted descending by score, use `break` when score drops below threshold. Add structured log event for filtered count.

```python
# After reranking loop, filter by confidence threshold
threshold = settings.knowledge_confidence_threshold
results = [r for r in results if r.score >= threshold]

logger.info(
    "knowledge.search.confidence_filtered",
    threshold=threshold,
    pre_filter=len(reranked),
    post_filter=len(results),
    query=request.query[:80],
)
```

Note: `settings` is already available in the function — it's accessed from `self` or passed as parameter. Check exact access pattern before implementing.

**Validation:** `uv run ruff format app/knowledge/service.py && uv run ruff check --fix app/knowledge/service.py && uv run pyright app/knowledge/service.py`

### Step 3: Handle empty results in tool
**File:** `app/core/agents/tools/knowledge/search_knowledge.py`
**Action:** After calling `service.search()` and checking `response.results`, if empty, return a clear no-results message. Keep existing error handling for exceptions.

The "no results" path should return a plain string (not JSON) for clearer agent consumption:
```python
if not response.results:
    return (
        f"No relevant documents found for query: '{query}'. "
        "The knowledge base does not contain information matching this query with sufficient confidence."
    )
```

This goes between the `service.search()` call and the results-mapping loop.

**Validation:** `uv run ruff format app/core/agents/tools/knowledge/search_knowledge.py && uv run ruff check --fix app/core/agents/tools/knowledge/search_knowledge.py && uv run pyright app/core/agents/tools/knowledge/search_knowledge.py`

### Step 4: Update agent system prompt
**File:** `app/core/agents/agent.py`
**Action:** Add a `KNOWLEDGE BASE BEHAVIOR` section to `SYSTEM_PROMPT` before the `CITATION RULES` section (~line 87). Keep it concise:

```python
"KNOWLEDGE BASE BEHAVIOR:\n"
"- When knowledge search returns 'No relevant documents found', tell the user honestly.\n"
"- Do NOT fabricate or guess information when the knowledge base has no results.\n"
"- Suggest the user rephrase, try related topics, or upload the relevant document.\n\n"
```

**Validation:** `uv run ruff format app/core/agents/agent.py && uv run ruff check --fix app/core/agents/agent.py && uv run pyright app/core/agents/agent.py`

### Step 5: Add tests
**File:** `app/core/agents/tools/knowledge/tests/test_search_knowledge.py`
**Action:** Add 3 tests following existing patterns (AsyncMock service, MagicMock results):

1. **`test_search_no_results_returns_no_documents_message`** — Mock service returning empty `SearchResponse(results=[], ...)`. Assert return string contains "No relevant documents found".

2. **`test_search_filters_low_confidence_results`** — Mock service returning results with scores [0.8, 0.1]. Assert only the high-score result appears in output. (This tests the service layer filtering indirectly through the tool.)

3. **`test_system_prompt_contains_knowledge_base_behavior`** — Assert `SYSTEM_PROMPT` contains "No relevant documents found" and "Do NOT fabricate".

Follow existing mock patterns: patch `KnowledgeService`, `AsyncSessionLocal`, use `MagicMock` for result objects with `.score`, `.document_id`, `.chunk_content`, etc.

**Validation:** `uv run pytest app/core/agents/tools/knowledge/tests/test_search_knowledge.py -v && uv run pyright app/core/agents/tools/knowledge/tests/test_search_knowledge.py`

### Step 6: Final validation
Run full suite:
```bash
make check
```

## Preflight Warnings
- No fragile patterns found in existing knowledge tool tests
- Existing tests use `MagicMock` for settings — new tests must set `ctx.deps.settings.knowledge_confidence_threshold` on the mock
- The service `search()` method accesses settings — verify how (via `self.settings`, function param, or module-level). Read the function signature before implementing Step 2.

## Security Checklist
- [x] No new endpoints (no CTX-RBAC needed)
- [x] No user-supplied threshold (config-only, no CTX-INPUT)
- [x] Tool response doesn't expose internal scores when no results (just a message)
- [x] System prompt update prevents hallucination (CTX-AGENT)
- [x] No credential exposure in tool responses

## Verification
- [ ] `make check` passes (lint + types + tests)
- [ ] Pyright errors = 0 on all modified files (baseline: 0)
- [ ] New tests pass: `uv run pytest app/core/agents/tools/knowledge/tests/ -v`
- [ ] System prompt contains knowledge base behavior guidance
- [ ] Config setting `knowledge_confidence_threshold` has default 0.3
