# Plan: AI-6.3 Agent Router (Heuristic Domain Auto-Selection)

## Context

After AI-6.1 (BaseAgentService harness) and AI-6.2 (TransitAgent / KnowledgeAgent / VaultAgent / UnifiedAgent with the `agent` selector field on `ChatCompletionRequest`), every chat request currently requires the **client** to pre-select a domain. The default is `"unified"`, which means most traffic still hits the unified agent and pays the price of all 11 tools loaded into context.

AI-6.3 adds a **server-side heuristic router** that scores the prompt against three keyword signal sets (transit / knowledge / vault) and picks a domain agent automatically when the request comes in as `agent="unified"`. Cross-domain queries, ties, or zero-score prompts fall back to the existing UnifiedAgent — preserving today's behavior. The router is keyword-based (zero LLM latency) like the existing `app/core/agents/routing.py` tier classifier.

A new config flag `agent_multi_agent_enabled` (default `False`) gates the behavior so rollout is safe: when `False`, `chat_completions` behaves exactly as today.

## Security Context Assessment

| Context | Active? | Reason |
|---|---|---|
| **CTX-AGENT** | ✅ | New module is part of the agent pipeline; touches LLM-facing routing |
| **CTX-RBAC** | ⚠ partial | No new endpoints. `POST /v1/chat/completions` already requires `get_current_user` (`routes.py:39`). Verify behavior unchanged |
| **CTX-INPUT** | ⚠ partial | Router consumes user prompt strings. Already validated by `ChatCompletionRequest` Pydantic schema (`max_length=4000`). No new input surface |
| CTX-AUTH | ❌ | No auth/session changes |
| CTX-FILE | ❌ | No file handling |
| CTX-INFRA | ❌ | No Docker / nginx / CORS changes |

**CTX-AGENT requirements applied:**
- Router never exposes credentials or tokens in logs (use `prompt_hash`, not `prompt`).
- No agent-created artifacts; router is read-only classification.
- Output is internal `AgentDomain` enum, never rendered to users.
- Prompt-injection scanning is already handled by `BaseAgentService._check_prompt_injection` (`base.py:86`); the router is upstream of the agent pipeline but **only inspects keyword presence** — no LLM call, no execution path.

## Research Summary

### Existing infrastructure (no changes needed — reuse as-is)

| File | Symbol | Lines | Purpose |
|---|---|---|---|
| `app/core/agents/schemas.py` | `AgentName = Literal["unified","transit","knowledge","vault"]` | 14 | **Reuse this Literal as our domain type** — no new enum needed |
| `app/core/agents/schemas.py` | `ChatCompletionRequest.agent: AgentName` | 43 | Already exists; default `"unified"` is the trigger for auto-routing |
| `app/core/agents/agents/registry.py` | `get_agent_by_name(name: AgentName) -> BaseAgentService` | 27 | Resolves the chosen domain to a singleton agent — call this AFTER routing |
| `app/core/agents/routing.py` | `classify_prompt(prompt) -> ModelTier` | 65–103 | **Pattern template** for the new router (regex lists, case-insensitive, no `\b` for Latvian inflection) |
| `app/knowledge/router.py` | `needs_rag(query) -> RoutingDecision` | 73–100 | **Second template** — signal scoring with `RoutingDecision` NamedTuple + `knowledge.router.decision` log event |
| `app/core/logging.py` | `get_logger(__name__)` | — | Structlog logger; emit `agent.router.decision` per `domain.component.action_state` taxonomy |
| `app/core/config.py` | `Settings` class | 30+ | Add new flag near existing agent flags at lines 277–279 |

### Endpoint to modify

**`app/core/agents/routes.py:35–68`** — `chat_completions` currently:
```python
service = get_agent_by_name(body.agent)
logger.info("agent.chat.selected", agent=body.agent)
return await service.chat(body)
```
The change is **two lines**: when `body.agent == "unified"` AND `settings.agent_multi_agent_enabled`, call the router first to upgrade `"unified"` to a more specific domain. If the router returns `"unified"`, behavior is identical to today.

### Domain-agent identities (for reference)

| Domain | File | `agent_name` | Tools |
|---|---|---|---|
| `transit` | `app/core/agents/agents/transit.py` | `"transit_agent_v2"` | 5 transit tools |
| `knowledge` | `app/core/agents/agents/knowledge.py` | `"knowledge_agent"` | 1 RAG tool |
| `vault` | `app/core/agents/agents/vault.py` | `"vault_agent"` | 4 obsidian tools |
| `unified` | resolved via `get_agent_service()` (existing `AgentService` singleton) | `"base_agent"` | All 11 tools |

### Existing log events (do not collide)

`agent.chat_started`, `agent.chat_completed`, `agent.chat_failed`, `agent.chat.selected`, `agent.prompt_injection_detected`, `agent.correction.*`, `agent.quota_exceeded_http`, `knowledge.router.decision`. **New event:** `agent.router.decision` (no collision).

## Test Landscape

### Templates to mirror

| Test file | Lines | Why it's the model |
|---|---|---|
| `app/core/agents/tests/test_routing.py` | 115 | **Primary template** — class-per-tier organization, no parametrize, simple `assert classify_prompt(x) == y`, includes Latvian-with/without-diacritics cases |
| `app/core/agents/tests/test_routes.py` | 184 | Endpoint integration: shows `_setup_auth_override` + `_bypass_quota_tracker` autouse fixtures, `patch("app.core.agents.routes.get_agent_by_name")` mock pattern |
| `app/core/agents/tests/test_config.py` | 212 | Settings override pattern: `create_settings(**overrides)` + `patch.dict(os.environ)` + `get_settings.cache_clear()` |
| `app/core/tests/test_logging.py` | 105–156 | Structlog assertion via `capsys.readouterr()` + `json.loads()` |

### Existing fixtures we will reuse

- **Root `conftest.py`** — `mock_settings` fixture (clears `get_settings.cache_clear()`), `client` TestClient
- **`test_routes.py:_setup_auth_override`** — overrides `get_current_user` to mock admin
- **`test_routes.py:_bypass_quota_tracker`** — patches `get_quota_tracker` to return a stub that always allows the request
- **`models.ALLOW_MODEL_REQUESTS = False`** module-level guard (set at top of any test file that loads agents)

### Security convention test that touches our area

**`app/tests/test_security.py:1165–1178`** — `ChatCompletionsRouteSecurityAudit.test_agent_routes_use_get_client_ip` greps the source of `chat_completions` for `_get_client_ip` and forbids `request.client.host`. Our edit must not remove these. ✅ We only insert lines, not delete.

### Fragile patterns to avoid (from research)

1. **MagicMock without `spec`** — when patching `get_agent_by_name`, use `MagicMock(spec=BaseAgentService)` so signature drift breaks the test.
2. **Hardcoded enum strings** — assert against the `AgentName` Literal values, not raw strings, by importing the alias.
3. **Module-level singleton state** — domain agents are singletons in `registry.py`. Tests must not call `get_agent_by_name()` for real (it constructs HTTP clients). Always patch.
4. **Latvian regex without diacritic variants** — follow `routing.py:18-62`: pair `kavēj|kavej`, `maršrut|marsrut`, `pietur|pietūr`. Test BOTH forms.

## Type Check Baseline

Before any edits in `app/core/agents/`:

| Tool | Errors | Files affected |
|---|---|---|
| **Pyright** | **5** | `pipeline.py` (4), `tools/transit/client.py` (1) |
| **Mypy** | **3** | `pipeline.py` (1), `tools/transit/static_store.py` (2) |

**None of the baseline errors are in `routes.py` or in any file we edit.** New file `router.py` must introduce **zero** new errors. After `/be-execute`, totals must remain ≤ 5 pyright + 3 mypy in `app/core/agents/`. All baseline errors are pre-existing and unrelated to AI-6.3 — ignore them.

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| **CREATE** | `app/core/agents/router.py` | `AgentRouter` class — keyword scoring + `route()` returning `AgentName` |
| **UPDATE** | `app/core/config.py` | Add `agent_multi_agent_enabled: bool = False` next to existing agent flags (~line 280) |
| **UPDATE** | `app/core/agents/routes.py` | Wire router into `chat_completions` when flag enabled and incoming agent is `"unified"` |
| **CREATE** | `app/core/agents/tests/test_router.py` | 20+ unit tests: classification, ties, Latvian, flag-disabled, flag-enabled, edge cases |
| **UPDATE** | `app/core/agents/tests/test_routes.py` | Add 3 endpoint tests: flag-off (no routing), flag-on + transit prompt → routes to transit, flag-on + cross-domain → unified |

**No model/migration/schema changes.** No new endpoints. No router registration in `app/main.py`.

## Implementation Steps

### Step 1 — Add config flag

**File:** `app/core/config.py`

Find the existing block at lines 277–279:
```python
# Self-correction loop (AI-5.1)
agent_self_correction_enabled: bool = True
agent_max_correction_rounds: int = 1
```

Append immediately after:
```python

# Multi-agent auto-routing (AI-6.3)
agent_multi_agent_enabled: bool = False
```

**Validation:**
```bash
uv run ruff format app/core/config.py && \
uv run ruff check --fix app/core/config.py && \
uv run pyright app/core/config.py && \
uv run mypy app/core/config.py
```

---

### Step 2 — Create `app/core/agents/router.py`

**File:** `app/core/agents/router.py` (NEW)

```python
"""Heuristic agent router (AI-6.3).

Scores incoming prompts against three keyword signal sets — transit,
knowledge, vault — and returns the AgentName of the best-fit domain.
Ties or zero-score prompts fall back to "unified".

This module is intentionally LLM-free: scoring is regex-based, runs in
microseconds, and mirrors the design of ``app/core/agents/routing.py``
(model-tier classifier) and ``app/knowledge/router.py`` (RAG signal
scorer). It is the upstream classifier for the BaseAgentService pipeline.
"""

from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

from app.core.agents.schemas import AgentName
from app.core.logging import get_logger

logger = get_logger(__name__)


# Keyword signal sets. Each entry is a regex (case-insensitive). Latvian
# stems are written WITHOUT trailing word boundary so inflected forms
# match (`maršrut` → `maršruti`, `maršrutu`, `maršrutā`). Both diacritized
# and undiacriticized variants are listed because users frequently type
# without diacritics (`kavejas` instead of `kavējas`).

_TRANSIT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"maršrut", r"marsrut",
        r"pietur",
        r"autobus",
        r"kavēj", r"kavej",
        r"reis",
        r"grafik",
        r"vadītāj", r"vaditaj",
        r"transport",
        r"\broute\b", r"\broutes\b",
        r"\bstop\b", r"\bstops\b",
        r"\bdelay\b", r"\bdelays\b", r"\bdelayed\b",
        r"\bbus\b", r"\bbuses\b",
        r"\bschedule\b", r"\bschedules\b",
        r"\bdeparture\b", r"\bdepartures\b", r"\barrival\b",
        r"\bdriver\b", r"\bdrivers\b",
        r"\bvehicle\b", r"\bvehicles\b",
    )
)

_KNOWLEDGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"dokument",
        r"noteikum",
        r"procedūr", r"procedur",
        r"regul",
        r"likum",
        r"instrukcij",
        r"\bSOP\b",
        r"\bpolicy\b", r"\bpolicies\b",
        r"\bdocument\b", r"\bdocuments\b",
        r"\bprocedure\b", r"\bprocedures\b",
        r"\bregulation\b", r"\bregulations\b",
        r"\bcompliance\b",
        r"\bguideline\b", r"\bguidelines\b",
    )
)

_VAULT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bvault\b",
        r"\bobsidian\b",
        r"piezīm", r"piezim",
        r"\bnote\b", r"\bnotes\b",
        r"\bfolder\b", r"\bfolders\b",
        r"\btag\b", r"\btags\b",
        r"\bbacklink\b", r"\bbacklinks\b",
        r"\bmarkdown\b",
    )
)


class RoutingDecision(NamedTuple):
    """Result of a single classification call."""

    domain: AgentName
    transit_score: int
    knowledge_score: int
    vault_score: int


def _score(prompt: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    """Count how many distinct patterns match anywhere in ``prompt``."""

    return sum(1 for pat in patterns if pat.search(prompt))


def _prompt_hash(prompt: str) -> str:
    """Short SHA-256 prefix for log correlation without leaking content."""

    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


class AgentRouter:
    """Heuristic prompt → domain agent classifier.

    Usage:
        router = AgentRouter()
        decision = router.classify("Kuri maršruti kavējas?")
        # decision.domain == "transit"
    """

    def classify(self, prompt: str) -> RoutingDecision:
        """Score the prompt and return the best-fit ``AgentName``.

        Tie-breaking rules (in order):

        1. If the maximum score is 0, return ``"unified"``.
        2. If two or more domains share the maximum score, return
           ``"unified"`` (treat as cross-domain).
        3. Otherwise return the unique top-scoring domain.
        """

        text = prompt.strip()
        if not text:
            decision = RoutingDecision("unified", 0, 0, 0)
            self._log(text, decision)
            return decision

        transit = _score(text, _TRANSIT_PATTERNS)
        knowledge = _score(text, _KNOWLEDGE_PATTERNS)
        vault = _score(text, _VAULT_PATTERNS)

        scores: dict[AgentName, int] = {
            "transit": transit,
            "knowledge": knowledge,
            "vault": vault,
        }
        top_score = max(scores.values())

        domain: AgentName
        if top_score == 0:
            domain = "unified"
        else:
            winners = [name for name, score in scores.items() if score == top_score]
            domain = winners[0] if len(winners) == 1 else "unified"

        decision = RoutingDecision(
            domain=domain,
            transit_score=transit,
            knowledge_score=knowledge,
            vault_score=vault,
        )
        self._log(text, decision)
        return decision

    def route(self, prompt: str) -> AgentName:
        """Convenience wrapper that returns only the chosen ``AgentName``."""

        return self.classify(prompt).domain

    @staticmethod
    def _log(prompt: str, decision: RoutingDecision) -> None:
        logger.info(
            "agent.router.decision",
            prompt_hash=_prompt_hash(prompt),
            prompt_length=len(prompt),
            domain=decision.domain,
            transit_score=decision.transit_score,
            knowledge_score=decision.knowledge_score,
            vault_score=decision.vault_score,
        )


_singleton: AgentRouter | None = None


def get_agent_router() -> AgentRouter:
    """Return the process-wide ``AgentRouter`` singleton."""

    global _singleton
    if _singleton is None:
        _singleton = AgentRouter()
    return _singleton
```

**Notes:**
- Anti-pattern #2: no `object` type hints — all parameters concretely typed.
- Anti-pattern #5: no unused imports.
- Anti-pattern #8: no EN DASH (uses ASCII `-` only).
- Anti-pattern #44: never log raw prompt — only `prompt_hash` + `prompt_length`.
- Anti-pattern #54: returned domain uses the existing `AgentName` Literal alias.

**Validation:**
```bash
uv run ruff format app/core/agents/router.py && \
uv run ruff check --fix app/core/agents/router.py && \
uv run pyright app/core/agents/router.py && \
uv run mypy app/core/agents/router.py
```

---

### Step 3 — Wire router into `chat_completions`

**File:** `app/core/agents/routes.py`

Add to imports near the top:
```python
from app.core.agents.router import get_agent_router
from app.core.config import get_settings
```
(Use `get_settings` if not already imported — verify and skip the duplicate import.)

Replace the agent-resolution block (currently `routes.py:66–67`):
```python
service = get_agent_by_name(body.agent)
logger.info("agent.chat.selected", agent=body.agent)
```

With:
```python
selected_agent: AgentName = body.agent
if body.agent == "unified" and get_settings().agent_multi_agent_enabled:
    last_user_message = next(
        (msg.content for msg in reversed(body.messages) if msg.role == "user"),
        "",
    )
    selected_agent = get_agent_router().route(last_user_message)

service = get_agent_by_name(selected_agent)
logger.info(
    "agent.chat.selected",
    agent=selected_agent,
    requested_agent=body.agent,
    auto_routed=selected_agent != body.agent,
)
```

Add `AgentName` to the existing `from app.core.agents.schemas import ...` line (it's likely already imported via `ChatCompletionRequest`; if not, add it).

**Notes:**
- We only auto-route when the client asked for `"unified"`. An explicit `agent="transit"` request from the client is never overridden.
- The `last_user_message` lookup uses `reversed()` to score the most recent user turn (matches how RAG router behaves).
- The `requested_agent` and `auto_routed` log fields make A/B analysis trivial.

**Validation:**
```bash
uv run ruff format app/core/agents/routes.py && \
uv run ruff check --fix app/core/agents/routes.py && \
uv run pyright app/core/agents/routes.py && \
uv run mypy app/core/agents/routes.py
```

---

### Step 4 — Unit tests for the router

**File:** `app/core/agents/tests/test_router.py` (NEW)

Required coverage (≥ 20 tests):

| # | Class | Test | Asserts |
|---|---|---|---|
| 1 | `TestAgentRouterTransit` | `test_latvian_route_delay` | `route("Kuri maršruti kavējas?") == "transit"` |
| 2 | " | `test_latvian_route_delay_no_diacritics` | `route("Kuri marsruti kavejas?") == "transit"` |
| 3 | " | `test_latvian_stop_query` | `route("Kur ir tuvākā pietura?") == "transit"` |
| 4 | " | `test_english_delay_query` | `route("Which routes are delayed?") == "transit"` |
| 5 | " | `test_english_schedule_query` | `route("What's the bus schedule?") == "transit"` |
| 6 | " | `test_driver_query` | `route("Kurš vadītājs ir reisā?") == "transit"` |
| 7 | `TestAgentRouterKnowledge` | `test_latvian_procedure_query` | `route("Kāda ir avārijas procedūra?") == "knowledge"` |
| 8 | " | `test_latvian_document_query` | `route("Atrodi dokumentus par drošību") == "knowledge"` |
| 9 | " | `test_english_sop_query` | `route("Show me the SOP for fueling") == "knowledge"` |
| 10 | " | `test_english_compliance_query` | `route("What does the compliance regulation say?") == "knowledge"` |
| 11 | `TestAgentRouterVault` | `test_vault_keyword` | `route("Show my vault notes") == "vault"` |
| 12 | " | `test_obsidian_keyword` | `route("Search obsidian for X") == "vault"` |
| 13 | " | `test_latvian_notes_query` | `route("Parādi manas piezīmes") == "vault"` |
| 14 | " | `test_folder_query` | `route("List folders in vault") == "vault"` |
| 15 | `TestAgentRouterUnified` | `test_empty_prompt` | `route("") == "unified"` |
| 16 | " | `test_whitespace_only` | `route("   ") == "unified"` |
| 17 | " | `test_unknown_topic` | `route("Hello, how are you?") == "unified"` |
| 18 | " | `test_cross_domain_transit_and_knowledge` | `route("What routes serve the hospitals mentioned in the SOP?") == "unified"` (tie) |
| 19 | " | `test_cross_domain_vault_and_transit` | `route("Show vault notes about delayed routes") == "unified"` |
| 20 | `TestRoutingDecisionScores` | `test_classify_returns_scores` | `classify("delayed buses").transit_score >= 1`; other scores `== 0` |
| 21 | " | `test_classify_returns_decision_namedtuple` | isinstance check + `decision.domain == "transit"` |
| 22 | `TestAgentRouterLogging` | `test_emits_decision_event` | uses `capsys` to read stdout, `json.loads`, asserts `event == "agent.router.decision"`, `domain == "transit"`, `prompt_hash` is 12 chars |
| 23 | " | `test_log_does_not_contain_raw_prompt` | sentinel string in prompt is NOT in captured log line |
| 24 | `TestSingleton` | `test_get_agent_router_returns_same_instance` | `get_agent_router() is get_agent_router()` |

**Test file skeleton:**
```python
"""Tests for AI-6.3 AgentRouter heuristic classifier."""

from __future__ import annotations

import json

import pytest

from app.core.agents.router import (
    AgentRouter,
    RoutingDecision,
    get_agent_router,
)


@pytest.fixture
def router() -> AgentRouter:
    return AgentRouter()


class TestAgentRouterTransit:
    def test_latvian_route_delay(self, router: AgentRouter) -> None:
        assert router.route("Kuri maršruti kavējas?") == "transit"

    # ... etc.
```

**Notes:**
- Anti-pattern #26: every test param annotated → return `-> None` required.
- Anti-pattern #28: no bare `[]` literals.
- Use `capsys: pytest.CaptureFixture[str]` for logging tests (matches `test_logging.py:105` template).

**Validation:**
```bash
uv run ruff format app/core/agents/tests/test_router.py && \
uv run ruff check --fix app/core/agents/tests/test_router.py && \
uv run pyright app/core/agents/tests/test_router.py && \
uv run pytest app/core/agents/tests/test_router.py -v
```

Expected: **24 passed in < 1s** (no async, no DB, no LLM).

---

### Step 5 — Endpoint integration tests

**File:** `app/core/agents/tests/test_routes.py` (UPDATE)

Add three tests to the existing file (do not modify existing fixtures or other tests):

```python
class TestChatCompletionsAutoRouting:
    """AI-6.3: server-side AgentRouter wires into chat_completions."""

    def test_flag_disabled_no_auto_routing(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When AGENT_MULTI_AGENT_ENABLED is False, body.agent is honored verbatim."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "false")
        get_settings.cache_clear()

        fake_service = MagicMock(spec=BaseAgentService)
        fake_service.chat = AsyncMock(return_value=_fake_chat_response())
        with patch(
            "app.core.agents.routes.get_agent_by_name",
            return_value=fake_service,
        ) as resolver:
            client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Kuri maršruti kavējas?"}]},
            )
            resolver.assert_called_once_with("unified")

    def test_flag_enabled_routes_transit_prompt(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When flag is on and prompt is transit-y, request reaches transit agent."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "true")
        get_settings.cache_clear()

        fake_service = MagicMock(spec=BaseAgentService)
        fake_service.chat = AsyncMock(return_value=_fake_chat_response())
        with patch(
            "app.core.agents.routes.get_agent_by_name",
            return_value=fake_service,
        ) as resolver:
            client.post(
                "/v1/chat/completions",
                json={"messages": [{"role": "user", "content": "Which routes are delayed?"}]},
            )
            resolver.assert_called_once_with("transit")

    def test_flag_enabled_cross_domain_falls_back_to_unified(
        self,
        client: TestClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Tied scores → unified."""
        monkeypatch.setenv("AGENT_MULTI_AGENT_ENABLED", "true")
        get_settings.cache_clear()

        fake_service = MagicMock(spec=BaseAgentService)
        fake_service.chat = AsyncMock(return_value=_fake_chat_response())
        with patch(
            "app.core.agents.routes.get_agent_by_name",
            return_value=fake_service,
        ) as resolver:
            client.post(
                "/v1/chat/completions",
                json={
                    "messages": [
                        {
                            "role": "user",
                            "content": "What routes serve the hospitals mentioned in the SOP?",
                        }
                    ]
                },
            )
            resolver.assert_called_once_with("unified")
```

Imports to add at the top of `test_routes.py` (if missing):
```python
from app.core.agents.base import BaseAgentService
from app.core.config import get_settings
```

**Cleanup:** add `get_settings.cache_clear()` after each test (or use a teardown fixture) so the env var leak doesn't poison sibling tests. Mirror what `test_config.py:20` already does.

**Validation:**
```bash
uv run pytest app/core/agents/tests/test_routes.py::TestChatCompletionsAutoRouting -v
```

---

### Step 6 — Full quality gate

```bash
uv run ruff format app/core/ && \
uv run ruff check --fix app/core/ && \
uv run pyright app/core/agents/ && \
uv run mypy app/core/agents/ && \
uv run pytest app/core/agents/tests/ -v
```

Then the project-wide gate:
```bash
make check
```

## Preflight Warnings

From the test-scout research, watch for these brittle patterns when editing tests:

1. **`models.ALLOW_MODEL_REQUESTS = False`** is set at module level in `test_routes.py`. The new tests don't trigger real LLM calls (we mock `get_agent_by_name` with a `BaseAgentService` spec), so this guard is sufficient — but never call `agent.run()` directly inside the new tests.
2. **`get_settings.cache_clear()`** must be called before AND after env-var monkey-patching, or the cached `Settings()` will leak between tests. The `mock_settings` fixture in root `conftest.py` already does this — prefer using it where possible.
3. **`MagicMock(spec=BaseAgentService)`** is required (not bare `MagicMock()`). Without `spec`, signature drift in `BaseAgentService.chat()` will silently break.
4. **Do NOT touch `chat_completions`'s `_get_client_ip` call** — `app/tests/test_security.py:1165–1178` greps the source for it.
5. **Avoid tuple-unpacking `RoutingDecision`** in tests. Use named field access (`decision.domain`, `decision.transit_score`) so adding fields later doesn't break.

## Security Checklist

- [x] No new endpoints — auth/RBAC unchanged
- [x] No new input surface — prompt is validated by `ChatCompletionRequest` (`max_length=4000`)
- [x] No file handling
- [x] No credentials, tokens, or raw prompts in logs (use `prompt_hash`)
- [x] Router is read-only classification — no DB writes, no agent-created artifacts
- [x] Default-off flag (`agent_multi_agent_enabled = False`) preserves current behavior
- [x] Existing prompt-injection scanning (`base.py:86`) still runs downstream — router is upstream and is a no-op for injection patterns
- [x] `agent.router.decision` log event follows `domain.component.action_state` taxonomy

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] `uv run pytest app/core/agents/tests/test_router.py -v` → ≥ 20 passed
- [ ] `uv run pytest app/core/agents/tests/test_routes.py::TestChatCompletionsAutoRouting -v` → 3 passed
- [ ] `uv run pyright app/core/agents/` → ≤ 5 errors (baseline)
- [ ] `uv run mypy app/core/agents/` → ≤ 3 errors (baseline)
- [ ] Security convention test still passes: `uv run pytest app/tests/test_security.py::ChatCompletionsRouteSecurityAudit -v`
- [ ] Smoke check: with `AGENT_MULTI_AGENT_ENABLED=false`, behavior identical to before this change (no `agent.router.decision` events emitted)
- [ ] Smoke check: with `AGENT_MULTI_AGENT_ENABLED=true`, sample prompts route as expected:
  - "Kuri maršruti kavējas?" → `transit`
  - "Kāda ir procedūra?" → `knowledge`
  - "Show my vault notes" → `vault`
  - "What routes serve the hospitals mentioned in the SOP?" → `unified`
