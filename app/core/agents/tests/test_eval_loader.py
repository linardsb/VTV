"""Tests for ``app.core.agents.evals.schemas`` and ``loader`` (AI-7.1)."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportPrivateUsage=false

from __future__ import annotations

import dataclasses
from pathlib import Path
from textwrap import dedent

import pytest

from app.core.agents.evals.loader import (
    load_all_cases,
    load_eval_cases,
    parse_eval_file,
)
from app.core.agents.evals.schemas import (
    KNOWN_TOOLS,
    QualityCriterion,
)
from app.core.agents.tests.conftest import make_eval_case, make_quality_criterion


def _write(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body).lstrip(), encoding="utf-8")
    return path


# --- Schema validation ------------------------------------------------------


def test_eval_case_valid_minimal() -> None:
    case = make_eval_case()
    assert case.id == "test_001"
    assert case.expected_domain == "transit"
    assert len(case.quality_criteria) == 5


def test_eval_case_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="id must be non-empty"):
        make_eval_case(id="")


def test_eval_case_rejects_empty_prompt() -> None:
    with pytest.raises(ValueError, match="prompt must be non-empty"):
        make_eval_case(prompt="   ")


def test_eval_case_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="language="):
        make_eval_case(language="fr")


def test_eval_case_rejects_unknown_domain() -> None:
    with pytest.raises(ValueError, match="expected_domain="):
        make_eval_case(expected_domain="weather")


def test_eval_case_rejects_wrong_criteria_count_too_few() -> None:
    with pytest.raises(ValueError, match="must have exactly 5 quality_criteria"):
        make_eval_case(
            quality_criteria=tuple(make_quality_criterion(name=f"c{i}") for i in range(4))
        )


def test_eval_case_rejects_wrong_criteria_count_too_many() -> None:
    with pytest.raises(ValueError, match="must have exactly 5 quality_criteria"):
        make_eval_case(
            quality_criteria=tuple(make_quality_criterion(name=f"c{i}") for i in range(6))
        )


def test_eval_case_rejects_unknown_tool() -> None:
    with pytest.raises(ValueError, match="unknown tools"):
        make_eval_case(expected_tools=("not_a_real_tool",))


def test_eval_case_accepts_empty_expected_tools() -> None:
    case = make_eval_case(expected_tools=())
    assert case.expected_tools == ()


def test_quality_criterion_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        QualityCriterion(name="", description="desc")


def test_quality_criterion_rejects_empty_description() -> None:
    with pytest.raises(ValueError, match="description must be non-empty"):
        QualityCriterion(name="name", description=" ")


def test_eval_case_is_frozen() -> None:
    case = make_eval_case()
    with pytest.raises(dataclasses.FrozenInstanceError):
        case.id = "mutated"  # type: ignore[misc]


# --- YAML loader: per-file parsing ------------------------------------------


_VALID_CASE_YAML = """
cases:
  - id: sample_001
    prompt: Hello
    language: en
    expected_domain: transit
    expected_tools:
      - query_bus_status
    quality_criteria:
      - name: c1
        description: d1
      - name: c2
        description: d2
      - name: c3
        description: d3
      - name: c4
        description: d4
      - name: c5
        description: d5
"""


def test_parse_eval_file_valid(tmp_eval_dir: Path) -> None:
    path = _write(tmp_eval_dir / "transit.yaml", _VALID_CASE_YAML)
    cases = parse_eval_file(path)
    assert cases is not None
    assert len(cases) == 1
    assert cases[0].id == "sample_001"


def test_parse_eval_file_missing_returns_none(tmp_eval_dir: Path) -> None:
    assert parse_eval_file(tmp_eval_dir / "nope.yaml") is None


def test_parse_eval_file_malformed_yaml_returns_none(tmp_eval_dir: Path) -> None:
    path = _write(
        tmp_eval_dir / "transit.yaml",
        """
        cases:
          - id: bad
            unterminated: [
        """,
    )
    assert parse_eval_file(path) is None


def test_parse_eval_file_top_level_not_dict_returns_none(
    tmp_eval_dir: Path,
) -> None:
    path = _write(
        tmp_eval_dir / "transit.yaml",
        """
        - id: sample_001
        - id: sample_002
        """,
    )
    assert parse_eval_file(path) is None


def test_parse_eval_file_missing_cases_key_returns_none(
    tmp_eval_dir: Path,
) -> None:
    path = _write(
        tmp_eval_dir / "transit.yaml",
        """
        version: 1
        """,
    )
    assert parse_eval_file(path) is None


def test_parse_eval_file_cases_not_a_list_returns_none(
    tmp_eval_dir: Path,
) -> None:
    path = _write(
        tmp_eval_dir / "transit.yaml",
        """
        cases:
          id: sample_001
        """,
    )
    assert parse_eval_file(path) is None


def test_parse_eval_file_skips_invalid_case_keeps_valid(
    tmp_eval_dir: Path,
) -> None:
    path = _write(
        tmp_eval_dir / "transit.yaml",
        """
        cases:
          - id: good_001
            prompt: ok
            language: en
            expected_domain: transit
            expected_tools: [query_bus_status]
            quality_criteria:
              - {name: c1, description: d1}
              - {name: c2, description: d2}
              - {name: c3, description: d3}
              - {name: c4, description: d4}
              - {name: c5, description: d5}
          - id: bad_001
            prompt: bad
            language: en
            expected_domain: weather
            expected_tools: []
            quality_criteria:
              - {name: c1, description: d1}
              - {name: c2, description: d2}
              - {name: c3, description: d3}
              - {name: c4, description: d4}
              - {name: c5, description: d5}
        """,
    )
    cases = parse_eval_file(path)
    assert cases is not None
    assert len(cases) == 1
    assert cases[0].id == "good_001"


# --- YAML loader: directory-level loading -----------------------------------


def test_load_eval_cases_missing_file_returns_empty(tmp_eval_dir: Path) -> None:
    assert load_eval_cases("transit", cases_root=tmp_eval_dir) == []


def test_load_eval_cases_path_traversal_blocked(
    tmp_eval_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = load_eval_cases("../../etc/passwd", cases_root=tmp_eval_dir)
    assert result == []
    captured = capsys.readouterr()
    assert "path_escaped" in (captured.out + captured.err)


def test_load_all_cases_loads_three_domains(tmp_eval_dir: Path) -> None:
    _write(tmp_eval_dir / "transit.yaml", _VALID_CASE_YAML)
    _write(
        tmp_eval_dir / "knowledge.yaml",
        _VALID_CASE_YAML.replace("sample_001", "knowledge_sample")
        .replace("expected_domain: transit", "expected_domain: knowledge")
        .replace("query_bus_status", "search_knowledge_base"),
    )
    _write(
        tmp_eval_dir / "vault.yaml",
        _VALID_CASE_YAML.replace("sample_001", "vault_sample")
        .replace("expected_domain: transit", "expected_domain: vault")
        .replace("query_bus_status", "obsidian_query_vault"),
    )
    suite = load_all_cases(cases_root=tmp_eval_dir)
    assert set(suite.keys()) == {"transit", "knowledge", "vault"}
    assert len(suite["transit"]) == 1
    assert len(suite["knowledge"]) == 1
    assert len(suite["vault"]) == 1


def test_load_all_cases_detects_duplicate_ids(
    tmp_eval_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write(tmp_eval_dir / "transit.yaml", _VALID_CASE_YAML)
    _write(
        tmp_eval_dir / "knowledge.yaml",
        _VALID_CASE_YAML.replace("expected_domain: transit", "expected_domain: knowledge").replace(
            "query_bus_status", "search_knowledge_base"
        ),
    )
    load_all_cases(cases_root=tmp_eval_dir)
    captured = capsys.readouterr()
    assert "duplicate_ids" in (captured.out + captured.err)


# --- Production-suite integrity --------------------------------------------


def test_production_transit_has_15_cases() -> None:
    cases = load_eval_cases("transit")
    assert len(cases) == 15


def test_production_knowledge_has_10_cases() -> None:
    cases = load_eval_cases("knowledge")
    assert len(cases) == 10


def test_production_vault_has_5_cases() -> None:
    cases = load_eval_cases("vault")
    assert len(cases) == 5


def test_production_all_case_ids_are_unique() -> None:
    suite = load_all_cases()
    all_ids = [case.id for cases in suite.values() for case in cases]
    assert len(all_ids) == len(set(all_ids))


def test_production_all_cases_have_5_criteria() -> None:
    suite = load_all_cases()
    for cases in suite.values():
        for case in cases:
            assert len(case.quality_criteria) == 5


def test_production_every_known_tool_appears_at_least_once() -> None:
    suite = load_all_cases()
    referenced: set[str] = set()
    for cases in suite.values():
        for case in cases:
            referenced.update(case.expected_tools)
    missing = KNOWN_TOOLS - referenced
    assert not missing, f"Tools never referenced in any eval case: {sorted(missing)}"


def test_production_each_case_expected_domain_matches_file() -> None:
    suite = load_all_cases()
    for domain, cases in suite.items():
        for case in cases:
            assert case.expected_domain == domain
