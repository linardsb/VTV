"""Frozen dataclasses for RAG retrieval evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QAPair:
    """One synthetic QA pair for RAG retrieval evaluation."""

    question: str
    source_chunk_id: int
    source_document_id: int
    source_heading_path: str | None
    language: str
    generated_at: str  # ISO-8601
    model_used: str


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    """Aggregate retrieval metrics from one eval run."""

    total_pairs: int
    recall_at_1: float
    recall_at_5: float
    mrr: float  # Mean Reciprocal Rank


@dataclass(frozen=True, slots=True)
class EvalReport:
    """Summary of a retrieval evaluation run."""

    run_id: str
    timestamp: str
    qa_file: str
    metrics: RetrievalMetrics
    errors: int
