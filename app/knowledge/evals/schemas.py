"""Frozen dataclasses for RAG retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QAPair:
    """One synthetic QA pair for RAG retrieval evaluation."""

    question: str
    source_chunk_id: int
    source_document_id: int
    source_chunk_index: int
    source_heading_path: str | None
    language: str
    generated_at: str  # ISO-8601
    model_used: str


@dataclass(frozen=True, slots=True)
class PairMetrics:
    """Per-pair retrieval metrics."""

    relevance_hit: bool  # Was source chunk in top-k results?
    rank: int | None  # 1-indexed rank of source chunk, None if not found
    mrr_contribution: float  # 1/rank if found, else 0.0
    completeness: float  # Fraction of sibling chunks retrieved (0.0-1.0)


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Aggregate retrieval metrics from one eval run."""

    total_pairs: int
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float  # Mean Reciprocal Rank
    mean_completeness: float


@dataclass(frozen=True, slots=True)
class EvalReport:
    """Summary of a retrieval evaluation run."""

    run_id: str
    timestamp: str
    qa_file: str
    metrics: RetrievalMetrics
    errors: int


@dataclass(frozen=True, slots=True)
class FaithfulnessResult:
    """LLM-judged faithfulness for one QA pair."""

    grounded: bool | None  # Answer derivable from chunks?
    accurate: bool | None  # Matches source content?
    complete: bool | None  # No key info missing?
    passed: bool | None  # All three True = pass; None = error
    error: str | None  # Error message if LLM call failed


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Per-QA-pair evaluation result combining metrics + faithfulness."""

    qa_pair: QAPair
    pair_metrics: PairMetrics
    faithfulness: FaithfulnessResult
    search_latency_ms: float
    judge_latency_ms: float


@dataclass(frozen=True, slots=True)
class RunReport:
    """Full eval run report with retrieval metrics + faithfulness stats."""

    run_id: str
    timestamp: str
    qa_file: str
    total_pairs: int
    retrieval_metrics: RetrievalMetrics
    mean_faithfulness: float  # Fraction of pairs where passed=True
    faithfulness_errors: int  # Count of pairs where passed=None
    case_results: tuple[CaseResult, ...]


@dataclass(frozen=True, slots=True)
class RAGBaseline:
    """Stored baseline from a known-good RAG eval run."""

    recall_at_1: float
    recall_at_3: float
    recall_at_10: float
    mrr: float
    mean_completeness: float
    mean_faithfulness: float
    total_pairs: int
    generated_at: str  # ISO-8601
    corpus_checksum: str  # SHA-256 of sorted source chunk IDs from QA file


@dataclass(frozen=True, slots=True)
class RegressionFinding:
    """One metric that regressed beyond tolerance."""

    metric_name: str
    baseline_value: float
    current_value: float
    delta: float  # current - baseline (negative = regression)
    tolerance: float


@dataclass(frozen=True, slots=True)
class RegressionReport:
    """Result of comparing current metrics against a stored baseline."""

    passed: bool
    tolerance: float
    findings: tuple[RegressionFinding, ...]
    corpus_checksum_match: bool
    generated_at: str
