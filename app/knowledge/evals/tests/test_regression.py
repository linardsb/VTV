# pyright: reportUnknownMemberType=false
"""Tests for RAG regression baselines (AI-11.4)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from app.knowledge.evals.regression import (
    check_regression,
    compute_corpus_checksum,
    generate_baseline,
    main,
    read_baseline,
    write_baseline,
)
from app.knowledge.evals.schemas import (
    RAGBaseline,
    RetrievalMetrics,
    RunReport,
)
from app.knowledge.evals.tests.conftest import make_qa_pair


def _make_retrieval_metrics(**overrides: Any) -> RetrievalMetrics:
    defaults: dict[str, Any] = {
        "total_pairs": 10,
        "recall_at_1": 0.70,
        "recall_at_3": 0.85,
        "recall_at_5": 0.90,
        "recall_at_10": 0.95,
        "mrr": 0.80,
        "mean_completeness": 0.75,
    }
    defaults.update(overrides)
    return RetrievalMetrics(**defaults)


def _make_run_report(**overrides: Any) -> RunReport:
    defaults: dict[str, Any] = {
        "run_id": "test123",
        "timestamp": "2026-04-12T10:00:00+00:00",
        "qa_file": "evals/rag/qa_pairs.jsonl",
        "total_pairs": 10,
        "retrieval_metrics": _make_retrieval_metrics(),
        "mean_faithfulness": 0.90,
        "faithfulness_errors": 0,
        "case_results": (),
    }
    defaults.update(overrides)
    return RunReport(**defaults)


class TestComputeCorpusChecksum:
    def test_deterministic_same_order(self) -> None:
        pairs = [make_qa_pair(source_chunk_id=1), make_qa_pair(source_chunk_id=2)]
        assert compute_corpus_checksum(pairs) == compute_corpus_checksum(pairs)

    def test_deterministic_different_order(self) -> None:
        pairs_a = [make_qa_pair(source_chunk_id=1), make_qa_pair(source_chunk_id=2)]
        pairs_b = [make_qa_pair(source_chunk_id=2), make_qa_pair(source_chunk_id=1)]
        assert compute_corpus_checksum(pairs_a) == compute_corpus_checksum(pairs_b)


class TestGenerateBaseline:
    def test_extracts_all_metrics(self) -> None:
        report = _make_run_report()
        pairs = [make_qa_pair(source_chunk_id=1)]
        baseline = generate_baseline(report, qa_pairs=pairs)

        assert baseline.recall_at_1 == pytest.approx(0.70)
        assert baseline.recall_at_3 == pytest.approx(0.85)
        assert baseline.recall_at_10 == pytest.approx(0.95)
        assert baseline.mrr == pytest.approx(0.80)
        assert baseline.mean_completeness == pytest.approx(0.75)
        assert baseline.mean_faithfulness == pytest.approx(0.90)
        assert baseline.total_pairs == 10
        assert baseline.corpus_checksum
        assert baseline.generated_at

    def test_injectable_timestamp(self) -> None:
        report = _make_run_report()
        pairs = [make_qa_pair(source_chunk_id=1)]
        fixed_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
        baseline = generate_baseline(report, qa_pairs=pairs, now=fixed_time)

        assert baseline.generated_at == "2026-01-15T12:00:00+00:00"


class TestCheckRegression:
    def _baseline(self, **overrides: Any) -> RAGBaseline:
        defaults: dict[str, Any] = {
            "recall_at_1": 0.70,
            "recall_at_3": 0.85,
            "recall_at_10": 0.95,
            "mrr": 0.80,
            "mean_completeness": 0.75,
            "mean_faithfulness": 0.90,
            "total_pairs": 10,
            "generated_at": "2026-04-12T10:00:00+00:00",
            "corpus_checksum": compute_corpus_checksum([make_qa_pair(source_chunk_id=1)]),
        }
        defaults.update(overrides)
        return RAGBaseline(**defaults)

    def test_no_regression_within_tolerance(self) -> None:
        baseline = self._baseline()
        report = _make_run_report(retrieval_metrics=_make_retrieval_metrics(recall_at_3=0.83))
        pairs = [make_qa_pair(source_chunk_id=1)]
        result = check_regression(report, baseline, qa_pairs=pairs)

        assert result.passed is True
        assert len(result.findings) == 0

    def test_regression_detected_beyond_tolerance(self) -> None:
        baseline = self._baseline()
        report = _make_run_report(retrieval_metrics=_make_retrieval_metrics(recall_at_3=0.80))
        pairs = [make_qa_pair(source_chunk_id=1)]
        result = check_regression(report, baseline, qa_pairs=pairs)

        assert result.passed is False
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.metric_name == "recall_at_3"
        assert finding.delta == pytest.approx(-0.05)

    def test_multiple_regressions(self) -> None:
        baseline = self._baseline()
        report = _make_run_report(
            retrieval_metrics=_make_retrieval_metrics(recall_at_3=0.80, mrr=0.70),
        )
        pairs = [make_qa_pair(source_chunk_id=1)]
        result = check_regression(report, baseline, qa_pairs=pairs)

        assert result.passed is False
        assert len(result.findings) == 2
        metric_names = {f.metric_name for f in result.findings}
        assert metric_names == {"recall_at_3", "mrr"}

    def test_custom_tolerance(self) -> None:
        baseline = self._baseline()
        report = _make_run_report(retrieval_metrics=_make_retrieval_metrics(recall_at_3=0.80))
        pairs = [make_qa_pair(source_chunk_id=1)]
        result = check_regression(report, baseline, qa_pairs=pairs, tolerance=0.10)

        assert result.passed is True
        assert len(result.findings) == 0

    def test_corpus_checksum_mismatch(self) -> None:
        baseline = self._baseline()
        report = _make_run_report()
        different_pairs = [make_qa_pair(source_chunk_id=999)]
        result = check_regression(report, baseline, qa_pairs=different_pairs)

        assert result.corpus_checksum_match is False


class TestWriteReadBaseline:
    def test_round_trip(self, tmp_path: Any) -> None:
        pairs = [make_qa_pair(source_chunk_id=1)]
        baseline = RAGBaseline(
            recall_at_1=0.70,
            recall_at_3=0.85,
            recall_at_10=0.95,
            mrr=0.80,
            mean_completeness=0.75,
            mean_faithfulness=0.90,
            total_pairs=10,
            generated_at="2026-04-12T10:00:00+00:00",
            corpus_checksum=compute_corpus_checksum(pairs),
        )
        out = tmp_path / "baseline.json"
        write_baseline(baseline, baseline_path=out)

        loaded = read_baseline(baseline_path=out)
        assert loaded is not None
        assert loaded.recall_at_1 == pytest.approx(baseline.recall_at_1)
        assert loaded.recall_at_3 == pytest.approx(baseline.recall_at_3)
        assert loaded.recall_at_10 == pytest.approx(baseline.recall_at_10)
        assert loaded.mrr == pytest.approx(baseline.mrr)
        assert loaded.mean_completeness == pytest.approx(baseline.mean_completeness)
        assert loaded.mean_faithfulness == pytest.approx(baseline.mean_faithfulness)
        assert loaded.total_pairs == baseline.total_pairs
        assert loaded.corpus_checksum == baseline.corpus_checksum

    def test_read_missing_returns_none(self, tmp_path: Any) -> None:
        result = read_baseline(baseline_path=tmp_path / "nonexistent.json")
        assert result is None


class TestCLI:
    def test_baseline_subcommand(self, tmp_path: Any) -> None:
        report = _make_run_report()
        pairs = [make_qa_pair(source_chunk_id=1)]
        report_path = tmp_path / "report.json"
        qa_path = tmp_path / "qa.jsonl"

        with report_path.open("w") as fh:
            from dataclasses import asdict

            json.dump(asdict(report), fh, default=str)
        with qa_path.open("w") as fh:
            for p in pairs:
                fh.write(json.dumps(asdict(p)) + "\n")

        baseline_path = tmp_path / "baseline.json"
        exit_code = main(
            [
                "baseline",
                "--report",
                str(report_path),
                "--qa-file",
                str(qa_path),
                "--baseline-path",
                str(baseline_path),
            ]
        )

        assert exit_code == 0
        assert baseline_path.is_file()

        raw = json.loads(baseline_path.read_text())
        assert raw["recall_at_3"] == pytest.approx(0.85)

    def test_check_subcommand_regression(self, tmp_path: Any) -> None:
        pairs = [make_qa_pair(source_chunk_id=1)]
        good_baseline = RAGBaseline(
            recall_at_1=0.70,
            recall_at_3=0.85,
            recall_at_10=0.95,
            mrr=0.80,
            mean_completeness=0.75,
            mean_faithfulness=0.90,
            total_pairs=10,
            generated_at="2026-04-12T10:00:00+00:00",
            corpus_checksum=compute_corpus_checksum(pairs),
        )
        baseline_path = tmp_path / "baseline.json"
        write_baseline(good_baseline, baseline_path=baseline_path)

        degraded_report = _make_run_report(
            retrieval_metrics=_make_retrieval_metrics(recall_at_3=0.50)
        )
        report_path = tmp_path / "report.json"
        qa_path = tmp_path / "qa.jsonl"

        with report_path.open("w") as fh:
            from dataclasses import asdict

            json.dump(asdict(degraded_report), fh, default=str)
        with qa_path.open("w") as fh:
            for p in pairs:
                fh.write(json.dumps(asdict(p)) + "\n")

        exit_code = main(
            [
                "check",
                "--report",
                str(report_path),
                "--qa-file",
                str(qa_path),
                "--baseline-path",
                str(baseline_path),
            ]
        )

        assert exit_code == 1
