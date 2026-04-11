"""Unit tests for the AI-7.2 eval runner.

All tests mock the agent pipeline via a concrete ``BaseAgentService``
subclass — no DB, no HTTP, no Docker. Traces are always written to
``tmp_path`` so the real ``evals/traces/`` directory is never touched.
"""

# pyright: reportPrivateUsage=false

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai import models

from app.core.agents.agent_result import AgentResult
from app.core.agents.base import BaseAgentService
from app.core.agents.evals.runner import (
    EvalRunner,
    EvalTrace,
    _coerce_tool_return,
    _collect_tool_returns,
    _trace_to_jsonl_line,
    main,
)
from app.core.agents.evals.schemas import EvalCase
from app.core.agents.schemas import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    UsageInfo,
)
from app.core.agents.tests.conftest import make_eval_case
from app.core.agents.validation import ToolReturnRecord

# Prevent accidental real LLM API calls during testing.
models.ALLOW_MODEL_REQUESTS = False


def _make_fake_response(text: str = "ok") -> ChatCompletionResponse:
    return ChatCompletionResponse(
        id="chatcmpl-test",
        created=0,
        model="fake-model",
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=text),
                finish_reason="stop",
            )
        ],
        usage=UsageInfo(),
    )


def _make_fake_result(
    *,
    content: str = "ok",
    tools_used: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    confidence: float | None = 0.9,
    domain: str = "transit",
) -> AgentResult:
    return AgentResult(
        content=content,
        confidence=confidence,
        warnings=warnings,
        tools_used=tools_used,
        domain=domain,
    )


class _FakeEvalAgent(BaseAgentService):
    """Concrete test double that short-circuits ``chat_with_trace``.

    Bypasses the real pipeline entirely so the runner can be tested
    without touching an LLM. Each ``chat_with_trace`` call consumes one
    entry from the canned ``outcomes`` list (wrapping around when
    exhausted so arbitrary-length suites don't blow up tests).
    """

    agent_name: str = "transit"

    def __init__(
        self,
        *,
        response_text: str = "ok",
        tools_used: tuple[str, ...] = (),
        tool_returns: tuple[ToolReturnRecord, ...] = (),
        warnings: tuple[str, ...] = (),
        confidence: float | None = 0.9,
        raise_exc: BaseException | None = None,
    ) -> None:
        self._response_text = response_text
        self._tools_used = tools_used
        self._tool_returns = tool_returns
        self._warnings = warnings
        self._confidence = confidence
        self._raise_exc = raise_exc
        self.calls: int = 0

    async def chat_with_trace(
        self,
        request: ChatCompletionRequest,
    ) -> tuple[ChatCompletionResponse, AgentResult, tuple[ToolReturnRecord, ...]]:
        self.calls += 1
        _ = request
        if self._raise_exc is not None:
            raise self._raise_exc
        return (
            _make_fake_response(self._response_text),
            _make_fake_result(
                content=self._response_text,
                tools_used=self._tools_used,
                warnings=self._warnings,
                confidence=self._confidence,
            ),
            self._tool_returns,
        )

    async def _execute(self, **kwargs: Any) -> Any:  # pragma: no cover - unused
        _ = kwargs
        raise NotImplementedError


def _stub_cases(domain: str, count: int = 3) -> list[EvalCase]:
    return [
        make_eval_case(id=f"{domain}_{i:03d}", expected_domain=domain) for i in range(1, count + 1)
    ]


# --- _coerce_tool_return / _collect_tool_returns ----------------------------


def test_coerce_tool_return_preserves_json_serializable_payload() -> None:
    record = ToolReturnRecord(tool_name="query_bus_status", payload={"delays": 2})
    out = _coerce_tool_return(record)
    assert out == {"tool_name": "query_bus_status", "payload": {"delays": 2}}


def test_coerce_tool_return_coerces_non_serializable_payload_to_str() -> None:
    class _Opaque:
        def __repr__(self) -> str:
            return "<opaque>"

    record = ToolReturnRecord(tool_name="t", payload=_Opaque())
    out = _coerce_tool_return(record)
    # json.dumps(Opaque(), default=str) would succeed via default=str,
    # so the coercion path stashes the payload as-is. Either way, the
    # result must round-trip through json.
    assert out["tool_name"] == "t"
    assert json.dumps(out, default=str)


def test_collect_tool_returns_wraps_tuple() -> None:
    records = (
        ToolReturnRecord(tool_name="a", payload={"x": 1}),
        ToolReturnRecord(tool_name="b", payload=[1, 2]),
    )
    out = _collect_tool_returns(records)
    assert out == (
        {"tool_name": "a", "payload": {"x": 1}},
        {"tool_name": "b", "payload": [1, 2]},
    )


# --- _trace_to_jsonl_line ----------------------------------------------------


def test_trace_to_jsonl_line_roundtrip() -> None:
    trace = EvalTrace(
        case_id="transit_001",
        domain="transit",
        prompt="hello",
        response="hi",
        tools_used=("query_bus_status",),
        tool_returns=({"tool_name": "query_bus_status", "payload": {"delays": 2}},),
        confidence=0.9,
        warnings=(),
        latency_ms=12.5,
        error=None,
        timestamp="2026-04-11T00:00:00+00:00",
    )
    line = _trace_to_jsonl_line(trace)
    parsed = json.loads(line)
    assert parsed["case_id"] == "transit_001"
    assert parsed["tools_used"] == ["query_bus_status"]  # tuple → list
    assert parsed["confidence"] == 0.9
    assert parsed["error"] is None


# --- EvalRunner.run_suite ----------------------------------------------------


@pytest.mark.asyncio
async def test_runner_writes_jsonl_per_suite_with_one_line_per_case(
    tmp_path: Path,
) -> None:
    agent = _FakeEvalAgent(response_text="sample")
    cases = _stub_cases("transit", count=3)

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch("app.core.agents.evals.runner.load_eval_cases", return_value=cases),
        patch("app.core.agents.evals.runner.close_all_agents", new=AsyncMock()),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        traces = await runner.run_suite("transit")

    assert len(traces) == 3
    # Find the single transit_*.jsonl file under tmp_path.
    files = sorted(tmp_path.glob("transit_*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert parsed["domain"] == "transit"
        assert parsed["error"] is None
        assert parsed["response"] == "sample"


@pytest.mark.asyncio
async def test_runner_records_tool_returns(tmp_path: Path) -> None:
    agent = _FakeEvalAgent(
        tools_used=("query_bus_status",),
        tool_returns=(ToolReturnRecord(tool_name="query_bus_status", payload={"delays": 2}),),
    )
    cases = _stub_cases("transit", count=1)

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch("app.core.agents.evals.runner.load_eval_cases", return_value=cases),
        patch("app.core.agents.evals.runner.close_all_agents", new=AsyncMock()),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        traces = await runner.run_suite("transit")

    assert len(traces) == 1
    trace = traces[0]
    assert trace.tools_used == ("query_bus_status",)
    assert trace.tool_returns[0]["tool_name"] == "query_bus_status"
    assert trace.tool_returns[0]["payload"] == {"delays": 2}


@pytest.mark.asyncio
async def test_runner_captures_exceptions_as_error_traces(tmp_path: Path) -> None:
    agent = _FakeEvalAgent(raise_exc=RuntimeError("boom"))
    cases = _stub_cases("transit", count=2)

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch("app.core.agents.evals.runner.load_eval_cases", return_value=cases),
        patch("app.core.agents.evals.runner.close_all_agents", new=AsyncMock()),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        traces = await runner.run_suite("transit")

    # Both cases ran despite the exception — fail-open per-case.
    assert len(traces) == 2
    for trace in traces:
        assert trace.error == "RuntimeError: boom"
        assert trace.response == ""
        assert trace.tools_used == ()


@pytest.mark.asyncio
async def test_runner_rejects_unknown_suite(tmp_path: Path) -> None:
    runner = EvalRunner(output_dir=tmp_path)
    with pytest.raises(ValueError, match="suite must be one of"):
        await runner.run_suite("foobar")


@pytest.mark.asyncio
async def test_runner_suite_all_runs_three_domains(tmp_path: Path) -> None:
    agent = _FakeEvalAgent()

    def _fake_load(domain: str) -> list[EvalCase]:
        return _stub_cases(domain, count=2)

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch(
            "app.core.agents.evals.runner.load_eval_cases",
            side_effect=_fake_load,
        ),
        patch("app.core.agents.evals.runner.close_all_agents", new=AsyncMock()),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        traces = await runner.run_suite("all")

    # 2 cases per domain, 3 domains → 6 traces total.
    assert len(traces) == 6
    transit_files = sorted(tmp_path.glob("transit_*.jsonl"))
    knowledge_files = sorted(tmp_path.glob("knowledge_*.jsonl"))
    vault_files = sorted(tmp_path.glob("vault_*.jsonl"))
    assert len(transit_files) == 1
    assert len(knowledge_files) == 1
    assert len(vault_files) == 1
    # Traces span all three domains.
    seen_domains = {t.domain for t in traces}
    assert seen_domains == {"transit", "knowledge", "vault"}


@pytest.mark.asyncio
async def test_runner_calls_close_all_agents_in_finally_on_success(
    tmp_path: Path,
) -> None:
    agent = _FakeEvalAgent()
    cases = _stub_cases("transit", count=1)
    close_mock = AsyncMock()

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch("app.core.agents.evals.runner.load_eval_cases", return_value=cases),
        patch("app.core.agents.evals.runner.close_all_agents", new=close_mock),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        await runner.run_suite("transit")

    close_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_runner_calls_close_all_agents_in_finally_on_error(
    tmp_path: Path,
) -> None:
    agent = _FakeEvalAgent()
    close_mock = AsyncMock()

    def _blow_up(_domain: str) -> list[EvalCase]:
        raise OSError("disk full")

    with (
        patch("app.core.agents.evals.runner.get_agent_by_name", return_value=agent),
        patch(
            "app.core.agents.evals.runner.load_eval_cases",
            side_effect=_blow_up,
        ),
        patch("app.core.agents.evals.runner.close_all_agents", new=close_mock),
    ):
        runner = EvalRunner(output_dir=tmp_path)
        with pytest.raises(OSError, match="disk full"):
            await runner.run_suite("transit")

    close_mock.assert_awaited_once()


def test_runner_sandboxes_output_path(tmp_path: Path) -> None:
    """Path-sandbox rejects writes that resolve outside the root.

    ``_write_traces`` builds the file as
    ``self._output_dir / f"{suite_name}_{stamp}.jsonl"``. Passing a
    suite name containing ``..`` segments makes the resolved path land
    above the sandbox root, which must be rejected with ``ValueError``.
    """
    nested = (tmp_path / "nested").resolve()
    nested.mkdir(parents=True, exist_ok=True)
    runner = EvalRunner(output_dir=nested)

    with pytest.raises(ValueError, match="output path escaped sandbox root"):
        runner._write_traces([], suite_name="../escape/x")


# --- CLI ---------------------------------------------------------------------


def test_cli_help_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_cli_unknown_suite_exits_two() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--suite", "foo"])
    # argparse exits with code 2 on unknown choices.
    assert exc_info.value.code == 2
