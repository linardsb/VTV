# Plan: Agent Architecture Assessment & Enhancement Roadmap

## Feature Metadata
**Feature Type**: Assessment + Enhancement Roadmap
**Estimated Complexity**: Low (assessment) → High (Obsidian tools, already planned)
**Primary Systems Affected**: `app/core/agents/`, `app/core/config.py`

## Feature Description

This plan documents the current state of the VTV Pydantic AI agent, confirms its capabilities, explains how Pydantic AI works under the hood, and provides a terminal testing guide. The agent is already functional with 5 transit tools and an OpenAI-compatible chat endpoint. The next major milestone is adding 4 Obsidian vault tools (already planned in `.agents/plans/obsidian-vault-tools.md`).

The VTV agent is a unified AI assistant built on [Pydantic AI](https://ai.pydantic.dev/) that helps Riga's transit dispatchers query real-time bus data and (soon) manage an Obsidian knowledge vault. It exposes an OpenAI-compatible `/v1/chat/completions` endpoint that the CMS frontend's chat sidebar consumes.

## Current Agent Architecture

### What's Built (All Functional)

```
app/core/agents/                    # Agent feature slice
├── agent.py          (64 lines)    # Agent[TransitDeps, str] factory + singleton
├── service.py        (136 lines)   # AgentService: chat orchestration + singleton
├── routes.py         (77 lines)    # POST /v1/chat/completions, GET /v1/models
├── schemas.py        (104 lines)   # OpenAI-compatible request/response models
├── config.py         (69 lines)    # LLM provider resolution (TestModel/FallbackModel/string)
├── exceptions.py     (92 lines)    # AgentError hierarchy → HTTP status mapping
├── quota.py          (102 lines)   # Per-IP daily query quota (50/day, in-memory)
├── tools/
│   ├── transit/                    # 5 transit tools (ALL COMPLETE)
│   │   ├── deps.py                # TransitDeps dataclass (httpx.AsyncClient + Settings)
│   │   ├── client.py   (367 lines) # GTFS-RT protobuf client with 20s cache
│   │   ├── static_cache.py (429)   # Static GTFS ZIP parser (24h TTL)
│   │   ├── schemas.py  (489 lines) # 20+ Pydantic response models
│   │   ├── query_bus_status.py     # Tool 1: bus status/overview/departures (3 actions)
│   │   ├── get_route_schedule.py   # Tool 2: timetable by route/date/direction
│   │   ├── search_stops.py         # Tool 3: search by name or proximity
│   │   ├── get_adherence_report.py # Tool 4: on-time performance metrics
│   │   ├── check_driver_availability.py # Tool 5: driver staffing queries
│   │   ├── driver_data.py          # Mock driver data (Phase 2: CMS API)
│   │   └── tests/                  # 104 unit tests (ALL PASSING)
│   └── obsidian/                   # NOT YET CREATED (4 tools planned)
└── tests/                          # 22 agent-level tests (ALL PASSING)
```

**Total test count: 126 agent tests + 9 transit REST tests = 135 tests**

### How the Agent Works (Data Flow)

```
HTTP Request → POST /v1/chat/completions
    │
    ├── Rate limiting: 10 requests/min per IP (slowapi)
    ├── Quota check: 50 queries/day per IP (QueryQuotaTracker)
    │
    ▼
routes.py → AgentService.chat(request)
    │
    ├── Extracts last user message from request.messages
    │
    ▼
agent.run(user_prompt, deps=TransitDeps)
    │
    ├── Pydantic AI selects tool(s) based on agent-optimized docstrings
    ├── Tool receives RunContext[TransitDeps] with:
    │   ├── ctx.deps.http_client (connection-pooled httpx.AsyncClient)
    │   └── ctx.deps.settings (feed URLs, cache TTL, etc.)
    │
    ├── Tool fetches data:
    │   ├── GTFS-RT feeds (vehicle positions, trip updates, alerts) — 20s cache
    │   └── GTFS static ZIP (routes, stops, trips, calendar) — 24h cache
    │
    ├── Tool returns JSON string (not exception) — even errors are strings
    │
    ▼
ChatCompletionResponse (OpenAI-compatible format)
    ├── id: "chatcmpl-{uuid}"
    ├── model: "anthropic:claude-sonnet-4-5"
    ├── choices: [{message: {role: "assistant", content: "..."}}]
    └── usage: {prompt_tokens: 0, completion_tokens: 0}  # Not yet implemented
```

### Key Design Decisions Already Made

1. **Single agent, all tools** — PRD says "one agent, all tools". No routing logic.
2. **`Agent[TransitDeps, str]`** — deps inject shared httpx client; output is always string.
3. **Tools return strings, not raise exceptions** — errors are descriptive text for the LLM.
4. **Module-level singleton** — `agent.py` line 64 creates the agent at import time; `service.py` manages the `AgentService` singleton with connection pooling.
5. **LLM provider is swappable** — `config.py` resolves `"provider:model"` string, `TestModel()`, or `FallbackModel(primary, fallback)` from env vars. Zero code changes to switch providers.
6. **OpenAI-compatible API** — CMS frontend (and any OpenAI SDK client) can talk to the agent.

## How Pydantic AI Works (Research Summary)

### Core Concepts

**Agent creation** ([ai.pydantic.dev/agent](https://ai.pydantic.dev/agent/)):
```python
from pydantic_ai import Agent

agent = Agent(
    'anthropic:claude-sonnet-4-5',  # or Model instance, or FallbackModel
    deps_type=MyDeps,               # Type-safe dependency injection
    output_type=str,                 # Agent's return type (str, BaseModel, etc.)
    system_prompt="You are...",      # System instructions
    tools=[tool1, tool2, ...],       # Registered tool functions
)
```

**Dependency injection** ([ai.pydantic.dev/dependencies](https://ai.pydantic.dev/dependencies/)):
```python
from dataclasses import dataclass
from pydantic_ai import RunContext

@dataclass
class MyDeps:
    http_client: httpx.AsyncClient
    settings: Settings

@agent.tool
async def my_tool(ctx: RunContext[MyDeps], param: str) -> str:
    client = ctx.deps.http_client  # Type-safe access
    return "result"

# At call time:
result = await agent.run("query", deps=MyDeps(...))
```

**Testing** ([ai.pydantic.dev/testing](https://ai.pydantic.dev/testing/)):
```python
from pydantic_ai.models.test import TestModel

# Option 1: Override at run time
with agent.override(model=TestModel()):
    result = await agent.run("test prompt", deps=mock_deps)

# Option 2: Create agent with TestModel
test_agent = create_agent(model=TestModel())
```

**FallbackModel** ([ai.pydantic.dev/models/overview](https://ai.pydantic.dev/models/overview/)):
```python
from pydantic_ai.models.fallback import FallbackModel

# Tries Anthropic first; if it fails, falls back to Ollama
model = FallbackModel(
    'anthropic:claude-sonnet-4-5',
    'ollama:llama3.1:70b'
)
agent = Agent(model, ...)
```

### VTV's Current Pydantic AI Usage

| Concept | VTV Implementation | File |
|---------|-------------------|------|
| Agent creation | `Agent(model, deps_type=TransitDeps, output_type=str, tools=[...])` | `agent.py:47-59` |
| Deps injection | `TransitDeps(http_client, settings)` via `RunContext[TransitDeps]` | `deps.py:14-25` |
| Tool registration | 5 functions passed as `tools=[...]` list | `agent.py:52-58` |
| Model resolution | `get_agent_model()` returns string, TestModel, or FallbackModel | `config.py:29-68` |
| Chat execution | `agent.run(user_prompt, deps=self._deps)` | `service.py:64` |
| Testing | `agent.override(model=TestModel())` context manager | Test files |
| Error handling | Tools return error strings; exceptions → HTTP status in `exceptions.py` | Multiple |

### What VTV Does Correctly

- **Type-safe deps**: `RunContext[TransitDeps]` gives tools typed access to `ctx.deps.http_client` and `ctx.deps.settings`.
- **Agent-optimized docstrings**: Each tool has WHEN TO USE / WHEN NOT TO USE / ACTIONS / EFFICIENCY / COMPOSITION sections that guide LLM tool selection.
- **Graceful errors**: Tools never raise — they return descriptive strings that the LLM can relay to the user.
- **Connection pooling**: Single `httpx.AsyncClient` shared across all tool invocations via deps.
- **TestModel for CI**: Tests use `TestModel()` (no real LLM calls needed).

## Testing the Agent in Terminal

### 1. Quick health check (no LLM needed)
```bash
curl -s http://localhost:8123/health | python3 -m json.tool
# Expected: {"status": "healthy", "service": "api"}
```

### 2. List available models
```bash
curl -s http://localhost:8123/v1/models | python3 -m json.tool
# Expected: {"object": "list", "data": [{"id": "anthropic:claude-sonnet-4-5", ...}]}
```

### 3. Chat with the agent (requires valid LLM API key in .env)
```bash
curl -s -X POST http://localhost:8123/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Which bus routes are currently delayed in Riga?"}
    ]
  }' | python3 -m json.tool
```

**Expected response structure:**
```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "model": "anthropic:claude-sonnet-4-5",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "I checked the real-time data for Riga's bus network..."
      },
      "finish_reason": "stop"
    }
  ]
}
```

### 4. Test with TestModel (no API key needed)

Set `LLM_PROVIDER=test` and `LLM_MODEL=test-model` in `.env`, then restart the server:
```bash
# Update .env temporarily
sed -i '' 's/LLM_PROVIDER=anthropic/LLM_PROVIDER=test/' .env
sed -i '' 's/LLM_MODEL=claude-sonnet-4-5/LLM_MODEL=test-model/' .env

# Restart server
uv run uvicorn app.main:app --reload --port 8123

# Send test request
curl -s -X POST http://localhost:8123/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello"}]}' | python3 -m json.tool

# Restore .env
sed -i '' 's/LLM_PROVIDER=test/LLM_PROVIDER=anthropic/' .env
sed -i '' 's/LLM_MODEL=test-model/LLM_MODEL=claude-sonnet-4-5/' .env
```

### 5. Run the test suite
```bash
# All agent tests (126 tests)
uv run pytest app/core/agents/ -v -m "not integration"

# Just transit tool tests (104 tests)
uv run pytest app/core/agents/tools/transit/tests/ -v

# Full project test suite
uv run pytest -v -m "not integration"
```

### 6. Using Python REPL for interactive testing
```bash
uv run python -c "
import asyncio
from pydantic_ai.models.test import TestModel
from app.core.agents.agent import create_agent
from app.core.agents.tools.transit.deps import create_transit_deps

async def main():
    agent = create_agent(model=TestModel())
    deps = create_transit_deps()
    result = await agent.run('What routes are delayed?', deps=deps)
    print(f'Agent response: {result.output}')
    await deps.http_client.aclose()

asyncio.run(main())
"
```

## Current LLM Configuration

**File:** `app/core/config.py` (lines 44-48)

| Setting | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `test` | Provider name (anthropic, ollama, openai, test) |
| `LLM_MODEL` | `test-model` | Model name within provider |
| `LLM_FALLBACK_PROVIDER` | `None` | Optional fallback provider |
| `LLM_FALLBACK_MODEL` | `None` | Optional fallback model |

**To use Claude (real LLM):**
```bash
# In .env:
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5
# Requires ANTHROPIC_API_KEY env var (read by pydantic-ai automatically)
```

**To use local Ollama:**
```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b
```

**To use hybrid (local + cloud fallback):**
```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:70b
LLM_FALLBACK_PROVIDER=anthropic
LLM_FALLBACK_MODEL=claude-sonnet-4-5
```

## Transit Tools Summary (5/5 Complete)

| # | Tool | Actions | Data Source | Tests |
|---|------|---------|-------------|-------|
| 1 | `query_bus_status` | status, route_overview, stop_departures | GTFS-RT feeds | 12 |
| 2 | `get_route_schedule` | timetable by route/date/direction/time | GTFS static ZIP | 15 |
| 3 | `search_stops` | search by name, nearby by lat/lon | GTFS static ZIP | 14 |
| 4 | `get_adherence_report` | on-time metrics per route or network | GTFS-RT + static | 17 |
| 5 | `check_driver_availability` | drivers by shift/date/route | Mock provider | 12 |

All tools follow the same pattern: validate params → fetch data → build response model → serialize to JSON string → return. Errors are returned as descriptive strings, not raised.

## Next Steps: Obsidian Vault Tools

A complete 17-task implementation plan already exists at:
**`.agents/plans/obsidian-vault-tools.md`** (1066 lines)

### What It Adds

4 new tools bringing the total from 5 to 9:
- `obsidian_query_vault` — Search and discover vault content (5 actions)
- `obsidian_manage_notes` — Individual note CRUD (5 actions)
- `obsidian_manage_folders` — Folder operations (4 actions)
- `obsidian_bulk_operations` — Batch operations with dry_run (5 actions)

### Key Architecture Change

The deps type migrates from `TransitDeps` to `UnifiedDeps`:
```python
# Before (current):
@dataclass
class TransitDeps:
    http_client: httpx.AsyncClient
    settings: Settings

# After (planned):
@dataclass
class UnifiedDeps:
    transit_http_client: httpx.AsyncClient
    obsidian_http_client: httpx.AsyncClient  # SSL verify=False for self-signed cert
    settings: Settings

# Backwards compatibility alias:
TransitDeps = UnifiedDeps  # Existing imports still work
```

### Prerequisites Before Executing the Obsidian Plan

1. **Obsidian desktop app** must be installed with the [Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api) enabled
2. **Copy the API key** from Obsidian plugin settings to `.env`:
   ```bash
   OBSIDIAN_API_KEY=your-bearer-token-here
   OBSIDIAN_VAULT_URL=https://127.0.0.1:27124
   ```
3. **Or proceed without Obsidian** — the plan includes graceful error handling when vault is not configured (`obsidian_api_key=None` returns helpful error strings)

### To Execute

```bash
# From Claude Code:
/be-execute .agents/plans/obsidian-vault-tools.md
```

## Answers to Your Questions

### "Is the agent in a good initial spot and directory in core?"
**Yes.** The agent lives at `app/core/agents/` following VTV's vertical slice architecture. It has a clean separation: `agent.py` (creation), `service.py` (orchestration), `routes.py` (HTTP), `config.py` (LLM settings), `deps.py` (dependency injection), `schemas.py` (OpenAI-compatible types). This is exactly where the PRD and CLAUDE.md say it should be.

### "It has agents/tools/transit already where the agent can gather information on live traffic?"
**Correct.** 5 transit tools in `app/core/agents/tools/transit/` query live GTFS-RT data from Rigas Satiksme (vehicle positions, trip updates, alerts) and static GTFS data (routes, stops, trips, schedules). All 104 transit tool tests pass.

### "Does the Agent have a basic chat capability?"
**Yes.** `POST /v1/chat/completions` accepts OpenAI-format messages and returns OpenAI-format responses. It's rate-limited (10/min), quota-tracked (50/day), and handles errors gracefully. See the "Testing the Agent in Terminal" section above for curl examples.

### "How to test in terminal?"
See the comprehensive testing section above. Quick version:
```bash
# Health check:
curl -s http://localhost:8123/health

# Chat (requires LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY):
curl -s -X POST http://localhost:8123/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Which routes are delayed?"}]}' | python3 -m json.tool

# Run tests (no API key needed):
uv run pytest app/core/agents/ -v -m "not integration"
```

## Relevant Files

### Core Agent Files
- `app/core/agents/agent.py` — Agent factory + singleton (64 lines)
- `app/core/agents/service.py` — Chat orchestration + response building (136 lines)
- `app/core/agents/routes.py` — HTTP endpoints with rate limiting (77 lines)
- `app/core/agents/schemas.py` — OpenAI-compatible types (104 lines)
- `app/core/agents/config.py` — LLM provider resolution (69 lines)
- `app/core/agents/exceptions.py` — Error hierarchy (92 lines)
- `app/core/agents/quota.py` — Daily quota tracker (102 lines)

### Transit Tool Files
- `app/core/agents/tools/transit/deps.py` — TransitDeps dataclass (43 lines)
- `app/core/agents/tools/transit/client.py` — GTFS-RT protobuf client (367 lines)
- `app/core/agents/tools/transit/static_cache.py` — Static GTFS ZIP parser (429 lines)
- `app/core/agents/tools/transit/schemas.py` — 20+ Pydantic response models (489 lines)
- `app/core/agents/tools/transit/query_bus_status.py` — Tool 1 (462 lines)
- `app/core/agents/tools/transit/search_stops.py` — Tool 3 (326 lines)

### Configuration
- `app/core/config.py` — Settings class with LLM and GTFS config (84 lines)
- `.env.example` — All env vars with defaults (43 lines)

### Existing Plans
- `.agents/plans/obsidian-vault-tools.md` — 17-task plan for 4 vault tools (1066 lines)

## Research Documentation

- [Pydantic AI - Agent docs](https://ai.pydantic.dev/agent/) — Agent creation, system prompts, tool registration
- [Pydantic AI - Dependencies](https://ai.pydantic.dev/dependencies/) — deps_type, RunContext injection
- [Pydantic AI - Tools](https://ai.pydantic.dev/tools/) — Tool function signatures, validation
- [Pydantic AI - Models Overview](https://ai.pydantic.dev/models/overview/) — FallbackModel, provider switching
- [Pydantic AI - Testing](https://ai.pydantic.dev/testing/) — TestModel, FunctionModel, agent.override
- [Pydantic AI - Multi-Agent](https://ai.pydantic.dev/multi-agent-applications/) — Agent delegation patterns
- [Pydantic AI API - Agent](https://ai.pydantic.dev/api/agent/) — Full Agent class reference
- [Obsidian Local REST API](https://github.com/coddingtonbear/obsidian-local-rest-api) — Vault tool backend

## Acceptance Criteria

This assessment is complete when:
- [x] Agent architecture documented with file paths and line counts
- [x] Pydantic AI patterns explained with VTV-specific examples
- [x] Terminal testing guide with curl commands provided
- [x] Transit tools confirmed as functional (5/5 complete, 104 tests)
- [x] Chat capability confirmed (POST /v1/chat/completions)
- [x] LLM provider switching explained (env var config)
- [x] Next steps identified (Obsidian vault tools plan exists)
- [x] All relevant files catalogued

## Notes

- The agent currently passes only the **last user message** to the LLM (not full conversation history). This is intentional for the MVP — multi-turn context can be added later by passing `message_history` to `agent.run()`.
- Token usage in responses is always `{0, 0, 0}` — Pydantic AI tracks usage internally via `result.usage()` but VTV doesn't surface it yet.
- The agent's system prompt mentions "knowledge management" but vault tools aren't implemented yet. The LLM will correctly say "I don't have vault tools" if asked.
- The API server must be running (`uv run uvicorn app.main:app --reload --port 8123`) for curl tests to work. The health endpoint confirms it's up.
