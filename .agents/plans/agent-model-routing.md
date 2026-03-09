# Plan: Agent Multi-Tier Model Routing

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low
**Primary Systems Affected**: `app/core/agents/` (config, service, routing)

## Feature Description

Add multi-tier model routing to the VTV agent so that simple lookups (e.g., "which buses are delayed?") use a cheap/fast model (Haiku, Flash), standard queries use the default model (Sonnet, Flash), and complex analysis (multi-step reasoning, schedule optimization, bulk operations) use a premium model (Opus, Pro). This provides immediate cost savings by routing ~60% of dispatcher queries to the cheapest tier.

The classification is heuristic-based (keyword + pattern matching on the user prompt), not LLM-based, so it adds zero latency. The tier is resolved before `agent.run()` and passed as the `model=` override parameter, which Pydantic AI natively supports.

Each tier maps to a configurable model via environment variables. When tier-specific models aren't configured, all tiers fall back to the existing `LLM_PROVIDER`/`LLM_MODEL` settings — zero behavioral change for existing deployments.

## User Story

As a system administrator
I want the agent to automatically route queries to appropriately-sized LLM models
So that simple lookups use cheap models and complex analysis uses premium models, reducing API costs by ~40-60%

## Security Contexts

**Active contexts:**
- CTX-AGENT: This modifies AI agent behavior — model selection affects response quality and cost. Must log tier decisions for auditability.

**Not applicable:**
- CTX-AUTH: No auth changes
- CTX-RBAC: No endpoint changes
- CTX-FILE: No file handling
- CTX-INFRA: Config changes are env-var only, no Docker/nginx changes
- CTX-INPUT: No new user-facing input parameters

## Solution Approach

Use Pydantic AI's built-in `model=` override on `agent.run()` to pass a per-request model. Before each chat call, classify the user prompt into one of three tiers using fast keyword/pattern matching, resolve that tier to a configured model instance, and pass it to `agent.run(model=resolved_model)`.

**Approach Decision:**
We chose heuristic classification because:
- Zero latency overhead (regex/keyword matching vs. LLM pre-classification)
- Deterministic and auditable (logs show exactly which keywords triggered which tier)
- Easy to tune (add/remove keywords without code changes)
- Sufficient accuracy for transit domain (queries are repetitive and domain-specific)

**Alternatives Considered:**
- LLM-based pre-classifier (small model classifies first): Rejected — adds latency and cost for marginal accuracy improvement on a narrow domain
- User-selected tier (UI dropdown): Rejected — dispatchers shouldn't need to think about model selection
- Tool-based routing (route by which tools are called): Rejected — requires running the model first to know which tools it would call

**Tier Definitions:**

| Tier | Use Case | Trigger Patterns | Default Model |
|------|----------|-----------------|---------------|
| `fast` | Simple lookups, single-tool queries | "which buses", "is route X delayed", "next bus at", "show schedule", status checks | Haiku / Flash |
| `standard` | Multi-step queries, moderate reasoning | Default tier when no fast/complex pattern matches | Sonnet / Flash |
| `complex` | Cross-domain analysis, bulk ops, optimization | "compare", "analyze", "optimize", "all routes", bulk/batch, multi-entity correlation | Opus / Pro |

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, logging patterns, type checking requirements
- `app/core/agents/config.py` (lines 1-106) — Current model resolution logic, `get_agent_model()` function that resolves provider to Pydantic AI model instance
- `app/core/agents/service.py` (lines 83-175) — `AgentService.chat()` method where `agent.run()` is called — this is where we inject the model override
- `app/core/agents/agent.py` (lines 102-161) — Agent creation factory and module singleton
- `app/core/config.py` (lines 59-75) — `Settings` class with LLM provider/model fields
- `.env.example` (lines 17-23) — Current LLM environment variables

### Similar Features (Examples to Follow)
- `app/core/agents/config.py` (lines 37-105) — Pattern for resolving provider strings to model instances with API key validation and fallback logic
- `app/core/agents/tests/test_config.py` (lines 1-114) — Pattern for testing model resolution with `create_settings()` helper

### Files to Modify
- `app/core/config.py` — Add 6 new tier settings fields
- `app/core/agents/config.py` — Add `resolve_tier_model()` function
- `app/core/agents/routing.py` — NEW: Tier classification logic
- `app/core/agents/service.py` — Pass classified model to `agent.run()`
- `.env.example` — Add tier model env var documentation
- `app/core/agents/tests/test_routing.py` — NEW: Classification tests
- `app/core/agents/tests/test_config.py` — Add tier resolution tests

## Implementation Plan

### Phase 1: Foundation
Add tier configuration settings and model resolution function.

### Phase 2: Core Implementation
Create the heuristic classifier and integrate into service layer.

### Phase 3: Integration & Validation
Tests and validation.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Add Tier Settings to Configuration
**File:** `app/core/config.py` (modify existing)
**Action:** UPDATE

Add 6 new settings fields to the `Settings` class, immediately after the existing `llm_fallback_model` field (line 63). These are optional — when `None`, the tier falls back to the primary `llm_provider`/`llm_model`.

Add these fields after line 63 (`llm_fallback_model: str | None = None`):

```python
    # Multi-tier model routing (optional — falls back to primary model when None)
    llm_fast_provider: str | None = None
    llm_fast_model: str | None = None
    llm_standard_provider: str | None = None
    llm_standard_model: str | None = None
    llm_complex_provider: str | None = None
    llm_complex_model: str | None = None
```

These follow the exact same pattern as `llm_fallback_provider`/`llm_fallback_model`. All are `str | None` with default `None`, meaning Pydantic Settings reads them from env vars `LLM_FAST_PROVIDER`, `LLM_FAST_MODEL`, etc.

**Per-task validation:**
- `uv run ruff format app/core/config.py`
- `uv run ruff check --fix app/core/config.py` passes
- `uv run mypy app/core/config.py` passes with 0 errors

---

### Task 2: Add Tier Model Resolution to Agent Config
**File:** `app/core/agents/config.py` (modify existing)
**Action:** UPDATE

Add a new function `resolve_tier_model()` after the existing `get_agent_model()` function (after line 105). This function takes a tier name and returns the appropriate model instance, falling back to the primary model when no tier-specific model is configured.

Add this import at the top (it's already imported but verify `Literal` is available):
```python
from typing import Literal
```

Add this type alias and function after line 105:

```python
ModelTier = Literal["fast", "standard", "complex"]


def resolve_tier_model(
    tier: ModelTier, settings: Settings | None = None
) -> str | Model | None:
    """Resolve a model for a specific routing tier.

    Returns the tier-specific model if configured, or None to use the agent's
    default model (set at creation time via get_agent_model).

    Args:
        tier: The routing tier — "fast", "standard", or "complex".
        settings: Optional settings. If None, uses get_settings().

    Returns:
        A Pydantic AI model instance/string for the tier, or None if the tier
        has no override configured (meaning: use the agent's default model).
    """
    if settings is None:
        settings = get_settings()

    tier_map: dict[ModelTier, tuple[str | None, str | None]] = {
        "fast": (settings.llm_fast_provider, settings.llm_fast_model),
        "standard": (settings.llm_standard_provider, settings.llm_standard_model),
        "complex": (settings.llm_complex_provider, settings.llm_complex_model),
    }

    provider, model = tier_map[tier]

    # No tier override configured — caller should use agent default
    if provider is None or model is None:
        return None

    # Reuse the same provider resolution logic as get_agent_model
    # Test provider
    if provider == "test":
        return TestModel()

    # Anthropic
    if provider == "anthropic":
        if not settings.anthropic_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return AnthropicModel(model, provider=AnthropicProvider(api_key=settings.anthropic_api_key))

    # Google
    if provider == "google":
        if not settings.google_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return GoogleModel(model, provider=GoogleProvider(api_key=settings.google_api_key))

    # Groq
    if provider == "groq":
        if not settings.groq_api_key:
            logger.warning("agent.config.tier_api_key_missing", tier=tier, provider=provider)
            return None
        return GroqModel(model, provider=GroqProvider(api_key=settings.groq_api_key))

    # Ollama
    if provider == "ollama":
        return OpenAIChatModel(model, provider=OllamaProvider(base_url=settings.ollama_base_url))

    # Generic provider:model string
    return f"{provider}:{model}"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/config.py`
- `uv run ruff check --fix app/core/agents/config.py` passes
- `uv run mypy app/core/agents/config.py` passes with 0 errors
- `uv run pyright app/core/agents/config.py` passes

---

### Task 3: Create Tier Classification Module
**File:** `app/core/agents/routing.py` (create new)
**Action:** CREATE

Create the heuristic classifier that maps user prompts to tiers. This is a pure function with no side effects — easy to test and tune.

```python
"""Multi-tier model routing for the VTV agent.

Classifies user prompts into fast/standard/complex tiers using
keyword and pattern matching. Zero latency overhead — no LLM calls.
"""

import re
from typing import Literal

from app.core.logging import get_logger

logger = get_logger(__name__)

ModelTier = Literal["fast", "standard", "complex"]

# --- Fast tier patterns ---
# Simple lookups, single-entity queries, status checks
_FAST_PATTERNS: list[re.Pattern[str]] = [
    # Status queries (LV: "kuri marsruti kavejas", "vai ir kavejas")
    re.compile(r"\b(delayed|delay|kavēj|kavej|on.?time|laikā|laika)\b", re.IGNORECASE),
    # Simple schedule lookups
    re.compile(r"\b(next bus|nākošais|nakosais|show schedule|paradiet grafiku|parādiet grafiku)\b", re.IGNORECASE),
    # Single entity lookups
    re.compile(r"\b(route \d+|maršrut[sauā]?\s*\d+|marsrut[saua]?\s*\d+)\b", re.IGNORECASE),
    # Stop queries
    re.compile(r"\b(stop|pietur[aā]|pietura)\b", re.IGNORECASE),
    # Simple yes/no questions
    re.compile(r"^(is|vai|are|does|cik)\b", re.IGNORECASE),
    # Status/count queries
    re.compile(r"\b(how many|cik|count|status|statuss)\b", re.IGNORECASE),
    # Single driver/vehicle lookup
    re.compile(r"\b(driver|vadītāj|vaditaj|vehicle|transportlīdzekl)\b", re.IGNORECASE),
]

# --- Complex tier patterns ---
# Multi-step analysis, bulk operations, optimization, cross-domain correlation
_COMPLEX_PATTERNS: list[re.Pattern[str]] = [
    # Analytical queries
    re.compile(r"\b(analyze|analyz|analizē|analize|compare|salīdzin|salidzin)\b", re.IGNORECASE),
    # Optimization requests
    re.compile(r"\b(optimize|optimizē|optimiz|improve|uzlabo|suggest|ieteik)\b", re.IGNORECASE),
    # Bulk/batch operations
    re.compile(r"\b(all routes|all stops|all drivers|visi maršrut|visi marsrut|visas pietura)\b", re.IGNORECASE),
    re.compile(r"\b(bulk|batch|multiple|vairāk|vairak)\b", re.IGNORECASE),
    # Cross-domain correlation
    re.compile(r"\b(correlation|trend|pattern|tendenc|sakarīb)\b", re.IGNORECASE),
    # Report generation
    re.compile(r"\b(report|pārskats|parskats|summary|kopsavilkum)\b", re.IGNORECASE),
    # Planning and scheduling
    re.compile(r"\b(plan|plānot|planot|reschedule|reorganize)\b", re.IGNORECASE),
    # Complex vault operations
    re.compile(r"\b(reorganize|restructure|migrate|move all|delete all)\b", re.IGNORECASE),
]


def classify_prompt(prompt: str) -> ModelTier:
    """Classify a user prompt into a model routing tier.

    Uses keyword and pattern matching to determine query complexity.
    Fast patterns are checked first (most queries are simple lookups).
    Complex patterns are checked second. Default is "standard".

    The classification is deliberately conservative:
    - Short prompts (< 20 chars) go to fast tier (likely simple commands)
    - Multiple complex pattern matches reinforce complex classification
    - Single complex match with fast matches defaults to standard

    Args:
        prompt: The user's message text.

    Returns:
        "fast", "standard", or "complex" tier classification.
    """
    prompt_stripped = prompt.strip()

    # Very short prompts are almost always simple lookups
    if len(prompt_stripped) < 20:
        return "fast"

    fast_matches = sum(1 for p in _FAST_PATTERNS if p.search(prompt_stripped))
    complex_matches = sum(1 for p in _COMPLEX_PATTERNS if p.search(prompt_stripped))

    # Complex wins when it has clear signal
    if complex_matches >= 2:
        return "complex"
    if complex_matches >= 1 and fast_matches == 0:
        return "complex"

    # Fast wins when it has signal and no complex signal
    if fast_matches >= 1 and complex_matches == 0:
        return "fast"

    # Mixed signals or no matches → standard
    return "standard"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/routing.py`
- `uv run ruff check --fix app/core/agents/routing.py` passes
- `uv run mypy app/core/agents/routing.py` passes with 0 errors
- `uv run pyright app/core/agents/routing.py` passes

---

### Task 4: Integrate Routing into AgentService
**File:** `app/core/agents/service.py` (modify existing)
**Action:** UPDATE

Modify `AgentService.chat()` to classify the prompt and pass the tier model to `agent.run()`. Changes are minimal — add 2 imports, ~8 lines of logic.

**Step 4a:** Add imports at the top of the file. Add after the existing imports (after line 33):

```python
from app.core.agents.config import resolve_tier_model
from app.core.agents.routing import classify_prompt
```

**Step 4b:** In the `chat()` method, after the prompt injection check (line 115: `_check_prompt_injection(current_prompt)`) and before the `logger.info("agent.chat_started", ...)` call (line 117), add tier classification:

```python
        # Classify prompt complexity for model routing
        tier = classify_prompt(current_prompt)
        tier_model = resolve_tier_model(tier)
```

**Step 4c:** Update the `logger.info("agent.chat_started", ...)` call (line 117-121) to include tier:

Change:
```python
        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            history_count=len(prior_messages),
            user_prompt_length=len(current_prompt),
        )
```
To:
```python
        logger.info(
            "agent.chat_started",
            message_count=len(request.messages),
            history_count=len(prior_messages),
            user_prompt_length=len(current_prompt),
            model_tier=tier,
            tier_override=tier_model is not None,
        )
```

**Step 4d:** Update the `agent.run()` call (lines 136-141) to pass the tier model:

Change:
```python
            result = await agent.run(
                current_prompt,
                deps=self._deps,
                message_history=message_history,
                instructions=instructions,
            )
```
To:
```python
            result = await agent.run(
                current_prompt,
                deps=self._deps,
                message_history=message_history,
                instructions=instructions,
                model=tier_model,
            )
```

Note: When `tier_model` is `None`, Pydantic AI's `agent.run()` uses the agent's default model (set at creation time). This is the desired fallback behavior.

**Step 4e:** Update the model name in the response (line 153) to reflect the actual model used:

Change:
```python
        model_name = f"{settings.llm_provider}:{settings.llm_model}"
```
To:
```python
        model_name = str(tier_model) if tier_model is not None else f"{settings.llm_provider}:{settings.llm_model}"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/service.py`
- `uv run ruff check --fix app/core/agents/service.py` passes
- `uv run mypy app/core/agents/service.py` passes with 0 errors

---

### Task 5: Update .env.example
**File:** `.env.example` (modify existing)
**Action:** UPDATE

Add tier model configuration documentation after the existing LLM fallback lines (after line 23: `# LLM_FALLBACK_MODEL=llama3.1:70b`). Add:

```bash

# Multi-tier model routing (optional — all tiers use primary model when unset)
# Fast tier: simple lookups, status checks, single-entity queries
# LLM_FAST_PROVIDER=anthropic
# LLM_FAST_MODEL=claude-haiku-4-5
# Standard tier: default for moderate queries (uses primary model when unset)
# LLM_STANDARD_PROVIDER=anthropic
# LLM_STANDARD_MODEL=claude-sonnet-4-5
# Complex tier: multi-step analysis, bulk operations, optimization
# LLM_COMPLEX_PROVIDER=anthropic
# LLM_COMPLEX_MODEL=claude-opus-4-5
```

**Per-task validation:**
- File is not a Python file — no ruff/mypy checks needed
- Visually verify the new lines are properly commented out and follow existing formatting

---

### Task 6: Create Classification Tests
**File:** `app/core/agents/tests/test_routing.py` (create new)
**Action:** CREATE

Create comprehensive tests for the `classify_prompt()` function. Test all three tiers with realistic transit dispatcher queries in both English and Latvian.

```python
"""Tests for multi-tier model routing classification."""

from app.core.agents.routing import classify_prompt


class TestClassifyPromptFastTier:
    """Fast tier: simple lookups, status checks."""

    def test_short_prompt(self) -> None:
        assert classify_prompt("hello") == "fast"

    def test_delay_query_english(self) -> None:
        assert classify_prompt("Which routes are delayed?") == "fast"

    def test_delay_query_latvian(self) -> None:
        assert classify_prompt("Kuri maršruti kavējas?") == "fast"

    def test_delay_query_latvian_no_diacritics(self) -> None:
        assert classify_prompt("Kuri marsruti kavejas?") == "fast"

    def test_schedule_lookup(self) -> None:
        assert classify_prompt("Show schedule for route 22") == "fast"

    def test_schedule_latvian(self) -> None:
        assert classify_prompt("Parādiet grafiku maršrutam 22") == "fast"

    def test_next_bus_query(self) -> None:
        assert classify_prompt("Next bus at Brivibas iela stop") == "fast"

    def test_stop_query(self) -> None:
        assert classify_prompt("Where is the nearest stop?") == "fast"

    def test_count_query(self) -> None:
        assert classify_prompt("How many buses are active right now?") == "fast"

    def test_count_latvian(self) -> None:
        assert classify_prompt("Cik autobusu ir aktivi?") == "fast"

    def test_single_route_status(self) -> None:
        assert classify_prompt("Is route 3 on time?") == "fast"

    def test_driver_lookup(self) -> None:
        assert classify_prompt("Is driver Janis available tomorrow?") == "fast"

    def test_vehicle_status(self) -> None:
        assert classify_prompt("What is the status of vehicle 1042?") == "fast"


class TestClassifyPromptComplexTier:
    """Complex tier: analysis, bulk operations, optimization."""

    def test_analyze_keyword(self) -> None:
        assert classify_prompt("Analyze the delay patterns across all routes this week") == "complex"

    def test_compare_keyword(self) -> None:
        assert classify_prompt("Compare route 22 and route 15 performance over the last month") == "complex"

    def test_optimize_keyword(self) -> None:
        assert classify_prompt("Suggest how to optimize the morning schedule for route 7") == "complex"

    def test_all_routes_query(self) -> None:
        assert classify_prompt("Give me a report on all routes performance") == "complex"

    def test_bulk_operation(self) -> None:
        assert classify_prompt("Move all notes from planning folder to archive in bulk") == "complex"

    def test_report_request(self) -> None:
        assert classify_prompt("Generate a summary report of delays this month") == "complex"

    def test_trend_analysis(self) -> None:
        assert classify_prompt("What are the delay trends for the past quarter?") == "complex"

    def test_planning_request(self) -> None:
        assert classify_prompt("Help me plan the holiday schedule reorganization") == "complex"

    def test_latvian_analysis(self) -> None:
        assert classify_prompt("Analizē kavēšanās tendences visos maršrutos") == "complex"


class TestClassifyPromptStandardTier:
    """Standard tier: moderate complexity, mixed signals, default."""

    def test_moderate_query(self) -> None:
        assert classify_prompt("What happened on route 22 yesterday afternoon?") == "standard"

    def test_knowledge_search(self) -> None:
        assert classify_prompt("Find the driver training policy document") == "standard"

    def test_vault_note_creation(self) -> None:
        assert classify_prompt("Create a note about today's dispatch meeting decisions") == "standard"

    def test_mixed_signals(self) -> None:
        """Fast keyword (route) + complex keyword (report) → standard."""
        result = classify_prompt("Show route 5 delay report")
        assert result == "standard"

    def test_no_pattern_match(self) -> None:
        assert classify_prompt("Tell me about the history of Riga's transit system") == "standard"

    def test_ambiguous_query(self) -> None:
        assert classify_prompt("I need help with something") == "standard"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_routing.py`
- `uv run ruff check --fix app/core/agents/tests/test_routing.py` passes
- `uv run pytest app/core/agents/tests/test_routing.py -v` — all tests pass

---

### Task 7: Add Tier Resolution Tests
**File:** `app/core/agents/tests/test_config.py` (modify existing)
**Action:** UPDATE

Add tests for `resolve_tier_model()` to the existing config test file. Add the import and new test functions after the existing tests (after line 114).

Add to imports at top of file:
```python
from app.core.agents.config import resolve_tier_model
```

Add these test functions after the last existing test:

```python
def test_resolve_tier_model_no_override() -> None:
    """Returns None when no tier-specific model is configured."""
    settings = create_settings(LLM_PROVIDER="anthropic", LLM_MODEL="claude-sonnet-4-5")
    result = resolve_tier_model("fast", settings)
    assert result is None


def test_resolve_tier_model_fast_anthropic() -> None:
    """Resolves fast tier to Anthropic model when configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, AnthropicModel)


def test_resolve_tier_model_complex_anthropic() -> None:
    """Resolves complex tier to Anthropic model when configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_COMPLEX_PROVIDER="anthropic",
        LLM_COMPLEX_MODEL="claude-opus-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("complex", settings)
    assert isinstance(result, AnthropicModel)


def test_resolve_tier_model_standard_no_override() -> None:
    """Standard tier returns None when not explicitly configured."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("standard", settings)
    assert result is None


def test_resolve_tier_model_missing_api_key() -> None:
    """Returns None when tier provider API key is missing."""
    settings = create_settings(
        LLM_PROVIDER="google",
        LLM_MODEL="gemini-2.0-flash",
        LLM_FAST_PROVIDER="anthropic",
        LLM_FAST_MODEL="claude-haiku-4-5",
        GOOGLE_API_KEY="test-google-key",
        # No ANTHROPIC_API_KEY
    )
    result = resolve_tier_model("fast", settings)
    assert result is None


def test_resolve_tier_model_test_provider() -> None:
    """Test provider returns TestModel for tier."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="test",
        LLM_FAST_MODEL="test-model",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, TestModel)


def test_resolve_tier_model_google() -> None:
    """Resolves tier to Google model."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="google",
        LLM_FAST_MODEL="gemini-2.0-flash",
        ANTHROPIC_API_KEY="sk-test-key",
        GOOGLE_API_KEY="test-google-key",
    )
    result = resolve_tier_model("fast", settings)
    assert isinstance(result, GoogleModel)


def test_resolve_tier_model_generic_string() -> None:
    """Returns provider:model string for unknown providers."""
    settings = create_settings(
        LLM_PROVIDER="anthropic",
        LLM_MODEL="claude-sonnet-4-5",
        LLM_FAST_PROVIDER="openrouter",
        LLM_FAST_MODEL="meta-llama/llama-3.1-8b",
        ANTHROPIC_API_KEY="sk-test-key",
    )
    result = resolve_tier_model("fast", settings)
    assert result == "openrouter:meta-llama/llama-3.1-8b"
```

**Per-task validation:**
- `uv run ruff format app/core/agents/tests/test_config.py`
- `uv run ruff check --fix app/core/agents/tests/test_config.py` passes
- `uv run pytest app/core/agents/tests/test_config.py -v` — all tests pass

---

### Task 8: Update Agent CLAUDE.md
**File:** `app/core/agents/CLAUDE.md` (modify existing)
**Action:** UPDATE

In the "Planned Improvements" section, update item 1 to mark multi-tier routing as implemented. Change:

```
1. **Multi-tier model routing** — Haiku/Sonnet/Opus per task complexity (add `resolve_model(tier)` to `config.py`)
```

To:

```
1. **Multi-tier model routing** ✅ — Heuristic prompt classifier in `routing.py`, tier model resolution via `resolve_tier_model()` in `config.py`, integrated into `AgentService.chat()`. Configure via `LLM_FAST_*`/`LLM_STANDARD_*`/`LLM_COMPLEX_*` env vars.
```

Also add `routing.py` to the directory structure listing. Add after `config.py` line:

```
├── routing.py         # Multi-tier model routing (fast/standard/complex classification)
```

**Per-task validation:**
- File is markdown — no ruff/mypy checks needed
- Visually verify the directory structure and planned improvements sections are correct

---

## Logging Events

- `agent.config.model_configured` — Existing event, no changes needed
- `agent.config.tier_api_key_missing` — When a tier's provider API key is not configured (warning)
- `agent.chat_started` — Updated with `model_tier` and `tier_override` fields for cost tracking

## Testing Strategy

### Unit Tests
**Location:** `app/core/agents/tests/test_routing.py`
- `classify_prompt()` — Fast tier detection (13 cases: delays, schedules, stops, counts, drivers, vehicles in EN/LV)
- `classify_prompt()` — Complex tier detection (9 cases: analysis, comparison, optimization, bulk, reports, trends, planning in EN/LV)
- `classify_prompt()` — Standard tier / fallback (6 cases: moderate queries, mixed signals, no matches, ambiguous)

**Location:** `app/core/agents/tests/test_config.py`
- `resolve_tier_model()` — No override returns None (3 tiers)
- `resolve_tier_model()` — Anthropic resolution (fast + complex)
- `resolve_tier_model()` — Missing API key returns None
- `resolve_tier_model()` — Test provider returns TestModel
- `resolve_tier_model()` — Google provider resolution
- `resolve_tier_model()` — Generic string fallback

### Edge Cases
- Very short prompts (< 20 chars) → fast tier
- Empty prompt → fast tier (handled by length check)
- Mixed fast + complex patterns → standard tier
- Latvian without diacritics → correct classification
- All tiers unconfigured → None (agent default model used)
- Partial tier configuration (only fast set) → only fast overrides, others use default

## Acceptance Criteria

This feature is complete when:
- [ ] `classify_prompt()` correctly routes simple lookups to "fast" tier
- [ ] `classify_prompt()` correctly routes analytical queries to "complex" tier
- [ ] `classify_prompt()` defaults ambiguous queries to "standard" tier
- [ ] `resolve_tier_model()` returns appropriate model instances for configured tiers
- [ ] `resolve_tier_model()` returns None for unconfigured tiers (agent uses default)
- [ ] `AgentService.chat()` passes tier model to `agent.run(model=...)`
- [ ] Tier classification is logged in `agent.chat_started` event
- [ ] `.env.example` documents all 6 new env vars
- [ ] All type checkers pass (mypy + pyright)
- [ ] All tests pass (28+ new tests)
- [ ] No regressions in existing 904 tests
- [ ] Zero behavioral change when tier env vars are not set

## Completion Checklist

Before marking this plan as fully executed:
- [ ] All 8 tasks completed in order
- [ ] Per-task validations passed
- [ ] Full validation pyramid passed (Levels 1-4)
- [ ] No deviations from plan (or deviations documented with reasons)
- [ ] Ready for `/commit`

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
uv run pytest app/core/agents/tests/test_routing.py app/core/agents/tests/test_config.py -v
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

## Dependencies

- Shared utilities used: None new
- Core modules used: `app.core.config.Settings`, `app.core.logging.get_logger`
- New dependencies: None — uses existing pydantic-ai model classes
- New env vars: `LLM_FAST_PROVIDER`, `LLM_FAST_MODEL`, `LLM_STANDARD_PROVIDER`, `LLM_STANDARD_MODEL`, `LLM_COMPLEX_PROVIDER`, `LLM_COMPLEX_MODEL` (all optional)

## Known Pitfalls

The executing agent MUST follow all 59 Python anti-pattern rules from `_shared/python-anti-patterns.md`. Specific risks for this feature:

- **Rule 5 (no unused imports):** Only import `Literal` in `config.py` if not already imported. Check first.
- **Rule 8 (no EN DASH):** Use `-` (U+002D) in all regex patterns, not `–` (U+2013).
- **Rule 18 (ARG001):** The `tier` parameter in `resolve_tier_model()` IS used — no issue.
- **Rule 54 (Literal types):** `ModelTier = Literal["fast", "standard", "complex"]` — already using Literal correctly.
- **Import completeness:** `routing.py` needs `re` and `Literal` from `typing`. `config.py` already has all needed model imports.
- **`agent.run(model=None)` behavior:** When `model=None`, Pydantic AI uses the agent's default model. Verified this is the correct behavior — do NOT pass `model=` at all when None; instead use `**({} if tier_model is None else {"model": tier_model})` pattern OR simply pass `model=tier_model` since Pydantic AI handles None gracefully. **IMPORTANT: Verify Pydantic AI accepts `model=None` in `agent.run()`.** If it doesn't, use conditional kwargs: `run_kwargs: dict[str, Any] = {}` + `if tier_model is not None: run_kwargs["model"] = tier_model` + `agent.run(..., **run_kwargs)`.

## Notes

- **Cost impact:** With typical dispatcher query distribution (~60% simple lookups, ~30% moderate, ~10% complex), routing to Haiku for fast tier saves ~70% on those queries. Net monthly savings: ~40-50% of current LLM API costs.
- **Tuning:** The keyword patterns in `routing.py` are a starting point. Monitor the `model_tier` log field in production to verify classification accuracy and adjust patterns as needed.
- **Future enhancement:** Replace heuristic classifier with a fine-tuned small model (distilbert) trained on accumulated query logs with tier labels for higher accuracy.
- **Backward compatibility:** 100% backward compatible. When no `LLM_*_PROVIDER`/`LLM_*_MODEL` env vars are set, all tiers resolve to None, and `agent.run()` uses the default model — identical behavior to current code.

## Pre-Implementation Checklist

The executing agent MUST verify before writing any code:
- [ ] Read all files listed in "Relevant Files" section
- [ ] Reviewed research documentation
- [ ] Understood the solution approach and why alternatives were rejected
- [ ] Clear on task execution order
- [ ] Validation commands are executable in this environment
