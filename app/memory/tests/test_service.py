"""Unit tests for MemoryService."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, patch

import pytest

from app.memory.exceptions import MemoryNotFoundError
from app.memory.schemas import (
    CompactionResult,
    MemoryEntryCreate,
    MemoryRecallByQueryRequest,
    MemoryRecallRequest,
    MemoryRecallResponse,
)
from app.memory.service import MemoryService
from app.memory.tests.conftest import make_embedding, make_memory


def _make_service() -> tuple[MemoryService, AsyncMock]:
    """Create a service with a mocked repository."""
    mock_db = AsyncMock()
    svc = MemoryService(mock_db)
    mock_repo = AsyncMock()
    svc.repository = mock_repo
    return svc, mock_repo


@pytest.mark.asyncio
async def test_store_creates_entry() -> None:
    svc, mock_repo = _make_service()
    entry = make_memory(id=10)
    mock_repo.store.return_value = entry
    mock_repo.find_similar.return_value = []

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        data = MemoryEntryCreate(
            agent_type="transit",
            memory_type="semantic",
            content="Route 5 peak hours",
            source="agent",
        )
        result = await svc.store(data)

    assert result.id == 10
    mock_repo.store.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_entry() -> None:
    svc, mock_repo = _make_service()
    entry = make_memory(id=42)
    mock_repo.get.return_value = entry

    result = await svc.get(42)

    assert result.id == 42


@pytest.mark.asyncio
async def test_get_raises_not_found() -> None:
    svc, mock_repo = _make_service()
    mock_repo.get.return_value = None

    with pytest.raises(MemoryNotFoundError):
        await svc.get(999)


@pytest.mark.asyncio
async def test_recall_returns_scored_results() -> None:
    svc, mock_repo = _make_service()
    entry = make_memory(id=1)
    mock_repo.recall.return_value = [(entry, 0.95)]
    mock_repo.increment_recalled_count.return_value = None

    request = MemoryRecallRequest(embedding=make_embedding())
    results = await svc.recall(request)

    assert len(results) == 1
    assert isinstance(results[0], MemoryRecallResponse)
    assert results[0].score == pytest.approx(0.95)
    mock_repo.increment_recalled_count.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_recall_empty_results() -> None:
    svc, mock_repo = _make_service()
    mock_repo.recall.return_value = []

    request = MemoryRecallRequest(embedding=make_embedding())
    results = await svc.recall(request)

    assert results == []


@pytest.mark.asyncio
async def test_get_by_type_delegates() -> None:
    svc, mock_repo = _make_service()
    entries = [make_memory(id=1), make_memory(id=2)]
    mock_repo.get_by_type.return_value = entries

    result = await svc.get_by_type("semantic", limit=10)

    assert len(result) == 2
    mock_repo.get_by_type.assert_awaited_once_with("semantic", 10)


@pytest.mark.asyncio
async def test_delete_decayed_delegates() -> None:
    svc, mock_repo = _make_service()
    mock_repo.delete_decayed.return_value = 3

    count = await svc.delete_decayed(0.2)

    assert count == 3
    mock_repo.delete_decayed.assert_awaited_once_with(0.2)


@pytest.mark.asyncio
async def test_delete_decayed_default_threshold() -> None:
    svc, mock_repo = _make_service()
    mock_repo.delete_decayed.return_value = 0

    count = await svc.delete_decayed()

    assert count == 0
    mock_repo.delete_decayed.assert_awaited_once_with(0.1)


# --- store with embedding/dedup ---


@pytest.mark.asyncio
async def test_store_generates_embedding_when_none() -> None:
    svc, mock_repo = _make_service()
    mock_repo.find_similar.return_value = []
    entry = make_memory(id=10)
    mock_repo.store.return_value = entry

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        data = MemoryEntryCreate(
            agent_type="transit",
            memory_type="semantic",
            content="Route 5 peak hours",
            source="agent",
        )
        result = await svc.store(data)

    assert result.id == 10
    mock_provider.embed.assert_awaited_once()
    mock_repo.store.assert_awaited_once()


@pytest.mark.asyncio
async def test_store_skips_duplicate() -> None:
    svc, mock_repo = _make_service()
    existing = make_memory(id=99)
    mock_repo.find_similar.return_value = [(existing, 0.97)]

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        data = MemoryEntryCreate(
            agent_type="transit",
            memory_type="semantic",
            content="Route 5 peak hours",
            source="agent",
        )
        result = await svc.store(data)

    assert result.id == 99
    mock_repo.store.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_uses_provided_embedding() -> None:
    svc, mock_repo = _make_service()
    mock_repo.find_similar.return_value = []
    entry = make_memory(id=10)
    mock_repo.store.return_value = entry

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_embed.return_value = mock_provider

        data = MemoryEntryCreate(
            agent_type="transit",
            memory_type="semantic",
            content="Route 5 peak hours",
            embedding=make_embedding(),
            source="agent",
        )
        result = await svc.store(data)

    assert result.id == 10
    mock_provider.embed.assert_not_awaited()


# --- recall_by_query ---


@pytest.mark.asyncio
async def test_recall_by_query_embeds_text() -> None:
    svc, mock_repo = _make_service()
    entry = make_memory(id=1)
    mock_repo.recall.return_value = [(entry, 0.9)]
    mock_repo.increment_recalled_count.return_value = None

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        request = MemoryRecallByQueryRequest(query="route 5 delays")
        results = await svc.recall_by_query(request)

    assert len(results) == 1
    mock_provider.embed.assert_awaited_once_with(["route 5 delays"])


@pytest.mark.asyncio
async def test_recall_by_query_returns_scored_results() -> None:
    svc, mock_repo = _make_service()
    entry = make_memory(id=1)
    mock_repo.recall.return_value = [(entry, 0.85)]
    mock_repo.increment_recalled_count.return_value = None

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        request = MemoryRecallByQueryRequest(query="test query")
        results = await svc.recall_by_query(request)

    assert results[0].score == pytest.approx(0.85)
    mock_repo.increment_recalled_count.assert_awaited_once_with(1)


# --- compact ---


@pytest.mark.asyncio
async def test_compact_applies_decay_per_type() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 0
    mock_repo.find_similar_pairs.return_value = []
    mock_repo.find_promotable.return_value = []

    await svc.compact()

    # Should call apply_decay for procedural, episodic, query_pattern (not semantic)
    assert mock_repo.apply_decay.await_count == 3
    calls = [c.args for c in mock_repo.apply_decay.await_args_list]
    assert ("procedural", 90) in calls
    assert ("episodic", 30) in calls
    assert ("query_pattern", 60) in calls


@pytest.mark.asyncio
async def test_compact_deletes_decayed() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 5
    mock_repo.find_similar_pairs.return_value = []
    mock_repo.find_promotable.return_value = []

    result = await svc.compact()

    assert result.decayed_deleted == 5
    mock_repo.delete_decayed.assert_awaited_once()


@pytest.mark.asyncio
async def test_compact_merges_similar() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 0
    entry_a = make_memory(id=1, recalled_count=3)
    entry_b = make_memory(id=2, recalled_count=1)
    mock_repo.find_similar_pairs.return_value = [(entry_a, entry_b, 0.94)]
    mock_repo.merge_entries.return_value = entry_a
    mock_repo.find_promotable.return_value = []

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        result = await svc.compact()

    assert result.merged == 1
    mock_repo.merge_entries.assert_awaited_once()
    # entry_a has higher recalled_count, should be kept
    call_kwargs = mock_repo.merge_entries.await_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("keep_id") or call_kwargs.args[0] == 1


@pytest.mark.asyncio
async def test_compact_promotes_episodes() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 0
    mock_repo.find_similar_pairs.return_value = []
    promotable = [make_memory(id=1, memory_type="episodic", recalled_count=5)]
    mock_repo.find_promotable.return_value = promotable
    mock_repo.update_memory_type.return_value = None

    result = await svc.compact()

    assert result.promoted == 1
    mock_repo.update_memory_type.assert_awaited_once_with(1, "procedural")


@pytest.mark.asyncio
async def test_compact_returns_result() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 2
    mock_repo.find_similar_pairs.return_value = []
    mock_repo.find_promotable.return_value = []

    result = await svc.compact()

    assert isinstance(result, CompactionResult)
    assert result.decayed_deleted == 2
    assert result.merged == 0
    assert result.promoted == 0


# --- promote_episodes ---


@pytest.mark.asyncio
async def test_promote_episodes_updates_type() -> None:
    svc, mock_repo = _make_service()
    entries = [
        make_memory(id=1, memory_type="episodic", recalled_count=5),
        make_memory(id=2, memory_type="episodic", recalled_count=4),
    ]
    mock_repo.find_promotable.return_value = entries
    mock_repo.update_memory_type.return_value = None

    count = await svc.promote_episodes()

    assert count == 2
    assert mock_repo.update_memory_type.await_count == 2


@pytest.mark.asyncio
async def test_promote_episodes_returns_zero_when_none() -> None:
    svc, mock_repo = _make_service()
    mock_repo.find_promotable.return_value = []

    count = await svc.promote_episodes()

    assert count == 0


# --- LLM intent merging tests ---


@pytest.mark.asyncio
async def test_compact_uses_llm_merge_when_enabled() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 0
    entry_a = make_memory(id=1, recalled_count=3, content="Content A")
    entry_b = make_memory(id=2, recalled_count=1, content="Content B")
    mock_repo.find_similar_pairs.return_value = [(entry_a, entry_b, 0.94)]
    mock_repo.merge_entries.return_value = entry_a
    mock_repo.find_promotable.return_value = []

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        with patch("app.memory.service.get_settings") as mock_settings:
            mock_settings.return_value.memory_llm_merge_enabled = True
            mock_settings.return_value.memory_merge_threshold = 0.92
            mock_settings.return_value.memory_procedural_decay_days = 90
            mock_settings.return_value.memory_episodic_decay_days = 30
            mock_settings.return_value.memory_query_pattern_decay_days = 60
            mock_settings.return_value.memory_decay_min_weight = 0.1
            mock_settings.return_value.memory_promotion_threshold = 3

            with patch.object(svc, "_llm_merge", return_value="LLM merged text") as mock_llm:
                result = await svc.compact()

    assert result.merged == 1
    mock_llm.assert_awaited_once_with("Content A", "Content B")
    # Verify merge_entries received LLM output, not concatenation
    call_kwargs = mock_repo.merge_entries.await_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("merged_content") == "LLM merged text"


@pytest.mark.asyncio
async def test_llm_merge_falls_back_on_failure() -> None:
    svc, _ = _make_service()

    with patch("app.core.agents.config.resolve_tier_model", side_effect=RuntimeError("No model")):
        result = await svc._llm_merge("Content A", "Content B")

    # Should fall back to concatenation
    assert result == "Content A\n---\nContent B"


@pytest.mark.asyncio
async def test_compact_uses_concatenation_when_llm_disabled() -> None:
    svc, mock_repo = _make_service()
    mock_repo.apply_decay.return_value = 0
    mock_repo.delete_decayed.return_value = 0
    entry_a = make_memory(id=1, recalled_count=3, content="Content A")
    entry_b = make_memory(id=2, recalled_count=1, content="Content B")
    mock_repo.find_similar_pairs.return_value = [(entry_a, entry_b, 0.94)]
    mock_repo.merge_entries.return_value = entry_a
    mock_repo.find_promotable.return_value = []

    with patch("app.memory.service._get_embedding") as mock_embed:
        mock_provider = AsyncMock()
        mock_provider.embed.return_value = [make_embedding()]
        mock_embed.return_value = mock_provider

        result = await svc.compact()

    assert result.merged == 1
    call_kwargs = mock_repo.merge_entries.await_args
    assert call_kwargs is not None
    merged = call_kwargs.kwargs.get("merged_content", "")
    assert "Content A\n---\nContent B" == merged


@pytest.mark.asyncio
async def test_llm_merge_truncates_content() -> None:
    svc, _ = _make_service()
    long_content = "x" * 1000

    with patch("app.core.agents.config.resolve_tier_model", return_value="test-model"):
        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_result = AsyncMock()
            mock_result.output = "merged"
            mock_agent_instance = AsyncMock()
            mock_agent_instance.run.return_value = mock_result
            mock_agent_cls.return_value = mock_agent_instance

            result = await svc._llm_merge(long_content, long_content)

    assert result == "merged"
    # Verify content was truncated to 500 chars each
    call_args = mock_agent_instance.run.call_args
    assert call_args is not None
    prompt = call_args.args[0]
    # Each entry should be 500 chars max in the prompt
    assert "x" * 501 not in prompt
