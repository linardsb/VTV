"""Regression baselines for agent eval suites (AI-7.4).

Aggregates :class:`SuiteJudgement` outputs into per-criterion pass-rate
baselines, persists them as JSON under ``evals/baselines/`` (committed,
not gitignored), and compares fresh runs against the stored numbers with
a configurable percentage-point tolerance.

The default tolerance is 3pp via
:attr:`Settings.eval_baseline_tolerance_pct`. ``make eval-check`` is the
CI gate; ``make eval-baseline`` writes/updates the canonical numbers.

Security posture mirrors :mod:`app.core.agents.evals.judge`:

* Path-sandboxed I/O via ``Path.is_relative_to``.
* No raw prompt/response logging (verdicts contain only criterion grades).
* No new env vars; reuses :func:`get_settings`.

Usage::

    python -m app.core.agents.evals.regression baseline --suite transit
    python -m app.core.agents.evals.regression check --suite transit
    python -m app.core.agents.evals.regression check --suite all --update-baseline
"""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Final

from app.core.agents.evals.judge import (
    LLMJudge,
    _cases_by_id,
    _newest_trace_for_suite,
)
from app.core.agents.evals.schemas import (
    VALID_DOMAINS,
    BaselineReport,
    CriterionBaseline,
    RegressionFinding,
    RegressionReport,
    SuiteJudgement,
)
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_BASELINE_DIR: Final[Path] = Path("evals/baselines")
_DEFAULT_TRACE_DIR: Final[Path] = Path("evals/traces")
_SUITE_CHOICES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault", "all")
_DOMAIN_SUITES: Final[tuple[str, ...]] = ("transit", "knowledge", "vault")
_RATE_DECIMALS: Final[int] = 4


def _utc_now_iso(now: _dt.datetime | None = None) -> str:
    """Return an ISO-8601 UTC timestamp (injectable for tests)."""
    moment = now if now is not None else _dt.datetime.now(_dt.UTC)
    return moment.isoformat()


def generate_baseline(
    judgement: SuiteJudgement,
    *,
    total_cases: int,
    now: _dt.datetime | None = None,
) -> BaselineReport:
    """Aggregate a ``SuiteJudgement`` into per-criterion pass rates.

    Verdicts with ``error is not None`` are excluded from the
    denominator so a flaky judge does not inflate the failure rate.

    Args:
        judgement: The suite judgement produced by :class:`LLMJudge`.
        total_cases: Number of distinct eval cases the suite contains.
            Stored on the report; does not affect the rate calculation.
        now: Optional UTC timestamp override (test seam).

    Returns:
        A :class:`BaselineReport` with one :class:`CriterionBaseline`
        per criterion observed in the judgement.
    """
    counts: dict[str, list[int]] = {}
    for verdict in judgement.verdicts:
        if verdict.error is not None:
            continue
        bucket = counts.setdefault(verdict.criterion_name, [0, 0])
        bucket[1] += 1
        if verdict.passed:
            bucket[0] += 1

    timestamp = _utc_now_iso(now)
    criteria: list[CriterionBaseline] = []
    for criterion_name in sorted(counts):
        passed_count, sample_count = counts[criterion_name]
        rate = round(passed_count / sample_count, _RATE_DECIMALS) if sample_count else 0.0
        criteria.append(
            CriterionBaseline(
                suite=judgement.suite,
                criterion_name=criterion_name,
                pass_rate=rate,
                sample_count=sample_count,
                created_at=timestamp,
            )
        )

    logger.info(
        "agent.evals.regression.baseline_generated",
        suite=judgement.suite,
        criteria_count=len(criteria),
        total_cases=total_cases,
    )

    return BaselineReport(
        suite=judgement.suite,
        criteria=tuple(criteria),
        total_cases=total_cases,
        created_at=timestamp,
    )


def check_regression(
    current: BaselineReport,
    baseline: BaselineReport,
    *,
    tolerance_pct: float = 3.0,
    now: _dt.datetime | None = None,
) -> RegressionReport:
    """Compare a fresh ``BaselineReport`` against a stored baseline.

    A criterion regresses when
    ``(current.pass_rate - baseline.pass_rate) * 100 < -tolerance_pct``.
    Criteria present in ``current`` but absent in ``baseline`` are
    reported under ``missing_baselines`` (not failed).

    Args:
        current: Pass-rate report from the run being checked.
        baseline: Stored canonical baseline.
        tolerance_pct: Allowed drop in percentage points before a
            regression is recorded. Must be ``>= 0``.
        now: Optional UTC timestamp override (test seam).

    Returns:
        A :class:`RegressionReport`. Empty ``findings`` means the run
        passed.

    Raises:
        ValueError: If ``tolerance_pct`` is negative.
    """
    if tolerance_pct < 0:
        msg = f"tolerance_pct must be >= 0; got {tolerance_pct}"
        raise ValueError(msg)

    baseline_by_name = {c.criterion_name: c for c in baseline.criteria}
    findings: list[RegressionFinding] = []
    missing: list[str] = []

    for current_crit in current.criteria:
        baseline_crit = baseline_by_name.get(current_crit.criterion_name)
        if baseline_crit is None:
            missing.append(current_crit.criterion_name)
            logger.info(
                "agent.evals.regression.baseline_missing",
                suite=current.suite,
                criterion_name=current_crit.criterion_name,
            )
            continue
        delta_pct = (current_crit.pass_rate - baseline_crit.pass_rate) * 100.0
        if delta_pct < -tolerance_pct:
            finding = RegressionFinding(
                suite=current.suite,
                criterion_name=current_crit.criterion_name,
                baseline_rate=baseline_crit.pass_rate,
                current_rate=current_crit.pass_rate,
                delta_pct=delta_pct,
                tolerance_pct=tolerance_pct,
            )
            findings.append(finding)
            logger.warning(
                "agent.evals.regression.regression_detected",
                suite=current.suite,
                criterion_name=current_crit.criterion_name,
                delta_pct=round(delta_pct, 2),
            )

    if not findings:
        logger.info(
            "agent.evals.regression.check_passed",
            suite=current.suite,
            total_checks=len(current.criteria),
        )

    return RegressionReport(
        suite=current.suite,
        tolerance_pct=tolerance_pct,
        findings=tuple(findings),
        missing_baselines=tuple(missing),
        created_at=_utc_now_iso(now),
    )


def _baseline_to_json(report: BaselineReport) -> dict[str, Any]:
    return {
        "suite": report.suite,
        "total_cases": report.total_cases,
        "created_at": report.created_at,
        "criteria": [
            {
                "name": c.criterion_name,
                "pass_rate": c.pass_rate,
                "sample_count": c.sample_count,
            }
            for c in report.criteria
        ],
    }


def _baseline_from_json(data: dict[str, Any], suite: str) -> BaselineReport:
    raw_criteria = data.get("criteria") or []
    if not isinstance(raw_criteria, list):
        msg = "baseline 'criteria' must be a list"
        raise ValueError(msg)
    created_at = str(data.get("created_at") or "")
    total_cases_raw = data.get("total_cases", 0)
    total_cases = int(total_cases_raw) if isinstance(total_cases_raw, int | float) else 0

    criteria: list[CriterionBaseline] = []
    for entry in raw_criteria:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "")
        pass_rate_raw = entry.get("pass_rate", 0.0)
        sample_count_raw = entry.get("sample_count", 0)
        if not name:
            continue
        pass_rate = float(pass_rate_raw) if isinstance(pass_rate_raw, int | float) else 0.0
        sample_count = int(sample_count_raw) if isinstance(sample_count_raw, int | float) else 0
        criteria.append(
            CriterionBaseline(
                suite=suite,
                criterion_name=name,
                pass_rate=round(pass_rate, _RATE_DECIMALS),
                sample_count=sample_count,
                created_at=created_at,
            )
        )

    return BaselineReport(
        suite=suite,
        criteria=tuple(criteria),
        total_cases=total_cases,
        created_at=created_at,
    )


def write_baseline(
    report: BaselineReport,
    *,
    baseline_dir: Path,
) -> Path:
    """Write a ``BaselineReport`` to ``<baseline_dir>/<suite>_baseline.json``.

    Path-sandboxed via :meth:`pathlib.Path.is_relative_to`. The directory
    is created on demand.

    Args:
        report: The baseline to persist.
        baseline_dir: Target directory; resolved and used as the sandbox
            root.

    Returns:
        The resolved path of the written file.

    Raises:
        ValueError: If the resolved output path escapes ``baseline_dir``
            or the suite name is not in :data:`VALID_DOMAINS`.
    """
    if report.suite not in VALID_DOMAINS:
        msg = f"baseline suite={report.suite!r} not in {sorted(VALID_DOMAINS)}"
        raise ValueError(msg)

    root = baseline_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    out_path = (root / f"{report.suite}_baseline.json").resolve()
    if not out_path.is_relative_to(root):
        logger.warning(
            "agent.evals.regression.path_escaped",
            path=str(out_path),
            root=str(root),
        )
        msg = "baseline path escaped sandbox root"
        raise ValueError(msg)

    payload = _baseline_to_json(report)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")

    logger.info(
        "agent.evals.regression.baseline_written",
        suite=report.suite,
        path=str(out_path),
    )
    return out_path


def read_baseline(
    suite: str,
    *,
    baseline_dir: Path,
) -> BaselineReport | None:
    """Load a stored baseline JSON file.

    Args:
        suite: Domain name (must be in :data:`VALID_DOMAINS`).
        baseline_dir: Directory holding ``{suite}_baseline.json``.

    Returns:
        The parsed :class:`BaselineReport`, or ``None`` if the file does
        not exist (first-run case).

    Raises:
        ValueError: If the suite name is invalid or the resolved path
            escapes ``baseline_dir``.
    """
    if suite not in VALID_DOMAINS:
        msg = f"suite={suite!r} not in {sorted(VALID_DOMAINS)}"
        raise ValueError(msg)

    root = baseline_dir.resolve()
    if not root.is_dir():
        return None
    target = (root / f"{suite}_baseline.json").resolve()
    if not target.is_relative_to(root):
        logger.warning(
            "agent.evals.regression.path_escaped",
            path=str(target),
            root=str(root),
        )
        msg = "baseline path escaped sandbox root"
        raise ValueError(msg)
    if not target.is_file():
        return None

    with target.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if not isinstance(raw, dict):
        msg = f"baseline file {target} does not contain a JSON object"
        raise ValueError(msg)
    return _baseline_from_json(raw, suite)


# --- CLI --------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="app.core.agents.evals.regression",
        description="Generate and check per-criterion eval baselines.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--suite",
        required=True,
        choices=_SUITE_CHOICES,
        help="Suite to operate on: transit, knowledge, vault, or all.",
    )
    common.add_argument(
        "--trace-dir",
        type=Path,
        default=_DEFAULT_TRACE_DIR,
        help=f"Directory holding the JSONL trace files. Default: {_DEFAULT_TRACE_DIR}.",
    )
    common.add_argument(
        "--baseline-dir",
        type=Path,
        default=_DEFAULT_BASELINE_DIR,
        help=f"Directory for the JSON baseline files. Default: {_DEFAULT_BASELINE_DIR}.",
    )

    baseline_p = sub.add_parser(
        "baseline",
        parents=[common],
        help="Generate or update baselines from the latest judged run.",
    )
    baseline_p.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing baseline file.",
    )

    check_p = sub.add_parser(
        "check",
        parents=[common],
        help="Judge latest traces and compare against the stored baseline.",
    )
    check_p.add_argument(
        "--tolerance-pct",
        type=float,
        default=None,
        help="Override the per-criterion tolerance in percentage points.",
    )
    check_p.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite baseline with the new numbers after a clean check.",
    )

    return parser


async def _judge_one_suite(
    suite: str,
    *,
    trace_dir: Path,
) -> tuple[SuiteJudgement, int] | None:
    """Run the judge over the newest trace for ``suite``.

    Returns ``None`` if there is no trace file (CLI converts to exit 2).
    """
    trace_path = _newest_trace_for_suite(trace_dir, suite)
    if trace_path is None:
        logger.error(
            "agent.evals.regression.no_trace",
            suite=suite,
            trace_dir=str(trace_dir),
        )
        return None
    cases = _cases_by_id(suite)
    judge = LLMJudge()
    judgement = await judge.judge_trace_file(trace_path, suite, cases)
    return judgement, len(cases)


async def _run_baseline(args: argparse.Namespace) -> int:
    suites: tuple[str, ...] = _DOMAIN_SUITES if args.suite == "all" else (args.suite,)
    baseline_dir: Path = args.baseline_dir
    trace_dir: Path = args.trace_dir

    for suite in suites:
        if not args.force:
            existing = read_baseline(suite, baseline_dir=baseline_dir)
            if existing is not None:
                logger.error(
                    "agent.evals.regression.aborted",
                    error_type="FileExistsError",
                    error=f"baseline already exists for suite={suite}; pass --force to overwrite",
                    suite=suite,
                )
                return 2
        judged = await _judge_one_suite(suite, trace_dir=trace_dir)
        if judged is None:
            return 2
        judgement, total_cases = judged
        report = generate_baseline(judgement, total_cases=total_cases)
        write_baseline(report, baseline_dir=baseline_dir)
    return 0


async def _run_check(args: argparse.Namespace) -> int:
    settings = get_settings()
    tolerance_pct: float = (
        float(args.tolerance_pct)
        if args.tolerance_pct is not None
        else float(settings.eval_baseline_tolerance_pct)
    )
    suites: tuple[str, ...] = _DOMAIN_SUITES if args.suite == "all" else (args.suite,)
    baseline_dir: Path = args.baseline_dir
    trace_dir: Path = args.trace_dir

    any_regression = False
    for suite in suites:
        baseline = read_baseline(suite, baseline_dir=baseline_dir)
        if baseline is None:
            logger.error(
                "agent.evals.regression.aborted",
                error_type="FileNotFoundError",
                error=f"no baseline for suite={suite}; run 'baseline' first",
                suite=suite,
            )
            return 2
        judged = await _judge_one_suite(suite, trace_dir=trace_dir)
        if judged is None:
            return 2
        judgement, total_cases = judged
        current = generate_baseline(judgement, total_cases=total_cases)
        logger.info(
            "agent.evals.regression.check_started",
            suite=suite,
            tolerance_pct=tolerance_pct,
        )
        report = check_regression(
            current,
            baseline,
            tolerance_pct=tolerance_pct,
        )
        if not report.passed:
            any_regression = True
            for finding in report.findings:
                print(
                    f"[{finding.suite}] regression: {finding.criterion_name} "
                    f"baseline={finding.baseline_rate:.4f} "
                    f"current={finding.current_rate:.4f} "
                    f"delta={finding.delta_pct:+.2f}pp "
                    f"tolerance={finding.tolerance_pct:.2f}pp"
                )
        if report.passed and args.update_baseline:
            write_baseline(current, baseline_dir=baseline_dir)

    return 1 if any_regression else 0


async def _amain(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "baseline":
            return await _run_baseline(args)
        if args.command == "check":
            return await _run_check(args)
    except (OSError, ValueError) as exc:
        logger.error(
            "agent.evals.regression.aborted",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 2
    return 2


def main(argv: list[str] | None = None) -> int:
    """Synchronous CLI entrypoint that drives :func:`_amain`."""
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "check_regression",
    "generate_baseline",
    "main",
    "read_baseline",
    "write_baseline",
]
