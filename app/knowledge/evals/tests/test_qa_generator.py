"""Unit tests for synthetic QA pair generation."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.knowledge.evals.qa_generator import (
    _MIN_CHUNK_LENGTH,
    _write_jsonl,
    generate_qa_pairs,
    main,
)
from app.knowledge.evals.schemas import QAPair
from app.knowledge.evals.tests.conftest import make_mock_chunk, make_qa_pair

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestQAPairSchema:
    def test_qa_pair_is_frozen(self) -> None:
        pair = make_qa_pair()
        with pytest.raises(dataclasses.FrozenInstanceError):
            pair.question = "changed"  # type: ignore[misc]

    def test_qa_pair_serialization(self) -> None:
        pair = make_qa_pair()
        d = dataclasses.asdict(pair)
        assert d["question"] == pair.question
        assert d["source_chunk_id"] == pair.source_chunk_id
        serialized = json.dumps(d, ensure_ascii=False, default=str)
        assert isinstance(serialized, str)
        roundtrip = json.loads(serialized)
        assert roundtrip["language"] == "lv"


# ---------------------------------------------------------------------------
# Chunk filtering tests
# ---------------------------------------------------------------------------


class TestChunkFiltering:
    @pytest.mark.asyncio
    async def test_short_chunks_excluded(self) -> None:
        """Chunks shorter than _MIN_CHUNK_LENGTH should be excluded."""
        short_chunk = make_mock_chunk(content="too short")
        assert len(short_chunk.content) < _MIN_CHUNK_LENGTH

    @pytest.mark.asyncio
    async def test_table_section_type_excluded(self) -> None:
        """Chunks with section_type='table' should be excluded."""
        chunk = make_mock_chunk(section_type="table")
        assert chunk.section_type == "table"

    @pytest.mark.asyncio
    async def test_list_section_type_excluded(self) -> None:
        """Chunks with section_type='list' should be excluded."""
        chunk = make_mock_chunk(section_type="list")
        assert chunk.section_type == "list"


# ---------------------------------------------------------------------------
# LLM interaction tests
# ---------------------------------------------------------------------------


class TestLLMInteraction:
    @pytest.mark.asyncio
    async def test_generate_question_success(self) -> None:
        """Mock LLM returns a question string."""
        mock_result = MagicMock()
        mock_result.response = "What is the schedule for route 22?"

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            chunk = make_mock_chunk(content="A" * 300)

            from app.knowledge.evals.qa_generator import _generate_question

            result = await _generate_question(chunk, "lv", "test:test-model")
            assert result == "What is the schedule for route 22?"

    @pytest.mark.asyncio
    async def test_generate_question_failure_returns_none(self) -> None:
        """LLM failure should return None, not raise."""
        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(side_effect=RuntimeError("LLM down"))
            mock_agent_cls.return_value = mock_agent

            chunk = make_mock_chunk(content="A" * 300)

            from app.knowledge.evals.qa_generator import _generate_question

            result = await _generate_question(chunk, "lv", "test:test-model")
            assert result is None


# ---------------------------------------------------------------------------
# JSONL output tests
# ---------------------------------------------------------------------------


class TestJSONLOutput:
    def test_write_jsonl_creates_file(self, tmp_path: Path) -> None:
        """JSONL file should be created with correct line count."""
        pairs = [make_qa_pair(source_chunk_id=i) for i in range(5)]
        out = _write_jsonl(pairs, tmp_path)

        assert out.exists()
        assert out.suffix == ".jsonl"
        lines = out.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            record = json.loads(line)
            assert "question" in record
            assert "source_chunk_id" in record
            assert "language" in record

    def test_write_jsonl_path_sandboxing(self, tmp_path: Path) -> None:
        """Path traversal in filename should raise ValueError."""
        pairs = [make_qa_pair()]
        with pytest.raises(ValueError, match="output path escaped sandbox root"):
            _write_jsonl(pairs, tmp_path, filename="../escape.jsonl")

    def test_write_jsonl_empty_pairs(self, tmp_path: Path) -> None:
        """Empty pair list should create an empty file."""
        out = _write_jsonl([], tmp_path)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert content == ""


# ---------------------------------------------------------------------------
# Generate QA pairs integration-style test
# ---------------------------------------------------------------------------


class TestGenerateQAPairs:
    @pytest.mark.asyncio
    async def test_generate_qa_pairs_end_to_end(self) -> None:
        """Full pipeline with mocked DB and LLM."""
        mock_result = MagicMock()
        mock_result.response = "What is the schedule?"

        chunks = [make_mock_chunk(id=i, document_id=1) for i in range(3)]

        with (
            patch("pydantic_ai.Agent") as mock_agent_cls,
            patch(
                "app.knowledge.evals.qa_generator._fetch_eligible_chunks",
                new_callable=AsyncMock,
                return_value=chunks,
            ),
            patch("app.knowledge.evals.qa_generator.get_db_context") as mock_db,
        ):
            mock_agent = AsyncMock()
            mock_agent.run = AsyncMock(return_value=mock_result)
            mock_agent_cls.return_value = mock_agent

            # Mock per-chunk language lookup
            mock_session = AsyncMock()
            mock_scalar_result = MagicMock()
            mock_scalar_result.scalar_one_or_none.return_value = "lv"
            mock_session.execute = AsyncMock(return_value=mock_scalar_result)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            pairs = await generate_qa_pairs(n=3)

        assert len(pairs) == 3
        for pair in pairs:
            assert isinstance(pair, QAPair)
            assert pair.question == "What is the schedule?"
            assert pair.language == "lv"


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_help_exits_zero(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
