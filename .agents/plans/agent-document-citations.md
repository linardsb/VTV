# Plan: Agent Document Citations

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Primary Systems Affected**: Agent tool (knowledge search), Agent system prompt, Agent tool schemas

## Feature Description

When the AI agent cites results from the knowledge base search tool, it should include clickable markdown links that point to the document in the CMS. Currently, the `search_knowledge_base` tool returns results with `source` (filename) and `relevance_score` but strips the `document_id` — so the agent cannot construct a link to the original document.

This enhancement adds `document_id` to the agent-facing knowledge search schema, updates the system prompt to instruct the agent to format citations as markdown links (`[filename](/lv/documents/{id})`), and updates the tool docstring to describe the citation URL format. The frontend chat UI already renders markdown via `react-markdown`, so links will be clickable automatically — no frontend changes needed.

The URL format `/{locale}/documents/{id}` points to a future CMS documents page. The links will render as clickable in chat immediately; when the documents page is built, they will navigate correctly.

## User Story

As a dispatcher or administrator using the AI chat,
I want cited knowledge base documents to appear as clickable links,
So that I can click through to view the full source document.

## Solution Approach

The approach is minimal and surgical — three files need changes:

1. **Schema change**: Add `document_id: int` to `KnowledgeSearchResult` (the agent-facing schema in `app/core/agents/tools/knowledge/schemas.py`). This is a 1-line addition.

2. **Tool change**: Map `document_id` from the knowledge service's `SearchResult.document_id` through to the agent-facing response in `search_knowledge_base()`. This is a 1-line addition in the result mapping.

3. **Prompt change**: Add a citation instruction block to the `SYSTEM_PROMPT` in `app/core/agents/agent.py` that tells the agent to format knowledge base citations as `[title](/lv/documents/{id})` or `[title](/en/documents/{id})` matching the conversation language.

**Approach Decision:**
We chose to pass `document_id` in the tool result and instruct the agent via system prompt, because:
- The agent already handles language detection and can select `/lv/` vs `/en/` locale prefix
- Pre-formatting the full URL in the tool response would require knowing the user's language at tool-call time, which the tool function doesn't have
- The system prompt approach is consistent with how the agent already handles response formatting rules

**Alternatives Considered:**
- **Add `citation_url` field pre-formatted in tool response**: Rejected because the tool function doesn't know the user's locale. Would require passing locale through UnifiedDeps or hardcoding `/lv/`.
- **Frontend post-processing to inject links**: Rejected because it would require parsing the assistant's text, identifying document references, and injecting links — much more complex than having the agent format them natively.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/tools/knowledge/schemas.py` (lines 1-21) — Current agent-facing knowledge schemas (target for schema change)
- `app/core/agents/tools/knowledge/search_knowledge.py` (lines 1-139) — Current tool implementation (target for mapping change)
- `app/core/agents/agent.py` (lines 1-131) — System prompt and agent creation (target for prompt change)

### Similar Features (Examples to Follow)
- `app/core/agents/tools/transit/schemas.py` — Pattern for agent-facing Pydantic schemas with clear field descriptions
- `app/core/agents/tests/test_service.py` (lines 1-72) — Test patterns for agent module (TestModel override, mock deps)

### Files to Modify
- `app/core/agents/tools/knowledge/schemas.py` — Add `document_id` field
- `app/core/agents/tools/knowledge/search_knowledge.py` — Pass `document_id` in result mapping
- `app/core/agents/agent.py` — Add citation formatting instruction to SYSTEM_PROMPT

### Files to Create
- `app/core/agents/tools/knowledge/__init__.py` — Empty init (may already exist)
- `app/core/agents/tools/knowledge/tests/__init__.py` — Empty init for test package
- `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` — Unit tests for the tool

## Implementation Plan

### Phase 1: Schema Enhancement
Add `document_id` to the agent-facing `KnowledgeSearchResult` schema so the LLM receives document identifiers in tool results.

### Phase 2: Tool Mapping Update
Update the `search_knowledge_base` tool to pass `document_id` from the knowledge service's `SearchResult` through to the agent-facing response.

### Phase 3: System Prompt Citation Instructions
Add a `CITATION RULES` section to the system prompt instructing the agent to format knowledge base citations as clickable markdown links with the correct locale prefix.

### Phase 4: Tool Docstring Update
Update the tool's docstring to document the citation link format, so the agent has guidance at both the system prompt level and the tool-result level.

### Phase 5: Tests
Create unit tests for the knowledge search tool covering: happy path with document_id in results, empty results, error handling.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Create one task per file — each task targets exactly one file path.
Use action keywords: CREATE, UPDATE, ADD, REMOVE, REFACTOR, MIRROR

### Task 1: Add `document_id` to Agent-Facing Knowledge Schema
**File:** `app/core/agents/tools/knowledge/schemas.py` (modify existing)
**Action:** UPDATE

Read the file first. Then add a `document_id: int` field to `KnowledgeSearchResult`. Place it as the first field (before `content`) since it's the primary identifier.

The updated class should look like:

```python
class KnowledgeSearchResult(BaseModel):
    """Single search result for agent consumption."""

    document_id: int
    content: str
    source: str
    domain: str
    relevance_score: float
    page_or_section: str | None = None
```

No other changes to this file. Do NOT modify `KnowledgeSearchResponse`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/knowledge/schemas.py`
- `uv run ruff check --fix app/core/agents/tools/knowledge/schemas.py` passes
- `uv run mypy app/core/agents/tools/knowledge/schemas.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/knowledge/schemas.py` passes with 0 errors

---

### Task 2: Pass `document_id` Through in Tool Function
**File:** `app/core/agents/tools/knowledge/search_knowledge.py` (modify existing)
**Action:** UPDATE

Read the file first. In the result-mapping list comprehension (around lines 98-107), add `document_id=r.document_id` to the `KnowledgeSearchResult(...)` constructor call.

The updated mapping should look like:

```python
        results = [
            KnowledgeSearchResult(
                document_id=r.document_id,
                content=r.chunk_content[:_MAX_CONTENT_CHARS],
                source=r.document_filename,
                domain=r.domain,
                relevance_score=round(r.score, 4),
                page_or_section=f"chunk {r.chunk_index}",
            )
            for r in response.results
        ]
```

The `r` variable here is of type `SearchResult` from `app/knowledge/schemas.py`, which already has a `document_id: int` field — no changes needed to the knowledge feature's own schema.

Also update the tool's docstring to add a CITATION note. Find the existing docstring `Returns:` section (around line 64-65) and replace it:

```python
    Returns:
        JSON string with search results including document_id for citation links.
        Each result has document_id — use it to link: [title](/{locale}/documents/{id}).
```

No other changes to this file.

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/knowledge/search_knowledge.py`
- `uv run ruff check --fix app/core/agents/tools/knowledge/search_knowledge.py` passes
- `uv run mypy app/core/agents/tools/knowledge/search_knowledge.py` passes with 0 errors
- `uv run pyright app/core/agents/tools/knowledge/search_knowledge.py` passes with 0 errors

---

### Task 3: Add Citation Formatting Instructions to System Prompt
**File:** `app/core/agents/agent.py` (modify existing)
**Action:** UPDATE

Read the file first. Add a new `CITATION RULES` section to the `SYSTEM_PROMPT` string. Insert it AFTER the existing `RESPONSE FORMAT RULES` section (which ends around line 84) and BEFORE the final "When you don't have enough information..." paragraph (line 85-86).

The new section to insert (between the response format rules and the closing paragraph):

```python
    #
    # --- Citation rules ---
    #
    "CITATION RULES:\n"
    "- When citing knowledge base search results, ALWAYS include a clickable link.\n"
    "- Format: [document title or filename](/lv/documents/{document_id}) for Latvian responses.\n"
    "- Format: [document title or filename](/en/documents/{document_id}) for English responses.\n"
    "- Use the document_id from the search result to construct the link.\n"
    "- Place citations inline or as a 'Sources' list at the end of your response.\n"
    "- Example (Latvian): Skatiet [Vaditaju rokasgramata](/lv/documents/42) plasakai.\n"
    "- Example (English): See [Driver Handbook](/en/documents/42) for details.\n\n"
```

**CRITICAL:** Use only ASCII HYPHEN-MINUS (`-`, U+002D) in all strings. Do NOT use EN DASH (`-`, U+2013). The Ruff linter (RUF001) will reject EN DASH characters. Double-check every dash character.

**CRITICAL:** Use only ASCII apostrophes (`'`) not Unicode smart quotes. The Ruff linter (RUF001) will reject ambiguous Unicode.

**CRITICAL:** The Latvian example strings must NOT contain actual Latvian diacritics (a, c, e, g, etc.) inside the SYSTEM_PROMPT Python string — these are fine for Latvian, but double-check they pass Ruff RUF001. If they trigger ambiguous-unicode warnings, replace with ASCII approximations in the example text only (e.g., "Vaditaju rokasgramata" instead of "Vadītāju rokasgrāmata"). The agent will output proper diacritics in its actual responses; the prompt example just needs to convey the pattern.

The full SYSTEM_PROMPT string after this change should have this structure:
1. Role description (existing, lines 28-34)
2. LANGUAGE RULES (existing, lines 38-44)
3. LATVIAN TRANSIT GLOSSARY (existing, lines 48-57)
4. LATVIAN INPUT UNDERSTANDING (existing, lines 61-72)
5. RESPONSE FORMAT RULES (existing, lines 76-84)
6. **CITATION RULES (NEW — insert here)**
7. Closing paragraph (existing, lines 85-87)

No other changes to this file. Do NOT modify the `create_agent` function or the tool list.

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check --fix app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes with 0 errors
- `uv run pyright app/core/agents/agent.py` passes with 0 errors

---

### Task 4: Create Test Package Init Files
**File:** `app/core/agents/tools/knowledge/__init__.py` (create if not exists)
**Action:** CREATE (if not exists)

Check if this file exists. If not, create an empty `__init__.py`:

```python
```

**File:** `app/core/agents/tools/knowledge/tests/__init__.py` (create new)
**Action:** CREATE

Create the test package directory and empty init file:

```python
```

Also create the tests directory if it doesn't exist.

**Per-task validation:**
- Verify both files exist: `ls app/core/agents/tools/knowledge/__init__.py app/core/agents/tools/knowledge/tests/__init__.py`

---

### Task 5: Create Unit Tests for Knowledge Search Tool
**File:** `app/core/agents/tools/knowledge/tests/test_search_knowledge.py` (create new)
**Action:** CREATE

Create comprehensive unit tests for the `search_knowledge_base` tool function. The tests mock the database session and knowledge service to test the tool in isolation.

**IMPORTANT RULES for test code:**
- All test functions that have ANY parameter type annotations MUST also have `-> None` return type
- Use `from unittest.mock import AsyncMock, MagicMock, patch` for mocking
- Mock `app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal` as a context manager
- Mock `app.core.agents.tools.knowledge.search_knowledge.KnowledgeService` class
- The `ctx` parameter is a `RunContext[UnifiedDeps]` — create it as a `MagicMock` with `ctx.deps.settings` returning a `MagicMock`
- Parse the JSON string return value with `json.loads()` to assert on structure
- Do NOT use `assert` for type narrowing in production code, but `assert` IS allowed in test files (Ruff S101 is disabled for tests)

**Test 1: Happy path — results include document_id**
```python
@pytest.mark.asyncio
async def test_search_returns_document_id() -> None:
    """Verify search results include document_id for citation links."""
    # Mock ctx
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    # Mock search result from knowledge service
    mock_search_result = MagicMock()
    mock_search_result.chunk_content = "Driver must follow schedule adherence rules."
    mock_search_result.document_id = 42
    mock_search_result.document_filename = "driver-handbook.pdf"
    mock_search_result.domain = "transit"
    mock_search_result.language = "en"
    mock_search_result.chunk_index = 3
    mock_search_result.score = 0.8765
    mock_search_result.metadata_json = None

    mock_response = MagicMock()
    mock_response.results = [mock_search_result]
    mock_response.total_candidates = 1

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(
                ctx, query="schedule adherence"
            )

    result = json.loads(result_json)
    assert len(result["results"]) == 1
    assert result["results"][0]["document_id"] == 42
    assert result["results"][0]["source"] == "driver-handbook.pdf"
    assert result["results"][0]["relevance_score"] == 0.8765
    assert result["results"][0]["content"] == "Driver must follow schedule adherence rules."
    assert result["query"] == "schedule adherence"
```

**Test 2: Empty query returns error string**
```python
@pytest.mark.asyncio
async def test_search_empty_query_returns_error() -> None:
    """Verify empty query returns actionable error message."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    result = await search_knowledge_base(ctx, query="")
    assert "Error" in result
    assert "empty" in result.lower()
```

**Test 3: Whitespace-only query returns error**
```python
@pytest.mark.asyncio
async def test_search_whitespace_query_returns_error() -> None:
    """Verify whitespace-only query returns error."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    result = await search_knowledge_base(ctx, query="   ")
    assert "Error" in result
```

**Test 4: Multiple results all have document_id**
```python
@pytest.mark.asyncio
async def test_search_multiple_results_have_document_ids() -> None:
    """Verify all results in multi-result response include document_id."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    # Create 3 mock results with different document IDs
    mock_results = []
    for i in range(3):
        r = MagicMock()
        r.chunk_content = f"Content chunk {i}"
        r.document_id = 10 + i  # IDs: 10, 11, 12
        r.document_filename = f"doc-{i}.pdf"
        r.domain = "transit"
        r.language = "lv"
        r.chunk_index = 0
        r.score = 0.9 - (i * 0.1)
        r.metadata_json = None
        mock_results.append(r)

    mock_response = MagicMock()
    mock_response.results = mock_results
    mock_response.total_candidates = 3

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(ctx, query="transit policy")

    result = json.loads(result_json)
    assert len(result["results"]) == 3
    assert result["results"][0]["document_id"] == 10
    assert result["results"][1]["document_id"] == 11
    assert result["results"][2]["document_id"] == 12
```

**Test 5: Service exception returns error string**
```python
@pytest.mark.asyncio
async def test_search_service_error_returns_message() -> None:
    """Verify service exceptions return actionable error string."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.side_effect = RuntimeError("DB connection lost")
            mock_svc_cls.return_value = mock_svc

            result = await search_knowledge_base(ctx, query="overtime policy")

    assert "error" in result.lower()
    assert "DB connection lost" in result
```

**Test 6: Content truncation respects 500 char limit**
```python
@pytest.mark.asyncio
async def test_search_truncates_content_to_500_chars() -> None:
    """Verify chunk content is truncated to 500 characters."""
    ctx = MagicMock()
    ctx.deps.settings = MagicMock()
    ctx.deps.settings.embedding_provider = "jina"

    long_content = "A" * 1000  # 1000 chars

    mock_result = MagicMock()
    mock_result.chunk_content = long_content
    mock_result.document_id = 1
    mock_result.document_filename = "long-doc.pdf"
    mock_result.domain = "hr"
    mock_result.language = "en"
    mock_result.chunk_index = 0
    mock_result.score = 0.95
    mock_result.metadata_json = None

    mock_response = MagicMock()
    mock_response.results = [mock_result]
    mock_response.total_candidates = 1

    with patch(
        "app.core.agents.tools.knowledge.search_knowledge.AsyncSessionLocal"
    ) as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.core.agents.tools.knowledge.search_knowledge.KnowledgeService"
        ) as mock_svc_cls:
            mock_svc = AsyncMock()
            mock_svc.search.return_value = mock_response
            mock_svc_cls.return_value = mock_svc

            result_json = await search_knowledge_base(ctx, query="hr policy")

    result = json.loads(result_json)
    assert len(result["results"][0]["content"]) == 500
```

**Test 7: Verify system prompt contains citation rules**
```python
def test_system_prompt_contains_citation_rules() -> None:
    """Verify SYSTEM_PROMPT instructs agent to format citation links."""
    from app.core.agents.agent import SYSTEM_PROMPT

    assert "CITATION RULES" in SYSTEM_PROMPT
    assert "/documents/" in SYSTEM_PROMPT
    assert "document_id" in SYSTEM_PROMPT
```

The complete test file must:
- Import `json`, `pytest`, `MagicMock`, `AsyncMock`, `patch`
- Import `search_knowledge_base` from the tool module
- NOT import or use real database sessions
- Have all async test functions decorated with `@pytest.mark.asyncio`
- Have `-> None` return type on ALL test functions

**Per-task validation:**
- `uv run ruff format app/core/agents/tools/knowledge/tests/test_search_knowledge.py`
- `uv run ruff check --fix app/core/agents/tools/knowledge/tests/test_search_knowledge.py` passes
- `uv run pytest app/core/agents/tools/knowledge/tests/test_search_knowledge.py -v` — all 7 tests pass

---

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check --fix .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tools/knowledge/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
curl -s http://localhost:8123/health
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Logging Events

No new logging events are needed. The existing events in `search_knowledge_base()` already cover:
- `agent.knowledge.search_started` — emitted when search begins
- `agent.knowledge.search_completed` — emitted on success (includes result_count, total_found)
- `agent.knowledge.search_failed` — emitted on error (includes error details)

The `document_id` is now part of the result data, so it flows through the existing logging implicitly.

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tools/knowledge/tests/test_search_knowledge.py`
- Tool function happy path — results include `document_id`
- Empty/whitespace query — returns error string
- Multiple results — all have `document_id`
- Service exception — returns actionable error
- Content truncation — respects 500 char limit
- System prompt — contains citation rules

### Integration Tests
None needed. The tool function is already covered by mocked unit tests. The knowledge service's search is tested separately in `app/knowledge/tests/`.

### Edge Cases
- Empty query → error string returned (no crash)
- Whitespace query → error string returned
- Service throws exception → error string with message (no crash)
- Very long content → truncated to 500 chars
- `document_id` is always an int from database PK — no null edge case

## Acceptance Criteria

This feature is complete when:
- [ ] `KnowledgeSearchResult` schema has `document_id: int` field
- [ ] `search_knowledge_base()` maps `document_id` from service results
- [ ] `SYSTEM_PROMPT` contains citation formatting rules with locale-aware URL pattern
- [ ] Tool docstring mentions citation link format
- [ ] 7 unit tests pass covering happy path, errors, truncation, and prompt verification
- [ ] All type checkers pass (mypy + pyright) with 0 errors
- [ ] All existing tests still pass (no regressions)
- [ ] Ruff format and check pass with 0 errors
- [ ] No type suppressions added
- [ ] No new dependencies needed
- [ ] Ready for `/commit`

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 5 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Dependencies

- Shared utilities used: None new (existing `AsyncSessionLocal` from `app.core.database`)
- Core modules used: `app.core.agents.agent` (system prompt), `app.core.logging` (existing)
- New dependencies: None — all changes use existing packages
- New env vars: None

## Known Pitfalls

The executing agent MUST follow these rules to avoid common errors:

1. **No EN DASH in strings** — Ruff RUF001 forbids ambiguous Unicode like `–` (EN DASH, U+2013). LLMs naturally generate these in time ranges ("05:00–13:00") and prose. Always use `-` (HYPHEN-MINUS, U+002D): `"05:00-13:00"`, `"trainee - supervised only"`. This is especially critical in the SYSTEM_PROMPT string where the citation examples use hyphens.

2. **No `assert` in production code** — Ruff S101 forbids assert outside test files. The production code changes (Tasks 1-3) must not use assert. Test code (Task 5) can use assert freely.

3. **Pydantic AI `ctx` must be referenced** — Ruff ARG001 flags unused args. The existing tool already references `ctx` via `_settings = ctx.deps.settings`. Do not break this pattern.

4. **Partially annotated test functions need `-> None`** — Adding param type annotations to any test function parameter without a return type triggers mypy `no-untyped-def`. Always use `async def test_foo() -> None:`.

5. **No unused imports or variables** — Ruff F401 catches unused imports, F841 catches unused variables. Only import what the test file actually uses.

6. **Unicode in Latvian example text** — The system prompt Latvian examples (like "Vaditaju rokasgramata") should use ASCII-safe approximations (no diacritics) to avoid potential RUF001 warnings. The agent will produce proper diacritics in actual responses; the prompt example just needs to convey the URL pattern.

7. **Dict literal invariance in tests** — When constructing test data, use explicit type annotations if passing to functions expecting `dict[str, str | None]`.

## Notes

- **Future work**: When the CMS documents page (`/{locale}/documents/{id}`) is built, the citation links will automatically resolve. Until then, links render as clickable but navigate to a 404. This is acceptable — the chat UI still clearly shows the document name and ID.
- **Locale detection**: The agent determines locale from conversation context (system prompt says "match the user's language"). It will use `/lv/` for Latvian conversations and `/en/` for English. This is a best-effort approach — if the agent occasionally uses the wrong locale, the CMS can redirect.
- **Token efficiency**: Adding `document_id` (a single integer) has negligible impact on token consumption in tool results.
- **No migration needed**: The `document_id` already exists in the database (`documents.id` PK) and flows through the knowledge service's `SearchResult`. We're just exposing it to the agent-facing schema.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Understood the solution approach: schema + tool mapping + prompt
- [ ] Clear on task execution order (schema first, then tool, then prompt, then tests)
- [ ] Validation commands are executable in this environment
- [ ] Confirmed no EN DASH characters will be introduced in string literals
