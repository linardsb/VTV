# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false

"""RAG evaluation runner (AI-11.3).

Runs QA pairs through KnowledgeService.search(), computes retrieval metrics
via AI-11.2, and optionally judges faithfulness via LLM.

CLI: python -m app.knowledge.evals.runner --qa-file evals/rag/qa_pairs_*.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Final

from app.core.database import get_db_context
from app.core.logging import get_logger
from app.knowledge.evals.faithfulness import FaithfulnessJudge
from app.knowledge.evals.metrics import aggregate_metrics, compute_pair_metrics
from app.knowledge.evals.schemas import (
    CaseResult,
    FaithfulnessResult,
    PairMetrics,
    QAPair,
    RunReport,
)
from app.knowledge.schemas import SearchRequest, SearchResponse

logger = get_logger(__name__)

_DEFAULT_OUTPUT_DIR: Final[Path] = Path("evals/rag")
_NO_FAITHFULNESS: Final[FaithfulnessResult] = FaithfulnessResult(
    grounded=None,
    accurate=None,
    complete=None,
    passed=None,
    error=None,
)


class RAGEvalRunner:
    """Orchestrates RAG evaluation: search + metrics + faithfulness.

    Runs each QA pair through KnowledgeService.search(), computes
    retrieval metrics (AI-11.2), and optionally judges faithfulness
    via an LLM judge. Fail-open per pair.

    Example:
        >>> runner = RAGEvalRunner(judge=FaithfulnessJudge())
        >>> report = await runner.run(qa_pairs, limit=10)
        >>> report.mean_faithfulness
        0.85
    """

    def __init__(self, *, judge: FaithfulnessJudge | None = None) -> None:
        """Initialize the runner.

        Args:
            judge: Optional faithfulness judge. If None, faithfulness
                scoring is skipped and all results get passed=None.
        """
        self._judge = judge

    async def run(
        self,
        qa_pairs: list[QAPair],
        *,
        limit: int = 10,
        qa_file: str = "",
    ) -> RunReport:
        """Run evaluation on a list of QA pairs.

        Args:
            qa_pairs: QA pairs to evaluate.
            limit: Max search results per query.
            qa_file: Source file path for the report metadata.

        Returns:
            RunReport with retrieval metrics and faithfulness stats.
        """
        run_id = uuid.uuid4().hex[:12]
        logger.info(
            "knowledge.eval_runner.run_started",
            run_id=run_id,
            total_pairs=len(qa_pairs),
            limit=limit,
        )
        start = time.monotonic()

        case_results: list[CaseResult] = []
        pair_metrics_list: list[PairMetrics] = []

        for idx, pair in enumerate(qa_pairs):
            case_result = await self._evaluate_pair(idx, pair, limit=limit)
            case_results.append(case_result)
            pair_metrics_list.append(case_result.pair_metrics)

        retrieval_metrics = aggregate_metrics(pair_metrics_list)
        mean_faith, faith_errors = _compute_faithfulness_stats(case_results)

        elapsed_s = time.monotonic() - start
        logger.info(
            "knowledge.eval_runner.run_completed",
            run_id=run_id,
            total_pairs=len(qa_pairs),
            recall_at_3=round(retrieval_metrics.recall_at_3, 3),
            mrr=round(retrieval_metrics.mrr, 3),
            mean_faithfulness=round(mean_faith, 3),
            duration_s=round(elapsed_s, 1),
        )

        return RunReport(
            run_id=run_id,
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            qa_file=qa_file,
            total_pairs=len(qa_pairs),
            retrieval_metrics=retrieval_metrics,
            mean_faithfulness=mean_faith,
            faithfulness_errors=faith_errors,
            case_results=tuple(case_results),
        )

    async def _evaluate_pair(
        self,
        idx: int,
        pair: QAPair,
        *,
        limit: int,
    ) -> CaseResult:
        """Evaluate a single QA pair (fail-open)."""
        search_start = time.monotonic()
        search_latency_ms = 0.0
        judge_latency_ms = 0.0

        try:
            response = await self._search(pair, limit=limit)
            search_latency_ms = (time.monotonic() - search_start) * 1000

            pair_metrics = compute_pair_metrics(pair, response.results)

            faithfulness = _NO_FAITHFULNESS
            if self._judge is not None:
                judge_start = time.monotonic()
                source_content = _find_source_content(pair, response)
                faithfulness = await self._judge.judge(
                    pair.question,
                    response.results,
                    source_content,
                    pair_id=pair.source_chunk_id,
                )
                judge_latency_ms = (time.monotonic() - judge_start) * 1000

            logger.info(
                "knowledge.eval_runner.case_completed",
                case_index=idx,
                search_ms=round(search_latency_ms, 1),
                judge_ms=round(judge_latency_ms, 1),
            )

            return CaseResult(
                qa_pair=pair,
                pair_metrics=pair_metrics,
                faithfulness=faithfulness,
                search_latency_ms=search_latency_ms,
                judge_latency_ms=judge_latency_ms,
            )

        except Exception as exc:
            search_latency_ms = (time.monotonic() - search_start) * 1000
            logger.warning(
                "knowledge.eval_runner.case_failed",
                case_index=idx,
                error_type=type(exc).__name__,
            )
            return CaseResult(
                qa_pair=pair,
                pair_metrics=PairMetrics(
                    relevance_hit=False,
                    rank=None,
                    mrr_contribution=0.0,
                    completeness=0.0,
                ),
                faithfulness=FaithfulnessResult(
                    grounded=None,
                    accurate=None,
                    complete=None,
                    passed=None,
                    error=f"{type(exc).__name__}: {exc}",
                ),
                search_latency_ms=search_latency_ms,
                judge_latency_ms=0.0,
            )

    async def _search(self, pair: QAPair, *, limit: int) -> SearchResponse:
        """Run search via KnowledgeService."""
        from app.knowledge.service import KnowledgeService

        async with get_db_context() as session:
            svc = KnowledgeService(session)
            request = SearchRequest(
                query=pair.question,
                language=pair.language,
                limit=limit,
            )
            return await svc.search(request)


def _find_source_content(pair: QAPair, response: SearchResponse) -> str:
    """Find source chunk content from search results or return placeholder."""
    for result in response.results:
        if (
            result.document_id == pair.source_document_id
            and result.chunk_index == pair.source_chunk_index
        ):
            return result.chunk_content
    return "(source chunk not in search results)"


def _compute_faithfulness_stats(
    case_results: list[CaseResult],
) -> tuple[float, int]:
    """Compute mean faithfulness rate and error count.

    Returns:
        Tuple of (mean_faithfulness, error_count).
    """
    judged = 0
    passed = 0
    errors = 0

    for cr in case_results:
        if cr.faithfulness.passed is None:
            if cr.faithfulness.error is not None:
                errors += 1
        else:
            judged += 1
            if cr.faithfulness.passed:
                passed += 1

    mean_faith = passed / judged if judged > 0 else 0.0
    return mean_faith, errors


def _load_qa_pairs(path: Path) -> list[QAPair]:
    """Load QA pairs from a JSONL file.

    Args:
        path: Path to the JSONL file.

    Returns:
        List of QAPair instances.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    if not path.is_file():
        msg = f"QA file not found: {path}"
        raise FileNotFoundError(msg)

    pairs: list[QAPair] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            pairs.append(QAPair(**data))

    logger.info(
        "knowledge.eval_runner.qa_loaded",
        path=str(path),
        pair_count=len(pairs),
    )
    return pairs


def _write_report(report: RunReport, output_dir: Path) -> Path:
    """Write a RunReport to a path-sandboxed JSON file.

    Args:
        report: The run report to persist.
        output_dir: Target directory for the output file.

    Returns:
        Path to the written JSON file.

    Raises:
        ValueError: If the resolved output path escapes the sandbox.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"eval_report_{report.run_id}.json"
    out_path = output_dir / filename

    if not out_path.resolve().is_relative_to(output_dir.resolve()):
        msg = "output path escaped sandbox root"
        raise ValueError(msg)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(asdict(report), fh, ensure_ascii=False, default=str, indent=2)

    logger.info(
        "knowledge.eval_runner.report_written",
        path=str(out_path),
        total_pairs=report.total_pairs,
    )
    return out_path


# --- CLI --------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="app.knowledge.evals.runner",
        description="Run RAG evaluation on existing QA pairs (AI-11.3).",
    )
    parser.add_argument(
        "--qa-file",
        type=Path,
        required=True,
        help="Path to QA pairs JSONL file.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Directory to write the eval report. Defaults to {_DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max search results per query (default: 10).",
    )
    parser.add_argument(
        "--no-judge",
        action="store_true",
        help="Skip faithfulness judging (metrics only).",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    """Async CLI entry point."""
    args = _build_parser().parse_args(argv)

    try:
        qa_pairs = _load_qa_pairs(args.qa_file)
    except FileNotFoundError as exc:
        logger.error(
            "knowledge.eval_runner.aborted",
            error_type="FileNotFoundError",
            error=str(exc),
        )
        return 2

    if not qa_pairs:
        logger.warning("knowledge.eval_runner.no_pairs_loaded")
        return 1

    judge: FaithfulnessJudge | None = None
    if not args.no_judge:
        judge = FaithfulnessJudge()

    runner = RAGEvalRunner(judge=judge)
    report = await runner.run(
        qa_pairs,
        limit=args.limit,
        qa_file=str(args.qa_file),
    )

    out_path = _write_report(report, args.output_dir)
    print(
        f"Eval complete: {report.total_pairs} pairs, "
        f"recall@3={report.retrieval_metrics.recall_at_3:.3f}, "
        f"MRR={report.retrieval_metrics.mrr:.3f}, "
        f"faithfulness={report.mean_faithfulness:.3f} "
        f"-> {out_path}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Synchronous CLI entrypoint."""
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "RAGEvalRunner",
    "main",
]
