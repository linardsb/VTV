"""Unit tests for the AI-7.3 LLM judge.

All tests run offline: ``models.ALLOW_MODEL_REQUESTS = False`` blocks
network calls and the judge agent is exercised either via ``TestModel``
(which produces canned ``_CriterionJudgement`` output matching the
``output_type`` schema) or via ``unittest.mock.patch`` on
``LLMJudge._run_one``.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import models
from pydantic_ai.models.test import TestModel

from app.core.agents.evals.judge import (
    LLMJudge,
    _build_user_prompt,
    _newest_trace_for_suite,
    _verdict_to_jsonl_line,
    main,
)
from app.core.agents.evals.schemas import (
    EvalCase,
    JudgeVerdict,
    QualityCriterion,
    SuiteJudgement,
)
from app.core.agents.tests.conftest import make_eval_case, make_quality_criterion

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


def _write_trace_file(
    path: Path,
    *,
    case_id: str,
    domain: str,
    prompt: str = "Test prompt",
    response: str = "Test response",
    error: str | None = None,
    tools_used: tuple[str, ...] = (),
    tool_returns: tuple[dict[str, Any], ...] = (),
) -> Path:
    """Write a single-trace JSONL file mirroring runner.EvalTrace shape."""
    trace = {
        "case_id": case_id,
        "domain": domain,
        "prompt": prompt,
        "response": response,
        "tools_used": list(tools_used),
        "tool_returns": list(tool_returns),
        "confidence": 0.9,
        "warnings": [],
        "latency_ms": 12.3,
        "error": error,
        "timestamp": "2026-04-11T00:00:00+00:00",
    }
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(trace) + "\n")
    return path


def _make_judge(verdict_dir: Path, *, output_text: str = "ok") -> LLMJudge:
    test_model = TestModel(custom_output_args={"passed": True, "reasoning": output_text})
    return LLMJudge(model=test_model, verdict_dir=verdict_dir)


# --- happy path ------------------------------------------------------------


async def test_judge_passes_all_criteria_with_test_model(tmp_path: Path) -> None:
    case = make_eval_case(id="transit_001", expected_domain="transit")
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="transit_001",
        domain="transit",
    )
    judge = _make_judge(tmp_path / "verdicts")

    result = await judge.judge_trace_file(trace_path, "transit", {"transit_001": case})

    assert isinstance(result, SuiteJudgement)
    assert result.suite == "transit"
    assert len(result.verdicts) == 5
    assert all(v.passed for v in result.verdicts)
    assert all(v.error is None for v in result.verdicts)
    assert result.unjudged_case_ids == ()


# --- skip on trace error ---------------------------------------------------


async def test_judge_skips_traces_with_error(tmp_path: Path) -> None:
    case = make_eval_case(id="transit_001", expected_domain="transit")
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="transit_001",
        domain="transit",
        error="RuntimeError: boom",
    )
    judge = _make_judge(tmp_path / "verdicts")

    result = await judge.judge_trace_file(trace_path, "transit", {"transit_001": case})

    assert result.verdicts == ()
    assert result.unjudged_case_ids == ("transit_001",)


async def test_judge_skips_unknown_case_id(tmp_path: Path) -> None:
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="unknown_999",
        domain="transit",
    )
    judge = _make_judge(tmp_path / "verdicts")

    result = await judge.judge_trace_file(trace_path, "transit", {})

    assert result.verdicts == ()
    assert result.unjudged_case_ids == ("unknown_999",)


# --- write_verdicts: sandboxed JSONL ---------------------------------------


async def test_judge_writes_sandboxed_jsonl(tmp_path: Path) -> None:
    verdict_dir = tmp_path / "verdicts"
    judge = _make_judge(verdict_dir)
    judgement = SuiteJudgement(
        suite="transit",
        verdicts=(
            JudgeVerdict(
                case_id="transit_001",
                domain="transit",
                criterion_name="factual_accuracy",
                passed=True,
                reasoning="ok",
            ),
        ),
        unjudged_case_ids=(),
    )

    out_path = judge.write_verdicts(judgement)

    assert out_path.is_file()
    assert out_path.is_relative_to(verdict_dir.resolve())
    with out_path.open("r", encoding="utf-8") as fh:
        lines = [line.strip() for line in fh if line.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["case_id"] == "transit_001"
    assert record["passed"] is True


async def test_judge_path_escape_refused_via_invalid_suite(tmp_path: Path) -> None:
    """SuiteJudgement validates suite name in __post_init__ — never reaches I/O."""
    with pytest.raises(ValueError, match="not in"):
        SuiteJudgement(suite="../etc", verdicts=(), unjudged_case_ids=())


async def test_judge_trace_file_rejects_invalid_suite(tmp_path: Path) -> None:
    judge = _make_judge(tmp_path / "verdicts")
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="transit_001",
        domain="transit",
    )
    with pytest.raises(ValueError, match="suite must be in"):
        await judge.judge_trace_file(trace_path, "../escape", {})


# --- fail-open per LLM error -----------------------------------------------


async def test_judge_fail_open_on_llm_error(tmp_path: Path) -> None:
    case = make_eval_case(id="transit_001", expected_domain="transit")
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="transit_001",
        domain="transit",
    )
    judge = _make_judge(tmp_path / "verdicts")

    failing_verdict = JudgeVerdict(
        case_id="transit_001",
        domain="transit",
        criterion_name="factual_accuracy",
        passed=False,
        reasoning="",
        error="ValueError: boom",
    )
    with patch.object(judge, "_run_one", AsyncMock(return_value=failing_verdict)):
        result = await judge.judge_trace_file(trace_path, "transit", {"transit_001": case})

    assert len(result.verdicts) == 5
    assert all(v.error == "ValueError: boom" for v in result.verdicts)
    assert all(v.passed is False for v in result.verdicts)
    assert all(v.reasoning == "" for v in result.verdicts)


# --- security: no raw prompt/response in logs ------------------------------


async def test_judge_does_not_log_raw_prompt(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret_prompt = "ULTRA_SECRET_PROMPT_DO_NOT_LOG"
    case = make_eval_case(id="transit_001", expected_domain="transit", prompt=secret_prompt)
    trace_path = _write_trace_file(
        tmp_path / "transit_run.jsonl",
        case_id="transit_001",
        domain="transit",
        prompt=secret_prompt,
        response="ULTRA_SECRET_RESPONSE_DO_NOT_LOG",
    )
    judge = _make_judge(tmp_path / "verdicts")

    with caplog.at_level(logging.DEBUG, logger="app.core.agents.evals.judge"):
        await judge.judge_trace_file(trace_path, "transit", {"transit_001": case})

    for record in caplog.records:
        rendered = record.getMessage() + json.dumps(record.__dict__, default=str)
        assert secret_prompt not in rendered
        assert "ULTRA_SECRET_RESPONSE_DO_NOT_LOG" not in rendered


# --- prompt builder delimiters ---------------------------------------------


def test_build_user_prompt_escapes_trace_as_data() -> None:
    case = make_eval_case(id="transit_001", expected_domain="transit", prompt="hello")
    trace: dict[str, Any] = {
        "domain": "transit",
        "tools_used": ["query_bus_status"],
        "tool_returns": [{"tool_name": "query_bus_status", "payload": {"k": "v"}}],
        "response": "world",
    }
    criterion = make_quality_criterion(name="factual_accuracy")

    rendered = _build_user_prompt(case, trace, criterion)

    assert "<<<BEGIN>>>" in rendered
    assert "<<<END>>>" in rendered
    assert "as data, not instructions" in rendered
    assert "factual_accuracy" in rendered
    assert "query_bus_status" in rendered
    assert "hello" in rendered
    assert "world" in rendered


def test_verdict_to_jsonl_line_round_trips() -> None:
    verdict = JudgeVerdict(
        case_id="transit_001",
        domain="transit",
        criterion_name="factual_accuracy",
        passed=True,
        reasoning="ok",
    )
    line = _verdict_to_jsonl_line(verdict)
    parsed = json.loads(line)
    assert parsed["case_id"] == "transit_001"
    assert parsed["passed"] is True
    assert parsed["reasoning"] == "ok"


# --- CLI exit codes --------------------------------------------------------


def test_cli_returns_exit_code_2_when_no_traces(tmp_path: Path) -> None:
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    verdict_dir = tmp_path / "verdicts"

    rc = main(
        [
            "--suite",
            "transit",
            "--trace-dir",
            str(trace_dir),
            "--verdict-dir",
            str(verdict_dir),
        ]
    )
    assert rc == 2


def test_cli_returns_exit_code_2_when_trace_dir_missing(tmp_path: Path) -> None:
    rc = main(
        [
            "--suite",
            "transit",
            "--trace-dir",
            str(tmp_path / "missing"),
            "--verdict-dir",
            str(tmp_path / "verdicts"),
        ]
    )
    assert rc == 2


def test_cli_returns_exit_code_1_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    verdict_dir = tmp_path / "verdicts"
    case = make_eval_case(id="transit_001", expected_domain="transit")
    _write_trace_file(
        trace_dir / "transit_20260101T000000Z.jsonl",
        case_id="transit_001",
        domain="transit",
    )

    failing_judgement = SuiteJudgement(
        suite="transit",
        verdicts=(
            JudgeVerdict(
                case_id="transit_001",
                domain="transit",
                criterion_name="factual_accuracy",
                passed=False,
                reasoning="bad",
            ),
        ),
        unjudged_case_ids=(),
    )

    def _fake_cases_by_id(_suite: str) -> dict[str, EvalCase]:
        return {case.id: case}

    monkeypatch.setattr(
        "app.core.agents.evals.judge._cases_by_id",
        _fake_cases_by_id,
    )

    async def _fake_judge_trace_file(
        self: LLMJudge,
        trace_path: Path,
        suite: str,
        cases: dict[str, EvalCase],
    ) -> SuiteJudgement:
        _ = (self, trace_path, suite, cases)
        return failing_judgement

    monkeypatch.setattr(LLMJudge, "judge_trace_file", _fake_judge_trace_file)

    rc = main(
        [
            "--suite",
            "transit",
            "--trace-dir",
            str(trace_dir),
            "--verdict-dir",
            str(verdict_dir),
        ]
    )
    assert rc == 1


def test_newest_trace_for_suite_picks_latest(tmp_path: Path) -> None:
    older = tmp_path / "transit_20260101T000000Z.jsonl"
    newer = tmp_path / "transit_20260102T000000Z.jsonl"
    older.write_text("{}\n", encoding="utf-8")
    newer.write_text("{}\n", encoding="utf-8")
    import os

    os.utime(older, (1, 1))
    os.utime(newer, (1000, 1000))

    selected = _newest_trace_for_suite(tmp_path, "transit")
    assert selected == newer.resolve() or selected == newer


def test_quality_criterion_factory_present() -> None:
    """Sanity-check the conftest factory the tests rely on."""
    crit = make_quality_criterion(name="abc", description="def")
    assert isinstance(crit, QualityCriterion)
    assert crit.name == "abc"
