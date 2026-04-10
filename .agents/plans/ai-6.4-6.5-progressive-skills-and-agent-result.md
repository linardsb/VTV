# Plan: AI-6.4 Progressive Skill System (L3) + AI-6.5 AgentResult Protocol

## Context

Two related upgrades to the agent module (`app/core/agents/`) building on AI-6.1 (BaseAgentService 11-hook harness), AI-6.2 (domain agent subclasses with `selector` field), and AI-6.3 (heuristic auto-router).

**AI-6.4** — Replace flat skill injection (every active `AgentSkill` row from `app/skills/` loaded into every prompt) with a per-agent, on-demand, priority-gated skill loader. New L3 skill files live in the repo as markdown with YAML front matter (`token_cost`, `priority`, `version`, `keywords`). Each domain agent owns a skill budget; supplementary (P3) skills drop first when capacity is tight, then standard (P2). Goal: ~30% reduction in skill-context tokens for domain agents while keeping the existing DB-backed flat skill system fully functional.

**AI-6.5** — Lightweight `AgentResult` frozen dataclass returned internally from the agent pipeline (`content`, `confidence`, `warnings`, `tools_used`, `domain`). `BaseAgentService.chat()` builds it from `_PipelineOutcome` plus the active domain, optionally re-runs against a complex tier when `confidence < 0.3`, then converts to the existing OpenAI-compatible `ChatCompletionResponse`. The HTTP contract is unchanged.

## Security Context Assessment

| Context | Active? | Why |
|---|---|---|
| **CTX-AGENT** | ✅ | Both tasks live inside `app/core/agents/`. Skill files become a new injection vector — must validate front matter, never `eval()` or template-execute markdown bodies, and treat skill files as trusted (in-repo, not user-uploaded). `AgentResult` must not echo credentials or internal stack traces in `warnings`. |
| **CTX-INFRA** | ✅ (light) | Adds `pyyaml>=6.0` to `pyproject.toml`. No env vars, no Docker changes. New optional setting `agent_progressive_skills_enabled` with default `True`. |
| **CTX-INPUT** | ✅ (light) | `detect_relevant_skills()` consumes the user prompt for keyword matching. Match must be done on lowercased prompt with bounded keyword lists; never compile user input as regex. |
| CTX-AUTH | ❌ | No auth/session changes. |
| CTX-RBAC | ❌ | No new endpoints. |
| CTX-FILE | ❌ | No file uploads. Skill files are package data, not user-supplied. |

**Required guardrails:**
- YAML front matter parsed with `yaml.safe_load` (never `yaml.load`)
- Skill file paths resolved with `Path(__file__).parent / "skills" / domain` and constrained to that subtree (`is_relative_to` check)
- Bare `except: pass` is forbidden — every load failure logs `agent.skill_loader.failed` with the file path and falls back to "no skill loaded"
- Re-routing on low confidence is rate-limited to **one extra LLM call per chat** (no infinite escalation loops)

## Research Summary

### Current agent module layout
```
app/core/agents/
├── base.py            # BaseAgentService — 11 hooks (lines 151–479), _PipelineOutcome dataclass (115–130)
├── service.py         # AgentService — unified concrete subclass with full QA + correction
├── agent.py           # build_instructions_with_skills() — skills injection point (146–166)
├── router.py          # AI-6.3 heuristic AgentRouter (returns AgentName)
├── routing.py         # ModelTier classifier (fast/standard/complex)
├── config.py          # resolve_tier_model() — tier→Model mapping
├── correction.py      # AI-5.1 SelfCorrectionLoop, CorrectedResult dataclass
├── validation.py      # AI-5.2 Issue (frozen=True), ValidationResult — example pattern to copy
├── pipeline.py        # complex-tier orchestrator
├── metrics.py         # AI-5.3 CorrectionMetricsTracker singleton
├── routes.py          # /v1/chat/completions endpoint (lines 37–83)
├── agents/            # AI-6.2 domain subclasses
│   ├── transit.py     # TransitAgent — 5 transit tools, full QA
│   ├── knowledge.py   # KnowledgeAgent — 1 RAG tool, no correction
│   ├── vault.py       # VaultAgent — 4 obsidian tools, safe-delete prompt
│   └── registry.py    # get_agent_by_name() singleton factory
└── tests/             # 15 test files, no conftest.py (local fixtures)
```

### Where skills are wired today
- `BaseAgentService.chat()` line **188** calls Hook 3 `detect_relevant_skills(prompt)` → returns string
- Hook 5 `build_system_prompt(skills_text, memory_text)` line **194** delegates to `agent.py:build_instructions_with_skills()` (lines 146–166)
- Base default `detect_relevant_skills()` returns `""`; concrete `AgentService` and the AI-6.2 domain subclasses currently call `SkillService.get_active_skills_content()` (`app/skills/service.py:103–135`) which loads **every active row** under an 8000-char global budget
- The DB-backed `app/skills/` feature stays unchanged — both flat DB skills and new L3 markdown skills must be composable in one prompt

### How `_execute()` returns today
Each subclass implements `async def _execute(...) -> _PipelineOutcome` (`base.py:115–130`):
```python
@dataclass(slots=True)
class _PipelineOutcome:
    response_text: str
    warnings: list[str] | None
    messages: list[ModelMessage] = field(default_factory=list)
```
We will **extend** it (additive, non-breaking) with two optional fields and add the new `AgentResult` as a separate frozen wrapper built inside `chat()`.

### Tier model resolution
`config.py:resolve_tier_model(tier: ModelTier) -> Model | str | None` already exists and returns the configured fast/standard/complex provider+model. AI-6.5 re-routing reuses it — no new tier infrastructure needed.

### Frozen-dataclass precedent
`validation.py:120` — `Issue(frozen=True)` is the in-tree pattern to copy.

### Reference VSA features
- AI-5.2 `validation.py` (frozen dataclass + module-level constants)
- AI-6.2 `agents/transit.py` (subclass overriding multiple hooks)
- AI-6.3 `router.py` (keyword-based classifier with structured logging)

### Dependencies
- **`pyyaml>=6.0`** — NOT in `pyproject.toml`, must add. Used only for `yaml.safe_load` on skill front matter.
- **`tiktoken`** — NOT in deps. Skip it: estimate tokens with `len(text) // 4` (matches the existing convention in `app/skills/schemas.py:9` `TOKEN_BUDGET_CHARS = 8000` ≈ 2000 tokens).

## Test Landscape

### Existing patterns to copy

| Pattern | Source | Use for |
|---|---|---|
| `_FakeAgentService(BaseAgentService)` minimal subclass | `tests/test_base.py:38–84` | New `_FakeBudgetAgent` for `chat()` re-routing tests |
| `models.ALLOW_MODEL_REQUESTS = False` + `agent.override(model=TestModel())` | `tests/test_service.py:36–38` | All AgentResult tests |
| `_create_transit_agent_service()` patches `create_unified_deps` at import site | `tests/test_transit_agent.py:37–47` | Domain-agent skill-loader integration tests |
| `@pytest.fixture(autouse=True) _reset_singleton` for tracker | `tests/test_metrics.py:44–49` | Reset skill-loader cache per test |
| `make_skill(**overrides)` factory | `app/skills/tests/conftest.py:11–27` | Reused unchanged for the flat-skill compatibility tests |
| Frozen dataclass equality + immutability assertions | `validation.py:120` `Issue` + `tests/test_validation.py` | `AgentResult` and `SkillMeta` tests |

### No `app/core/agents/tests/conftest.py` exists yet
We will **create one** (small, ~40 lines) so factories can be shared:
- `make_agent_result(**overrides) -> AgentResult`
- `make_skill_meta(**overrides) -> SkillMeta`
- `tmp_skill_dir(tmp_path) -> Path` — writes a minimal skill tree under `tmp_path/skills/{transit,knowledge,vault}/` for loader tests

### Security convention tests
`app/tests/test_security.py` runs at the module level and walks endpoints + filesystem; new modules under `app/core/agents/` are not endpoints and add no new file uploads. **No new security convention tests required**, but the existing suite must remain green.

## Type Check Baseline

Captured **2026-04-10** before this work.

**Whole-module baselines** (`uv run pyright app/core/agents/` / `mypy app/core/agents/`):

| Path | pyright errors | mypy errors | Notes |
|---|---|---|---|
| `app/core/agents/` | **5** | **3** | Pre-existing — see below. New files MUST add 0. |
| `app/skills/` | 0 | 0 | Clean. New code touching this dir must preserve 0. |

**Targeted baselines** (just the files this plan modifies — `base.py`, `service.py`, `agents/{transit,knowledge,vault}.py`, `__init__.py`, `core/config.py`):

| Tool | Errors on target files | Errors in transitive deps |
|---|---|---|
| pyright | **0** | 0 (transitive errors live outside target set) |
| mypy | **0 in target files** | 3 (`tools/transit/static_store.py:149,150` + `pipeline.py:136`) |

The 3 mypy errors surface only because mypy follows imports from `service.py`/`pipeline.py`. After implementation, running `mypy <target files>` should still show **3** errors and **0 in target files** — anything more is a regression introduced by this plan.

Pre-existing errors (do **not** touch):
- `pipeline.py:47,49,136` — partially-unknown list types + `model` arg-type. Both checkers.
- `tools/transit/client.py:193` — possibly-unbound `response` (pyright only).
- `tools/transit/static_store.py:149,150` — async SQLAlchemy `Result` typing (mypy only).

**Acceptance:** after AI-6.4+6.5, `app/core/agents/` ≤ 5 pyright + ≤ 3 mypy, `app/skills/` = 0 / 0, target files alone = 0 / 0.

## Files to Create / Modify

### Create

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/context_budget.py` | `ContextBudget(frozen=True)` dataclass + `AGENT_BUDGETS` per-agent dict + `agent_budget_for(name)` lookup |
| CREATE | `app/core/agents/skill_loader.py` | `SkillMeta` dataclass, `parse_skill_file()`, `discover_skills()`, `load_skills_within_budget()`, module-level skill cache |
| CREATE | `app/core/agents/agent_result.py` | `AgentResult(frozen=True)` dataclass + `_to_chat_completion(result, tier_model, request) -> ChatCompletionResponse` helper |
| CREATE | `app/core/agents/skills/__init__.py` | Empty package marker |
| CREATE | `app/core/agents/skills/transit/delay_analysis.md` | P2, ~450 token L3 skill |
| CREATE | `app/core/agents/skills/transit/schedule_interpretation.md` | P2, ~400 |
| CREATE | `app/core/agents/skills/transit/route_comparison.md` | P3, ~350 |
| CREATE | `app/core/agents/skills/transit/driver_availability.md` | P3, ~300 |
| CREATE | `app/core/agents/skills/transit/adherence_reporting.md` | P3, ~350 |
| CREATE | `app/core/agents/skills/knowledge/sop_retrieval.md` | P1, ~500 |
| CREATE | `app/core/agents/skills/knowledge/regulation_interpretation.md` | P2, ~450 |
| CREATE | `app/core/agents/skills/knowledge/shift_handover.md` | P3, ~300 |
| CREATE | `app/core/agents/skills/knowledge/incident_response.md` | P2, ~400 |
| CREATE | `app/core/agents/skills/vault/search_patterns.md` | P2, ~300 |
| CREATE | `app/core/agents/skills/vault/bulk_operations.md` | P3, ~250 |
| CREATE | `app/core/agents/skills/vault/folder_organization.md` | P3, ~250 |
| CREATE | `app/core/agents/tests/conftest.py` | Shared factories (`make_agent_result`, `make_skill_meta`, `tmp_skill_dir`) |
| CREATE | `app/core/agents/tests/test_context_budget.py` | Budget dataclass + lookup tests |
| CREATE | `app/core/agents/tests/test_skill_loader.py` | YAML parsing, priority gating, budget enforcement, keyword matching |
| CREATE | `app/core/agents/tests/test_agent_result.py` | Frozen-ness, chat conversion, low-confidence re-routing |

### Modify

| Action | File | Purpose |
|---|---|---|
| UPDATE | `pyproject.toml` | Add `pyyaml>=6.0` to `[project] dependencies`; mypy `[[overrides]]` block for `yaml` if it lacks stubs (it ships them — verify and only add if needed) |
| UPDATE | `app/core/config.py` | Add 3 settings: `agent_progressive_skills_enabled: bool = True`, `agent_confidence_reroute_enabled: bool = True`, `agent_confidence_reroute_threshold: float = 0.3` |
| UPDATE | `app/core/agents/base.py` | (a) extend `_PipelineOutcome` with optional `confidence: float \| None = None` and `tools_used: tuple[str, ...] = ()`; (b) `chat()` builds `AgentResult`, runs confidence re-route, then converts to `ChatCompletionResponse`; (c) update default `detect_relevant_skills()` docstring noting subclasses should call `skill_loader.load_skills_within_budget` |
| UPDATE | `app/core/agents/agents/transit.py` | Override `detect_relevant_skills(prompt)` → call `skill_loader.load_skills_within_budget("transit", prompt, AGENT_BUDGETS["transit"])` and concatenate with the existing flat-skill output (back-compat); populate `_PipelineOutcome.confidence` (heuristic) and `tools_used` |
| UPDATE | `app/core/agents/agents/knowledge.py` | Same pattern; confidence comes from the RAG reranker top score when available |
| UPDATE | `app/core/agents/agents/vault.py` | Same pattern; confidence = 1.0 when no warnings, 0.5 when warnings present |
| UPDATE | `app/core/agents/service.py` | (Unified `AgentService`) override `detect_relevant_skills()` to load the union of all three domain skill packs within the unified budget; populate confidence/tools_used in `_execute()` |
| UPDATE | `app/core/agents/__init__.py` | Re-export `AgentResult`, `ContextBudget`, `AGENT_BUDGETS` for external imports |

### Untouched (verify still passes)
- `app/core/agents/pipeline.py` — pre-existing pyright errors at L47/49/136. Do not modify.
- `app/skills/` — entire DB-backed feature stays as-is (both systems coexist).
- `app/core/agents/routes.py` — `chat()` still returns `ChatCompletionResponse`, so the route signature is unchanged.

## Implementation Steps

> One file per step. Each step's validation block is the minimal command to confirm the step is sane in isolation. The full pyramid runs at the end.

### Step 1 — Add `pyyaml` dependency
**File:** `pyproject.toml`
- Insert `"pyyaml>=6.0",` into `[project] dependencies` (alphabetical).
- Run `uv sync` to lock + install.
- Verify `python -c "import yaml; print(yaml.__version__)"`.
- If `yaml` lacks shipped stubs under our pyright/mypy config, add to `[tool.mypy] [[overrides]]`:
  ```toml
  [[tool.mypy.overrides]]
  module = ["yaml"]
  ignore_missing_imports = true
  ```
  Confirmed PyYAML 6.x ships type stubs in `types-PyYAML` — only add the override if `mypy` flags it.

**Validation:** `uv run python -c "import yaml; yaml.safe_load('a: 1')"`

### Step 2 — `context_budget.py`
**File:** `app/core/agents/context_budget.py` (~25 lines)

```python
@dataclass(frozen=True, slots=True)
class ContextBudget:
    system_prompt_max: int = 3000
    skill_docs_max: int = 2000
    memory_max: int = 1500
    user_message_max: int = 3000
    total_max: int = 10000

AGENT_BUDGETS: Final[dict[str, ContextBudget]] = {
    "transit":   ContextBudget(skill_docs_max=2500),
    "knowledge": ContextBudget(skill_docs_max=2000),
    "vault":     ContextBudget(skill_docs_max=1500),
    "unified":   ContextBudget(skill_docs_max=3000),
}

def agent_budget_for(agent_name: str) -> ContextBudget:
    return AGENT_BUDGETS.get(agent_name, ContextBudget())
```

**Validation:** `uv run ruff format app/core/agents/context_budget.py && uv run ruff check --fix app/core/agents/context_budget.py && uv run pyright app/core/agents/context_budget.py && uv run mypy app/core/agents/context_budget.py`

### Step 3 — `skill_loader.py`
**File:** `app/core/agents/skill_loader.py`

Public API:
```python
@dataclass(frozen=True, slots=True)
class SkillMeta:
    name: str
    priority: int                    # 1=P1, 2=P2, 3=P3
    token_cost: int
    version: int = 1
    keywords: tuple[str, ...] = ()
    domain: str = ""

def parse_skill_file(path: Path) -> tuple[SkillMeta, str] | None: ...
def discover_skills(domain: str, root: Path | None = None) -> list[_LoadedSkill]: ...
def load_skills_within_budget(
    domain: str, prompt: str, budget: ContextBudget,
    *, skill_root: Path | None = None,
) -> str: ...
def clear_cache() -> None: ...   # test helper
```

Implementation requirements:
- `_SKILL_ROOT = Path(__file__).parent / "skills"` (module-level `Final`).
- `parse_skill_file` reads file, requires file to start with `---`, splits on `---` (max 3 parts), `yaml.safe_load`s the front matter (must be a dict), validates `priority in {1,2,3}`, coerces `token_cost` to int (default `max(1, len(body)//4)`), defaults `name` to `path.stem`, casts `keywords` to lowercase `tuple[str, ...]`. Any failure logs `agent.skill_loader.<reason>` at WARNING and returns `None` — never raises.
- `discover_skills` walks `<root>/<domain>/*.md` sorted, calls `parse_skill_file`, drops `None`s. Defense-in-depth: `path.resolve().is_relative_to(base.resolve())` check before parsing (logs `agent.skill_loader.path_escaped` on miss).
- Module-level cache `_cache: dict[str, list[_LoadedSkill]]` guarded by `threading.Lock`. `clear_cache()` empties it. When `discover_skills` is called with an explicit `root`, bypass cache (test mode).
- `_matches_prompt(skill, prompt_lower)`: `True` if `skill.meta.keywords` is empty OR any keyword is `in prompt_lower`.
- `load_skills_within_budget`:
  1. `cap = budget.skill_docs_max`; return `""` if `cap <= 0`.
  2. Filter cached domain skills by `_matches_prompt(s, prompt.lower())`.
  3. Sort candidates by `(priority, token_cost, name)` — ascending. Cheap-of-equal-priority wins ties.
  4. Iterate; for each skill compute `remaining_pct = (cap - used) / cap` and apply priority gating: drop P3 when `<0.7`, drop P2 when `<0.3`, P1 always considered. Then check `used + skill.token_cost > cap` → drop.
  5. Track a `skipped: list[tuple[str, str]]` of `(name, reason)` for the log line.
  6. Log `agent.skill_loader.loaded` with `domain`, `loaded`, `skipped`, `tokens_used`, `budget` (info level).
  7. Return `"AGENT SKILLS (L3):\n\n## <name>\n<body>\n\n…"` or `""` when nothing selected.

**Hard constraints:**
- `yaml.safe_load` only — never `yaml.load`.
- No bare `except:` — every failure path logs and returns `None`/`""` (anti-pattern #37).
- `_LoadedSkill` is `@dataclass(slots=True)` (mutable) since it's an internal record; `SkillMeta` is `frozen=True`.
- Token estimate `len(body) // 4` mirrors `app/skills/schemas.py:TOKEN_BUDGET_CHARS`.

**Validation:** `uv run ruff format app/core/agents/skill_loader.py && uv run ruff check --fix app/core/agents/skill_loader.py && uv run pyright app/core/agents/skill_loader.py && uv run mypy app/core/agents/skill_loader.py`

### Step 4 — Skill markdown files
Create the 12 markdown skill files listed in the table above. Each file uses the YAML front matter format from `parse_skill_file`. Body should be ≤ `token_cost * 4` characters and contain concise SOP-style numbered guidance (call tool X first, do/don't list, format requirements). Each body should answer "what should the agent do *differently* when this skill is loaded?".

**Reference example** — `app/core/agents/skills/transit/delay_analysis.md`:
```markdown
---
name: delay_analysis
priority: 2
token_cost: 450
version: 1
keywords: [delay, late, behind, on time, schedule, adherence, kavējums, kavē, nokavē]
---
# Delay analysis

When the user asks about delays or schedule adherence:
1. Always call `get_adherence_report` first — never estimate from memory.
2. Distinguish trip-level (single run) from route-level (rolling window).
3. Magnitude buckets: <2 min on time, 2–5 minor, 5–15 significant, >15 critical.
4. If timeframe is missing, ask — do not silently fall back.
5. Hypothesize root cause only when tool data supports it.
```

**P1 (always loaded) example** — `app/core/agents/skills/knowledge/sop_retrieval.md`: `keywords: []` so it matches every prompt; body covers "always call `search_knowledge_base` first, never paraphrase, cite sources, surface conflicts".

For the remaining 10 files: model on the AI-6.4 spec (transit: schedule_interpretation, route_comparison, driver_availability, adherence_reporting; knowledge: regulation_interpretation, shift_handover, incident_response; vault: search_patterns, bulk_operations, folder_organization). Pick 5–10 keywords each in both English and Latvian where applicable.

**Validation:** counts + parse smoke test:
```bash
ls app/core/agents/skills/transit/*.md | wc -l   # 5
ls app/core/agents/skills/knowledge/*.md | wc -l # 4
ls app/core/agents/skills/vault/*.md | wc -l     # 3
uv run python -c "from pathlib import Path; from app.core.agents.skill_loader import parse_skill_file; \
  [print('OK', p) if parse_skill_file(p) else exit(f'BAD {p}') for p in Path('app/core/agents/skills').rglob('*.md')]"
```

### Step 5 — `agent_result.py`
**File:** `app/core/agents/agent_result.py`

Public API — **dataclass only, no rendering helper**:
```python
VALID_DOMAINS: Final[frozenset[str]] = frozenset({"transit", "knowledge", "vault", "unified"})

@dataclass(frozen=True, slots=True)
class AgentResult:
    content: str                    # already-rendered response text (post _post_process)
    confidence: float | None        # 0.0–1.0; None when not measurable
    warnings: tuple[str, ...]       # METADATA ONLY — never rendered into content
    tools_used: tuple[str, ...]
    domain: str

    def __post_init__(self) -> None:
        # raise ValueError if domain not in VALID_DOMAINS
        # raise ValueError if confidence not None and not in [0.0, 1.0]
```

**Critical design note (preflight fix):** AgentResult.warnings is **metadata**. It is **not** rendered into the response content. The existing `BaseAgentService._post_process()` (`base.py:356–389`) already appends warnings as `⚠️` footnotes onto `response_text` *before* the AgentResult is built. If `to_chat_completion()` also appended warnings, they would render twice. We fix this by **not having a `to_chat_completion()` helper at all** — `chat()` keeps calling the existing `self._build_response(content=..., tier_model=...)` method (which is already overridden in `service.py:328` for `get_settings()` patchability). AgentResult lives alongside the response purely so the re-route gate has a clean object to inspect and so future consumers (logs, metrics, audit) can read structured fields.

**Implementation:**
- `__post_init__` is the only valid mutation hook on a frozen dataclass — both pyright and mypy accept it.
- No imports from `schemas.py` needed — this module is purely a data container.

**Validation:** `uv run ruff format app/core/agents/agent_result.py && uv run ruff check --fix app/core/agents/agent_result.py && uv run pyright app/core/agents/agent_result.py && uv run mypy app/core/agents/agent_result.py`

### Step 6 — Settings additions
**File:** `app/core/config.py`

Add to `Settings` (place near the other `agent_*` flags):
```python
    # AI-6.4 Progressive L3 skills
    agent_progressive_skills_enabled: bool = True
    # AI-6.5 Confidence-based re-routing
    agent_confidence_reroute_enabled: bool = True
    agent_confidence_reroute_threshold: float = 0.3
```
No env-var or secret involved — defaults are safe.

**Validation:** `uv run ruff format app/core/config.py && uv run ruff check --fix app/core/config.py && uv run pyright app/core/config.py && uv run mypy app/core/config.py`

### Step 7 — Extend `_PipelineOutcome` and rewire `BaseAgentService.chat()`
**File:** `app/core/agents/base.py`

**(a)** Extend `_PipelineOutcome` (around line 115) with two **optional, defaulted** fields:
- `confidence: float | None = None`
- `tools_used: tuple[str, ...] = ()`

Both are additive — no existing constructor call site needs updating. **Verify first** with `Grep "_PipelineOutcome(" app/core/agents/` (anti-pattern #11/#29).

**(b)** Add imports near the top of `base.py`:
```python
from app.core.agents.agent_result import AgentResult, VALID_DOMAINS
from app.core.agents.config import resolve_tier_model
```
(`get_settings` is already imported in `base.py`.)

**(c)** Rewrite the tail of `chat()` (lines ~220–238). The flow becomes: pipeline → AgentResult → re-route check → existing `_build_response()`. Concretely, after `final_text = self._post_process(...)`:

1. Build `result = AgentResult(content=final_text, confidence=outcome.confidence, warnings=tuple(outcome.warnings or ()), tools_used=outcome.tools_used, domain=self.agent_name if self.agent_name in VALID_DOMAINS else "unified")`.
2. **Confidence re-route gate** (single retry, hard cap):
   - `settings = get_settings()`
   - If `settings.agent_confidence_reroute_enabled` AND `result.confidence is not None` AND `result.confidence < settings.agent_confidence_reroute_threshold` AND `tier != "complex"`:
     - `complex_model = resolve_tier_model("complex")`; if `None`, skip.
     - `logger.info("agent.chat.confidence_reroute", domain=..., confidence=..., threshold=...)`
     - Call `retry_outcome = await self._execute(...same kwargs..., model=complex_model)` **exactly once**. Re-run `_post_process()` on the retry outcome. Rebuild `result` with the new content/confidence; `tier_model` is reassigned to `complex_model` for response labeling.
3. Build the response with the **existing** method: `response = self._build_response(content=result.content, tier_model=tier_model)`. **Do not** introduce a new helper — `_build_response()` already handles the `None` tier_model fallback to `f"{settings.llm_provider}:{settings.llm_model}"` (`base.py:425–455`).
4. Existing `agent.chat_completed` log line stays. Optionally extend it with `confidence=result.confidence` and `tools_used=result.tools_used` for observability.

**Why this preserves test compatibility:**
- `test_base.py:266–282` tests `_build_response()` directly — method definition is untouched.
- `test_base.py:305–320` (`test_chat_happy_path_drives_full_pipeline`) constructs `_FakeAgentService(warnings=[])` and asserts `response.choices[0].message.content == "RESPONSE"`. With `warnings=[]`, `_post_process` does not append footnotes, so `final_text == "RESPONSE"`, AgentResult.content == "RESPONSE", `_build_response` returns content unchanged. ✓
- `test_knowledge_agent.py:132` asserts `"\u26a0\ufe0f"` (⚠️) NOT in response — still true because we did not change the warning rendering in `_post_process`.

**(d)** Add a `model: Model | str | None = None` kwarg to the abstract `_execute()` signature on `BaseAgentService` — each subclass override (Steps 8–11) must accept it and pass it through to its `agent.run(...)` call (or wherever the model is selected). This is the wiring that makes the re-route work.

**(e)** Update the default `detect_relevant_skills(prompt)` docstring to mention `skill_loader.load_skills_within_budget()` and the `agent_progressive_skills_enabled` flag — but keep its body returning `""` (subclasses opt in).

**Anti-patterns to watch:**
- Do not add `# type: ignore` (#32). If pyright trips on the new optional fields, adjust types; do not suppress.
- Logging stays `domain.component.action_state`.
- Re-route is **at most one** extra LLM call — no recursive escalation.

**Validation:** `uv run ruff format app/core/agents/base.py && uv run ruff check --fix app/core/agents/base.py && uv run pyright app/core/agents/base.py && uv run mypy app/core/agents/base.py`

### Step 8 — `TransitAgent` integration
**File:** `app/core/agents/agents/transit.py`

**Modify (do not replace) the existing `detect_relevant_skills()` at line 186.** It currently does the flat DB skill load (lines 186–195). Keep that body intact and append the L3 layer:

```python
async def detect_relevant_skills(self, prompt: str) -> str:
    """Load flat DB skills + L3 progressive skills (both fail-open to '')."""
    parts: list[str] = []

    # Existing behavior: flat DB skill load (unchanged from current lines 186–195).
    try:
        async with AsyncSessionLocal() as db:
            skill_service = SkillService(db)
            flat = await skill_service.get_active_skills_content()
            if flat:
                parts.append(flat)
    except Exception:
        logger.warning("agent.skills_load_failed", exc_info=True)

    # New (AI-6.4): L3 progressive skill pack, gated by flag.
    if get_settings().agent_progressive_skills_enabled:
        try:
            l3 = load_skills_within_budget(
                domain="transit",
                prompt=prompt,
                budget=agent_budget_for("transit"),
            )
            if l3:
                parts.append(l3)
        except Exception:
            logger.warning("agent.l3_skills_load_failed", exc_info=True)

    return "\n\n".join(parts)
```

**Critical:** **do NOT** call `super().detect_relevant_skills(prompt)` — the base default returns `""` and would erase the flat-skill behavior. Inline the existing flat-skill block instead. (The pre-existing TODO `# NOTE: duplicated from AgentService; extract on AI-6.2.1` at line 184 stays — that extraction is out of scope for this plan.)

In `_execute()` (line 261), populate confidence and tools_used on the returned `_PipelineOutcome`:
- `tools_used = tuple(record.tool_name for record in tool_returns)` — `tool_returns` is already extracted by the existing QA path.
- `confidence` heuristic for transit: `1.0` when QA passed with no warnings, `0.6` when warnings only, `0.3` when QA had errors the correction loop resolved, otherwise `None`.

Add the `model: str | Model | None = None` kwarg to `_execute()` and pass through to the underlying Pydantic AI run. This signature must match the new abstract definition in `base.py:332` from Step 7d.

**Imports to add:**
```python
from app.core.agents.context_budget import agent_budget_for
from app.core.agents.skill_loader import load_skills_within_budget
```
(`get_settings`, `SkillService`, `AsyncSessionLocal`, `logger` are already imported.)

**Validation:** `uv run ruff format app/core/agents/agents/transit.py && uv run ruff check --fix app/core/agents/agents/transit.py && uv run pyright app/core/agents/agents/transit.py && uv run mypy app/core/agents/agents/transit.py`

### Step 9 — `KnowledgeAgent` integration
**File:** `app/core/agents/agents/knowledge.py`

**Add a new** `detect_relevant_skills()` override (knowledge agent currently inherits the base default `""`, so this is a fresh method, not a modification). Knowledge agent has historically not loaded flat DB skills — the new override only loads the L3 layer:

```python
async def detect_relevant_skills(self, prompt: str) -> str:
    if not get_settings().agent_progressive_skills_enabled:
        return ""
    try:
        return load_skills_within_budget(
            domain="knowledge", prompt=prompt, budget=agent_budget_for("knowledge"),
        )
    except Exception:
        logger.warning("agent.l3_skills_load_failed", exc_info=True)
        return ""
```

In `_execute()` (line 192), add the `model: str | Model | None = None` kwarg matching the new abstract signature, and populate:
- `tools_used = ("search_knowledge_base",)` when the tool was actually invoked (extract from the message history; empty tuple if the LLM answered without tool use).
- `confidence` from the RAG tool's top reranker score when available. The knowledge tool already returns reranker scores per result — capture the top score when extracting `tool_returns`. Fall back to `None` when the tool was not called.

**Imports to add:** `from app.core.agents.context_budget import agent_budget_for` + `from app.core.agents.skill_loader import load_skills_within_budget`. (`get_settings`, `logger` are already imported.)

**Validation:** `uv run ruff format app/core/agents/agents/knowledge.py && uv run ruff check --fix app/core/agents/agents/knowledge.py && uv run pyright app/core/agents/agents/knowledge.py && uv run mypy app/core/agents/agents/knowledge.py`

### Step 10 — `VaultAgent` integration
**File:** `app/core/agents/agents/vault.py`

**Add a new** `detect_relevant_skills()` override (same shape as the knowledge agent above, with `domain="vault"` and `agent_budget_for("vault")`). Vault agent also did not previously load flat DB skills.

In `_execute()` (line 201), add the `model` kwarg and populate:
- `tools_used = tuple(<tool names from message history>)`.
- `confidence`: `1.0` when no warnings, `0.5` when warnings present (vault tools are deterministic file ops, so the only signal is whether the response had QA warnings).

**Imports to add:** same two as Knowledge.

**Validation:** `uv run ruff format app/core/agents/agents/vault.py && uv run ruff check --fix app/core/agents/agents/vault.py && uv run pyright app/core/agents/agents/vault.py && uv run mypy app/core/agents/agents/vault.py`

### Step 11 — Unified `AgentService`
**File:** `app/core/agents/service.py`

**Modify (do not replace) the existing `detect_relevant_skills()` at line 130.** Same pattern as TransitAgent: keep the existing flat DB skill block intact, then append the L3 layer. The unified agent loads skills from **all three** L3 packs because it has access to all 11 tools.

Pseudocode:
1. Existing flat-skill load (lines 130–139) → append to `parts` if non-empty (wrap in `try/except` exactly as it is today).
2. If `agent_progressive_skills_enabled`: derive a per-domain sub-budget = `agent_budget_for("unified")` with `skill_docs_max = AGENT_BUDGETS["unified"].skill_docs_max // 3`. Call `load_skills_within_budget` for each of `transit`, `knowledge`, `vault` with that sub-budget, append the non-empty results to `parts`.
3. Return `"\n\n".join(parts)`.

**Critical:** do **not** call `super().detect_relevant_skills(prompt)` — same reason as Step 8.

In `_execute()` (line 213), add the `model` kwarg matching the new abstract signature in `base.py:332`. Populate confidence/tools_used using the same heuristic as `TransitAgent` (this is the most-used path; the unified service.py:_execute is the canonical implementation).

**Note on the `_build_response()` override** (`service.py:328`): leave it as-is. The plan keeps `chat()` calling `self._build_response(...)`, so this override is still active and `test_service.py` patches of `get_settings` continue to work.

**Imports to add:**
```python
from app.core.agents.context_budget import AGENT_BUDGETS, ContextBudget, agent_budget_for
from app.core.agents.skill_loader import load_skills_within_budget
```

**Validation:** `uv run ruff format app/core/agents/service.py && uv run ruff check --fix app/core/agents/service.py && uv run pyright app/core/agents/service.py && uv run mypy app/core/agents/service.py`

### Step 12 — `__init__.py` re-exports
**File:** `app/core/agents/__init__.py`
Add to `__all__` (or insert if missing):
```python
from app.core.agents.agent_result import AgentResult
from app.core.agents.context_budget import AGENT_BUDGETS, ContextBudget, agent_budget_for
```
Keep the existing exports intact.

**Validation:** `uv run ruff check app/core/agents/__init__.py && uv run pyright app/core/agents/__init__.py`

### Step 13 — Test conftest
**File:** `app/core/agents/tests/conftest.py` (new, ~40 lines)

Provide three helpers (all with `-> ReturnType` annotations — anti-pattern #7/#26):
- `make_agent_result(**overrides: Any) -> AgentResult` — defaults: `content="ok"`, `confidence=0.9`, `warnings=()`, `tools_used=()`, `domain="unified"`.
- `make_skill_meta(**overrides: Any) -> SkillMeta` — defaults: `name="test_skill"`, `priority=2`, `token_cost=100`, `keywords=("test",)`, `domain="transit"`.
- `tmp_skill_dir(tmp_path)` fixture — `mkdir`s `tmp_path/skills/{transit,knowledge,vault}/` and returns the `skills/` Path.

Plus an `autouse` fixture `_reset_skill_cache` (Generator) that calls `clear_cache()` before and after each test — copies the `_reset_singleton` idiom from `tests/test_metrics.py:44–49`.

**Validation:** `uv run pyright app/core/agents/tests/conftest.py && uv run mypy app/core/agents/tests/conftest.py`

### Step 14 — `test_context_budget.py`
**File:** `app/core/agents/tests/test_context_budget.py` — **5 tests**
1. `ContextBudget` is frozen (`pytest.raises(dataclasses.FrozenInstanceError)`).
2. `ContextBudget` defaults: `system_prompt_max=3000`, `skill_docs_max=2000`, etc.
3. `agent_budget_for("transit")` → 2500 skills cap.
4. `agent_budget_for("knowledge")` → 2000 cap.
5. `agent_budget_for("unknown")` → falls back to default `ContextBudget()` with `skill_docs_max=2000`.

**Validation:** `uv run pytest app/core/agents/tests/test_context_budget.py -v`

### Step 15 — `test_skill_loader.py`
**File:** `app/core/agents/tests/test_skill_loader.py` — **15+ tests** (matches AI-6.4 spec)

Use `tmp_skill_dir` and write skill markdown files inside it for each test.

Test groups:
1. **Front-matter parsing (5 tests)**
   - Valid front matter → `SkillMeta` populated correctly.
   - Missing front matter delimiter → returns `None` + logs warning.
   - Malformed YAML → returns `None` + logs warning.
   - YAML returning a list → returns `None`.
   - Invalid `priority` (e.g., 4) → returns `None`.
2. **Discovery (3 tests)**
   - `discover_skills("transit", root)` returns sorted list of valid skills only.
   - Empty directory → empty list.
   - Mixed valid + invalid files → only valid files returned.
3. **Keyword matching (2 tests)**
   - Skill with keyword matches lowercased prompt.
   - Skill with empty keywords always matches.
4. **Priority gating (3 tests)**
   - P1 skill always loaded even when budget is tight.
   - P3 skill skipped when remaining capacity < 70% (build a budget where this is forced).
   - P2 skill skipped when remaining capacity < 30%.
5. **Budget enforcement (2 tests)**
   - When two skills would exceed `skill_docs_max`, the cheaper-of-equal-priority wins (sort order).
   - Returned text contains `## <skill_name>` headers for every loaded skill.
6. **Integration with real skill files (2 tests)**
   - `load_skills_within_budget("knowledge", "what's the SOP for incident X?", budget)` includes `sop_retrieval` (P1, no keywords) and `incident_response`.
   - `load_skills_within_budget("transit", "is bus 12 delayed?", agent_budget_for("transit"))` includes `delay_analysis` but NOT `driver_availability`.

**Validation:** `uv run pytest app/core/agents/tests/test_skill_loader.py -v`

### Step 16 — `test_agent_result.py`
**File:** `app/core/agents/tests/test_agent_result.py` — **8+ tests**
1. `AgentResult` is frozen.
2. Construction with valid fields succeeds.
3. `domain="bogus"` raises `ValueError`.
4. `confidence=1.5` raises `ValueError`.
5. `confidence=None` is allowed.
6. `to_chat_completion(result, "claude-sonnet-4-5")` → `ChatCompletionResponse` with content + valid id.
7. Warnings appended as a "_Warnings:_" footnote in the response content.
8. **Re-route integration:** patch a `_FakeAgent` subclass so its first `_execute()` returns `confidence=0.2`, second returns `confidence=0.9`. Drive `chat()` and assert `_execute()` was called twice and the second call's content reaches the response. Use `models.ALLOW_MODEL_REQUESTS = False` and `agent.override(model=TestModel())` per the `test_base.py` precedent.

**Validation:** `uv run pytest app/core/agents/tests/test_agent_result.py -v`

### Step 17 — Sanity-run existing agent tests
After all edits, run the legacy agent tests to confirm the additive `_PipelineOutcome` changes and the new `chat()` plumbing did not regress AI-6.1/6.2/6.3 behavior:

```bash
uv run pytest app/core/agents/tests/ -v
```

If `test_transit_agent.py`, `test_knowledge_agent.py`, or `test_vault_agent.py` break because their assertions on `chat()` output change shape (the warnings footnote is new), update those assertions in the same step — do **not** add the footnote conditionally.

Anti-pattern reminder: when removing/renaming a response field, grep for it across `app/*/tests/` and update in the SAME step (anti-pattern #59). The footnote is additive, but the legacy tests may assert exact-string content.

## Preflight Warnings

From the test-scout pass, the following fragile patterns exist in nearby tests — **do not import these into new tests**:

1. **`test_routes.py:28` sets `limiter.enabled = False` at module level.** New tests should isolate via fixture, not module mutation. Anti-pattern #13 reminder.
2. **`test_base.py:38–84` `_FakeAgentService` records `execute_calls` as `list[dict[str, Any]]`.** New `_FakeBudgetAgent` for confidence re-routing must use a typed list, not `list[Any]`. Anti-pattern #28.
3. **`test_service.py:36` `models.ALLOW_MODEL_REQUESTS = False` at module level** — fine to copy, but place inside the new test files too so they fail fast if accidentally network-bound.
4. **`tests/test_metrics.py:44–49` `_reset_singleton` autouse fixture** — copy this idiom for `clear_cache()` (already done in Step 13 conftest).
5. **No `conftest.py` exists in `app/core/agents/tests/` today.** Step 13 introduces one — confirm it does not collide with `app/skills/tests/conftest.py` (different package, fine).
6. `_PipelineOutcome` constructor calls — grep before extending: `uv run grep -rn "_PipelineOutcome(" app/core/agents/` and verify all sites are kwargs-only (anti-pattern #11). Sites in service.py / agents/*.py / pipeline.py must be inspected.

## Security Checklist

- [ ] `yaml.safe_load` only — never `yaml.load`
- [ ] Skill file paths sandboxed under `Path(__file__).parent / "skills"` with `is_relative_to` check
- [ ] No `except: pass` — all loader failures log `agent.skill_loader.*` and fall back gracefully
- [ ] No prompt-string injection: keyword matching is `kw in prompt.lower()`, never compiled as regex
- [ ] `AgentResult.warnings` is plain text — never include exception tracebacks
- [ ] Re-routing capped at 1 extra LLM call per `chat()` — no unbounded escalation
- [ ] No new endpoints, no auth/RBAC changes required
- [ ] Settings defaults are safe (`agent_progressive_skills_enabled=True`, `agent_confidence_reroute_threshold=0.3`)
- [ ] `agent_confidence_reroute_enabled` flag allows rollback without code revert

## Verification

Final pyramid (run in order — each must pass before the next):

```bash
# 1. Syntax + format
uv run ruff format app/core/agents/
uv run ruff check --fix app/core/agents/

# 2. Types
uv run pyright app/core/agents/
uv run mypy app/core/agents/

# 3. New tests
uv run pytest app/core/agents/tests/test_context_budget.py \
              app/core/agents/tests/test_skill_loader.py \
              app/core/agents/tests/test_agent_result.py -v

# 4. Existing agent tests (regression)
uv run pytest app/core/agents/tests/ -v

# 5. Existing flat-skill feature (must still be 0/0 type errors)
uv run pyright app/skills/
uv run mypy app/skills/
uv run pytest app/skills/tests/ -v

# 6. Full unit suite
make test

# 7. Security audit
make security-audit-quick
```

**Acceptance gates:**
- [ ] `pyright app/core/agents/` ≤ **5** errors (baseline; new code adds 0)
- [ ] `mypy app/core/agents/` ≤ **3** errors (baseline; new code adds 0)
- [ ] `pyright app/skills/` = **0**, `mypy app/skills/` = **0**
- [ ] All 15+ skill-loader tests pass
- [ ] All 8+ AgentResult tests pass
- [ ] All 5 context-budget tests pass
- [ ] Existing 15 agent test files still green
- [ ] `make security-audit-quick` clean
- [ ] Manual smoke: with `agent_progressive_skills_enabled=True`, send a transit query about delays through `/v1/chat/completions`. Confirm `agent.skill_loader.loaded` log shows `delay_analysis` loaded, `driver_availability` skipped, and the response is well-formed
- [ ] Manual smoke: with a synthetic low-confidence response (use `TestModel` returning low-confidence outcome), confirm `agent.chat.confidence_reroute` log fires exactly once
- [ ] Token-usage comparison: capture skill-context length before/after for a transit-domain query and confirm ≥ 30% reduction (acceptance criterion from AI-6.4 spec)

## Open Questions / Decisions

1. **Token estimation method.** This plan uses `len(text) // 4` (matches existing `app/skills/schemas.py`) instead of adding `tiktoken` as a dependency. If finer granularity is needed later, swap in tiktoken behind the same `_estimate_tokens(text)` helper without API changes.
2. **Unified-agent budget split.** First pass divides `unified.skill_docs_max` evenly across the three domains. A smarter approach would weight by detected domain affinity from `AgentRouter.score()` — defer to a follow-up if metrics show unbalanced loading.
3. **Confidence heuristics.** Per-domain heuristics (1.0/0.6/0.3 for transit, reranker score for knowledge, 1.0/0.5 for vault) are intentionally rough. The point is to enable the re-route mechanism; tuning the heuristics to real telemetry is a follow-up once `agent.chat.confidence_reroute` log volume is observable.
