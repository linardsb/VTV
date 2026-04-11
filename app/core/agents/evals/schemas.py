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


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    """One per-criterion grade for one eval case (AI-7.3).

    Attributes:
        case_id: Stable ``EvalCase.id``.
        domain: Matches ``EvalTrace.domain``; must be in ``VALID_DOMAINS``.
        criterion_name: Short identifier from ``QualityCriterion.name``.
        passed: Binary pass/fail decision from the judge.
        reasoning: One-line rationale, ≤280 characters.
        error: ``None`` on success; populated when judging itself errored
            (LLM failure, schema parse error). Errored verdicts have
            ``passed=False`` and ``reasoning=""``.
    """

    case_id: str
    domain: str
    criterion_name: str
    passed: bool
    reasoning: str
    error: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id or not self.case_id.strip():
            raise ValueError("JudgeVerdict.case_id must be non-empty")
        if self.domain not in VALID_DOMAINS:
            raise ValueError(f"JudgeVerdict.domain={self.domain!r} not in {sorted(VALID_DOMAINS)}")
        if not self.criterion_name or not self.criterion_name.strip():
            raise ValueError("JudgeVerdict.criterion_name must be non-empty")
        if len(self.reasoning) > 280:
            raise ValueError("JudgeVerdict.reasoning must be <=280 chars")


@dataclass(frozen=True, slots=True)
class SuiteJudgement:
    """All verdicts for one suite plus the unjudged case IDs (AI-7.3).

    Attributes:
        suite: Domain name (one of ``VALID_DOMAINS``).
        verdicts: Per-criterion verdicts produced by the judge.
        unjudged_case_ids: IDs of cases skipped because their trace had
            ``error is not None`` (unreachable, infra failure, etc.).
    """

    suite: str
    verdicts: tuple[JudgeVerdict, ...]
    unjudged_case_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.suite not in VALID_DOMAINS:
            raise ValueError(f"SuiteJudgement.suite={self.suite!r} not in {sorted(VALID_DOMAINS)}")


@dataclass(frozen=True, slots=True)
class CriterionBaseline:
    """Per-criterion pass-rate snapshot for one suite (AI-7.4).

    Attributes:
        suite: Domain name (one of ``VALID_DOMAINS``).
        criterion_name: Short identifier from ``QualityCriterion.name``.
        pass_rate: Fraction in ``[0.0, 1.0]``; rounded to 4 decimals on
            disk for stable diffs.
        sample_count: Number of clean (non-errored) verdicts that fed
            this rate.
        created_at: ISO-8601 UTC timestamp captured when the baseline was
            generated.
    """

    suite: str
    criterion_name: str
    pass_rate: float
    sample_count: int
    created_at: str

    def __post_init__(self) -> None:
        if self.suite not in VALID_DOMAINS:
            raise ValueError(
                f"CriterionBaseline.suite={self.suite!r} not in {sorted(VALID_DOMAINS)}"
            )
        if not self.criterion_name or not self.criterion_name.strip():
            raise ValueError("CriterionBaseline.criterion_name must be non-empty")
        if not (0.0 <= self.pass_rate <= 1.0):
            raise ValueError(f"CriterionBaseline.pass_rate={self.pass_rate} not in [0, 1]")
        if self.sample_count < 0:
            raise ValueError("CriterionBaseline.sample_count must be >= 0")


@dataclass(frozen=True, slots=True)
class BaselineReport:
    """Full baseline for one suite — all criteria rolled up (AI-7.4).

    Attributes:
        suite: Domain name (one of ``VALID_DOMAINS``).
        criteria: Per-criterion baselines for this suite.
        total_cases: Number of distinct eval cases that contributed.
        created_at: ISO-8601 UTC timestamp.
    """

    suite: str
    criteria: tuple[CriterionBaseline, ...]
    total_cases: int
    created_at: str

    def __post_init__(self) -> None:
        if self.suite not in VALID_DOMAINS:
            raise ValueError(f"BaselineReport.suite={self.suite!r} not in {sorted(VALID_DOMAINS)}")
        if self.total_cases < 0:
            raise ValueError("BaselineReport.total_cases must be >= 0")


@dataclass(frozen=True, slots=True)
class RegressionFinding:
    """One criterion whose pass rate regressed beyond tolerance (AI-7.4).

    Attributes:
        suite: Domain name.
        criterion_name: Short identifier from ``QualityCriterion.name``.
        baseline_rate: Stored baseline pass-rate fraction.
        current_rate: Pass-rate from the run being checked.
        delta_pct: ``(current - baseline) * 100``; negative on regression.
        tolerance_pct: Tolerance threshold this finding breached.
    """

    suite: str
    criterion_name: str
    baseline_rate: float
    current_rate: float
    delta_pct: float
    tolerance_pct: float


@dataclass(frozen=True, slots=True)
class RegressionReport:
    """Result of comparing a fresh run against a stored baseline (AI-7.4).

    Attributes:
        suite: Domain name.
        tolerance_pct: Tolerance applied during the comparison.
        findings: Criteria that regressed beyond tolerance. Empty tuple
            means the run passed.
        missing_baselines: Criterion names present in the current run but
            absent from the stored baseline (reported, not failed).
        created_at: ISO-8601 UTC timestamp.
    """

    suite: str
    tolerance_pct: float
    findings: tuple[RegressionFinding, ...]
    missing_baselines: tuple[str, ...]
    created_at: str

    @property
    def passed(self) -> bool:
        """Return ``True`` when no regressions were detected."""
        return not self.findings


__all__ = [
    "KNOWN_TOOLS",
    "REQUIRED_CRITERIA_COUNT",
    "VALID_DOMAINS",
    "VALID_LANGUAGES",
    "BaselineReport",
    "CriterionBaseline",
    "EvalCase",
    "JudgeVerdict",
    "QualityCriterion",
    "RegressionFinding",
    "RegressionReport",
    "SuiteJudgement",
]
