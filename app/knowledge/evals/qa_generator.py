"""Synthetic QA pair generation from knowledge base documents.

Samples eligible chunks from the corpus, uses a fast-tier LLM to generate
plausible dispatcher questions, and writes (question, source_chunk_id,
source_heading_path, language) tuples as JSONL ground truth for RAG
retrieval evaluation.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import random
import time
from dataclasses import asdict
from pathlib import Path
from typing import Final

from sqlalchemy import func, or_, select

from app.core.config import Settings, get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.knowledge.evals.schemas import QAPair
from app.knowledge.models import Document, DocumentChunk

logger = get_logger(__name__)

_DEFAULT_OUTPUT_DIR: Final[Path] = Path("evals/rag")
_MIN_CHUNK_LENGTH: Final[int] = 200
_EXCLUDED_SECTION_TYPES: Final[frozenset[str]] = frozenset({"list", "table"})
_MAX_CHUNK_PROMPT_CHARS: Final[int] = 2000

_QA_SYSTEM_PROMPT = (
    "Given the following passage from a transit operations document, "
    "write one specific factual question that a dispatcher might ask, "
    "where this passage would be the ideal answer. "
    "Respond in {language}. Question only, no preamble."
)


def _resolve_model(settings: Settings) -> str:
    """Resolve the model string for QA generation.

    Priority: llm_fast > primary model.
    """
    if settings.llm_fast_provider and settings.llm_fast_model:
        return f"{settings.llm_fast_provider}:{settings.llm_fast_model}"
    return f"{settings.llm_provider}:{settings.llm_model}"


async def _fetch_eligible_chunks(
    n: int,
    language_mix: dict[str, float],
    settings: Settings | None = None,
) -> list[DocumentChunk]:
    """Fetch eligible chunks stratified by language.

    Args:
        n: Total number of chunks to sample.
        language_mix: Language code to weight mapping (must sum to ~1.0).
        settings: Optional settings override.

    Returns:
        List of sampled DocumentChunk instances.
    """
    _ = settings  # reserved for future filtering overrides
    start = time.monotonic()
    logger.info(
        "knowledge.qa_generator.fetch_started",
        n=n,
        language_mix=language_mix,
    )

    results: list[DocumentChunk] = []

    async with get_db_context() as session:
        for lang, weight in language_mix.items():
            target = max(1, round(n * weight))

            stmt = (
                select(DocumentChunk)
                .join(Document, DocumentChunk.document_id == Document.id)
                .where(
                    func.length(DocumentChunk.content) >= _MIN_CHUNK_LENGTH,
                    or_(
                        DocumentChunk.section_type.is_(None),
                        DocumentChunk.section_type.notin_(_EXCLUDED_SECTION_TYPES),
                    ),
                    Document.status == "completed",
                    Document.language == lang,
                )
                .order_by(
                    DocumentChunk.heading_path.isnot(None).desc(),
                    func.random(),
                )
                .limit(target)
            )
            rows = await session.execute(stmt)
            chunks = list(rows.scalars().all())
            random.shuffle(chunks)
            results.extend(chunks)

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "knowledge.qa_generator.fetch_completed",
        eligible_count=len(results),
        elapsed_ms=round(elapsed_ms, 1),
    )
    return results


async def _generate_question(
    chunk: DocumentChunk,
    language: str,
    model_str: str,
) -> str | None:
    """Generate a single question from a chunk using the fast-tier LLM.

    Args:
        chunk: The source document chunk.
        language: Language code for the generated question.
        model_str: Pydantic AI model string.

    Returns:
        Generated question string, or None on failure.
    """
    from pydantic_ai import Agent

    content = chunk.content[:_MAX_CHUNK_PROMPT_CHARS]
    start = time.monotonic()

    try:
        agent = Agent(
            model_str,
            system_prompt=_QA_SYSTEM_PROMPT.format(language=language),
        )
        result = await agent.run(content)
        question = str(result.response).strip()

        elapsed_ms = (time.monotonic() - start) * 1000
        logger.info(
            "knowledge.qa_generator.question_generated",
            chunk_id=chunk.id,
            language=language,
            elapsed_ms=round(elapsed_ms, 1),
        )
        return question

    except Exception as exc:
        elapsed_ms = (time.monotonic() - start) * 1000
        logger.warning(
            "knowledge.qa_generator.question_failed",
            chunk_id=chunk.id,
            error_type=type(exc).__name__,
            error=str(exc),
            elapsed_ms=round(elapsed_ms, 1),
        )
        return None


async def generate_qa_pairs(
    n: int = 100,
    language_mix: dict[str, float] | None = None,
    settings: Settings | None = None,
) -> list[QAPair]:
    """Generate synthetic QA pairs from the knowledge base corpus.

    Args:
        n: Number of QA pairs to generate.
        language_mix: Language code to weight mapping. Defaults to 70% lv, 30% en.
        settings: Optional settings override.

    Returns:
        List of successfully generated QAPair instances.
    """
    if language_mix is None:
        language_mix = {"lv": 0.7, "en": 0.3}

    if settings is None:
        settings = get_settings()

    model_str = _resolve_model(settings)
    chunks = await _fetch_eligible_chunks(n, language_mix, settings)

    pairs: list[QAPair] = []
    skipped = 0
    start = time.monotonic()

    for chunk in chunks:
        # Determine language from the parent document
        async with get_db_context() as session:
            doc_row = await session.execute(
                select(Document.language).where(Document.id == chunk.document_id)
            )
            lang = doc_row.scalar_one_or_none() or "lv"

        question = await _generate_question(chunk, lang, model_str)
        if question is None:
            skipped += 1
            continue

        pair = QAPair(
            question=question,
            source_chunk_id=chunk.id,
            source_document_id=chunk.document_id,
            source_heading_path=chunk.heading_path,
            language=lang,
            generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
            model_used=model_str,
        )
        pairs.append(pair)

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "knowledge.qa_generator.batch_completed",
        total_requested=n,
        total_generated=len(pairs),
        skipped=skipped,
        elapsed_ms=round(elapsed_ms, 1),
    )
    return pairs


def _write_jsonl(
    pairs: list[QAPair],
    output_dir: Path,
    filename: str | None = None,
) -> Path:
    """Write QA pairs to a path-sandboxed JSONL file.

    Args:
        pairs: QA pairs to write.
        output_dir: Target directory for the output file.
        filename: Optional filename override (for testing). Defaults to timestamped.

    Returns:
        Path to the written JSONL file.

    Raises:
        ValueError: If the resolved output path escapes the sandbox.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"qa_pairs_{timestamp}.jsonl"
    out_path = output_dir / filename

    if not out_path.resolve().is_relative_to(output_dir.resolve()):
        msg = "output path escaped sandbox root"
        raise ValueError(msg)

    with out_path.open("w", encoding="utf-8") as f:
        for pair in pairs:
            line = json.dumps(asdict(pair), ensure_ascii=False, default=str)
            f.write(line + "\n")

    logger.info(
        "knowledge.qa_generator.output_written",
        path=str(out_path),
        pair_count=len(pairs),
    )
    return out_path


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="app.knowledge.evals",
        description="Generate synthetic QA pairs from the knowledge base corpus.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of QA pairs to generate (default: 100).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Directory to write JSONL output. Defaults to {_DEFAULT_OUTPUT_DIR}.",
    )
    parser.add_argument(
        "--lv-ratio",
        type=float,
        default=0.7,
        help="Fraction of Latvian chunks (0.0-1.0, default: 0.7).",
    )
    return parser


async def _amain(argv: list[str] | None = None) -> int:
    """Async CLI entry point."""
    args = _build_parser().parse_args(argv)

    if args.count < 1:
        logger.error("knowledge.qa_generator.invalid_count", count=args.count)
        return 1

    lv_ratio = max(0.0, min(1.0, args.lv_ratio))
    language_mix = {"lv": lv_ratio, "en": round(1.0 - lv_ratio, 2)}

    try:
        pairs = await generate_qa_pairs(n=args.count, language_mix=language_mix)
    except Exception as exc:
        logger.error(
            "knowledge.qa_generator.generation_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        return 1

    if not pairs:
        logger.warning("knowledge.qa_generator.no_pairs_generated")
        return 1

    out_path = _write_jsonl(pairs, args.output_dir)
    print(f"Generated {len(pairs)} QA pairs -> {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    return asyncio.run(_amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
