# pyright: reportUnknownMemberType=false
"""Unit tests for retrieval metrics computation."""

from __future__ import annotations

import pytest

from app.knowledge.evals.metrics import (
    _count_sibling_hits,
    _find_source_rank,
    aggregate_metrics,
    compute_pair_metrics,
)
from app.knowledge.evals.schemas import PairMetrics
from app.knowledge.evals.tests.conftest import make_qa_pair, make_search_result

# ---------------------------------------------------------------------------
# _find_source_rank
# ---------------------------------------------------------------------------


class TestFindSourceRank:
    def test_source_at_rank_1(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=0)
        results = [
            make_search_result(document_id=1, chunk_index=0),
            make_search_result(document_id=1, chunk_index=1),
        ]
        assert _find_source_rank(pair, results) == 1

    def test_source_at_rank_5(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=4)
        results = [make_search_result(document_id=1, chunk_index=i) for i in range(5)]
        assert _find_source_rank(pair, results) == 5

    def test_source_not_found(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=99)
        results = [
            make_search_result(document_id=1, chunk_index=0),
        ]
        assert _find_source_rank(pair, results) is None


# ---------------------------------------------------------------------------
# _count_sibling_hits
# ---------------------------------------------------------------------------


class TestCountSiblingHits:
    def test_counts_matching_heading_paths(self) -> None:
        pair = make_qa_pair(source_heading_path="Section > Sub")
        results = [
            make_search_result(heading_path="Section > Sub"),
            make_search_result(heading_path="Section > Sub"),
            make_search_result(heading_path="Other"),
        ]
        assert _count_sibling_hits(pair, results) == 2

    def test_no_heading_path_returns_zero(self) -> None:
        pair = make_qa_pair(source_heading_path=None)
        results = [make_search_result(heading_path="Section > Sub")]
        assert _count_sibling_hits(pair, results) == 0


# ---------------------------------------------------------------------------
# compute_pair_metrics
# ---------------------------------------------------------------------------


class TestComputePairMetrics:
    def test_relevance_hit(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=0)
        results = [make_search_result(document_id=1, chunk_index=0)]
        m = compute_pair_metrics(pair, results)
        assert m.relevance_hit is True
        assert m.mrr_contribution == 1.0

    def test_relevance_miss(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=99)
        results = [make_search_result(document_id=1, chunk_index=0)]
        m = compute_pair_metrics(pair, results)
        assert m.relevance_hit is False
        assert m.mrr_contribution == 0.0
        assert m.rank is None

    def test_mrr_contribution_rank_1(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=0)
        results = [make_search_result(document_id=1, chunk_index=0)]
        m = compute_pair_metrics(pair, results)
        assert m.mrr_contribution == pytest.approx(1.0)

    def test_mrr_contribution_rank_3(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=2)
        results = [make_search_result(document_id=1, chunk_index=i) for i in range(3)]
        m = compute_pair_metrics(pair, results)
        assert m.rank == 3
        assert m.mrr_contribution == pytest.approx(1.0 / 3.0)

    def test_completeness_single_chunk(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=0)
        results = [make_search_result(document_id=1, chunk_index=0)]
        m = compute_pair_metrics(pair, results, sibling_count=1)
        assert m.completeness == pytest.approx(1.0)

    def test_completeness_multi_chunk_partial(self) -> None:
        pair = make_qa_pair(
            source_document_id=1,
            source_chunk_index=0,
            source_heading_path="Section > Sub",
        )
        results = [
            make_search_result(document_id=1, chunk_index=0, heading_path="Section > Sub"),
            make_search_result(document_id=1, chunk_index=1, heading_path="Section > Sub"),
            make_search_result(document_id=2, chunk_index=0, heading_path="Other"),
        ]
        m = compute_pair_metrics(pair, results, sibling_count=3)
        assert m.completeness == pytest.approx(2.0 / 3.0)

    def test_completeness_multi_chunk_full(self) -> None:
        pair = make_qa_pair(
            source_document_id=1,
            source_chunk_index=0,
            source_heading_path="Section > Sub",
        )
        results = [
            make_search_result(document_id=1, chunk_index=i, heading_path="Section > Sub")
            for i in range(3)
        ]
        m = compute_pair_metrics(pair, results, sibling_count=3)
        assert m.completeness == pytest.approx(1.0)

    def test_completeness_miss(self) -> None:
        pair = make_qa_pair(source_document_id=1, source_chunk_index=99)
        results = [make_search_result(document_id=1, chunk_index=0)]
        m = compute_pair_metrics(pair, results, sibling_count=1)
        assert m.completeness == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# aggregate_metrics
# ---------------------------------------------------------------------------


class TestAggregateMetrics:
    def test_recall_at_k(self) -> None:
        per_pair = [
            PairMetrics(relevance_hit=True, rank=1, mrr_contribution=1.0, completeness=1.0),
            PairMetrics(relevance_hit=True, rank=3, mrr_contribution=1 / 3, completeness=0.5),
            PairMetrics(relevance_hit=True, rank=7, mrr_contribution=1 / 7, completeness=0.3),
            PairMetrics(relevance_hit=False, rank=None, mrr_contribution=0.0, completeness=0.0),
        ]
        m = aggregate_metrics(per_pair)
        assert m.total_pairs == 4
        assert m.recall_at_1 == pytest.approx(1 / 4)
        assert m.recall_at_3 == pytest.approx(2 / 4)
        assert m.recall_at_5 == pytest.approx(2 / 4)
        assert m.recall_at_10 == pytest.approx(3 / 4)

    def test_mrr_aggregation(self) -> None:
        per_pair = [
            PairMetrics(relevance_hit=True, rank=1, mrr_contribution=1.0, completeness=1.0),
            PairMetrics(relevance_hit=True, rank=2, mrr_contribution=0.5, completeness=1.0),
            PairMetrics(relevance_hit=False, rank=None, mrr_contribution=0.0, completeness=0.0),
        ]
        m = aggregate_metrics(per_pair)
        assert m.mrr == pytest.approx(0.5)

    def test_empty_input(self) -> None:
        m = aggregate_metrics([])
        assert m.total_pairs == 0
        assert m.recall_at_1 == 0.0
        assert m.recall_at_3 == 0.0
        assert m.recall_at_5 == 0.0
        assert m.recall_at_10 == 0.0
        assert m.mrr == 0.0
        assert m.mean_completeness == 0.0

    def test_mean_completeness(self) -> None:
        per_pair = [
            PairMetrics(relevance_hit=True, rank=1, mrr_contribution=1.0, completeness=1.0),
            PairMetrics(relevance_hit=True, rank=2, mrr_contribution=0.5, completeness=0.5),
            PairMetrics(relevance_hit=False, rank=None, mrr_contribution=0.0, completeness=0.0),
        ]
        m = aggregate_metrics(per_pair)
        assert m.mean_completeness == pytest.approx(0.5)
