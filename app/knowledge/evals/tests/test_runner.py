# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportPrivateUsage=false

"""Tests for RAGEvalRunner (AI-11.3)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.knowledge.evals.runner import (
    RAGEvalRunner,
    _load_qa_pairs,
    _write_report,
    main,
)
from app.knowledge.evals.schemas import (
    CaseResult,
    FaithfulnessResult,
    PairMetrics,
    RetrievalMetrics,
    RunReport,
)
from app.knowledge.evals.tests.conftest import make_qa_pair, make_search_result
from app.knowledge.schemas import SearchResponse


def _make_search_response(**overrides: Any) -> SearchResponse:
    """Build a SearchResponse with defaults."""
    defaults: dict[str, Any] = {
        "results": [make_search_result()],
        "query": "test query",
        "total_candidates": 1,
        "reranked": False,
    }
    defaults.update(overrides)
    return SearchResponse(**defaults)


def _mock_search(response: SearchResponse) -> AsyncMock:
    """Create a mock for RAGEvalRunner._search."""
    return AsyncMock(return_value=response)


class TestRAGEvalRunner:
    """Tests for RAGEvalRunner.run()."""

    @pytest.mark.anyio
    async def test_run_happy_path_with_judge(self) -> None:
        """Full run with judge: metrics + faithfulness computed."""
        pairs = [make_qa_pair()]
        response = _make_search_response()
        faith_result = FaithfulnessResult(
            grounded=True,
            accurate=True,
            complete=True,
            passed=True,
            error=None,
        )

        mock_judge = AsyncMock()
        mock_judge.judge = AsyncMock(return_value=faith_result)

        runner = RAGEvalRunner(judge=mock_judge)
        runner._search = _mock_search(response)  # type: ignore[method-assign]

        report = await runner.run(pairs, qa_file="test.jsonl")

        assert report.total_pairs == 1
        assert report.mean_faithfulness == 1.0
        assert report.faithfulness_errors == 0
        assert len(report.case_results) == 1
        assert report.case_results[0].faithfulness.passed is True

    @pytest.mark.anyio
    async def test_run_happy_path_without_judge(self) -> None:
        """No judge: faithfulness all None, mean_faithfulness=0.0."""
        pairs = [make_qa_pair()]
        response = _make_search_response()

        runner = RAGEvalRunner(judge=None)
        runner._search = _mock_search(response)  # type: ignore[method-assign]

        report = await runner.run(pairs)

        assert report.total_pairs == 1
        assert report.mean_faithfulness == 0.0
        assert report.faithfulness_errors == 0
        assert report.case_results[0].faithfulness.passed is None
        assert report.case_results[0].faithfulness.error is None

    @pytest.mark.anyio
    async def test_run_fail_open_on_search_error(self) -> None:
        """Search error: CaseResult with error faithfulness."""
        pairs = [make_qa_pair()]

        runner = RAGEvalRunner(judge=None)
        runner._search = AsyncMock(side_effect=RuntimeError("DB down"))  # type: ignore[method-assign]

        report = await runner.run(pairs)

        assert report.total_pairs == 1
        cr = report.case_results[0]
        assert cr.pair_metrics.relevance_hit is False
        assert cr.faithfulness.error is not None
        assert "RuntimeError" in cr.faithfulness.error

    @pytest.mark.anyio
    async def test_run_zero_pairs_returns_empty_report(self) -> None:
        """Empty list: RunReport with 0 pairs, 0.0 metrics."""
        runner = RAGEvalRunner()
        report = await runner.run([])

        assert report.total_pairs == 0
        assert report.mean_faithfulness == 0.0
        assert report.retrieval_metrics.recall_at_3 == 0.0
        assert report.retrieval_metrics.mrr == 0.0
        assert len(report.case_results) == 0

    @pytest.mark.anyio
    async def test_run_computes_retrieval_metrics(self) -> None:
        """Verify recall/MRR from known search results."""
        pair = make_qa_pair(source_document_id=1, source_chunk_index=0)
        # Result matches the source chunk -> rank 1
        response = _make_search_response(
            results=[make_search_result(document_id=1, chunk_index=0, score=0.9)],
        )

        runner = RAGEvalRunner(judge=None)
        runner._search = _mock_search(response)  # type: ignore[method-assign]

        report = await runner.run([pair])

        assert report.retrieval_metrics.recall_at_1 == 1.0
        assert report.retrieval_metrics.mrr == 1.0
        assert report.case_results[0].pair_metrics.rank == 1


class TestRunReportOutput:
    """Tests for report file output."""

    def test_write_report_path_sandboxing(self, tmp_path: Path) -> None:
        """Path escape attempt -> ValueError."""
        report = RunReport(
            run_id="test123",
            timestamp="2026-04-12T10:00:00",
            qa_file="test.jsonl",
            total_pairs=0,
            retrieval_metrics=RetrievalMetrics(
                total_pairs=0,
                recall_at_1=0.0,
                recall_at_3=0.0,
                recall_at_5=0.0,
                recall_at_10=0.0,
                mrr=0.0,
                mean_completeness=0.0,
            ),
            mean_faithfulness=0.0,
            faithfulness_errors=0,
            case_results=(),
        )
        # Monkey-patch run_id to include path traversal
        object.__setattr__(report, "run_id", "../../../escape")
        # The filename eval_report_../../../escape.json escapes the sandbox
        with pytest.raises(ValueError, match="output path escaped sandbox root"):
            _write_report(report, tmp_path)

    def test_write_report_creates_valid_json(self, tmp_path: Path) -> None:
        """Round-trip JSON serialization."""
        report = RunReport(
            run_id="abc123",
            timestamp="2026-04-12T10:00:00",
            qa_file="test.jsonl",
            total_pairs=1,
            retrieval_metrics=RetrievalMetrics(
                total_pairs=1,
                recall_at_1=1.0,
                recall_at_3=1.0,
                recall_at_5=1.0,
                recall_at_10=1.0,
                mrr=1.0,
                mean_completeness=1.0,
            ),
            mean_faithfulness=0.85,
            faithfulness_errors=0,
            case_results=(
                CaseResult(
                    qa_pair=make_qa_pair(),
                    pair_metrics=PairMetrics(
                        relevance_hit=True,
                        rank=1,
                        mrr_contribution=1.0,
                        completeness=1.0,
                    ),
                    faithfulness=FaithfulnessResult(
                        grounded=True,
                        accurate=True,
                        complete=True,
                        passed=True,
                        error=None,
                    ),
                    search_latency_ms=10.5,
                    judge_latency_ms=200.0,
                ),
            ),
        )
        out_path = _write_report(report, tmp_path)
        assert out_path.exists()

        data = json.loads(out_path.read_text(encoding="utf-8"))
        assert data["run_id"] == "abc123"
        assert data["mean_faithfulness"] == 0.85
        assert len(data["case_results"]) == 1


class TestCLI:
    """Tests for CLI entry points."""

    def test_cli_help_exits_zero(self) -> None:
        """--help exits with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_cli_missing_qa_file_exits_nonzero(self) -> None:
        """Non-existent QA file exits with code 2."""
        exit_code = main(["--qa-file", "/nonexistent/qa_pairs.jsonl"])
        assert exit_code == 2

    def test_load_qa_pairs_from_jsonl(self, tmp_path: Path) -> None:
        """Write JSONL to tmp_path, load and verify."""
        qa_file = tmp_path / "test_pairs.jsonl"
        pair_data = {
            "question": "Test question?",
            "source_chunk_id": 1,
            "source_document_id": 1,
            "source_chunk_index": 0,
            "source_heading_path": None,
            "language": "lv",
            "generated_at": "2026-04-12T10:00:00+00:00",
            "model_used": "test:model",
        }
        qa_file.write_text(json.dumps(pair_data) + "\n", encoding="utf-8")

        pairs = _load_qa_pairs(qa_file)
        assert len(pairs) == 1
        assert pairs[0].question == "Test question?"
        assert pairs[0].source_chunk_id == 1

    def test_load_qa_pairs_file_not_found(self) -> None:
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            _load_qa_pairs(Path("/nonexistent/file.jsonl"))
