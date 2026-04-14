"""Backfill lemmatized_content for existing Latvian document chunks (KB-2).

Iterates all chunks belonging to documents where ``language == 'lv'`` and
populates ``DocumentChunk.lemmatized_content`` via the UDPipe lemmatizer.
Does NOT re-embed or re-chunk — only the new column is written.

Prerequisite: the UDPipe model must be present on disk (run
``make download-udpipe-model``) and ``LATVIAN_LEMMATIZER_ENABLED=true``.

Usage:
    uv run python scripts/backfill_lemmatized_content.py --dry-run
    uv run python scripts/backfill_lemmatized_content.py
    uv run python scripts/backfill_lemmatized_content.py --document-id 42
    uv run python scripts/backfill_lemmatized_content.py --batch-size 200
    uv run python scripts/backfill_lemmatized_content.py --limit 10
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger
from app.knowledge.lemmatizer import get_lemmatizer_provider
from app.knowledge.models import Document, DocumentChunk

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill lemmatized_content on document_chunks for Latvian docs. "
            "Does not re-embed or re-chunk. Run --dry-run first."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing to the DB.",
    )
    parser.add_argument(
        "--document-id",
        type=int,
        default=None,
        help="Only process chunks belonging to this document id.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Chunks per DB transaction (default: 100, min: 1).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum chunks to update across all documents.",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")
    return args


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not settings.latvian_lemmatizer_enabled and not args.dry_run:
        print(
            "[backfill] latvian_lemmatizer_enabled=False — refusing to run "
            "(use --dry-run to preview or set LATVIAN_LEMMATIZER_ENABLED=true).",
            file=sys.stderr,
        )
        return 2

    lemmatizer = get_lemmatizer_provider(settings)
    # Warm up so the first batch doesn't pay model load latency.
    await lemmatizer.warm_up()

    async with get_db_context() as db:
        # Count Latvian chunks to process
        count_stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.language == "lv")
        )
        if args.document_id is not None:
            count_stmt = count_stmt.where(DocumentChunk.document_id == args.document_id)

        result = await db.execute(count_stmt)
        chunks = list(result.scalars().all())
        if args.limit is not None:
            chunks = chunks[: args.limit]

        total_docs = len({c.document_id for c in chunks})
        logger.info(
            "knowledge.lemmatizer.backfill_started",
            total_chunks=len(chunks),
            total_docs=total_docs,
            dry_run=args.dry_run,
        )
        print(f"[backfill] candidate chunks: {len(chunks)} across {total_docs} Latvian docs")

        if args.dry_run:
            print("[backfill] dry-run — no writes performed.")
            return 0

        start = time.monotonic()
        updated = 0
        for i in range(0, len(chunks), args.batch_size):
            batch = chunks[i : i + args.batch_size]
            for chunk in batch:
                if not chunk.content:
                    continue
                try:
                    lemmatized = lemmatizer.lemmatize(chunk.content, "lv")
                except Exception as exc:
                    logger.error(
                        "knowledge.lemmatizer.failed",
                        reason="backfill_lemmatize_error",
                        chunk_id=chunk.id,
                        error=str(exc),
                        error_type=type(exc).__name__,
                    )
                    continue
                await db.execute(
                    update(DocumentChunk)
                    .where(DocumentChunk.id == chunk.id)
                    .values(lemmatized_content=lemmatized)
                )
                updated += 1
            await db.commit()

        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "knowledge.lemmatizer.backfill_completed",
            updated_chunks=updated,
            elapsed_ms=elapsed_ms,
        )
        print(f"[backfill] updated {updated} chunks in {elapsed_ms}ms")

    return 0


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
