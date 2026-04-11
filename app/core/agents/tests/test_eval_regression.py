"""Unit tests for the AI-7.4 regression baseline + check.

Pure-function tests — no LLM, no async model calls. ``pytest.approx`` is
used for float comparisons.
"""

# pyright: reportPrivateUsage=false, reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

from __future__ import annotations

import argparse
import datetime as _dt
import json
from pathlib import Path

import pytest

from app.core.agents.evals.regression import (
    _baseline_from_json,
    _baseline_to_json,
    _run_check,
    check_regression,
    generate_baseline,
    main,
    read_baseline,
    write_baseline,
)
from app.core.agents.evals.schemas import (
    BaselineReport,
    CriterionBaseline,
    JudgeVerdict,
    SuiteJudgement,
)


def _make_judgement(
    suite: str,
    pairs: list[tuple[str, bool]],
    *,
    error_pairs: list[tuple[str, str]] | None = None,
) -> SuiteJudgement:
    verdicts: list[JudgeVerdict] = []
    for criterion_name, passed in pairs:
        verdicts.append(
            JudgeVerdict(
                case_id="case_001",
                domain=suite,
                criterion_name=criterion_name,
                passed=passed,
                reasoning="ok" if passed else "bad",
            )
        )
    for criterion_name, error in error_pairs or []:
        verdicts.append(
            JudgeVerdict(
                case_id="case_001",
                domain=suite,
                criterion_name=criterion_name,
                passed=False,
                reasoning="",
                error=error,
            )
        )
    return SuiteJudgement(
        suite=suite,
        verdicts=tuple(verdicts),
        unjudged_case_ids=(),
    )


def _make_baseline(
    suite: str,
    rates: list[tuple[str, float, int]],
    *,
    created_at: str = "2026-04-11T00:00:00+00:00",
) -> BaselineReport:
    criteria = tuple(
        CriterionBaseline(
            suite=suite,
            criterion_name=name,
            pass_rate=rate,
            sample_count=count,
            created_at=created_at,
        )
        for name, rate, count in rates
    )
    return BaselineReport(
        suite=suite,
        criteria=criteria,
        total_cases=len(criteria),
        created_at=created_at,
    )


# --- generate_baseline ------------------------------------------------------


def test_generate_baseline_aggregates_pass_rates() -> None:
    judgement = _make_judgement(
        "transit",
        [
            ("factual_accuracy", True),
            ("factual_accuracy", True),
            ("factual_accuracy", True),
            ("factual_accuracy", False),
            ("factual_accuracy", False),
        ],
    )

    report = generate_baseline(judgement, total_cases=5)

    assert report.suite == "transit"
    assert report.total_cases == 5
    assert len(report.criteria) == 1
    crit = report.criteria[0]
    assert crit.criterion_name == "factual_accuracy"
    assert crit.sample_count == 5
    assert crit.pass_rate == pytest.approx(0.6, abs=1e-9)


def test_generate_baseline_skips_errored_verdicts() -> None:
    judgement = _make_judgement(
        "transit",
        [
            ("factual_accuracy", True),
            ("factual_accuracy", True),
        ],
        error_pairs=[
            ("factual_accuracy", "RuntimeError: judge died"),
            ("factual_accuracy", "TimeoutError: slow"),
        ],
    )

    report = generate_baseline(judgement, total_cases=2)

    crit = report.criteria[0]
    assert crit.sample_count == 2
    assert crit.pass_rate == pytest.approx(1.0, abs=1e-9)


def test_generate_baseline_handles_multiple_criteria() -> None:
    judgement = _make_judgement(
        "knowledge",
        [
            ("factual_accuracy", True),
            ("citation_grounding", False),
            ("factual_accuracy", False),
            ("citation_grounding", False),
        ],
    )

    report = generate_baseline(judgement, total_cases=2)

    by_name = {c.criterion_name: c for c in report.criteria}
    assert by_name["factual_accuracy"].pass_rate == pytest.approx(0.5, abs=1e-9)
    assert by_name["citation_grounding"].pass_rate == pytest.approx(0.0, abs=1e-9)


# --- check_regression -------------------------------------------------------


def test_check_regression_identical_passes() -> None:
    base = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    report = check_regression(base, base, tolerance_pct=3.0)
    assert report.passed is True
    assert report.findings == ()
    assert report.missing_baselines == ()


def test_check_regression_within_tolerance_passes() -> None:
    baseline = _make_baseline("transit", [("factual_accuracy", 0.80, 10)])
    current = _make_baseline("transit", [("factual_accuracy", 0.78, 10)])
    report = check_regression(current, baseline, tolerance_pct=3.0)
    assert report.passed is True


def test_check_regression_exceeds_tolerance_fails() -> None:
    baseline = _make_baseline("transit", [("factual_accuracy", 0.80, 10)])
    current = _make_baseline("transit", [("factual_accuracy", 0.75, 10)])
    report = check_regression(current, baseline, tolerance_pct=3.0)

    assert report.passed is False
    assert len(report.findings) == 1
    finding = report.findings[0]
    assert finding.criterion_name == "factual_accuracy"
    assert finding.delta_pct == pytest.approx(-5.0, abs=1e-9)
    assert finding.tolerance_pct == 3.0
    assert finding.baseline_rate == pytest.approx(0.80, abs=1e-9)
    assert finding.current_rate == pytest.approx(0.75, abs=1e-9)


def test_check_regression_missing_criterion_in_baseline() -> None:
    baseline = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    current = _make_baseline(
        "transit",
        [
            ("factual_accuracy", 0.9, 10),
            ("new_check", 0.5, 10),
        ],
    )
    report = check_regression(current, baseline, tolerance_pct=3.0)
    assert report.passed is True
    assert report.missing_baselines == ("new_check",)
    assert report.findings == ()


def test_check_regression_tolerance_zero_is_strict() -> None:
    baseline = _make_baseline("transit", [("factual_accuracy", 0.80, 10)])
    current = _make_baseline("transit", [("factual_accuracy", 0.7999, 10)])
    report = check_regression(current, baseline, tolerance_pct=0.0)
    assert report.passed is False
    assert len(report.findings) == 1


def test_check_regression_negative_tolerance_rejected() -> None:
    base = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    with pytest.raises(ValueError, match="must be >= 0"):
        check_regression(base, base, tolerance_pct=-1.0)


# --- baseline I/O -----------------------------------------------------------


def test_write_and_read_baseline_roundtrip(tmp_path: Path) -> None:
    report = _make_baseline(
        "transit",
        [
            ("factual_accuracy", 0.9333, 15),
            ("citation_grounding", 0.8000, 15),
        ],
    )

    out_path = write_baseline(report, baseline_dir=tmp_path)
    assert out_path.is_file()

    loaded = read_baseline("transit", baseline_dir=tmp_path)
    assert loaded is not None
    assert loaded.suite == "transit"
    assert len(loaded.criteria) == 2
    by_name = {c.criterion_name: c for c in loaded.criteria}
    assert by_name["factual_accuracy"].pass_rate == pytest.approx(0.9333, abs=1e-9)
    assert by_name["factual_accuracy"].sample_count == 15
    assert by_name["citation_grounding"].pass_rate == pytest.approx(0.80, abs=1e-9)


def test_read_baseline_returns_none_when_missing(tmp_path: Path) -> None:
    assert read_baseline("transit", baseline_dir=tmp_path) is None


def test_write_baseline_invalid_suite_rejected(tmp_path: Path) -> None:
    """BaselineReport itself rejects invalid suite — defense in depth."""
    with pytest.raises(ValueError, match="not in"):
        BaselineReport(
            suite="../etc",
            criteria=(),
            total_cases=0,
            created_at="now",
        )


def test_read_baseline_invalid_suite_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not in"):
        read_baseline("../escape", baseline_dir=tmp_path)


def test_baseline_to_json_round_trip() -> None:
    report = _make_baseline(
        "transit",
        [("factual_accuracy", 0.9333, 15)],
    )
    payload = _baseline_to_json(report)
    rebuilt = _baseline_from_json(payload, "transit")
    assert rebuilt.suite == "transit"
    assert rebuilt.criteria[0].pass_rate == pytest.approx(0.9333, abs=1e-9)
    assert rebuilt.criteria[0].sample_count == 15


def test_baseline_json_file_is_indented_for_review(tmp_path: Path) -> None:
    """Baselines are committed; the JSON should be diff-friendly."""
    report = _make_baseline("transit", [("factual_accuracy", 0.9333, 15)])
    out_path = write_baseline(report, baseline_dir=tmp_path)
    text = out_path.read_text(encoding="utf-8")
    parsed = json.loads(text)
    assert parsed["suite"] == "transit"
    assert "\n" in text
    assert "  " in text


# --- CLI exit codes ---------------------------------------------------------


def test_cli_check_returns_2_when_baseline_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    rc = main(
        [
            "check",
            "--suite",
            "transit",
            "--trace-dir",
            str(trace_dir),
            "--baseline-dir",
            str(baseline_dir),
        ]
    )
    assert rc == 2


def test_cli_baseline_refuses_overwrite_without_force(tmp_path: Path) -> None:
    baseline_dir = tmp_path / "baselines"
    report = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    write_baseline(report, baseline_dir=baseline_dir)

    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    rc = main(
        [
            "baseline",
            "--suite",
            "transit",
            "--trace-dir",
            str(trace_dir),
            "--baseline-dir",
            str(baseline_dir),
        ]
    )
    assert rc == 2


async def test_cli_check_exit_code_on_regression(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_dir = tmp_path / "baselines"
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()

    baseline = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    write_baseline(baseline, baseline_dir=baseline_dir)

    failing_judgement = _make_judgement(
        "transit",
        [("factual_accuracy", False)] * 10,
    )

    async def _fake_judge_one_suite(suite: str, *, trace_dir: Path) -> tuple[SuiteJudgement, int]:
        _ = (suite, trace_dir)
        return failing_judgement, 10

    monkeypatch.setattr(
        "app.core.agents.evals.regression._judge_one_suite",
        _fake_judge_one_suite,
    )

    args = argparse.Namespace(
        suite="transit",
        trace_dir=trace_dir,
        baseline_dir=baseline_dir,
        tolerance_pct=3.0,
        update_baseline=False,
    )
    rc = await _run_check(args)
    assert rc == 1


async def test_cli_check_passes_after_baseline_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline_dir = tmp_path / "baselines"
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()

    baseline = _make_baseline("transit", [("factual_accuracy", 0.9, 10)])
    write_baseline(baseline, baseline_dir=baseline_dir)

    matching_judgement = _make_judgement(
        "transit",
        [("factual_accuracy", True)] * 9 + [("factual_accuracy", False)],
    )

    async def _fake_judge_one_suite(suite: str, *, trace_dir: Path) -> tuple[SuiteJudgement, int]:
        _ = (suite, trace_dir)
        return matching_judgement, 10

    monkeypatch.setattr(
        "app.core.agents.evals.regression._judge_one_suite",
        _fake_judge_one_suite,
    )

    args = argparse.Namespace(
        suite="transit",
        trace_dir=trace_dir,
        baseline_dir=baseline_dir,
        tolerance_pct=3.0,
        update_baseline=False,
    )
    rc = await _run_check(args)
    assert rc == 0


# --- helpers ----------------------------------------------------------------


def test_utc_now_iso_default_returns_utc() -> None:
    """Smoke check on the timestamp seam used by the public API."""
    explicit = _dt.datetime(2026, 4, 11, 12, 0, 0, tzinfo=_dt.UTC)
    judgement = _make_judgement("transit", [("factual_accuracy", True)])
    report = generate_baseline(judgement, total_cases=1, now=explicit)
    assert report.created_at.startswith("2026-04-11T12:00:00")
