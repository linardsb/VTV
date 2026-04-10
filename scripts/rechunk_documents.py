"""Re-chunk all existing knowledge documents using the new SemanticChunker.

ONE-SHOT MIGRATION (AI-4.4): walks every Document row, deletes its existing
chunks, and re-runs the ingestion pipeline (extract -> semantic chunk -> embed
-> two-phase parent/child store) against the file on disk. Documents whose
file_path is missing are skipped with a warning.

DESTRUCTIVE: chunk rows are deleted before re-creation. Run with --dry-run
first to preview impact. Document metadata, tags, and embeddings cache are
NOT touched. Auto-tagging is NOT re-run (would clobber human-curated tags).

Usage:
    uv run python scripts/rechunk_documents.py --dry-run
    uv run python scripts/rechunk_documents.py
    uv run python scripts/rechunk_documents.py --document-id 42
    uv run python scripts/rechunk_documents.py --batch-size 5
    uv run python scripts/rechunk_documents.py --limit 10 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
import traceback
from pathlib import Path

# Allow `from app.*` imports when run via `uv run python scripts/...`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import get_db_context
from app.knowledge.repository import KnowledgeRepository
from app.knowledge.service import KnowledgeService


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments with validation."""
    parser = argparse.ArgumentParser(
        description=(
            "Re-chunk all knowledge documents using the current chunking config. "
            "DESTRUCTIVE: deletes existing chunks before re-creating them. "
            "Run --dry-run first."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview which documents would be re-chunked without modifying the DB.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of documents to process per batch (default: 10, min: 1).",
    )
    parser.add_argument(
        "--document-id",
        type=int,
        default=None,
        help="Re-chunk only the specified document id (useful for testing).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of documents to process (useful for testing).",
    )
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error("--batch-size must be >= 1")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be >= 1")

    return args


async def _collect_doc_ids(
    repo: KnowledgeRepository,
    *,
    limit: int | None,
) -> list[int]:
    """Collect every document id, optionally capped by ``limit``.

    Pages through ``list_documents`` in chunks of 500 to avoid loading the
    entire table at once.
    """
    page_size = 500
    offset = 0
    ids: list[int] = []
    while True:
        page = await repo.list_documents(offset=offset, limit=page_size)
        if not page:
            break
        for doc in page:
            ids.append(doc.id)
            if limit is not None and len(ids) >= limit:
                return ids
        if len(page) < page_size:
            break
        offset += page_size
    return ids


async def main(args: argparse.Namespace) -> int:
    """Run the re-chunk migration. Returns shell exit code."""
    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"[rechunk] starting in {mode} mode")
    overall_start = time.monotonic()

    succeeded = 0
    skipped_no_file = 0
    failed: list[int] = []

    async with get_db_context() as session:
        repo = KnowledgeRepository(session)
        service = KnowledgeService(session)

        if args.document_id is not None:
            doc_ids = [args.document_id]
        else:
            doc_ids = await _collect_doc_ids(repo, limit=args.limit)

        total = len(doc_ids)
        print(f"[rechunk] {total} document(s) to process (batch_size={args.batch_size})")

        for batch_start in range(0, total, args.batch_size):
            batch = doc_ids[batch_start : batch_start + args.batch_size]
            for doc_id in batch:
                doc = await repo.get_document(doc_id)
                if doc is None:
                    print(f"[rechunk] doc {doc_id} not found, skipping")
                    failed.append(doc_id)
                    continue

                if not doc.file_path:
                    print(f"[rechunk] doc {doc_id} ({doc.filename}) has no stored file, skipping")
                    skipped_no_file += 1
                    continue

                if args.dry_run:
                    print(
                        f"[rechunk] DRY-RUN doc {doc_id} ({doc.filename}) "
                        f"would re-chunk: {doc.chunk_count} existing chunks"
                    )
                    succeeded += 1
                    continue

                doc_start = time.monotonic()
                try:
                    new_count = await service.rechunk_document(doc_id)
                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - doc_start) * 1000)
                    print(
                        f"[rechunk] doc {doc_id} ({doc.filename}) FAILED after "
                        f"{elapsed_ms}ms: {type(exc).__name__}: {exc}"
                    )
                    print(traceback.format_exc())
                    failed.append(doc_id)
                    continue

                elapsed_ms = int((time.monotonic() - doc_start) * 1000)
                print(
                    f"[rechunk] doc {doc_id} ({doc.filename}) "
                    f"{doc.chunk_count} -> {new_count} chunks ({elapsed_ms}ms)"
                )
                succeeded += 1

    overall_elapsed = time.monotonic() - overall_start
    print("[rechunk] -----------------------------------------")
    print(f"[rechunk] mode:            {mode}")
    print(f"[rechunk] processed:       {succeeded + skipped_no_file + len(failed)}")
    print(f"[rechunk] succeeded:       {succeeded}")
    print(f"[rechunk] skipped_no_file: {skipped_no_file}")
    print(f"[rechunk] failed:          {len(failed)}")
    if failed:
        preview = ", ".join(str(i) for i in failed[:5])
        more = f" (+{len(failed) - 5} more)" if len(failed) > 5 else ""
        print(f"[rechunk] failed ids:      {preview}{more}")
    print(f"[rechunk] wall_clock:      {overall_elapsed:.1f}s")

    return 1 if failed else 0


if __name__ == "__main__":
    parsed = _parse_args()
    sys.exit(asyncio.run(main(parsed)))
