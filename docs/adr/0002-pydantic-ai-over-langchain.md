# ADR-0002: Pydantic AI over LangChain

## Status

Accepted

## Context

VTV's AI agent needs to orchestrate 11 tools (transit queries, Obsidian vault operations, knowledge base search, skills management) with:

- Strict type safety (mypy + pyright in strict mode)
- Structured dependency injection (database sessions, Redis clients, API keys)
- Multi-model routing (fast models for simple queries, capable models for complex reasoning)
- Minimal abstraction overhead - tool functions should be plain async Python, not framework-specific classes

We evaluated three frameworks: LangChain, LlamaIndex, and Pydantic AI.

**LangChain** was rejected because:
- Heavy abstraction layer: tools must be `BaseTool` subclasses with `_run()` / `_arun()` methods
- Callback-based architecture adds complexity without benefit for our use case
- Type inference is weak - `Any` proliferates through the chain, breaking strict mypy
- Large dependency tree pulls in packages we don't need

**LlamaIndex** was rejected because:
- Optimized for RAG pipelines, not general-purpose tool orchestration
- Agent abstractions are less mature than its retrieval primitives
- Would require maintaining two frameworks (LlamaIndex for RAG + something else for non-RAG tools)

## Decision

We use **Pydantic AI** (`pydantic-ai>=1.58.0`) as the agent framework. The agent is defined as `Agent[UnifiedDeps, str]` in `app/core/agents/agent.py`, where:

- `UnifiedDeps` is a typed dataclass carrying all dependencies (db session, Redis, settings, API clients)
- Tools are plain `async def` functions decorated with `@agent.tool()` - no base classes, no callbacks
- Structured output uses Pydantic models or `TypedDict` for type-safe responses
- Multi-model routing is built-in via `Agent(model=...)` with tier-based selection

## Consequences

**Easier:**
- Tool functions are plain Python - test with standard pytest, no framework mocking needed
- Full type inference: `Agent[DepsType, ReturnType]` generics propagate through the entire call chain
- Dependency injection is explicit: `ctx.deps.settings`, `ctx.deps.db` - no global state
- Adding a new tool is one function + one import in `agent.py`

**Harder:**
- Pydantic AI has a smaller ecosystem than LangChain (fewer pre-built integrations)
- Contributors familiar with LangChain need to learn a different (simpler) API
- Some advanced patterns (multi-agent handoff, streaming tool calls) require manual implementation
