"""Unit tests for MemoryRepository."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.memory.repository import MemoryRepository
from app.memory.tests.conftest import make_embedding, make_memory

# --- store ---


@pytest.mark.asyncio
async def test_store_persists_entry(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    entry = make_memory()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await repo.store(entry)

    mock_db.add.assert_called_once_with(entry)
    mock_db.commit.assert_awaited_once()
    mock_db.refresh.assert_awaited_once_with(entry)
    assert result is entry


# --- get ---


@pytest.mark.asyncio
async def test_get_returns_entry(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    entry = make_memory(id=42)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = entry
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(42)

    assert result is entry
    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(999)

    assert result is None


# --- recall ---


@pytest.mark.asyncio
async def test_recall_returns_entries_with_scores(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    entry1 = make_memory(id=1)
    entry2 = make_memory(id=2)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (entry1, 0.1),  # distance 0.1 -> score 0.9
        (entry2, 0.3),  # distance 0.3 -> score 0.7
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding(), limit=10)

    assert len(results) == 2
    assert results[0][0] is entry1
    assert results[0][1] == pytest.approx(0.9)
    assert results[1][1] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_recall_filters_by_min_score(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    entry1 = make_memory(id=1)
    entry2 = make_memory(id=2)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (entry1, 0.1),  # score 0.9 - passes
        (entry2, 0.95),  # score 0.05 - below min_score
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding(), min_score=0.5)

    assert len(results) == 1
    assert results[0][0] is entry1


@pytest.mark.asyncio
async def test_recall_empty_when_no_matches(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding())

    assert results == []


@pytest.mark.asyncio
async def test_recall_with_agent_type_filter(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await repo.recall(make_embedding(), agent_type="transit")

    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_recall_with_memory_type_filter(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await repo.recall(make_embedding(), memory_type="semantic")

    mock_db.execute.assert_awaited_once()


# --- get_by_type ---


@pytest.mark.asyncio
async def test_get_by_type_returns_entries(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    entries = [make_memory(id=1), make_memory(id=2)]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = entries
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_type("semantic")

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_by_type_respects_limit(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    await repo.get_by_type("procedural", limit=5)

    mock_db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_type_empty(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_type("query_pattern")

    assert result == []


# --- increment_recalled_count ---


@pytest.mark.asyncio
async def test_increment_recalled_count(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    await repo.increment_recalled_count(42)

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


# --- delete_decayed ---


@pytest.mark.asyncio
async def test_delete_decayed_returns_count(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    count = await repo.delete_decayed(0.1)

    assert count == 5
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_decayed_returns_zero_when_none(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    count = await repo.delete_decayed(0.5)

    assert count == 0


# --- find_similar ---


@pytest.mark.asyncio
async def test_find_similar_returns_matches(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    entry = make_memory(id=1)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (entry, 0.03),  # distance 0.03 -> score 0.97
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.find_similar(make_embedding(), threshold=0.95)

    assert len(results) == 1
    assert results[0][0] is entry
    assert results[0][1] == pytest.approx(0.97)


@pytest.mark.asyncio
async def test_find_similar_returns_empty_no_matches(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (make_memory(id=1), 0.5),  # distance 0.5 -> score 0.5 (below 0.95)
    ]
    mock_db.execute = AsyncMock(return_value=mock_result)

    results = await repo.find_similar(make_embedding(), threshold=0.95)

    assert results == []


# --- apply_decay ---


@pytest.mark.asyncio
async def test_apply_decay_updates_entries(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 3
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    count = await repo.apply_decay("episodic", 30)

    assert count == 3
    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_decay_returns_zero_when_none(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 0
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    count = await repo.apply_decay("procedural", 90)

    assert count == 0


# --- merge_entries ---


@pytest.mark.asyncio
async def test_merge_entries_keeps_higher_recalled(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    keep = make_memory(id=1, recalled_count=5)
    remove = make_memory(id=2, recalled_count=2)

    call_count = 0

    async def mock_execute(stmt: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        # First two calls are SELECT (get), next two are UPDATE/DELETE, last is SELECT (get)
        if call_count <= 1:
            result.scalar_one_or_none.return_value = keep
        elif call_count == 2:
            result.scalar_one_or_none.return_value = remove
        elif call_count == 5:
            result.scalar_one_or_none.return_value = keep
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.commit = AsyncMock()

    merged = await repo.merge_entries(1, 2, "merged content", make_embedding())

    assert merged is keep


# --- find_similar_pairs ---


@pytest.mark.asyncio
async def test_find_similar_pairs_returns_above_threshold(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    entry_a = make_memory(id=1)
    entry_b = make_memory(id=2)

    # First call returns the raw SQL results, subsequent calls are get() lookups
    call_count = 0

    async def mock_execute(stmt: object, params: object = None) -> MagicMock:
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            # Raw SQL result: (a_id, b_id, score)
            result.all.return_value = [(1, 2, 0.95)]
        elif call_count == 2:
            result.scalar_one_or_none.return_value = entry_a
        elif call_count == 3:
            result.scalar_one_or_none.return_value = entry_b
        return result

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    pairs = await repo.find_similar_pairs(threshold=0.92)

    assert len(pairs) == 1
    assert pairs[0][0] is entry_a
    assert pairs[0][1] is entry_b
    assert pairs[0][2] == pytest.approx(0.95)


@pytest.mark.asyncio
async def test_find_similar_pairs_empty_when_no_similar(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    pairs = await repo.find_similar_pairs(threshold=0.92)

    assert pairs == []


# --- find_promotable ---


@pytest.mark.asyncio
async def test_find_promotable_returns_episodic_above_threshold(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    entries = [make_memory(id=1, memory_type="episodic", recalled_count=5)]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = entries
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.find_promotable(threshold=3)

    assert len(result) == 1
    assert result[0].recalled_count == 5


@pytest.mark.asyncio
async def test_find_promotable_empty_when_none_qualify(
    repo: MemoryRepository, mock_db: AsyncMock
) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute = AsyncMock(return_value=mock_result)

    result = await repo.find_promotable(threshold=3)

    assert result == []


# --- update_memory_type ---


@pytest.mark.asyncio
async def test_update_memory_type_executes(repo: MemoryRepository, mock_db: AsyncMock) -> None:
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()

    await repo.update_memory_type(1, "procedural")

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
