"""Eval runner + trace collection (AI-7.2).

CLI that runs synthetic ``EvalCase`` fixtures against the live per-domain
agents and writes one JSONL trace file per suite under ``evals/traces/``.
The runner is fail-open: an exception inside a single case produces an
``EvalTrace`` with ``error`` populated and the suite continues. The
runner never logs prompt or response content — only case IDs, domains,
counts, and latencies — mirroring the security posture of
:mod:`app.core.agents.evals.loader`.

Usage::

    python -m app.core.agents.evals.runner --suite transit
    python -m app.core.agents.evals.runner --suite all --output-dir evals/traces
"""

# pyright: reportUnknownMemberType=false

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from app.core.agents.agents.registry import close_all_agents, get_agent_by_name
from app.core.agents.evals.loader import load_eval_cases
from app.core.agents.evals.schemas import EvalCase
from app.core.agents.schemas import (
    AgentName,
    ChatCompletionRequest,
    ChatMessage,
)
from app.core.agents.validation import ToolReturnRecord
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_OUTPUT_DIR: Final[Path] = Path("evals/traces")
_SUITE_CHOICES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault", "all")
_DOMAIN_SUITES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault")


@dataclass(frozen=True, slots=True)
class EvalTrace:
    """One line of the JSONL trace output for one ``EvalCase`` run.

    Attributes:
        case_id: Stable ID from ``EvalCase.id`` (e.g. ``transit_001``).
        domain: The domain the case was routed to (``transit``/``knowledge``/
            ``vault``).
        prompt: The exact prompt fed to the agent.
        response: Final rendered response text (post ``_post_process``).
            Empty string on error.
        tools_used: Tool function names the agent invoked, in order.
        tool_returns: Per-tool JSON-serializable payloads from
            ``extract_tool_returns``. Non-serializable payloads are coerced
            to ``str``.
        confidence: ``AgentResult.confidence`` or ``None`` when unmeasured.
        warnings: QA warnings from validation; empty tuple on clean runs.
        latency_ms: Wall-clock time from request start to response ready.
        error: ``None`` on success, otherwise ``"<ExcType>: <str(exc)>"``.
        timestamp: ISO-8601 UTC timestamp captured at case start.
    """

    case_id: str
    domain: str
    prompt: str
    response: str
    tools_used: tuple[str, ...]
    tool_returns: tuple[dict[str, Any], ...]
    confidence: float | None
    warnings: tuple[str, ...]
    latency_ms: float
    error: str | None
    timestamp: str


def _coerce_tool_return(record: ToolReturnRecord) -> dict[str, Any]:
    """Return a JSON-serializable dict for one tool return.

    ``record.payload`` may be an arbitrary object graph from the tool.
    We try ``json.dumps`` first, falling back to ``str()`` so the trace
    never dies on a non-serializable payload.
    """
    payload: Any
    try:
        json.dumps(record.payload, ensure_ascii=False, default=str)
        payload = record.payload
    except (TypeError, ValueError):
        payload = str(record.payload)
    return {"tool_name": record.tool_name, "payload": payload}


def _collect_tool_returns(
    records: tuple[ToolReturnRecord, ...],
) -> tuple[dict[str, Any], ...]:
    """Coerce a tuple of ``ToolReturnRecord`` into JSON-safe dicts."""
    return tuple(_coerce_tool_return(r) for r in records)


def _trace_to_jsonl_line(trace: EvalTrace) -> str:
    """Serialize one ``EvalTrace`` as a single-line JSON string."""
    data = asdict(trace)
    # asdict turns tuples into lists, which is correct for JSONL.
    return json.dumps(data, ensure_ascii=False, default=str)


def _as_agent_name(domain: str) -> AgentName:
    """Narrow a validated domain string to the ``AgentName`` literal type."""
    if domain not in _DOMAIN_SUITES:
        msg = f"unexpected domain {domain!r}"
        raise ValueError(msg)
    return domain  # type: ignore[return-value]


@dataclass(slots=True)
class _SuiteSummary:
    """In-memory counters for the human-readable end-of-run summary."""

    suite: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    total_latency_ms: float = 0.0
    trace_path: Path | None = None


class EvalRunner:
    """Runs ``EvalCase`` fixtures through the live per-domain agents.

    The runner is fail-open: an exception inside ``_run_case`` produces an
    ``EvalTrace`` with ``error`` populated and the suite continues. Only
    infrastructure-level problems (e.g. unable to create the output
    directory, unknown suite name) abort the run.

    Example:
        >>> runner = EvalRunner(output_dir=Path("evals/traces"))
        >>> traces = await runner.run_suite("transit")
        >>> isinstance(traces, list)
        True
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize the runner.

        Args:
            output_dir: Where to write JSONL trace files. Defaults to
                ``evals/traces`` relative to CWD. The directory is created
                if missing; the resolved path is used as the sandbox root
                for subsequent per-trace file writes.
        """
        self._output_dir: Path = (output_dir or _DEFAULT_OUTPUT_DIR).resolve()
        self._summaries: list[_SuiteSummary] = []

    async def run_suite(self, suite: str) -> list[EvalTrace]:
        """Run one suite (``transit``/``knowledge``/``vault``) or all three.

        Args:
            suite: One of ``_SUITE_CHOICES``. ``all`` runs the three domain
                suites sequentially and writes one JSONL file per domain.

        Returns:
            Flat list of all traces produced in this invocation.

        Raises:
            ValueError: If ``suite`` is not in ``_SUITE_CHOICES``.
            OSError: If the output directory cannot be created.
        """
        if suite not in _SUITE_CHOICES:
            msg = f"suite must be one of {_SUITE_CHOICES}; got {suite!r}"
            raise ValueError(msg)

        self._output_dir.mkdir(parents=True, exist_ok=True)

        domains = _DOMAIN_SUITES if suite == "all" else (suite,)
        all_traces: list[EvalTrace] = []
        self._summaries = []

        try:
            for domain in domains:
                summary = _SuiteSummary(suite=domain)
                cases = load_eval_cases(domain)
                summary.total = len(cases)

                logger.info(
                    "agent.evals.runner.suite_started",
                    suite=domain,
                    total_cases=summary.total,
                    output_dir=str(self._output_dir),
                )

                traces = await self._run_cases(cases, domain)
                trace_path = self._write_traces(traces, suite_name=domain)
                summary.trace_path = trace_path

                for trace in traces:
                    summary.total_latency_ms += trace.latency_ms
                    if trace.error is None:
                        summary.passed += 1
                    else:
                        summary.failed += 1

                logger.info(
                    "agent.evals.runner.suite_completed",
                    suite=domain,
                    passed=summary.passed,
                    failed=summary.failed,
                    total_latency_ms=summary.total_latency_ms,
                    trace_path=str(trace_path),
                )

                all_traces.extend(traces)
                self._summaries.append(summary)
        finally:
            # AI-6.2: close per-domain HTTP clients. The unified AgentService
            # is closed by close_agent_service() in app.main lifespan; here we
            # only own the three domain singletons spun up by the runner.
            try:
                await close_all_agents()
            except Exception:
                logger.warning(
                    "agent.evals.runner.close_failed",
                    exc_info=True,
                )

        self._print_summary(self._summaries)
        return all_traces

    async def _run_cases(
        self,
        cases: list[EvalCase],
        domain: str,
    ) -> list[EvalTrace]:
        traces: list[EvalTrace] = []
        for case in cases:
            trace = await self._run_case(case, domain)
            traces.append(trace)
        return traces

    async def _run_case(self, case: EvalCase, domain: str) -> EvalTrace:
        """Execute one case through the matching domain agent (fail-open)."""
        agent_name = _as_agent_name(domain)
        agent = get_agent_by_name(agent_name)
        request = ChatCompletionRequest(
            messages=[ChatMessage(role="user", content=case.prompt)],
            agent=agent_name,
        )

        timestamp = _dt.datetime.now(_dt.UTC).isoformat()
        logger.info(
            "agent.evals.runner.case_started",
            case_id=case.id,
            domain=domain,
        )

        start = time.perf_counter()
        try:
            response, result, tool_return_records = await agent.chat_with_trace(
                request,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000.0
            logger.warning(
                "agent.evals.runner.case_failed",
                case_id=case.id,
                error_type=type(exc).__name__,
            )
            return EvalTrace(
                case_id=case.id,
                domain=domain,
                prompt=case.prompt,
                response="",
                tools_used=(),
                tool_returns=(),
                confidence=None,
                warnings=(),
                latency_ms=latency_ms,
                error=f"{type(exc).__name__}: {exc}",
                timestamp=timestamp,
            )

        latency_ms = (time.perf_counter() - start) * 1000.0

        logger.info(
            "agent.evals.runner.case_completed",
            case_id=case.id,
            latency_ms=round(latency_ms, 2),
            tools_count=len(result.tools_used),
            had_warnings=bool(result.warnings),
        )

        return EvalTrace(
            case_id=case.id,
            domain=domain,
            prompt=case.prompt,
            response=response.choices[0].message.content,
            tools_used=result.tools_used,
            tool_returns=_collect_tool_returns(tool_return_records),
            confidence=result.confidence,
            warnings=result.warnings,
            latency_ms=latency_ms,
            error=None,
            timestamp=timestamp,
        )

    def _write_traces(self, traces: list[EvalTrace], *, suite_name: str) -> Path:
        """Serialize traces as JSONL under ``<output_dir>/<suite>_<ts>.jsonl``.

        Path-sandboxed: after resolving, the output file must still be
        under ``self._output_dir`` or the method raises ``ValueError`` and
        emits an ``agent.evals.runner.path_escaped`` warning.
        """
        stamp = _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")
        out_path = (self._output_dir / f"{suite_name}_{stamp}.jsonl").resolve()
        if not out_path.is_relative_to(self._output_dir):
            logger.warning(
                "agent.evals.runner.path_escaped",
                path=str(out_path),
                root=str(self._output_dir),
            )
            msg = "output path escaped sandbox root"
            raise ValueError(msg)

        with out_path.open("w", encoding="utf-8") as fh:
            for trace in traces:
                fh.write(_trace_to_jsonl_line(trace))
                fh.write("\n")
        return out_path

    def _print_summary(self, summaries: list[_SuiteSummary]) -> None:
        """Print a human-readable summary to stdout (CLI UX only)."""
        for s in summaries:
            avg = (s.total_latency_ms / s.total) if s.total else 0.0
            trace = s.trace_path if s.trace_path is not None else "<no trace>"
            print(
                f"[{s.suite}] {s.passed}/{s.total} passed, "
                f"{s.failed} failed, avg {avg:.0f}ms, "
                f"trace={trace}"
            )


# --- CLI --------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.core.agents.evals.runner",
        description="Run synthetic EvalCases against the live VTV agents.",
    )
    parser.add_argument(
        "--suite",
        required=True,
        choices=_SUITE_CHOICES,
        help="Suite to run: transit, knowledge, vault, or all.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=(f"Directory to write JSONL trace files. Defaults to {_DEFAULT_OUTPUT_DIR}."),
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    runner = EvalRunner(output_dir=args.output_dir)
    try:
        traces = await runner.run_suite(args.suite)
    except (OSError, ValueError) as exc:
        logger.error(
            "agent.evals.runner.aborted",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 2
    failed = sum(1 for t in traces if t.error is not None)
    return 0 if failed == 0 else 1


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EvalRunner",
    "EvalTrace",
    "main",
]
