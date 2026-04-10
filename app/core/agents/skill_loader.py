"""Progressive L3 skill loader (AI-6.4).

Loads markdown skill files with YAML front matter from the in-repo
``app/core/agents/skills/{domain}/`` tree and returns a formatted block for
injection into the agent's system prompt. Priority-gated, token-budget-aware,
and fail-open: every failure logs and returns ``None``/``""`` rather than
raising, so a broken skill file can never take the chat pipeline down.

Security:
    * YAML parsing uses ``yaml.safe_load`` exclusively.
    * Skill file paths are sandboxed under ``Path(__file__).parent / "skills"``
      via ``Path.is_relative_to`` before any read.
    * Keyword matching is substring-only on ``prompt.lower()`` — never
      compiled as regex.
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import yaml

from app.core.agents.context_budget import ContextBudget
from app.core.logging import get_logger

logger = get_logger(__name__)


_SKILL_ROOT: Final[Path] = Path(__file__).parent / "skills"
_VALID_PRIORITIES: Final[frozenset[int]] = frozenset({1, 2, 3})


@dataclass(frozen=True, slots=True)
class SkillMeta:
    """Parsed front matter of an L3 skill file.

    Attributes:
        name: Logical skill name (front matter ``name`` or file stem).
        priority: 1=P1 always load, 2=P2 standard, 3=P3 supplementary.
        token_cost: Estimated token cost for budget accounting.
        version: Version integer for cache invalidation (default 1).
        keywords: Lowercased keywords; empty tuple means "always relevant".
        domain: Owning domain (e.g. ``transit``, ``knowledge``, ``vault``).
    """

    name: str
    priority: int
    token_cost: int
    version: int = 1
    keywords: tuple[str, ...] = ()
    domain: str = ""


@dataclass(slots=True)
class _LoadedSkill:
    """Internal record pairing ``SkillMeta`` with the skill body text."""

    meta: SkillMeta
    body: str


_cache: dict[str, list[_LoadedSkill]] = {}
_cache_lock: threading.Lock = threading.Lock()


def _estimate_tokens(text: str) -> int:
    """Rough token count — mirrors ``app.skills.schemas.TOKEN_BUDGET_CHARS``.

    Args:
        text: Arbitrary text to measure.

    Returns:
        ``max(1, len(text) // 4)`` — conservative estimate that avoids zero.
    """
    return max(1, len(text) // 4)


def _parse_yaml_mapping(raw: str) -> dict[str, Any] | None:
    """Parse YAML into a ``dict[str, Any]`` or return ``None`` on failure.

    Uses ``yaml.safe_load`` and rebuilds the result with ``str(key)`` so the
    downstream consumer always sees string-keyed data regardless of what
    YAML inferred for the key type.
    """
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(key): value for key, value in parsed.items()}


def parse_skill_file(path: Path) -> tuple[SkillMeta, str] | None:
    """Parse a single skill file into ``(SkillMeta, body)`` or ``None``.

    The file must start with ``---`` and contain a second ``---`` delimiter
    separating YAML front matter from the markdown body. Any parsing failure
    logs ``agent.skill_loader.<reason>`` at WARNING and returns ``None``.

    Args:
        path: Absolute path to the skill markdown file.

    Returns:
        A ``(SkillMeta, body)`` tuple on success; ``None`` on any failure.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning("agent.skill_loader.read_failed", path=str(path), exc_info=True)
        return None

    if not raw.startswith("---"):
        logger.warning("agent.skill_loader.missing_front_matter", path=str(path))
        return None

    parts = raw.split("---", 2)
    if len(parts) < 3:
        logger.warning("agent.skill_loader.unterminated_front_matter", path=str(path))
        return None

    front_matter_raw = parts[1]
    body = parts[2].lstrip("\n")

    front_matter = _parse_yaml_mapping(front_matter_raw)
    if front_matter is None:
        logger.warning(
            "agent.skill_loader.yaml_parse_failed_or_not_mapping",
            path=str(path),
        )
        return None

    # Coerce and validate fields.
    name_raw: Any = front_matter.get("name", path.stem)
    name = str(name_raw) if name_raw is not None else path.stem

    priority_raw: Any = front_matter.get("priority")
    try:
        priority = int(priority_raw) if priority_raw is not None else 2
    except (TypeError, ValueError):
        logger.warning(
            "agent.skill_loader.invalid_priority_type",
            path=str(path),
            priority=repr(priority_raw),
        )
        return None

    if priority not in _VALID_PRIORITIES:
        logger.warning(
            "agent.skill_loader.invalid_priority_value",
            path=str(path),
            priority=priority,
        )
        return None

    token_cost_raw: Any = front_matter.get("token_cost")
    try:
        token_cost = int(token_cost_raw) if token_cost_raw is not None else _estimate_tokens(body)
    except (TypeError, ValueError):
        token_cost = _estimate_tokens(body)
    if token_cost <= 0:
        token_cost = _estimate_tokens(body)

    version_raw: Any = front_matter.get("version", 1)
    try:
        version = int(version_raw)
    except (TypeError, ValueError):
        version = 1

    keywords_raw = front_matter.get("keywords", [])
    keywords: tuple[str, ...]
    if isinstance(keywords_raw, list):
        keywords = tuple(str(kw).lower() for kw in keywords_raw if kw is not None)
    else:
        keywords = ()

    meta = SkillMeta(
        name=name,
        priority=priority,
        token_cost=token_cost,
        version=version,
        keywords=keywords,
        domain=path.parent.name,
    )
    return meta, body


def discover_skills(domain: str, root: Path | None = None) -> list[_LoadedSkill]:
    """Load all valid skill files for a domain, sorted by filename.

    Uses a module-level cache keyed by domain unless an explicit ``root`` is
    provided (test mode bypasses the cache). Path traversal is rejected via
    ``is_relative_to`` — files outside ``<root>/<domain>/`` are skipped with
    a ``agent.skill_loader.path_escaped`` warning.

    Args:
        domain: Subdirectory name under ``root`` (e.g. ``"transit"``).
        root: Optional root override for tests. When ``None``, uses the
            package-level ``_SKILL_ROOT`` and consults the cache.

    Returns:
        List of ``_LoadedSkill`` records (empty if the directory is missing
        or contains only invalid files).
    """
    use_cache = root is None
    effective_root = root if root is not None else _SKILL_ROOT

    if use_cache:
        with _cache_lock:
            cached = _cache.get(domain)
            if cached is not None:
                return cached

    loaded = _discover_skills_uncached(domain, effective_root)

    if use_cache:
        with _cache_lock:
            _cache[domain] = loaded

    return loaded


def _discover_skills_uncached(domain: str, root: Path) -> list[_LoadedSkill]:
    """Uncached helper for ``discover_skills`` — walks the domain directory."""
    domain_dir = root / domain
    if not domain_dir.is_dir():
        return []

    try:
        root_resolved = domain_dir.resolve()
    except OSError:
        logger.warning("agent.skill_loader.resolve_failed", path=str(domain_dir), exc_info=True)
        return []

    loaded: list[_LoadedSkill] = []
    for path in sorted(domain_dir.glob("*.md")):
        try:
            resolved = path.resolve()
        except OSError:
            logger.warning("agent.skill_loader.resolve_failed", path=str(path), exc_info=True)
            continue
        if not resolved.is_relative_to(root_resolved):
            logger.warning("agent.skill_loader.path_escaped", path=str(path))
            continue
        parsed = parse_skill_file(resolved)
        if parsed is None:
            continue
        meta, body = parsed
        loaded.append(_LoadedSkill(meta=meta, body=body))
    return loaded


def _matches_prompt(skill: _LoadedSkill, prompt_lower: str) -> bool:
    """Return True when the skill has no keywords or any keyword hits."""
    if not skill.meta.keywords:
        return True
    return any(kw in prompt_lower for kw in skill.meta.keywords)


@dataclass(slots=True)
class _SelectionState:
    used: int = 0
    loaded: list[_LoadedSkill] = field(default_factory=lambda: list[_LoadedSkill]())
    skipped: list[tuple[str, str]] = field(default_factory=lambda: list[tuple[str, str]]())


def _should_gate_drop(priority: int, remaining_pct: float) -> tuple[bool, str]:
    """Return ``(drop, reason)`` per the AI-6.4 priority gating table."""
    if priority == 3 and remaining_pct < 0.7:
        return True, "p3_gated"
    if priority == 2 and remaining_pct < 0.3:
        return True, "p2_gated"
    return False, ""


def load_skills_within_budget(
    domain: str,
    prompt: str,
    budget: ContextBudget,
    *,
    skill_root: Path | None = None,
) -> str:
    """Return a formatted L3 skill block for injection into the system prompt.

    Loads domain skills, filters by keyword match against the lowercased
    prompt, sorts by ``(priority, token_cost, name)``, applies priority
    gating based on remaining budget capacity, and emits a single
    ``agent.skill_loader.loaded`` log line summarizing the decision.

    Args:
        domain: Domain directory name (``transit``, ``knowledge``, ``vault``).
        prompt: Current user prompt used for keyword matching.
        budget: ``ContextBudget`` — only ``skill_docs_max`` is consulted here.
        skill_root: Optional root override for tests.

    Returns:
        ``"AGENT SKILLS (L3):\\n\\n## <name>\\n<body>\\n\\n..."`` when skills
        are selected; empty string when nothing qualifies or on any failure.
    """
    cap = budget.skill_docs_max
    if cap <= 0:
        return ""

    try:
        candidates = discover_skills(domain, skill_root)
    except Exception:
        logger.warning("agent.skill_loader.discover_failed", domain=domain, exc_info=True)
        return ""

    if not candidates:
        return ""

    prompt_lower = prompt.lower()
    matched = [s for s in candidates if _matches_prompt(s, prompt_lower)]
    matched.sort(key=lambda s: (s.meta.priority, s.meta.token_cost, s.meta.name))

    state = _SelectionState()
    for skill in matched:
        remaining_pct = (cap - state.used) / cap if cap > 0 else 0.0
        drop, reason = _should_gate_drop(skill.meta.priority, remaining_pct)
        if drop:
            state.skipped.append((skill.meta.name, reason))
            continue
        if state.used + skill.meta.token_cost > cap:
            state.skipped.append((skill.meta.name, "budget_exceeded"))
            continue
        state.loaded.append(skill)
        state.used += skill.meta.token_cost

    logger.info(
        "agent.skill_loader.loaded",
        domain=domain,
        loaded=[s.meta.name for s in state.loaded],
        skipped=state.skipped,
        tokens_used=state.used,
        budget=cap,
    )

    if not state.loaded:
        return ""

    sections = [f"## {s.meta.name}\n{s.body.rstrip()}" for s in state.loaded]
    return "AGENT SKILLS (L3):\n\n" + "\n\n".join(sections)


def clear_cache() -> None:
    """Reset the module-level skill cache (test helper)."""
    with _cache_lock:
        _cache.clear()


__all__ = [
    "SkillMeta",
    "clear_cache",
    "discover_skills",
    "load_skills_within_budget",
    "parse_skill_file",
]
