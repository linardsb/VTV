# Plan: AI-7.1 Synthetic Test Cases (Agent Eval Foundation)

## Context

Build the foundation of the agent eval framework: **30 hand-authored YAML test cases** (15 transit + 10 knowledge + 5 vault) plus a **loader/validator** that parses, schema-validates, and exposes them as immutable `EvalCase` objects. AI-7.1 ships only the cases + loader; the runner, judges, and regression baselines arrive in AI-7.2/7.3.

Each case carries: `id`, `prompt`, `language`, `expected_tools`, `expected_domain`, `quality_criteria` (exactly 5 binary checks), and an optional `notes` field. Cases must reference real tool function names, plausible domain entities, and exercise the LV-first / EN-fallback language rules baked into the agent system prompts.

**Why now:** Without test cases, prompt/model/RAG changes silently regress quality. AI-6.5's confidence re-route gate, AI-6.4's progressive skills, and AI-6.3's auto-router are all live and need an objective regression signal before further tuning.

## Security Context Assessment

| Context | Active? | Why |
|---|---|---|
| **CTX-AGENT** | ✅ | This IS agent infrastructure. Loader output feeds the eval runner that drives `AgentService.chat()` |
| **CTX-FILE** | ✅ (light) | YAML files loaded from disk — must use `yaml.safe_load`, sandbox via `Path.is_relative_to`, fail-open on parse errors. Mirror `skill_loader.py` exactly |
| **CTX-INPUT** | ✅ (light) | `EvalCase` schema validation rejects malformed cases |
| CTX-AUTH | ❌ | No new endpoints, no auth touched |
| CTX-RBAC | ❌ | No HTTP routes added in AI-7.1 |
| CTX-INFRA | ❌ | No Docker/nginx/CORS changes |

**Concrete requirements applied:**
- `yaml.safe_load` only — never `yaml.load` (CTX-FILE).
- Path sandbox: every case file must resolve under `app/core/agents/evals/cases/` via `Path.is_relative_to` (CTX-FILE).
- Loader is fail-open: malformed file → log warning + skip, never raise (CTX-AGENT — eval infra must not crash anything that imports it).
- No raw prompts logged at INFO; only file paths and counts.

## Research Summary

### Agent tool inventory (exact function names — must match `expected_tools` in YAML)

**Transit (5 tools)** — registered in `app/core/agents/agents/transit.py:154-160`
- `query_bus_status` — real-time vehicle/route/stop status, delays, positions
- `get_route_schedule` — timetable by route/date/direction
- `search_stops` — name search OR proximity search (lat/lon)
- `get_adherence_report` — on-time performance metrics
- `check_driver_availability` — driver staffing queries

**Knowledge (1 tool)** — registered in `app/core/agents/agents/knowledge.py`
- `search_knowledge_base` — hybrid vector+fulltext RAG with citations + confidence threshold + RAG-router gate

**Vault (4 tools)** — registered in `app/core/agents/agents/vault.py`
- `obsidian_query_vault` — search/tags/list/recent/glob
- `obsidian_manage_notes` — CRUD + frontmatter/section editing
- `obsidian_manage_folders` — folder CRUD (delete requires `confirm: true`)
- `obsidian_bulk_operations` — batch ops with `dry_run` preview

### Reference patterns (mirror these exactly)

| Pattern | Source | Why we copy it |
|---|---|---|
| YAML front matter parser | `app/core/agents/skill_loader.py:83-96` (`_parse_yaml_mapping`) | Same `yaml.safe_load` + dict-coercion shape |
| Frozen dataclass + `__post_init__` validation | `app/core/agents/agent_result.py:21-49` | `EvalCase` mirrors this exactly |
| File loader with path sandbox | `app/core/agents/skill_loader.py:228-255` (`_discover_skills_uncached`) | Same `is_relative_to` pattern |
| Fail-open per-file loop | `skill_loader.py:241-254` | Bad case file logs warning, others still load |
| Frozen dataclass + slots | `skill_loader.py:38-56` (`SkillMeta`) | Memory + immutability |
| Conftest fixtures | `app/core/agents/tests/conftest.py:53-67` | Add `tmp_eval_dir` + `make_eval_case` next to `tmp_skill_dir` + `make_skill_meta` |
| Test file structure | `app/core/agents/tests/test_skill_loader.py` | Closest analog — file load + schema validation |

### System prompt language conventions (drives test case authoring)

- **All three agents are Latvian-first.** Default response language = LV. If user writes EN, respond EN.
- Transit prompt explicitly handles diacriticless input: `'marsruti' = maršruti`, `'kavejas' = kavējas`, `'kave' ≠ coffee`.
- Tool outputs are English; agent translates to user language.
- Knowledge agent enforces citation format `[title](/lv/documents/{id})` or `[title](/en/documents/{id})`.
- Vault agent enforces "delete requires confirm: true" + "bulk_operations should preview via dry_run first".

### Auto-router (AI-6.3) signals — design cases to route correctly

Located in `app/core/agents/router.py`. Cases should hit the right keyword bucket:
- **Transit:** `maršrut`, `marsrut`, `pietur`, `autobus`, `kavēj`, `reis`, `grafik`, `route`, `stop`, `delay`, `bus`, `schedule`, `departure`
- **Knowledge:** `dokument`, `noteikum`, `procedūr`, `regul`, `policy`, `document`, `procedure`, `regulation`, `compliance`
- **Vault:** `vault`, `obsidian`, `piezīm`, `note`, `folder`, `tag`

### Realistic domain entities for prompts

- **Transit:** route IDs `"22"`, `"bus_22"`; stop names `"Centrāltirgus"`, `"Stacijas laukums"`; vehicle IDs 4-digit; ISO dates; HH:MM times (incl. 24:30 overnight).
- **Knowledge:** doc types Policy / SOP / Regulation / Driver Record / Internal Communication; example ID `42`; mixed LV/EN corpus.
- **Vault:** note paths `"folder/My Note.md"`; kebab-case tags `"transit-ops"`, `"incident-response"`; YAML frontmatter `title`, `tags`, `created`, `updated`.

### Existing eval infrastructure

**None.** `app/core/agents/evals/` does not exist yet. AI-7.1 creates it from scratch.

## Test Landscape

- `app/core/agents/tests/conftest.py` already exists (untracked in git). Has `make_agent_result`, `make_skill_meta`, `tmp_skill_dir`, and `_reset_skill_cache` autouse fixture. AI-7.1 will **add** to this file, not replace.
- 19 test files in `app/core/agents/tests/`. The closest analog to AI-7.1 is `test_skill_loader.py` (file load + dataclass validation + fail-open). Mirror its structure.
- Convention: explicit per-case `def test_*()` functions; **no `pytest.mark.parametrize`** in this area. Follow that.
- All agent tests set `models.ALLOW_MODEL_REQUESTS = False` — but AI-7.1 loader never invokes the agent, so we don't need it.
- `_reset_skill_cache` autouse fixture is already in conftest. AI-7.1 will add a parallel `_reset_eval_cache` autouse fixture (only if the loader uses module-level caching — see Decision below).

## Type Check Baseline

Pre-existing errors in `app/core/agents/` (unrelated to AI-7.1's new files):

| Tool | Errors | Files |
|---|---|---|
| **pyright** | 5 | `pipeline.py:47,49,136,136` (4) + `tools/transit/client.py:193` (1) |
| **mypy** | 3 | `tools/transit/static_store.py:149,150` (2) + `pipeline.py:136` (1) |

**Acceptance:** post-implementation pyright errors ≤ 5 and mypy errors ≤ 3 in `app/core/agents/`. New files (`evals/*.py`, `tests/test_eval_loader.py`) must contribute **zero** new errors.

**PyYAML:** v6.0.3 installed; `pyyaml>=6.0` declared in `pyproject.toml:29`.

**types-PyYAML:** explicitly NOT installed (`pyproject.toml:177` comment: "treat as untyped"). Mirror `skill_loader.py:17` pyright file-level directive: `# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false`.

## Key Decisions

1. **One YAML file per domain, not one per case.** Lower file count, faster iteration, mirrors how email-hub structures eval suites. Each file is a `cases:` list at the top level.
2. **Frozen dataclass + `__post_init__` validation, NOT Pydantic.** Mirrors `SkillMeta` and `AgentResult` exactly — keeps the agent module dependency-light and gives slot efficiency.
3. **No module-level cache in the loader.** Cases are loaded once at runner startup; caching adds complexity for zero benefit at this stage. Skip the `_reset_eval_cache` fixture entirely.
4. **`expected_tools` is a list of strings, not a set or enum.** Strings allow YAML to round-trip cleanly; the loader validates each entry against `KNOWN_TOOLS` (a hardcoded frozenset of all 10 unique tool names).
5. **`quality_criteria` is exactly 5 entries per case.** Validated in `__post_init__`. Each criterion has `name: str` + `description: str` (free text — actual binary checks land in AI-7.2 with the judges).
6. **`expected_domain` field on every case** (`"transit" | "knowledge" | "vault"`). Lets the eval runner verify AI-6.3's auto-router classifies the prompt correctly.
7. **`id` field is the primary key.** Pattern `{domain}_{NNN}` (e.g. `transit_001`). Loader rejects duplicate IDs across the suite and returns them as warnings.
8. **No mock/fixture data files.** Test cases live in production `evals/cases/` directory and are also what `test_eval_loader.py` loads (round-trip integrity test).

## Files to Create/Modify

| Action | File | Purpose |
|---|---|---|
| CREATE | `app/core/agents/evals/__init__.py` | Empty package marker |
| CREATE | `app/core/agents/evals/schemas.py` | `EvalCase` + `QualityCriterion` frozen dataclasses + `KNOWN_TOOLS` + `VALID_DOMAINS` + `VALID_LANGUAGES` |
| CREATE | `app/core/agents/evals/loader.py` | `parse_eval_file()`, `load_eval_cases()`, `load_all_cases()`, `clear_cache()` (no-op stub for symmetry) |
| CREATE | `app/core/agents/evals/cases/transit.yaml` | 15 transit test cases |
| CREATE | `app/core/agents/evals/cases/knowledge.yaml` | 10 knowledge test cases |
| CREATE | `app/core/agents/evals/cases/vault.yaml` | 5 vault test cases |
| CREATE | `app/core/agents/tests/test_eval_loader.py` | Schema + loader tests + production-suite integrity |
| UPDATE | `app/core/agents/tests/conftest.py` | Add `make_eval_case()` factory + `tmp_eval_dir` fixture |
| UPDATE | `app/core/agents/CLAUDE.md` | Append `evals/` to directory tree + 1-line description under "Planned Improvements" item 6 |

## Implementation Steps

### Step 1 — `app/core/agents/evals/__init__.py`

Empty package marker (single docstring line).

```python
"""Agent eval framework (AI-7.x)."""
```

**Validation:** `uv run ruff check app/core/agents/evals/__init__.py`

---

### Step 2 — `app/core/agents/evals/schemas.py`

Frozen dataclasses + constants. Mirror `app/core/agents/agent_result.py` and `app/core/agents/skill_loader.py:38-56` exactly.

Required content:

```python
"""Eval framework schemas (AI-7.1).

Frozen dataclasses representing one synthetic test case for the agent
suite. Validation happens in __post_init__ — fail-fast on bad data so
the loader can skip the offending file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


VALID_DOMAINS: Final[frozenset[str]] = frozenset({"transit", "knowledge", "vault"})
VALID_LANGUAGES: Final[frozenset[str]] = frozenset({"lv", "en", "lv_diacriticless", "mixed"})

# Mirrors the exact tool function names registered in
# app/core/agents/agents/{transit,knowledge,vault}.py
KNOWN_TOOLS: Final[frozenset[str]] = frozenset({
    # transit (5)
    "query_bus_status", "get_route_schedule", "search_stops",
    "get_adherence_report", "check_driver_availability",
    # knowledge (1)
    "search_knowledge_base",
    # vault (4)
    "obsidian_query_vault", "obsidian_manage_notes",
    "obsidian_manage_folders", "obsidian_bulk_operations",
})

REQUIRED_CRITERIA_COUNT: Final[int] = 5


@dataclass(frozen=True, slots=True)
class QualityCriterion:
    name: str
    description: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("QualityCriterion.name must be non-empty")
        if not self.description or not self.description.strip():
            raise ValueError("QualityCriterion.description must be non-empty")


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    prompt: str
    language: str
    expected_domain: str
    expected_tools: tuple[str, ...]
    quality_criteria: tuple[QualityCriterion, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.id.strip():
            raise ValueError("EvalCase.id must be non-empty")
        if not self.prompt or not self.prompt.strip():
            raise ValueError(f"EvalCase[{self.id}].prompt must be non-empty")
        if self.language not in VALID_LANGUAGES:
            raise ValueError(
                f"EvalCase[{self.id}].language={self.language!r} not in {sorted(VALID_LANGUAGES)}"
            )
        if self.expected_domain not in VALID_DOMAINS:
            raise ValueError(
                f"EvalCase[{self.id}].expected_domain={self.expected_domain!r} "
                f"not in {sorted(VALID_DOMAINS)}"
            )
        if len(self.quality_criteria) != REQUIRED_CRITERIA_COUNT:
            raise ValueError(
                f"EvalCase[{self.id}] must have exactly {REQUIRED_CRITERIA_COUNT} "
                f"quality_criteria, got {len(self.quality_criteria)}"
            )
        unknown = [t for t in self.expected_tools if t not in KNOWN_TOOLS]
        if unknown:
            raise ValueError(
                f"EvalCase[{self.id}].expected_tools contains unknown tools: {unknown}"
            )


__all__ = [
    "KNOWN_TOOLS",
    "REQUIRED_CRITERIA_COUNT",
    "VALID_DOMAINS",
    "VALID_LANGUAGES",
    "EvalCase",
    "QualityCriterion",
]
```

**Validation:** `uv run ruff format app/core/agents/evals/schemas.py && uv run ruff check --fix app/core/agents/evals/schemas.py && uv run pyright app/core/agents/evals/schemas.py && uv run mypy app/core/agents/evals/schemas.py`

---

### Step 3 — `app/core/agents/evals/loader.py`

YAML parser + sandboxed file discovery. Mirror `skill_loader.py:83-96` and `:228-255`.

Top of file:

```python
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
```

API surface:

```python
def parse_eval_file(path: Path) -> list[EvalCase] | None:
    """Parse one YAML eval file → list[EvalCase] or None on any failure.

    Logs ``agent.evals.loader.<reason>`` at WARNING and returns None on:
      - read error / OSError
      - yaml.YAMLError
      - top-level not a dict OR missing 'cases' key
      - 'cases' value not a list
    Individual case validation errors are logged per-case but do NOT
    fail the whole file — bad cases are skipped, good ones returned.
    """

def load_eval_cases(
    domain: str,
    *,
    cases_root: Path | None = None,
) -> list[EvalCase]:
    """Load all cases for one domain from <cases_root>/<domain>.yaml.

    Path-sandboxed via Path.is_relative_to. Returns [] on missing file
    or any failure (fail-open).
    """

def load_all_cases(
    *,
    cases_root: Path | None = None,
) -> dict[str, list[EvalCase]]:
    """Load all three domains. Logs the per-domain count + total.

    Detects duplicate ``id`` across the suite — duplicates land in
    ``agent.evals.loader.duplicate_ids`` warning but are kept as-is
    (loader is fail-open; eval runner can decide to dedupe).
    """
```

Internal helpers (mirror `skill_loader.py`):
- `_CASES_ROOT: Final[Path] = Path(__file__).parent / "cases"`
- `_parse_yaml_mapping(raw: str) -> dict[str, Any] | None` — exact copy of `skill_loader._parse_yaml_mapping`
- `_build_case(raw: dict[str, Any], file_path: Path) -> EvalCase | None` — coerce + try/except `EvalCase(...)` → log + None on failure
- `_build_criteria(raw_list: object) -> tuple[QualityCriterion, ...] | None` — coerce list-of-dict → tuple-of-QualityCriterion

Path sandbox (must mirror `skill_loader.py:243-249`):
```python
domain_file = (cases_root / f"{domain}.yaml").resolve()
root_resolved = cases_root.resolve()
if not domain_file.is_relative_to(root_resolved):
    logger.warning("agent.evals.loader.path_escaped", path=str(domain_file))
    return []
```

`__all__` exports: `parse_eval_file`, `load_eval_cases`, `load_all_cases`.

**Validation:** `uv run ruff format app/core/agents/evals/loader.py && uv run ruff check --fix app/core/agents/evals/loader.py && uv run pyright app/core/agents/evals/loader.py && uv run mypy app/core/agents/evals/loader.py`

---

### Step 4 — `app/core/agents/evals/cases/transit.yaml`

15 cases. YAML schema (one entry shown — repeat for all 15):

```yaml
cases:
  - id: transit_001
    prompt: "Kuri maršruti šobrīd kavējas?"
    language: lv
    expected_domain: transit
    expected_tools:
      - query_bus_status
    quality_criteria:
      - name: factual_accuracy
        description: All delay claims trace to query_bus_status output, no fabricated routes.
      - name: language_correctness
        description: Response in Latvian with correct diacritics (kavējas, maršruti).
      - name: actionability
        description: Lists specific routes + delay magnitudes a dispatcher can act on.
      - name: data_freshness
        description: Notes timestamp; flags if data is >5min stale.
      - name: completeness
        description: All currently delayed routes mentioned, not a sample.
    notes: Baseline LV delay query — most common dispatcher request.
```

**Required coverage across the 15 transit cases** (each row = one case ID; pick prompts that distinctly hit the criterion):

| ID | Coverage | Lang | Expected tools |
|---|---|---|---|
| `transit_001` | LV delay query (baseline) | `lv` | `query_bus_status` |
| `transit_002` | EN delay query (language match) | `en` | `query_bus_status` |
| `transit_003` | Diacriticless LV input ("Kuri marsruti kavejas?") | `lv_diacriticless` | `query_bus_status` |
| `transit_004` | Specific route status (route 22) | `lv` | `query_bus_status` |
| `transit_005` | Stop search by name ("Centrāltirgus") | `lv` | `search_stops` |
| `transit_006` | Stop search by proximity (lat/lon) | `en` | `search_stops` |
| `transit_007` | Cross-tool: stop search → next departures at that stop | `lv` | `search_stops`, `query_bus_status` |
| `transit_008` | Schedule by route + date | `lv` | `get_route_schedule` |
| `transit_009` | Schedule by route + direction | `en` | `get_route_schedule` |
| `transit_010` | Adherence report interpretation (single route) | `lv` | `get_adherence_report` |
| `transit_011` | Multi-route adherence comparison | `lv` | `get_adherence_report` |
| `transit_012` | Driver availability (head count for shift) | `lv` | `check_driver_availability` |
| `transit_013` | Driver availability + schedule cross-ref | `lv` | `check_driver_availability`, `get_route_schedule` |
| `transit_014` | **Non-existent route handling** ("kā ir ar maršrutu 999?") | `lv` | `query_bus_status` |
| `transit_015` | **Mixed LV/EN prompt** (code-switching dispatcher) | `mixed` | `query_bus_status`, `get_route_schedule` |

Each case must specify exactly 5 `quality_criteria`. Reuse the same 5 names across transit cases for comparability:
1. `factual_accuracy` — claims trace to tool output
2. `language_correctness` — diacritics + language match
3. `actionability` — concrete next steps for dispatcher
4. `data_freshness` — flags stale data
5. `completeness` — all relevant tools invoked, no sampling

**Validation:** `uv run python -c "import yaml; d=yaml.safe_load(open('app/core/agents/evals/cases/transit.yaml')); assert len(d['cases'])==15, f'expected 15, got {len(d[\"cases\"])}'"`

Then load through the new loader: `uv run python -c "from app.core.agents.evals.loader import load_eval_cases; cases=load_eval_cases('transit'); assert len(cases)==15; print(f'transit: {len(cases)} cases OK')"`

---

### Step 5 — `app/core/agents/evals/cases/knowledge.yaml`

10 cases. Same structure as transit.yaml. Note: knowledge has only **one** tool (`search_knowledge_base`) — every case's `expected_tools` will be `[search_knowledge_base]`.

| ID | Coverage | Lang | Notes |
|---|---|---|---|
| `knowledge_001` | SOP retrieval with citation | `lv` | Should cite `[Title](/lv/documents/{id})` |
| `knowledge_002` | Regulation interpretation | `lv` | Multi-clause regulation lookup |
| `knowledge_003` | "No relevant docs" honesty | `lv` | Prompt about something not in corpus → must say "I don't know" |
| `knowledge_004` | Cross-lingual: LV question, EN document | `lv` | Tests retrieval across languages |
| `knowledge_005` | Cross-lingual: EN question, LV document | `en` | Mirror of 004 |
| `knowledge_006` | Temporal relevance (recent vs old SOP) | `lv` | Two SOPs with same topic, different dates |
| `knowledge_007` | Multi-doc synthesis (regulation + SOP) | `lv` | Should cite both |
| `knowledge_008` | Diacriticless LV knowledge query | `lv_diacriticless` | "kadi ir vaditaja noteikumi?" |
| `knowledge_009` | EN policy lookup | `en` | Direct policy retrieval |
| `knowledge_010` | Citation format check | `lv` | Verifies `[title](/lv/documents/{id})` format compliance |

5 quality criteria for knowledge:
1. `factual_accuracy` — every claim traces to a retrieved document
2. `citation_quality` — links use the required `[title](/{lang}/documents/{id})` format
3. `grounding` — no results → explicit "no relevant documents" not speculation
4. `language_correctness` — diacritics + matches user language
5. `honesty` — explicit uncertainty when confidence is low

---

### Step 6 — `app/core/agents/evals/cases/vault.yaml`

5 cases. Same structure.

| ID | Coverage | Lang | Expected tools |
|---|---|---|---|
| `vault_001` | Note search by tag | `lv` | `obsidian_query_vault` |
| `vault_002` | Note creation with frontmatter | `lv` | `obsidian_manage_notes` |
| `vault_003` | **Safe deletion** — must request `confirm: true` | `lv` | `obsidian_manage_notes` |
| `vault_004` | **Bulk operation with `dry_run` preview first** | `en` | `obsidian_bulk_operations` |
| `vault_005` | Folder organization (list + reorganize) | `lv` | `obsidian_query_vault`, `obsidian_manage_folders` |

5 quality criteria for vault:
1. `operation_correctness` — paths valid, content preserved
2. `safety` — deletion previewed + confirmation requested
3. `completeness` — all matching notes returned
4. `language_correctness` — language match + diacritics
5. `formatting` — valid YAML frontmatter, clean markdown

---

### Step 7 — `app/core/agents/tests/conftest.py` (UPDATE)

Append `make_eval_case` factory + `tmp_eval_dir` fixture. Do NOT add an autouse cache reset (loader has no cache — see Decision #3).

```python
# --- AI-7.1 eval case factories -----------------------------------------

from app.core.agents.evals.schemas import EvalCase, QualityCriterion


def make_quality_criterion(**overrides: Any) -> QualityCriterion:
    """Return a QualityCriterion with safe defaults for tests."""
    defaults: dict[str, Any] = {
        "name": "factual_accuracy",
        "description": "Stub description for tests.",
    }
    defaults.update(overrides)
    return QualityCriterion(**defaults)


def make_eval_case(**overrides: Any) -> EvalCase:
    """Return an EvalCase with safe defaults for tests (5 stub criteria)."""
    defaults: dict[str, Any] = {
        "id": "test_001",
        "prompt": "Test prompt",
        "language": "lv",
        "expected_domain": "transit",
        "expected_tools": ("query_bus_status",),
        "quality_criteria": tuple(
            make_quality_criterion(name=f"criterion_{i}") for i in range(5)
        ),
        "notes": "",
    }
    defaults.update(overrides)
    return EvalCase(**defaults)


@pytest.fixture
def tmp_eval_dir(tmp_path: Path) -> Path:
    """Create an empty cases/ directory under tmp_path and return it."""
    root = tmp_path / "cases"
    root.mkdir(parents=True, exist_ok=True)
    return root
```

**Note:** the existing `from typing import Any` import already covers `Any`. The existing `Path` import covers `Path`. The new `EvalCase`/`QualityCriterion` imports are the only additions needed at the top.

**Validation:** `uv run ruff format app/core/agents/tests/conftest.py && uv run ruff check --fix app/core/agents/tests/conftest.py && uv run pyright app/core/agents/tests/conftest.py`

---

### Step 8 — `app/core/agents/tests/test_eval_loader.py`

Test file mirroring `test_skill_loader.py` structure. Required coverage:

**Schema validation (no I/O):**
- `test_eval_case_valid_minimal` — happy path with `make_eval_case()`
- `test_eval_case_rejects_empty_id`
- `test_eval_case_rejects_empty_prompt`
- `test_eval_case_rejects_unknown_language`
- `test_eval_case_rejects_unknown_domain`
- `test_eval_case_rejects_wrong_criteria_count` — 4 and 6 both fail
- `test_eval_case_rejects_unknown_tool` — `expected_tools=("not_a_tool",)` raises
- `test_eval_case_accepts_empty_expected_tools` — agent might answer from memory; allowed
- `test_quality_criterion_rejects_empty_name`
- `test_quality_criterion_rejects_empty_description`
- `test_eval_case_is_frozen` — assigning to a field raises `dataclasses.FrozenInstanceError`

**YAML loader (file I/O via `tmp_eval_dir` + `_write` helper from `test_skill_loader.py`):**
- `test_parse_eval_file_valid` — happy path: write a valid 1-case YAML, parse, get 1 EvalCase
- `test_parse_eval_file_missing_returns_none` — non-existent path
- `test_parse_eval_file_malformed_yaml_returns_none`
- `test_parse_eval_file_top_level_not_dict_returns_none` — `cases:` is a list at the top
- `test_parse_eval_file_missing_cases_key_returns_none`
- `test_parse_eval_file_cases_not_a_list_returns_none`
- `test_parse_eval_file_skips_invalid_case_keeps_valid` — 2 cases, one with bad domain → returns 1
- `test_load_eval_cases_missing_file_returns_empty`
- `test_load_eval_cases_path_traversal_blocked` — attempt `../etc/passwd` → returns `[]` and logs `path_escaped`
- `test_load_all_cases_loads_three_domains`
- `test_load_all_cases_detects_duplicate_ids` — write same ID across two domain files, verify warning is logged

**Production-suite integrity (loads the real `evals/cases/` files):**
- `test_production_transit_has_15_cases` — `load_eval_cases("transit")` returns exactly 15
- `test_production_knowledge_has_10_cases`
- `test_production_vault_has_5_cases`
- `test_production_all_case_ids_are_unique` — no dupes across the full suite
- `test_production_all_cases_have_5_criteria` — implicit (already enforced by `__post_init__`), but test the count via `load_all_cases()`
- `test_production_every_known_tool_appears_at_least_once` — verifies coverage breadth (all 10 tool names show up across the suite)

Use the `_write` helper from `test_skill_loader.py:` (copy the 4-line dedent helper). Use `tmp_eval_dir` fixture from conftest. Every test function annotated `-> None`.

**Top-of-file pyright directive** (mirror `skill_loader.py:17` because YAML is untyped):
```python
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false
```

**Validation per file:**
```bash
uv run ruff format app/core/agents/tests/test_eval_loader.py
uv run ruff check --fix app/core/agents/tests/test_eval_loader.py
uv run pyright app/core/agents/tests/test_eval_loader.py
uv run pytest app/core/agents/tests/test_eval_loader.py -v
```

---

### Step 9 — `app/core/agents/CLAUDE.md` (UPDATE)

Two surgical edits:

1. Append after the `skills/` line in the directory tree (around line 41 of CLAUDE.md):
   ```
   ├── evals/             # AI-7.1: synthetic eval cases (YAML) + loader. 15 transit + 10 knowledge + 5 vault cases. Frozen `EvalCase` dataclass with `__post_init__` validation; loader is fail-open and path-sandboxed (mirrors skill_loader.py).
   ```

2. Replace the "6. Eval framework" line under "Planned Improvements" with:
   ```
   6. **Eval framework** — ✅ AI-7.1: 30 synthetic cases (15 transit + 10 knowledge + 5 vault) under `evals/cases/`, fail-open YAML loader with `EvalCase` schema validation. Pending AI-7.2: binary LLM judges + TPR/TNR calibration. Pending AI-7.3: regression baselines + CI gating.
   ```

**Validation:** none — markdown only.

## Preflight Warnings

From the test scout review of nearby code:

1. **Don't use `pytest.mark.parametrize`** — agent tests use explicit per-case `def test_*()` functions for readability. Follow that.
2. **Don't add `type: ignore` in test files** — mypy is relaxed for tests; use file-level pyright directives instead. (anti-pattern #14)
3. **Test helper functions need return type annotations** — `make_eval_case() -> EvalCase`, `_write() -> Path`. (anti-pattern #7)
4. **`from datetime import date` would shadow nothing here** — no `date` field in `EvalCase`, so safe. (anti-pattern #39 N/A)
5. **YAML lib is untyped** — file-level pyright directive required on `loader.py` and on `test_eval_loader.py` (every file that imports yaml).
6. **`yaml.safe_load` only** — never `yaml.load`. (CTX-FILE)
7. **`Path.is_relative_to`** — must call `.resolve()` on BOTH sides before comparing. (mirror `skill_loader.py:243-249`)
8. **No `assert` in production code** — only allowed in test files. `loader.py` and `schemas.py` use `if ... raise ValueError`. (anti-pattern #1)
9. **Don't import yaml at module top of `schemas.py`** — only `loader.py` needs it. Keeps schemas free of the untyped-lib pyright pollution.
10. **EN DASH ban** — keep all dashes in YAML files as `-` (U+002D), never `–`. (anti-pattern #8)

## Security Checklist

This task creates **no endpoints**. The non-endpoint security requirements that apply:

- [x] `yaml.safe_load` only (no arbitrary deserialization) — CTX-FILE
- [x] Path sandbox via `Path.is_relative_to` after `.resolve()` on both sides — CTX-FILE
- [x] Loader is fail-open: bad file → log + skip, never raise — CTX-AGENT (eval infra must not crash production code that imports it)
- [x] No raw prompts logged at INFO; only file paths + counts
- [x] `EvalCase.__post_init__` rejects unknown tool names, languages, domains
- [x] Test cases are static checked-in YAML, no user-provided input at runtime
- [x] No credentials, tokens, or connection strings in any case prompt or note

## Verification

Run from repo root:

```bash
# 1. Static + type checks (must add ZERO new errors)
uv run ruff format app/core/agents/evals/ app/core/agents/tests/test_eval_loader.py
uv run ruff check --fix app/core/agents/evals/ app/core/agents/tests/test_eval_loader.py
uv run pyright app/core/agents/  # ≤ 5 errors (baseline)
uv run mypy app/core/agents/     # ≤ 3 errors (baseline)

# 2. New tests pass
uv run pytest app/core/agents/tests/test_eval_loader.py -v

# 3. Full agent test suite still green (no regressions in conftest changes)
uv run pytest app/core/agents/tests/ -x

# 4. Round-trip: production cases load cleanly
uv run python -c "
from app.core.agents.evals.loader import load_all_cases
suite = load_all_cases()
counts = {k: len(v) for k, v in suite.items()}
print(counts)
assert counts == {'transit': 15, 'knowledge': 10, 'vault': 5}, counts
all_ids = [c.id for cs in suite.values() for c in cs]
assert len(all_ids) == len(set(all_ids)), 'duplicate IDs'
print(f'OK — {len(all_ids)} unique cases')
"

# 5. Make-level checks
make check
make security-audit-quick
```

## Acceptance Criteria

- [ ] `app/core/agents/evals/cases/transit.yaml` exists with exactly 15 cases covering the 15-row matrix in Step 4
- [ ] `app/core/agents/evals/cases/knowledge.yaml` exists with exactly 10 cases per Step 5 matrix
- [ ] `app/core/agents/evals/cases/vault.yaml` exists with exactly 5 cases per Step 6 matrix
- [ ] Every case has exactly 5 `quality_criteria`
- [ ] Every case's `expected_tools` references only names in `KNOWN_TOOLS`
- [ ] All 30 case `id` values are globally unique
- [ ] All 10 unique tool names appear in `expected_tools` of at least one case across the suite
- [ ] `load_all_cases()` returns `{"transit": 15, "knowledge": 10, "vault": 5}` with no warnings
- [ ] `parse_eval_file()` returns `None` for malformed YAML and skips invalid individual cases inside an otherwise-valid file
- [ ] Path traversal attempts in `load_eval_cases()` return `[]` and log `agent.evals.loader.path_escaped`
- [ ] `EvalCase` and `QualityCriterion` are frozen — assignment raises `FrozenInstanceError`
- [ ] Pyright + mypy error counts in `app/core/agents/` unchanged from baseline (5 / 3)
- [ ] `test_eval_loader.py` contains all schema + loader + production-integrity tests listed in Step 8
- [ ] `app/core/agents/CLAUDE.md` updated with `evals/` directory entry + Planned Improvements item 6 status
- [ ] No new endpoints, no auth changes, no migrations
