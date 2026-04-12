"""Retrieval metrics computation for RAG evaluation.

Computes per-pair metrics (relevance, position, completeness) and
aggregates them into recall@k, MRR, and mean completeness scores.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.knowledge.evals.schemas import PairMetrics, QAPair, RetrievalMetrics
from app.knowledge.schemas import SearchResult

logger = get_logger(__name__)


def _find_source_rank(qa_pair: QAPair, search_results: list[SearchResult]) -> int | None:
    """Return 1-indexed rank of the source chunk in results, or None if absent."""
    for i, result in enumerate(search_results):
        if (
            result.document_id == qa_pair.source_document_id
            and result.chunk_index == qa_pair.source_chunk_index
        ):
            return i + 1
    return None


def _count_sibling_hits(qa_pair: QAPair, search_results: list[SearchResult]) -> int:
    """Count results sharing the same heading_path as the source chunk."""
    if qa_pair.source_heading_path is None:
        return 0
    count = 0
    for result in search_results:
        if result.heading_path == qa_pair.source_heading_path:
            count += 1
    return count


def compute_pair_metrics(
    qa_pair: QAPair,
    search_results: list[SearchResult],
    sibling_count: int = 1,
) -> PairMetrics:
    """Compute retrieval metrics for a single QA pair.

    Args:
        qa_pair: The QA pair to evaluate.
        search_results: Ranked search results from KnowledgeService.search().
        sibling_count: Total number of sibling chunks sharing the same
            parent/heading as the source chunk. Used for completeness.

    Returns:
        PairMetrics with relevance, rank, MRR contribution, and completeness.
    """
    rank = _find_source_rank(qa_pair, search_results)
    relevance_hit = rank is not None
    mrr_contribution = 1.0 / rank if rank is not None else 0.0

    if sibling_count <= 1:
        completeness = 1.0 if relevance_hit else 0.0
    else:
        matched_siblings = _count_sibling_hits(qa_pair, search_results)
        completeness = matched_siblings / sibling_count

    return PairMetrics(
        relevance_hit=relevance_hit,
        rank=rank,
        mrr_contribution=mrr_contribution,
        completeness=completeness,
    )


def aggregate_metrics(per_pair: list[PairMetrics]) -> RetrievalMetrics:
    """Aggregate per-pair metrics into recall@k, MRR, and mean completeness.

    Args:
        per_pair: List of PairMetrics from compute_pair_metrics().

    Returns:
        RetrievalMetrics with recall@1/3/5/10, MRR, and mean completeness.
    """
    total = len(per_pair)
    if total == 0:
        return RetrievalMetrics(
            total_pairs=0,
            recall_at_1=0.0,
            recall_at_3=0.0,
            recall_at_5=0.0,
            recall_at_10=0.0,
            mrr=0.0,
            mean_completeness=0.0,
        )

    recall_at_1 = sum(1 for p in per_pair if p.rank is not None and p.rank <= 1) / total
    recall_at_3 = sum(1 for p in per_pair if p.rank is not None and p.rank <= 3) / total
    recall_at_5 = sum(1 for p in per_pair if p.rank is not None and p.rank <= 5) / total
    recall_at_10 = sum(1 for p in per_pair if p.rank is not None and p.rank <= 10) / total
    mrr = sum(p.mrr_contribution for p in per_pair) / total
    mean_completeness = sum(p.completeness for p in per_pair) / total

    return RetrievalMetrics(
        total_pairs=total,
        recall_at_1=recall_at_1,
        recall_at_3=recall_at_3,
        recall_at_5=recall_at_5,
        recall_at_10=recall_at_10,
        mrr=mrr,
        mean_completeness=mean_completeness,
    )
