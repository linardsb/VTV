"""Seed schema_examples table from YAML file (ML-5.4).

Usage: uv run python scripts/seed_schema_examples.py [--file data/schema_examples.yaml] [--dry-run]
Idempotent: upserts by question_text.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import get_db_context
from app.knowledge.embedding import get_embedding_provider


async def seed(yaml_path: str, dry_run: bool = False) -> None:
    """Load YAML examples, embed questions, and upsert into schema_examples."""
    path = Path(yaml_path)
    if not path.exists():
        print(f"ERROR: File not found: {yaml_path}")
        sys.exit(1)

    with Path.open(path) as f:
        data = yaml.safe_load(f)

    examples = data.get("examples", [])
    if not examples:
        print("No examples found in YAML file.")
        return

    print(f"Found {len(examples)} examples in {yaml_path}")

    if dry_run:
        for i, ex in enumerate(examples, 1):
            print(f"  [{i}] {ex['question'][:60]}...")
        print(f"\nDry run complete. {len(examples)} examples would be seeded.")
        return

    settings = get_settings()
    provider = get_embedding_provider(settings)

    # Embed all questions in batches
    questions = [ex["question"] for ex in examples]
    print(f"Embedding {len(questions)} questions...")
    embeddings = await provider.embed(questions)
    print(f"Embeddings generated ({len(embeddings[0])}-dim)")

    inserted = 0
    updated = 0

    async with get_db_context() as db:
        for ex, embedding in zip(examples, embeddings, strict=True):
            embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
            result = await _upsert_example(db, ex, embedding_str)
            if result == "inserted":
                inserted += 1
            else:
                updated += 1
        await db.commit()

    print(f"\nDone: {inserted} inserted, {updated} updated, {len(examples)} total")


async def _upsert_example(db: AsyncSession, ex: dict[str, object], embedding_str: str) -> str:
    """Upsert a single schema example. Returns 'inserted' or 'updated'."""
    # Check if exists
    result = await db.execute(
        text("SELECT id FROM schema_examples WHERE question_text = :q"),
        {"q": ex["question"]},
    )
    existing = result.scalar()

    tags_val = ex.get("tags")

    if existing:
        await db.execute(
            text(
                "UPDATE schema_examples SET "
                "sql_query = :sql, description = :desc, "
                "question_embedding = :emb::vector, "
                "tags = :tags, "
                "updated_at = NOW() "
                "WHERE id = :id"
            ),
            {
                "sql": ex["sql"],
                "desc": ex.get("description"),
                "emb": embedding_str,
                "tags": tags_val,
                "id": existing,
            },
        )
        return "updated"

    await db.execute(
        text(
            "INSERT INTO schema_examples "
            "(question_text, sql_query, description, question_embedding, tags) "
            "VALUES (:q, :sql, :desc, :emb::vector, :tags)"
        ),
        {
            "q": ex["question"],
            "sql": ex["sql"],
            "desc": ex.get("description"),
            "emb": embedding_str,
            "tags": tags_val,
        },
    )
    return "inserted"


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed schema_examples from YAML")
    parser.add_argument(
        "--file",
        default="data/schema_examples.yaml",
        help="Path to YAML file (default: data/schema_examples.yaml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing to database",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.file, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
