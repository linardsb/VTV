"""Tests for ``app.core.agents.skill_loader`` (AI-6.4)."""

# pyright: reportPrivateUsage=false

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from app.core.agents.context_budget import ContextBudget, agent_budget_for
from app.core.agents.skill_loader import (
    discover_skills,
    load_skills_within_budget,
    parse_skill_file,
)


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")
    return path


# --- Front matter parsing ---------------------------------------------------


def test_parse_skill_file_valid_front_matter(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "transit" / "delay.md",
        """
        ---
        name: delay_analysis
        priority: 2
        token_cost: 450
        version: 1
        keywords: [delay, late, kavejas]
        ---
        # Delay
        Body content.
        """,
    )
    result = parse_skill_file(path)
    assert result is not None
    meta, body = result
    assert meta.name == "delay_analysis"
    assert meta.priority == 2
    assert meta.token_cost == 450
    assert meta.keywords == ("delay", "late", "kavejas")
    assert meta.domain == "transit"
    assert "# Delay" in body


def test_parse_skill_file_missing_front_matter_delimiter(tmp_path: Path) -> None:
    path = _write(tmp_path / "transit" / "bad.md", "# Just body, no front matter\n")
    assert parse_skill_file(path) is None


def test_parse_skill_file_malformed_yaml(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "transit" / "bad.md",
        """
        ---
        name: bad
        priority: 2
        keywords: [unterminated
        ---
        Body.
        """,
    )
    assert parse_skill_file(path) is None


def test_parse_skill_file_yaml_returns_list(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "transit" / "bad.md",
        """
        ---
        - item
        - item2
        ---
        Body.
        """,
    )
    assert parse_skill_file(path) is None


def test_parse_skill_file_invalid_priority(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "transit" / "bad.md",
        """
        ---
        name: bad
        priority: 4
        token_cost: 100
        ---
        Body.
        """,
    )
    assert parse_skill_file(path) is None


# --- Discovery --------------------------------------------------------------


def test_discover_skills_returns_sorted_valid_list(tmp_path: Path, tmp_skill_dir: Path) -> None:
    _ = tmp_path
    _write(
        tmp_skill_dir / "transit" / "beta.md",
        """
        ---
        name: beta
        priority: 2
        token_cost: 100
        ---
        B
        """,
    )
    _write(
        tmp_skill_dir / "transit" / "alpha.md",
        """
        ---
        name: alpha
        priority: 2
        token_cost: 100
        ---
        A
        """,
    )
    loaded = discover_skills("transit", tmp_skill_dir)
    assert [s.meta.name for s in loaded] == ["alpha", "beta"]


def test_discover_skills_empty_directory(tmp_skill_dir: Path) -> None:
    assert discover_skills("transit", tmp_skill_dir) == []


def test_discover_skills_drops_invalid_files(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "transit" / "good.md",
        """
        ---
        name: good
        priority: 2
        token_cost: 100
        ---
        OK
        """,
    )
    _write(
        tmp_skill_dir / "transit" / "bad.md",
        "# no front matter",
    )
    loaded = discover_skills("transit", tmp_skill_dir)
    assert [s.meta.name for s in loaded] == ["good"]


# --- Keyword matching -------------------------------------------------------


def test_keyword_match_is_case_insensitive(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "transit" / "delay.md",
        """
        ---
        name: delay
        priority: 2
        token_cost: 100
        keywords: [kavejas]
        ---
        Delay body.
        """,
    )
    out = load_skills_within_budget(
        "transit",
        "Kuri marsruti KAVEJAS?",
        ContextBudget(skill_docs_max=2000),
        skill_root=tmp_skill_dir,
    )
    assert "## delay" in out


def test_empty_keywords_always_match(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "knowledge" / "sop.md",
        """
        ---
        name: sop
        priority: 1
        token_cost: 100
        keywords: []
        ---
        SOP body.
        """,
    )
    out = load_skills_within_budget(
        "knowledge",
        "totally unrelated",
        ContextBudget(skill_docs_max=2000),
        skill_root=tmp_skill_dir,
    )
    assert "## sop" in out


# --- Priority gating --------------------------------------------------------


def test_p1_skill_always_loaded_under_tight_budget(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "knowledge" / "sop.md",
        """
        ---
        name: sop
        priority: 1
        token_cost: 50
        keywords: []
        ---
        SOP.
        """,
    )
    out = load_skills_within_budget(
        "knowledge",
        "q",
        ContextBudget(skill_docs_max=60),
        skill_root=tmp_skill_dir,
    )
    assert "## sop" in out


def test_p3_skill_gated_when_capacity_below_70_percent(tmp_skill_dir: Path) -> None:
    # Loading sop (P1, 500) first uses 50% of a 1000-token cap; capacity drops
    # to 0.5, below the 0.7 gate for P3.
    _write(
        tmp_skill_dir / "knowledge" / "sop.md",
        """
        ---
        name: sop
        priority: 1
        token_cost: 500
        keywords: []
        ---
        SOP.
        """,
    )
    _write(
        tmp_skill_dir / "knowledge" / "extra.md",
        """
        ---
        name: extra
        priority: 3
        token_cost: 100
        keywords: []
        ---
        Extra.
        """,
    )
    out = load_skills_within_budget(
        "knowledge",
        "q",
        ContextBudget(skill_docs_max=1000),
        skill_root=tmp_skill_dir,
    )
    assert "## sop" in out
    assert "## extra" not in out  # P3 gated at 50% remaining


def test_p2_skill_gated_when_capacity_below_30_percent(tmp_skill_dir: Path) -> None:
    # P1 uses 80% of a 1000-cap; remaining 20% < 30% threshold for P2.
    _write(
        tmp_skill_dir / "knowledge" / "sop.md",
        """
        ---
        name: sop
        priority: 1
        token_cost: 800
        keywords: []
        ---
        SOP.
        """,
    )
    _write(
        tmp_skill_dir / "knowledge" / "extra.md",
        """
        ---
        name: extra
        priority: 2
        token_cost: 100
        keywords: []
        ---
        Extra.
        """,
    )
    out = load_skills_within_budget(
        "knowledge",
        "q",
        ContextBudget(skill_docs_max=1000),
        skill_root=tmp_skill_dir,
    )
    assert "## sop" in out
    assert "## extra" not in out


# --- Budget enforcement -----------------------------------------------------


def test_cheaper_skill_wins_under_budget_pressure(tmp_skill_dir: Path) -> None:
    # Two P2 skills with different costs; cap too small for both.
    _write(
        tmp_skill_dir / "transit" / "cheap.md",
        """
        ---
        name: cheap
        priority: 2
        token_cost: 100
        keywords: []
        ---
        Cheap.
        """,
    )
    _write(
        tmp_skill_dir / "transit" / "expensive.md",
        """
        ---
        name: expensive
        priority: 2
        token_cost: 800
        keywords: []
        ---
        Expensive.
        """,
    )
    out = load_skills_within_budget(
        "transit",
        "q",
        ContextBudget(skill_docs_max=500),
        skill_root=tmp_skill_dir,
    )
    assert "## cheap" in out
    assert "## expensive" not in out


def test_loaded_text_contains_header_prefix(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "transit" / "skill.md",
        """
        ---
        name: skill
        priority: 2
        token_cost: 100
        keywords: []
        ---
        Body.
        """,
    )
    out = load_skills_within_budget(
        "transit",
        "q",
        ContextBudget(skill_docs_max=2000),
        skill_root=tmp_skill_dir,
    )
    assert out.startswith("AGENT SKILLS (L3):")
    assert "## skill" in out


def test_empty_result_for_empty_or_missing_domain(tmp_skill_dir: Path) -> None:
    assert (
        load_skills_within_budget(
            "transit",
            "anything",
            ContextBudget(skill_docs_max=2000),
            skill_root=tmp_skill_dir,
        )
        == ""
    )


def test_zero_budget_returns_empty(tmp_skill_dir: Path) -> None:
    _write(
        tmp_skill_dir / "transit" / "skill.md",
        """
        ---
        name: skill
        priority: 1
        token_cost: 100
        keywords: []
        ---
        Body.
        """,
    )
    assert (
        load_skills_within_budget(
            "transit",
            "q",
            ContextBudget(skill_docs_max=0),
            skill_root=tmp_skill_dir,
        )
        == ""
    )


# --- Integration with real in-repo skill files ------------------------------


def test_real_knowledge_query_loads_sop_and_incident_response() -> None:
    out = load_skills_within_budget(
        "knowledge",
        "what's the SOP for incident X?",
        agent_budget_for("knowledge"),
    )
    assert "## sop_retrieval" in out
    assert "## incident_response" in out


def test_real_transit_delay_query_loads_delay_but_not_driver_availability() -> None:
    out = load_skills_within_budget(
        "transit",
        "is bus 12 delayed right now?",
        agent_budget_for("transit"),
    )
    assert "## delay_analysis" in out
    assert "## driver_availability" not in out
