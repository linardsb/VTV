"""Eval framework schemas (AI-7.1).

Frozen dataclasses representing one synthetic test case for the agent
suite. Validation happens in ``__post_init__`` — fail-fast on bad data so
the loader can skip the offending file without raising.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

VALID_DOMAINS: Final[frozenset[str]] = frozenset({"transit", "knowledge", "vault"})
VALID_LANGUAGES: Final[frozenset[str]] = frozenset({"lv", "en", "lv_diacriticless", "mixed"})

# Mirrors the exact tool function names registered in
# app/core/agents/agents/{transit,knowledge,vault}.py
KNOWN_TOOLS: Final[frozenset[str]] = frozenset(
    {
        # transit (5)
        "query_bus_status",
        "get_route_schedule",
        "search_stops",
        "get_adherence_report",
        "check_driver_availability",
        # knowledge (1)
        "search_knowledge_base",
        # vault (4)
        "obsidian_query_vault",
        "obsidian_manage_notes",
        "obsidian_manage_folders",
        "obsidian_bulk_operations",
    }
)

REQUIRED_CRITERIA_COUNT: Final[int] = 5


@dataclass(frozen=True, slots=True)
class QualityCriterion:
    """One binary quality check for an eval case.

    Attributes:
        name: Short identifier (e.g. ``factual_accuracy``).
        description: Free-text description of what the check verifies.
            Actual judging happens later in AI-7.2.
    """

    name: str
    description: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("QualityCriterion.name must be non-empty")
        if not self.description or not self.description.strip():
            raise ValueError("QualityCriterion.description must be non-empty")


@dataclass(frozen=True, slots=True)
class EvalCase:
    """Immutable synthetic agent test case.

    Attributes:
        id: Stable case identifier (``{domain}_{NNN}``).
        prompt: User-facing prompt fed to the agent during eval runs.
        language: One of :data:`VALID_LANGUAGES`.
        expected_domain: One of :data:`VALID_DOMAINS` — used by AI-7.2 to
            verify the AI-6.3 auto-router classifies the prompt correctly.
        expected_tools: Tuple of tool function names the agent should
            invoke. Empty tuple is allowed (agent may answer from memory).
        quality_criteria: Exactly :data:`REQUIRED_CRITERIA_COUNT` criteria.
        notes: Optional free-text annotation; defaults to empty string.

    Raises:
        ValueError: If any field fails validation.
    """

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
