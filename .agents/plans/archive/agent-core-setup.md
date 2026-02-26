# Plan: Agent Core Setup

## Feature Metadata
**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: `app/core/agents/`, `app/main.py`, `pyproject.toml`, `conftest.py` (root)

## Feature Description

Create the foundational AI agent infrastructure for VTV in `app/core/agents/`. This sets up a base Pydantic AI agent with a simple transit-focused system prompt, agent-specific configuration (LLM provider/model settings), and a test API endpoint (`POST /v1/chat/completions`) for sending messages and receiving responses.

This is the skeleton that all future agent tools (5 transit + 4 Obsidian vault) will plug into. The scope is deliberately minimal: one agent, one endpoint, no tools yet, no streaming. The goal is to prove the agent can receive a prompt, call an LLM (or TestModel in tests), and return a response — all with strict typing, structured logging, and proper test coverage.

A root-level `conftest.py` will also be created to provide shared test fixtures (FastAPI `TestClient`, mock settings) that all test modules can use, avoiding duplication across `app/core/tests/`, `app/shared/tests/`, and future feature test directories.

## User Story

As a developer building the VTV agent service,
I want a working base agent with an API endpoint,
So that I can iteratively add tools and capabilities with a tested foundation.

## Solution Approach

Place the agent in `app/core/agents/` as a core infrastructure module (not a feature slice) because:
- The agent is shared infrastructure that future feature tools plug into
- It follows the user's explicit request for `core/agents/`
- Agent config (LLM provider, model) is application-wide, not feature-specific

The API endpoint follows the OpenAI-compatible format (`POST /v1/chat/completions`) as specified in the PRD, making it compatible with any OpenAI client library.

**Approach Decision:**
We chose `app/core/agents/` (core infrastructure) because:
- The agent is a cross-cutting concern used by multiple future features (transit tools, obsidian tools)
- Agent configuration (LLM provider, model selection, fallback) is infrastructure-level
- User explicitly requested this location

**Alternatives Considered:**
- `app/agent/` (feature slice): Rejected because the agent isn't a standalone feature — it's infrastructure that features register tools with
- `app/agents/` (top-level feature): Rejected — same reason, plus doesn't follow the user's `core/agents/` request

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/config.py` (lines 1-61) — Settings pattern with `BaseSettings`, `@lru_cache`, `SettingsConfigDict`
- `app/core/logging.py` (lines 1-146) — Structured logging with `get_logger()`, event naming pattern
- `app/core/exceptions.py` (lines 1-86) — Exception hierarchy pattern, global handler registration
- `app/core/health.py` (lines 1-106) — Route pattern with `APIRouter`, `Depends()`
- `app/core/__init__.py` (line 1) — Module docstring pattern

### Similar Features (Examples to Follow)
- `app/core/health.py` — Route definition pattern with APIRouter, tags, typed returns
- `app/core/config.py` — Settings class pattern to mirror for agent config
- `app/tests/test_main.py` (lines 1-96) — TestClient fixture pattern, endpoint testing
- `app/core/tests/test_health.py` (lines 1-133) — AsyncMock pattern, patching loggers, testing error paths
- `app/core/tests/test_config.py` (lines 1-110) — Settings testing with `patch.dict(os.environ, ...)`
- `app/tests/conftest.py` (lines 1-71) — DB fixture pattern (reference for root conftest structure)

### Files to Modify
- `app/main.py` — Register agent router
- `pyproject.toml` — Add `pydantic-ai` dependency
- `.env.example` — Add LLM provider env vars
- `app/core/config.py` — Add LLM settings fields

## Research Documentation

Use these resources for implementation guidance:

- **Pydantic AI v1.0.5 — Agent Creation**
  - Pattern: `Agent('provider:model', deps_type=..., output_type=str, system_prompt='...')`
  - Agent accepts `system_prompt` as string or callable
  - Use `agent.run(prompt)` for async execution, returns `RunResult` with `.output`

- **Pydantic AI v1.0.5 — Testing with TestModel**
  - Pattern: `with agent.override(model=TestModel()): result = await agent.run(...)`
  - Set `models.ALLOW_MODEL_REQUESTS = False` at test module level to prevent accidental real API calls
  - `TestModel()` returns `'success (no tool calls)'` by default
  - Use `FunctionModel(fn)` for custom test responses

- **Pydantic AI v1.0.5 — FunctionModel for Custom Test Responses**
  - Pattern: `FunctionModel(call_fn)` where `call_fn(messages, info) -> ModelResponse`
  - Return `ModelResponse(parts=[TextPart('response text')])`
  - Useful for testing specific agent behaviors

## Implementation Plan

### Phase 1: Foundation
1. Add `pydantic-ai` dependency
2. Create root `conftest.py` with shared test fixtures
3. Add LLM config fields to Settings
4. Update `.env.example` with new env vars

### Phase 2: Core Implementation
5. Create `app/core/agents/__init__.py` module
6. Create agent config (`app/core/agents/config.py`)
7. Create agent schemas (`app/core/agents/schemas.py`)
8. Create agent exceptions (`app/core/agents/exceptions.py`)
9. Create base agent (`app/core/agents/agent.py`)
10. Create agent service (`app/core/agents/service.py`)
11. Create agent routes (`app/core/agents/routes.py`)

### Phase 3: Integration & Validation
12. Register agent router in `app/main.py`
13. Create agent tests
14. Run full validation pyramid

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add pydantic-ai Dependency
**File:** `pyproject.toml` (modify existing)
**Action:** UPDATE

Add `pydantic-ai` to the project dependencies list:
```
"pydantic-ai>=1.0.5",
```

Then run:
```bash
uv add pydantic-ai
```

**Per-task validation:**
- `uv run python -c "import pydantic_ai; print(pydantic_ai.__version__)"` succeeds

---

### Task 2: Create Root conftest.py
**File:** `conftest.py` (create new — at project root, next to pyproject.toml)
**Action:** CREATE

Create a root-level conftest.py that provides shared test fixtures for ALL test modules:

```python
"""Root pytest configuration and shared fixtures.

This conftest.py sits at the project root (next to pyproject.toml) and provides
fixtures available to ALL test modules across the application. Feature-specific
fixtures should remain in their respective tests/ directories.

Shared fixtures provided:
- client: FastAPI TestClient for endpoint testing
- mock_settings: Patched Settings for unit tests without .env dependency
"""
```

Define these fixtures:

1. `client` fixture (scope="function"):
   - Returns `TestClient(app)` from `app.main`
   - Pattern: follow `app/tests/test_main.py` lines 12-14

2. `mock_settings` fixture (scope="function"):
   - Uses `patch.dict(os.environ, {...})` to set test environment variables
   - Sets `DATABASE_URL=postgresql+asyncpg://test:test@localhost:5432/test_db`
   - Sets `ENVIRONMENT=test`, `LOG_LEVEL=DEBUG`
   - Sets `LLM_PROVIDER=test`, `LLM_MODEL=test-model` (for agent tests)
   - Clears settings cache with `get_settings.cache_clear()` before and after
   - Pattern: follow `app/core/tests/test_config.py` lines 23-31

All fixtures must have Google-style docstrings. No type annotations required in test files (per pyproject.toml ruff config).

**Per-task validation:**
- `uv run ruff format conftest.py`
- `uv run ruff check conftest.py` passes
- `uv run pytest --collect-only conftest.py` — fixtures are discoverable

---

### Task 3: Add LLM Settings to Config
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add LLM configuration fields to the `Settings` class, AFTER the existing CORS settings block:

```python
# LLM Provider
llm_provider: str = "test"
llm_model: str = "test-model"
llm_fallback_provider: str | None = None
llm_fallback_model: str | None = None
```

These use safe defaults (`"test"`) so the app works without LLM env vars. Production deployments override via environment variables.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check app/core/config.py` passes
- `uv run mypy app/core/config.py` passes
- Existing tests still pass: `uv run pytest app/core/tests/test_config.py -v`

---

### Task 4: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Uncomment and update the LLM Provider section:

```bash
# LLM Provider
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
# LLM_FALLBACK_PROVIDER=ollama
# LLM_FALLBACK_MODEL=llama3.1:70b
```

Remove the old commented-out LLM lines and the Obsidian lines (those will be added when vault tools are built).

**Per-task validation:**
- File is valid (no syntax errors in comments)

---

### Task 5: Create agents module init
**File:** `app/core/agents/__init__.py` (create new)
**Action:** CREATE

```python
"""AI agent infrastructure for VTV.

This module provides the base Pydantic AI agent, configuration,
schemas, and API routes for the unified agent service.
"""
```

**Per-task validation:**
- `uv run ruff check app/core/agents/__init__.py` passes
- `uv run python -c "import app.core.agents"` succeeds

---

### Task 6: Create Agent Config
**File:** `app/core/agents/config.py` (create new)
**Action:** CREATE

Create agent-specific configuration that reads from the main Settings:

Define a function `build_model_string(settings: Settings) -> str` that:
- Takes a `Settings` instance
- Returns `f"{settings.llm_provider}:{settings.llm_model}"` (e.g., `"anthropic:claude-sonnet-4-5"`)
- This is used by the agent factory to configure which LLM to use

Define a function `get_agent_model(settings: Settings | None = None) -> str | FallbackModel`:
- If `settings` is None, calls `get_settings()`
- If `settings.llm_fallback_provider` is set, returns `FallbackModel(primary, fallback)` from `pydantic_ai.models.fallback`
- Otherwise returns the primary model string
- Import `FallbackModel` from `pydantic_ai.models.fallback`

Include structured logging:
- `logger.info("agent.config.model_configured", provider=..., model=..., has_fallback=...)`

Follow pattern from `app/core/config.py` for imports and typing.

**Per-task validation:**
- `uv run ruff format app/core/agents/config.py`
- `uv run ruff check app/core/agents/config.py` passes
- `uv run mypy app/core/agents/config.py` passes

---

### Task 7: Create Agent Schemas
**File:** `app/core/agents/schemas.py` (create new)
**Action:** CREATE

Define OpenAI-compatible request/response schemas:

1. `ChatMessage(BaseModel)`:
   - `role: Literal["user", "assistant", "system"]`
   - `content: str`

2. `ChatCompletionRequest(BaseModel)`:
   - `messages: list[ChatMessage]` — with `Field(min_length=1)`
   - `model: str | None = None` — optional override (ignored in MVP, uses server config)

3. `ChatCompletionChoice(BaseModel)`:
   - `index: int = 0`
   - `message: ChatMessage`
   - `finish_reason: str = "stop"`

4. `UsageInfo(BaseModel)`:
   - `prompt_tokens: int = 0`
   - `completion_tokens: int = 0`
   - `total_tokens: int = 0`

5. `ChatCompletionResponse(BaseModel)`:
   - `id: str` — generated UUID
   - `object: Literal["chat.completion"] = "chat.completion"`
   - `created: int` — Unix timestamp
   - `model: str`
   - `choices: list[ChatCompletionChoice]`
   - `usage: UsageInfo`

All schemas use `model_config = ConfigDict(strict=True)` where appropriate.
All fields have type annotations. Use Google-style docstrings.
Follow pattern from `app/shared/schemas.py`.

**Per-task validation:**
- `uv run ruff format app/core/agents/schemas.py`
- `uv run ruff check app/core/agents/schemas.py` passes
- `uv run mypy app/core/agents/schemas.py` passes
- `uv run pyright app/core/agents/schemas.py` passes

---

### Task 8: Create Agent Exceptions
**File:** `app/core/agents/exceptions.py` (create new)
**Action:** CREATE

Define agent-specific exceptions following the pattern in `app/core/exceptions.py`:

1. `AgentError(Exception)` — Base exception for all agent errors
2. `AgentConfigurationError(AgentError)` — Invalid LLM config (wrong provider, missing key)
3. `AgentExecutionError(AgentError)` — Agent run failed (LLM timeout, rate limit, etc.)

Add an `agent_exception_handler` async function following the exact pattern from `app/core/exceptions.py` lines 33-66:
- Maps `AgentConfigurationError` → 500
- Maps `AgentExecutionError` → 502 (Bad Gateway — upstream LLM failed)
- Logs with `agent.error` event, includes `error_type`, `error_message`, `path`, `method`

Add a `setup_agent_exception_handlers(app: FastAPI) -> None` function that registers the handler for all three exception types.

**Per-task validation:**
- `uv run ruff format app/core/agents/exceptions.py`
- `uv run ruff check app/core/agents/exceptions.py` passes
- `uv run mypy app/core/agents/exceptions.py` passes

---

### Task 9: Create Base Agent
**File:** `app/core/agents/agent.py` (create new)
**Action:** CREATE

Create the base Pydantic AI agent:

1. Define `SYSTEM_PROMPT: str` constant with:
   ```
   You are a transit operations and knowledge management assistant for Riga's municipal bus system (VTV).
   You help dispatchers and administrators with transit queries, schedule information, and operational insights.
   Be concise, accurate, and helpful. When you don't have enough information to answer, say so clearly.
   ```

2. Define `create_agent(model: str | FallbackModel | None = None) -> Agent[None, str]` function:
   - If `model` is None, calls `get_agent_model()` from `app/core/agents/config`
   - Returns `Agent(model, output_type=str, system_prompt=SYSTEM_PROMPT)`
   - Uses `deps_type=None` (no dependencies yet — tools will add deps later)
   - Logs `agent.create_completed` with model info

3. Create module-level `agent` instance: `agent = create_agent()`

This follows the factory pattern so tests can call `create_agent()` with a `TestModel`.

**Per-task validation:**
- `uv run ruff format app/core/agents/agent.py`
- `uv run ruff check app/core/agents/agent.py` passes
- `uv run mypy app/core/agents/agent.py` passes
- `uv run pyright app/core/agents/agent.py` passes

---

### Task 10: Create Agent Service
**File:** `app/core/agents/service.py` (create new)
**Action:** CREATE

Create the service layer that orchestrates agent execution:

Define `class AgentService`:
- `__init__(self) -> None` — gets logger

Define `async def chat(self, request: ChatCompletionRequest) -> ChatCompletionResponse`:
  - Extracts the last user message from `request.messages`
  - Logs `agent.chat_started` with message count
  - Calls `agent.run(user_prompt)` (import `agent` from `app.core.agents.agent`)
  - Constructs `ChatCompletionResponse` with:
    - `id`: generated UUID string (e.g., `f"chatcmpl-{uuid.uuid4().hex[:12]}"`)
    - `created`: `int(time.time())`
    - `model`: agent model name from settings
    - `choices`: single `ChatCompletionChoice` with assistant message containing `result.output`
    - `usage`: `UsageInfo()` (zeroes for now — usage tracking added later)
  - Logs `agent.chat_completed` with response id
  - On exception: logs `agent.chat_failed` with `exc_info=True`, wraps in `AgentExecutionError`

Define `def get_agent_service() -> AgentService`:
  - Factory function for FastAPI dependency injection
  - Returns `AgentService()`

Follow structured logging pattern from `app/core/logging.py`:
- `logger.info("agent.chat_started", message_count=..., user_prompt_length=...)`
- `logger.info("agent.chat_completed", response_id=..., output_length=...)`
- `logger.error("agent.chat_failed", exc_info=True, error=str(e), error_type=type(e).__name__)`

**Per-task validation:**
- `uv run ruff format app/core/agents/service.py`
- `uv run ruff check app/core/agents/service.py` passes
- `uv run mypy app/core/agents/service.py` passes

---

### Task 11: Create Agent Routes
**File:** `app/core/agents/routes.py` (create new)
**Action:** CREATE

Create FastAPI routes for the agent API:

```python
router = APIRouter(prefix="/v1", tags=["agent"])
```

1. `POST /v1/chat/completions` endpoint:
   - Request body: `ChatCompletionRequest`
   - Response model: `ChatCompletionResponse`
   - Depends on `AgentService` via `Depends(get_agent_service)`
   - Delegates entirely to `service.chat(request)`
   - No try/except (let global exception handler catch `AgentExecutionError`)

2. `GET /v1/models` endpoint:
   - Returns a dict with model info: `{"object": "list", "data": [{"id": model_string, "object": "model"}]}`
   - Reads model from `get_settings()`

Both endpoints have Google-style docstrings.
Follow the thin-route pattern from `app/core/health.py`.

**Per-task validation:**
- `uv run ruff format app/core/agents/routes.py`
- `uv run ruff check app/core/agents/routes.py` passes
- `uv run mypy app/core/agents/routes.py` passes

---

### Task 12: Register Agent Router in main.py
**File:** `app/main.py` (modify existing)
**Action:** UPDATE

Add these changes:

1. Import the agent router:
   ```python
   from app.core.agents.routes import router as agent_router
   ```

2. Import the agent exception handler setup:
   ```python
   from app.core.agents.exceptions import setup_agent_exception_handlers
   ```

3. After `setup_exception_handlers(app)`, add:
   ```python
   setup_agent_exception_handlers(app)
   ```

4. After `app.include_router(health_router)`, add:
   ```python
   app.include_router(agent_router)
   ```

**Per-task validation:**
- `uv run ruff format app/main.py`
- `uv run ruff check app/main.py` passes
- `uv run mypy app/main.py` passes

---

### Task 13: Create Agent Tests
**File:** `app/core/agents/tests/__init__.py` (create new)
**Action:** CREATE

Empty init file for the test package.

---

### Task 14: Create Agent Config Tests
**File:** `app/core/agents/tests/test_config.py` (create new)
**Action:** CREATE

Test the agent configuration:

**Test 1:** `test_build_model_string`
- Create settings with `LLM_PROVIDER=anthropic`, `LLM_MODEL=claude-sonnet-4-5`
- Assert `build_model_string(settings)` returns `"anthropic:claude-sonnet-4-5"`

**Test 2:** `test_get_agent_model_no_fallback`
- Patch settings with no fallback provider
- Assert returns a string (not FallbackModel)

**Test 3:** `test_get_agent_model_with_fallback`
- Patch settings with `LLM_FALLBACK_PROVIDER=ollama`, `LLM_FALLBACK_MODEL=llama3.1:70b`
- Assert returns a `FallbackModel` instance

Follow pattern from `app/core/tests/test_config.py` for env patching.

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_config.py`
- `uv run ruff check app/core/agents/tests/test_config.py` passes
- `uv run pytest app/core/agents/tests/test_config.py -v` — all tests pass

---

### Task 15: Create Agent Schema Tests
**File:** `app/core/agents/tests/test_schemas.py` (create new)
**Action:** CREATE

Test schema validation:

**Test 1:** `test_chat_message_creation`
- Create `ChatMessage(role="user", content="Hello")`
- Assert fields are correct

**Test 2:** `test_chat_completion_request_requires_messages`
- Assert `ChatCompletionRequest(messages=[])` raises `ValidationError` (min_length=1)

**Test 3:** `test_chat_completion_request_valid`
- Create valid request with one user message
- Assert model validates

**Test 4:** `test_chat_completion_response_structure`
- Create a full `ChatCompletionResponse` with all fields
- Assert all fields serialize correctly

Follow pattern from `app/shared/tests/test_schemas.py`.

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_schemas.py`
- `uv run ruff check app/core/agents/tests/test_schemas.py` passes
- `uv run pytest app/core/agents/tests/test_schemas.py -v` — all tests pass

---

### Task 16: Create Agent Service Tests
**File:** `app/core/agents/tests/test_service.py` (create new)
**Action:** CREATE

Test the agent service with TestModel:

**IMPORTANT:** At the top of the file, add:
```python
from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
```
This prevents accidental real LLM API calls during testing.

**Test 1:** `test_chat_success`
- Create an `AgentService`
- Override agent with `TestModel()`: `with agent.override(model=TestModel()):`
- Import `agent` from `app.core.agents.agent`
- Send a `ChatCompletionRequest` with one user message
- Assert response has `object == "chat.completion"`
- Assert response has one choice
- Assert choice message role is `"assistant"`
- Assert choice message content is not empty

**Test 2:** `test_chat_extracts_last_user_message`
- Send request with multiple messages (system + user + assistant + user)
- Override with `TestModel()`
- Assert response succeeds (agent receives the last user message)

**Test 3:** `test_chat_failure_raises_agent_execution_error`
- Override agent with a `FunctionModel` that raises an exception
- Assert `AgentExecutionError` is raised
- Pattern: use `FunctionModel` from `pydantic_ai.models.function`

All tests use `@pytest.mark.asyncio` decorator.
Patch logger to suppress output: `with patch("app.core.agents.service.logger"):`

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_service.py`
- `uv run ruff check app/core/agents/tests/test_service.py` passes
- `uv run pytest app/core/agents/tests/test_service.py -v` — all tests pass

---

### Task 17: Create Agent Route Tests
**File:** `app/core/agents/tests/test_routes.py` (create new)
**Action:** CREATE

Test the API endpoints using TestClient:

**IMPORTANT:** At the top of the file, add:
```python
from pydantic_ai import models
models.ALLOW_MODEL_REQUESTS = False
```

**Test 1:** `test_chat_completions_endpoint`
- Create `TestClient(app)` from `app.main`
- Override agent with `TestModel()`
- POST to `/v1/chat/completions` with valid JSON body:
  ```json
  {"messages": [{"role": "user", "content": "Hello"}]}
  ```
- Assert status 200
- Assert response JSON has `object`, `choices`, `model` keys

**Test 2:** `test_chat_completions_empty_messages`
- POST with `{"messages": []}`
- Assert status 422 (validation error — min_length=1)

**Test 3:** `test_models_endpoint`
- GET `/v1/models`
- Assert status 200
- Assert response has `object: "list"` and `data` array

**Test 4:** `test_chat_completions_returns_assistant_message`
- Override agent with `TestModel()`
- POST valid request
- Assert `choices[0].message.role == "assistant"`
- Assert `choices[0].finish_reason == "stop"`

Follow pattern from `app/tests/test_main.py` for TestClient usage.

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_routes.py`
- `uv run ruff check app/core/agents/tests/test_routes.py` passes
- `uv run pytest app/core/agents/tests/test_routes.py -v` — all tests pass

---

## Logging Events

- `agent.config.model_configured` — When agent model is configured (provider, model, has_fallback)
- `agent.create_completed` — When base agent instance is created
- `agent.chat_started` — When a chat request begins (message_count, user_prompt_length)
- `agent.chat_completed` — When a chat response is generated (response_id, output_length)
- `agent.chat_failed` — When agent execution fails (error, error_type, exc_info=True)
- `agent.error` — When agent exception handler catches an error

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tests/`
- Config — model string building, fallback detection
- Schemas — validation, serialization, edge cases
- Service — chat flow with TestModel, error handling
- Routes — endpoint responses, validation errors

### Integration Tests
None needed for this phase. The agent uses `TestModel` for all tests. Integration tests with real LLM providers will be added when provider configuration is complete.

### Edge Cases
- Empty messages list → 422 validation error
- Agent execution failure → 502 with AgentExecutionError
- Missing LLM config → uses safe defaults ("test:test-model")

## Acceptance Criteria

This feature is complete when:
- [ ] `pydantic-ai` is installed and importable
- [ ] Root `conftest.py` exists with shared fixtures
- [ ] `app/core/agents/` module exists with config, schemas, exceptions, agent, service, routes
- [ ] `POST /v1/chat/completions` accepts messages and returns OpenAI-compatible response
- [ ] `GET /v1/models` returns configured model info
- [ ] Agent uses TestModel in tests — no real LLM calls
- [ ] All type checkers pass (mypy + pyright) with zero errors
- [ ] All tests pass (existing + new)
- [ ] Structured logging follows `agent.{action}_{state}` pattern
- [ ] No type suppressions added (except documented `# type: ignore[call-arg]` for pydantic-settings)
- [ ] Agent router registered in `app/main.py`
- [ ] No regressions in existing 66 unit tests

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All tasks completed in order (Tasks 1-17)
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

## Final Validation (5-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: Syntax & Style**
```bash
uv run ruff format .
uv run ruff check .
```

**Level 2: Type Safety**
```bash
uv run mypy app/
uv run pyright app/
```

**Level 3: Unit Tests (feature-specific)**
```bash
uv run pytest app/core/agents/tests/ -v
```

**Level 4: Full Test Suite (unit)**
```bash
uv run pytest -v -m "not integration"
```

**Level 5: Server Validation (if Docker running)**
```bash
uv run uvicorn app.main:app --port 8123 &
sleep 2
curl -s http://localhost:8123/v1/models
curl -s -X POST http://localhost:8123/v1/chat/completions -H "Content-Type: application/json" -d '{"messages":[{"role":"user","content":"Hello"}]}'
kill %1
```

**Success definition:** Levels 1-4 exit code 0, all tests pass, zero errors or warnings. Level 5 optional.

## Dependencies

- **Shared utilities used:** `get_logger()` from `app.core.logging`, `get_settings()` from `app.core.config`, `ErrorResponse` from `app.shared.schemas`
- **Core modules used:** `app.core.config`, `app.core.logging`, `app.core.exceptions` (pattern reference)
- **New dependencies:** `pydantic-ai>=1.0.5` — install with `uv add pydantic-ai`
- **New env vars:** `LLM_PROVIDER`, `LLM_MODEL`, `LLM_FALLBACK_PROVIDER` (optional), `LLM_FALLBACK_MODEL` (optional)

## Notes

- **No streaming in this phase.** SSE streaming will be added in a follow-up plan. The current endpoint returns complete responses.
- **No tools in this phase.** The agent has no tools registered yet. Transit and Obsidian tools will be added incrementally.
- **TestModel default response** is `"success (no tool calls)"`. Tests should assert on structure, not exact content.
- **The `agent` module-level instance** in `agent.py` will be created at import time. This is intentional — it's the singleton the routes use. Tests override it with `agent.override(model=TestModel())`.
- **FallbackModel import:** `from pydantic_ai.models.fallback import FallbackModel`. Verify this import path exists in pydantic-ai v1.0.5+.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
