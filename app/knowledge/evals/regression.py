"""RAG regression baselines (AI-11.4).

Extracts metric baselines from RunReport, persists as JSON under
evals/rag/baseline.json (committed, not gitignored), and compares
fresh runs against stored numbers with configurable tolerance.

CLI: python -m app.knowledge.evals.regression baseline --report <path>
     python -m app.knowledge.evals.regression check --report <path>
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import Any, Final

from app.core.logging import get_logger
from app.knowledge.evals.schemas import (
    QAPair,
    RAGBaseline,
    RegressionFinding,
    RegressionReport,
    RunReport,
)

logger = get_logger(__name__)

_DEFAULT_BASELINE_PATH: Final[Path] = Path("evals/rag/baseline.json")
_DEFAULT_QA_DIR: Final[Path] = Path("evals/rag")
_METRIC_NAMES: Final[tuple[str, ...]] = (
    "recall_at_1",
    "recall_at_3",
    "recall_at_10",
    "mrr",
    "mean_completeness",
    "mean_faithfulness",
)


def _utc_now_iso(now: _dt.datetime | None = None) -> str:
    moment = now if now is not None else _dt.datetime.now(_dt.UTC)
    return moment.isoformat()


def compute_corpus_checksum(qa_pairs: list[QAPair]) -> str:
    """SHA-256 of sorted source chunk IDs from QA pairs."""
    payload = "|".join(
        str(p.source_chunk_id) for p in sorted(qa_pairs, key=lambda p: p.source_chunk_id)
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def generate_baseline(
    report: RunReport,
    *,
    qa_pairs: list[QAPair],
    now: _dt.datetime | None = None,
) -> RAGBaseline:
    """Extract metric baseline from a RunReport.

    Args:
        report: Completed eval run report.
        qa_pairs: QA pairs used in the run (for corpus checksum).
        now: Optional UTC timestamp override (test seam).

    Returns:
        Frozen RAGBaseline with all tracked metrics.
    """
    rm = report.retrieval_metrics
    baseline = RAGBaseline(
        recall_at_1=rm.recall_at_1,
        recall_at_3=rm.recall_at_3,
        recall_at_10=rm.recall_at_10,
        mrr=rm.mrr,
        mean_completeness=rm.mean_completeness,
        mean_faithfulness=report.mean_faithfulness,
        total_pairs=report.total_pairs,
        generated_at=_utc_now_iso(now),
        corpus_checksum=compute_corpus_checksum(qa_pairs),
    )
    logger.info(
        "knowledge.evals.regression.baseline_generated",
        total_pairs=baseline.total_pairs,
        corpus_checksum=baseline.corpus_checksum[:12],
    )
    return baseline


def _get_metric(obj: RunReport | RAGBaseline, name: str) -> float:
    if name == "mean_faithfulness":
        return obj.mean_faithfulness
    if isinstance(obj, RunReport):
        return float(getattr(obj.retrieval_metrics, name))
    return float(getattr(obj, name))


def check_regression(
    current: RunReport,
    baseline: RAGBaseline,
    *,
    qa_pairs: list[QAPair],
    tolerance: float = 0.03,
) -> RegressionReport:
    """Compare current metrics against a stored baseline.

    A metric regresses when ``current - baseline < -tolerance``.

    Args:
        current: Fresh eval run report.
        baseline: Stored baseline to compare against.
        qa_pairs: Current QA pairs (for corpus checksum comparison).
        tolerance: Absolute drop allowed before flagging (default 0.03 = 3pp).

    Returns:
        RegressionReport with findings for each regressed metric.
    """
    findings: list[RegressionFinding] = []
    current_checksum = compute_corpus_checksum(qa_pairs)
    checksum_match = current_checksum == baseline.corpus_checksum

    if not checksum_match:
        logger.warning(
            "knowledge.evals.regression.corpus_checksum_mismatch",
            baseline_checksum=baseline.corpus_checksum[:12],
            current_checksum=current_checksum[:12],
        )

    for name in _METRIC_NAMES:
        current_val = _get_metric(current, name)
        baseline_val = _get_metric(baseline, name)
        delta = current_val - baseline_val
        if delta < -tolerance:
            findings.append(
                RegressionFinding(
                    metric_name=name,
                    baseline_value=baseline_val,
                    current_value=current_val,
                    delta=delta,
                    tolerance=tolerance,
                )
            )
            logger.warning(
                "knowledge.evals.regression.regression_detected",
                metric=name,
                delta=round(delta, 4),
            )

    passed = len(findings) == 0
    if passed:
        logger.info(
            "knowledge.evals.regression.check_passed",
            metrics_checked=len(_METRIC_NAMES),
        )

    return RegressionReport(
        passed=passed,
        tolerance=tolerance,
        findings=tuple(findings),
        corpus_checksum_match=checksum_match,
        generated_at=_utc_now_iso(),
    )


def _baseline_to_json(baseline: RAGBaseline) -> dict[str, Any]:
    return {
        "recall_at_1": baseline.recall_at_1,
        "recall_at_3": baseline.recall_at_3,
        "recall_at_10": baseline.recall_at_10,
        "mrr": baseline.mrr,
        "mean_completeness": baseline.mean_completeness,
        "mean_faithfulness": baseline.mean_faithfulness,
        "total_pairs": baseline.total_pairs,
        "generated_at": baseline.generated_at,
        "corpus_checksum": baseline.corpus_checksum,
    }


def _baseline_from_json(data: dict[str, Any]) -> RAGBaseline:
    def _float(key: str) -> float:
        raw = data.get(key, 0.0)
        return float(raw) if isinstance(raw, int | float) else 0.0

    def _int(key: str) -> int:
        raw = data.get(key, 0)
        return int(raw) if isinstance(raw, int | float) else 0

    return RAGBaseline(
        recall_at_1=_float("recall_at_1"),
        recall_at_3=_float("recall_at_3"),
        recall_at_10=_float("recall_at_10"),
        mrr=_float("mrr"),
        mean_completeness=_float("mean_completeness"),
        mean_faithfulness=_float("mean_faithfulness"),
        total_pairs=_int("total_pairs"),
        generated_at=str(data.get("generated_at") or ""),
        corpus_checksum=str(data.get("corpus_checksum") or ""),
    )


def write_baseline(baseline: RAGBaseline, *, baseline_path: Path) -> Path:
    """Write a RAGBaseline to a path-sandboxed JSON file.

    Args:
        baseline: The baseline to persist.
        baseline_path: Target file path.

    Returns:
        The resolved path of the written file.

    Raises:
        ValueError: If the resolved path escapes the parent directory.
    """
    resolved = baseline_path.resolve()
    parent = resolved.parent
    parent.mkdir(parents=True, exist_ok=True)

    if not resolved.is_relative_to(parent):
        logger.warning(
            "knowledge.evals.regression.path_escaped",
            path=str(resolved),
        )
        msg = "baseline path escaped sandbox root"
        raise ValueError(msg)

    payload = _baseline_to_json(baseline)
    with resolved.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    logger.info(
        "knowledge.evals.regression.baseline_written",
        path=str(resolved),
    )
    return resolved


def read_baseline(*, baseline_path: Path) -> RAGBaseline | None:
    """Load a stored RAGBaseline JSON file.

    Args:
        baseline_path: Path to the baseline JSON file.

    Returns:
        The parsed RAGBaseline, or None if the file does not exist.

    Raises:
        ValueError: If the resolved path escapes its parent directory.
    """
    resolved = baseline_path.resolve()
    parent = resolved.parent

    if not resolved.is_relative_to(parent):
        logger.warning(
            "knowledge.evals.regression.path_escaped",
            path=str(resolved),
        )
        msg = "baseline path escaped sandbox root"
        raise ValueError(msg)

    if not resolved.is_file():
        return None

    with resolved.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        msg = f"baseline file {resolved} does not contain a JSON object"
        raise ValueError(msg)
    return _baseline_from_json(raw)


# --- CLI --------------------------------------------------------------------


def _load_report(path: Path) -> RunReport:
    """Load a RunReport from a JSON file."""
    from dataclasses import fields as dc_fields

    from app.knowledge.evals.schemas import (
        CaseResult,
        FaithfulnessResult,
        PairMetrics,
        RetrievalMetrics,
    )

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    rm_data = data["retrieval_metrics"]
    retrieval_metrics = RetrievalMetrics(
        **{f.name: rm_data[f.name] for f in dc_fields(RetrievalMetrics)}
    )

    case_results: list[CaseResult] = []
    for cr_data in data.get("case_results", []):
        qa_data = cr_data["qa_pair"]
        qa_pair = QAPair(**{f.name: qa_data[f.name] for f in dc_fields(QAPair)})
        pm_data = cr_data["pair_metrics"]
        pair_metrics = PairMetrics(**{f.name: pm_data[f.name] for f in dc_fields(PairMetrics)})
        fr_data = cr_data["faithfulness"]
        faithfulness = FaithfulnessResult(
            **{f.name: fr_data[f.name] for f in dc_fields(FaithfulnessResult)}
        )
        case_results.append(
            CaseResult(
                qa_pair=qa_pair,
                pair_metrics=pair_metrics,
                faithfulness=faithfulness,
                search_latency_ms=cr_data["search_latency_ms"],
                judge_latency_ms=cr_data["judge_latency_ms"],
            )
        )

    return RunReport(
        run_id=data["run_id"],
        timestamp=data["timestamp"],
        qa_file=data["qa_file"],
        total_pairs=data["total_pairs"],
        retrieval_metrics=retrieval_metrics,
        mean_faithfulness=data["mean_faithfulness"],
        faithfulness_errors=data["faithfulness_errors"],
        case_results=tuple(case_results),
    )


def _load_qa_pairs(path: Path) -> list[QAPair]:
    """Load QA pairs from a JSONL file."""
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
    return pairs


def _resolve_qa_file(qa_file_arg: Path | None, report: RunReport) -> Path:
    """Resolve QA file path from CLI arg or report metadata."""
    if qa_file_arg is not None:
        return qa_file_arg
    if report.qa_file:
        return Path(report.qa_file)
    return _DEFAULT_QA_DIR / "qa_pairs.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.knowledge.evals.regression",
        description="Generate and check RAG eval regression baselines (AI-11.4).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    baseline_p = sub.add_parser(
        "baseline",
        help="Generate a baseline from an eval report.",
    )
    baseline_p.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to eval report JSON file.",
    )
    baseline_p.add_argument(
        "--qa-file",
        type=Path,
        default=None,
        help="Path to QA pairs JSONL file.",
    )
    baseline_p.add_argument(
        "--baseline-path",
        type=Path,
        default=_DEFAULT_BASELINE_PATH,
        help=f"Output path for baseline JSON. Default: {_DEFAULT_BASELINE_PATH}.",
    )
    baseline_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing baseline file.",
    )

    check_p = sub.add_parser(
        "check",
        help="Compare an eval report against the stored baseline.",
    )
    check_p.add_argument(
        "--report",
        type=Path,
        required=True,
        help="Path to eval report JSON file.",
    )
    check_p.add_argument(
        "--qa-file",
        type=Path,
        default=None,
        help="Path to QA pairs JSONL file.",
    )
    check_p.add_argument(
        "--baseline-path",
        type=Path,
        default=_DEFAULT_BASELINE_PATH,
        help=f"Path to baseline JSON. Default: {_DEFAULT_BASELINE_PATH}.",
    )
    check_p.add_argument(
        "--tolerance",
        type=float,
        default=0.03,
        help="Max allowed drop per metric (default: 0.03 = 3pp).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Synchronous CLI entrypoint."""
    args = _build_parser().parse_args(argv)

    try:
        report = _load_report(args.report)
        qa_path = _resolve_qa_file(args.qa_file, report)
        qa_pairs = _load_qa_pairs(qa_path)
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as exc:
        logger.error(
            "knowledge.evals.regression.aborted",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 2

    if args.command == "baseline":
        baseline_path: Path = args.baseline_path
        if not args.force and baseline_path.is_file():
            logger.error(
                "knowledge.evals.regression.aborted",
                error_type="FileExistsError",
                error=f"baseline already exists at {baseline_path}; pass --force to overwrite",
            )
            return 2
        baseline = generate_baseline(report, qa_pairs=qa_pairs)
        write_baseline(baseline, baseline_path=baseline_path)
        print(f"Baseline written: {baseline_path}")
        return 0

    if args.command == "check":
        baseline_path = args.baseline_path
        existing = read_baseline(baseline_path=baseline_path)
        if existing is None:
            logger.error(
                "knowledge.evals.regression.aborted",
                error_type="FileNotFoundError",
                error=f"no baseline at {baseline_path}; run 'baseline' first",
            )
            return 2
        result = check_regression(
            report,
            existing,
            qa_pairs=qa_pairs,
            tolerance=args.tolerance,
        )
        if not result.corpus_checksum_match:
            print("WARNING: corpus checksum mismatch - baseline may be stale")
        if not result.passed:
            for f in result.findings:
                print(
                    f"REGRESSION: {f.metric_name} "
                    f"baseline={f.baseline_value:.4f} "
                    f"current={f.current_value:.4f} "
                    f"delta={f.delta:+.4f} "
                    f"tolerance={f.tolerance:.4f}"
                )
            return 1
        print("All metrics within tolerance.")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "check_regression",
    "compute_corpus_checksum",
    "generate_baseline",
    "main",
    "read_baseline",
    "write_baseline",
]
