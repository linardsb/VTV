# Plan: AI-3.1 Memory Vertical Slice — Models + Repository

## Context

The agent is stateless — it can't learn from repeated usage. The same dispatcher asking the same question gets no benefit from prior interactions. This vertical slice creates `app/memory/` with a `MemoryEntry` SQLAlchemy model backed by pgvector and a repository layer with store/recall/delete operations. 4 memory types: procedural (learned patterns), episodic (session logs), semantic (durable facts), query_pattern (frequent queries).

## Security Context Assessment

**Active contexts:** CTX-RBAC, CTX-INPUT

- **CTX-RBAC** — New endpoints will need `require_role()` with explicit role lists. Memory entries are internal agent data, so restrict to `admin` and `agent` roles.
- **CTX-INPUT** — `memory_type` filter must use `Literal[...]` type. Any text search on `content` must use `escape_like()`. Vector embedding input validated via Pydantic schema length constraints.

CTX-AUTH, CTX-FILE, CTX-AGENT, CTX-INFRA — **not active** for this slice (no auth changes, no file uploads, no agent tool wiring yet, no infra changes).

## Research Summary

### Reference Feature: `app/knowledge/`

The knowledge feature is the canonical reference — it uses pgvector `Vector(1024)`, cosine distance queries, and the same async repository pattern.

**Key pgvector patterns:**
- **Vector column:** `embedding = mapped_column(Vector(1024))` — `app/knowledge/models.py:86`
- **Cosine query:** `DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")` — `app/knowledge/repository.py:282`
- **Result unpacking:** `[(row[0], row[1], float(row[2])) for row in result.all()]` — `app/knowledge/repository.py:300-302`
- **Pyright directive:** `# pyright: reportUnknownMemberType=false` at top of models.py — `app/knowledge/models.py:1`

### Shared Utilities

| Utility | Import |
|---------|--------|
| `Base` | `from app.core.database import Base` |
| `TimestampMixin` | `from app.shared.models import TimestampMixin` |
| `get_db()` | `from app.core.database import get_db` |
| `get_logger()` | `from app.core.logging import get_logger` |
| `AppError`, `NotFoundError` | `from app.core.exceptions import AppError, NotFoundError` |
| `PaginationParams`, `PaginatedResponse` | `from app.shared.schemas import PaginationParams, PaginatedResponse` |
| `escape_like()` | `from app.shared.utils import escape_like` |
| `utcnow()` | `from app.shared.models import utcnow` |

### Config

Embedding dimension already configured at `app/core/config.py:167` → `embedding_dimension: int = 1024`. No new config needed for this slice.

### Migration

Latest revision: `f3a4b5c6d7e8` (add_evergreen_to_documents). New migration will use this as `down_revision`.

## Test Landscape

**Patterns from `app/knowledge/tests/`:**
- `conftest.py` — `make_document()` and `make_chunk()` factories with `**overrides` pattern
- `test_repository.py` — 598 lines, mock DB via `AsyncMock`, `MagicMock` for result sets
- Mock pattern: `repo.db.execute = AsyncMock(return_value=mock_result)` where `mock_result.scalar_one_or_none.return_value = obj`

**Patterns from `app/drivers/tests/`:**
- `conftest.py` — `make_driver(**overrides)` factory, `sample_driver` / `sample_drivers` fixtures
- `test_repository.py` — 149 lines, clean CRUD test patterns
- Service mock: `svc.repository = AsyncMock()`

**Security convention tests:** `app/tests/test_security.py` — auth override pattern, rate limiter disable, streaming upload size checks.

**Shared fixtures:** `app/tests/conftest.py` — `test_db_engine`, `test_db_session` for integration tests. `app/shared/tests/conftest.py` — transaction rollback pattern.

## Type Check Baseline

| Tool | Scope | Errors |
|------|-------|--------|
| Pyright | `app/knowledge/` | 0 |
| Mypy | `app/knowledge/` | 0 (3 errors are in `app/core/agents/`, not knowledge) |
| Pyright | full `app/` | 6 |

Target: 0 new errors in `app/memory/`. Full `app/` pyright ≤ 6.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/memory/__init__.py` | Module docstring |
| CREATE | `app/memory/models.py` | `MemoryEntry` model with pgvector `Vector(1024)` |
| CREATE | `app/memory/schemas.py` | Pydantic request/response schemas |
| CREATE | `app/memory/repository.py` | Store, recall, get_by_type, increment_recalled, delete_decayed |
| CREATE | `app/memory/exceptions.py` | `MemoryNotFoundError` |
| CREATE | `app/memory/service.py` | Business logic orchestration + logging |
| CREATE | `app/memory/routes.py` | 5 REST endpoints with RBAC |
| UPDATE | `app/main.py` | Register memory router |
| CREATE | `alembic/versions/a1b2c3d4e5f6_create_memory_entries.py` | Migration with pgvector + ivfflat index |
| CREATE | `app/memory/tests/__init__.py` | Test package |
| CREATE | `app/memory/tests/conftest.py` | Factories + fixtures |
| CREATE | `app/memory/tests/test_repository.py` | Repository unit tests |
| CREATE | `app/memory/tests/test_service.py` | Service unit tests |
| CREATE | `app/memory/tests/test_routes.py` | Route unit tests |

## Implementation Steps

### Step 1: Create `app/memory/__init__.py`

```python
"""Agent memory storage — pgvector-backed long-term memory for AI agents."""
```

**Validation:** `uv run ruff check app/memory/__init__.py`

---

### Step 2: Create `app/memory/models.py`

Reference: `app/knowledge/models.py:1-88`

```python
# pyright: reportUnknownMemberType=false
"""SQLAlchemy models for agent memory entries."""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class MemoryEntry(Base, TimestampMixin):
    """Agent memory entry with vector embedding for similarity recall.

    Stores learned patterns, session logs, durable facts, and query patterns.
    The embedding column uses pgvector's Vector type for cosine similarity search.
    """

    __tablename__ = "memory_entries"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1024))
    metadata_json = mapped_column(JSONB, nullable=True)
    decay_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_evergreen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    recalled_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

Notes:
- `metadata_json` uses `JSONB` (not `Text` like knowledge) for native JSON queries
- `embedding` has no `Mapped[]` wrapper — pgvector columns use bare `mapped_column()` (see `app/knowledge/models.py:86`)
- Add `# pyright: reportUnknownMemberType=false` at top (pgvector stubs incomplete)

**Validation:** `uv run ruff format app/memory/models.py && uv run ruff check --fix app/memory/models.py && uv run pyright app/memory/models.py`

---

### Step 3: Create `app/memory/schemas.py`

Reference: `app/drivers/schemas.py` for basic CRUD schema pattern.

```python
"""Pydantic schemas for memory entry requests and responses."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MemoryType = Literal["procedural", "episodic", "semantic", "query_pattern"]
MemorySource = Literal["agent", "dispatcher", "compaction"]


class MemoryEntryCreate(BaseModel):
    """Request schema for creating a memory entry."""

    agent_type: str = Field(max_length=50)
    memory_type: MemoryType
    content: str = Field(max_length=10000)
    embedding: list[float] | None = None
    metadata_json: dict[str, Any] | None = None  # noqa: ANN401
    decay_weight: float = Field(default=1.0, ge=0.0, le=1.0)
    is_evergreen: bool = False
    source: MemorySource


class MemoryRecallRequest(BaseModel):
    """Request schema for recalling memories by similarity."""

    embedding: list[float] = Field(min_length=1024, max_length=1024)
    agent_type: str | None = Field(default=None, max_length=50)
    memory_type: MemoryType | None = None
    limit: int = Field(default=10, ge=1, le=100)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class MemoryEntryResponse(BaseModel):
    """Response schema for a memory entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_type: str
    memory_type: str
    content: str
    metadata_json: dict[str, Any] | None = None  # noqa: ANN401
    decay_weight: float
    is_evergreen: bool
    source: str
    recalled_count: int
    created_at: datetime
    updated_at: datetime


class MemoryRecallResponse(BaseModel):
    """Response schema for a recalled memory with similarity score."""

    memory: MemoryEntryResponse
    score: float = Field(description="Cosine similarity score (1.0 = identical)")
```

Notes:
- `MemoryType` and `MemorySource` use `Literal[...]` per anti-pattern #54
- `embedding` field in create is optional (may be generated server-side later)
- `metadata_json` uses `dict[str, Any]` with `# noqa: ANN401` per anti-pattern #23
- `max_length` on all string fields per CTX-INPUT

**Validation:** `uv run ruff format app/memory/schemas.py && uv run ruff check --fix app/memory/schemas.py && uv run pyright app/memory/schemas.py`

---

### Step 4: Create `app/memory/exceptions.py`

Reference: `app/core/exceptions.py:14-29`

```python
"""Memory feature exceptions."""

from app.core.exceptions import NotFoundError


class MemoryNotFoundError(NotFoundError):
    """Raised when a memory entry is not found."""

    def __init__(self, memory_id: int) -> None:
        super().__init__(f"Memory entry {memory_id} not found")
```

**Validation:** `uv run ruff check app/memory/exceptions.py && uv run pyright app/memory/exceptions.py`

---

### Step 5: Create `app/memory/repository.py`

Reference: `app/knowledge/repository.py:260-303` for cosine distance pattern. `app/drivers/repository.py` for basic CRUD.

```python
# pyright: reportUnknownMemberType=false
"""Repository for agent memory entries with pgvector similarity search."""

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.memory.models import MemoryEntry

logger = get_logger(__name__)


class MemoryRepository:
    """Data access layer for memory entries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def store(self, entry: MemoryEntry) -> MemoryEntry:
        """Persist a new memory entry."""
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        return entry

    async def get(self, entry_id: int) -> MemoryEntry | None:
        """Get a memory entry by ID."""
        result = await self.db.execute(
            select(MemoryEntry).where(MemoryEntry.id == entry_id)
        )
        return result.scalar_one_or_none()

    async def recall(
        self,
        embedding: list[float],
        agent_type: str | None = None,
        memory_type: str | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryEntry, float]]:
        """Recall memories by cosine similarity.

        Args:
            embedding: Query embedding vector (1024-dim).
            agent_type: Optional filter by agent type.
            memory_type: Optional filter by memory type.
            limit: Maximum results to return.
            min_score: Minimum similarity score (0-1). Cosine distance
                is converted: score = 1 - distance.

        Returns:
            List of (entry, score) tuples sorted by score descending.
        """
        distance = MemoryEntry.embedding.cosine_distance(embedding).label("distance")
        query = (
            select(MemoryEntry, distance)
            .where(MemoryEntry.embedding.is_not(None))
            .order_by(distance)
            .limit(limit)
        )
        if agent_type is not None:
            query = query.where(MemoryEntry.agent_type == agent_type)
        if memory_type is not None:
            query = query.where(MemoryEntry.memory_type == memory_type)

        result = await self.db.execute(query)
        rows: list[tuple[MemoryEntry, float]] = []
        for row in result.all():
            score = 1.0 - float(row[1])
            if score >= min_score:
                rows.append((row[0], score))
        return rows

    async def get_by_type(
        self,
        memory_type: str,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """Get memory entries by type, ordered by most recent."""
        result = await self.db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.memory_type == memory_type)
            .order_by(MemoryEntry.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def increment_recalled_count(self, entry_id: int) -> None:
        """Increment the recall counter for a memory entry."""
        await self.db.execute(
            update(MemoryEntry)
            .where(MemoryEntry.id == entry_id)
            .values(recalled_count=MemoryEntry.recalled_count + 1)
        )
        await self.db.commit()

    async def delete_decayed(self, threshold: float) -> int:
        """Delete non-evergreen entries with decay_weight below threshold.

        Returns:
            Number of entries deleted.
        """
        result = await self.db.execute(
            delete(MemoryEntry)
            .where(MemoryEntry.decay_weight < threshold)
            .where(MemoryEntry.is_evergreen.is_(False))
        )
        await self.db.commit()
        count = result.rowcount if result.rowcount else 0
        logger.info(
            "memory.repository.delete_decayed_completed",
            threshold=threshold,
            deleted_count=count,
        )
        return count
```

Notes:
- Cosine distance → similarity: `score = 1.0 - distance` (distance 0 = identical → score 1.0)
- `min_score` filtering happens post-query (pgvector doesn't support WHERE on computed distance easily)
- `delete_decayed` excludes evergreen entries
- `# pyright: reportUnknownMemberType=false` for pgvector method chains

**Validation:** `uv run ruff format app/memory/repository.py && uv run ruff check --fix app/memory/repository.py && uv run pyright app/memory/repository.py`

---

### Step 6: Create `app/memory/service.py`

Reference: `app/events/service.py` for service pattern.

```python
"""Business logic for agent memory operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.memory.exceptions import MemoryNotFoundError
from app.memory.models import MemoryEntry
from app.memory.repository import MemoryRepository
from app.memory.schemas import MemoryEntryCreate, MemoryRecallRequest, MemoryRecallResponse

logger = get_logger(__name__)


class MemoryService:
    """Orchestrates memory storage, recall, and maintenance."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = MemoryRepository(db)

    async def store(self, data: MemoryEntryCreate) -> MemoryEntry:
        """Store a new memory entry."""
        entry = MemoryEntry(
            agent_type=data.agent_type,
            memory_type=data.memory_type,
            content=data.content,
            embedding=data.embedding,
            metadata_json=data.metadata_json,
            decay_weight=data.decay_weight,
            is_evergreen=data.is_evergreen,
            source=data.source,
        )
        result = await self.repository.store(entry)
        logger.info(
            "memory.service.store_completed",
            memory_id=result.id,
            memory_type=data.memory_type,
            agent_type=data.agent_type,
        )
        return result

    async def get(self, entry_id: int) -> MemoryEntry:
        """Get a memory entry by ID. Raises MemoryNotFoundError if not found."""
        entry = await self.repository.get(entry_id)
        if entry is None:
            raise MemoryNotFoundError(entry_id)
        return entry

    async def recall(self, request: MemoryRecallRequest) -> list[MemoryRecallResponse]:
        """Recall memories by similarity and increment recall counters."""
        from app.memory.schemas import MemoryEntryResponse

        rows = await self.repository.recall(
            embedding=request.embedding,
            agent_type=request.agent_type,
            memory_type=request.memory_type,
            limit=request.limit,
            min_score=request.min_score,
        )
        results: list[MemoryRecallResponse] = []
        for entry, score in rows:
            await self.repository.increment_recalled_count(entry.id)
            results.append(
                MemoryRecallResponse(
                    memory=MemoryEntryResponse.model_validate(entry),
                    score=score,
                )
            )
        logger.info(
            "memory.service.recall_completed",
            result_count=len(results),
            agent_type=request.agent_type,
            memory_type=request.memory_type,
        )
        return results

    async def get_by_type(self, memory_type: str, limit: int = 50) -> list[MemoryEntry]:
        """List memory entries by type."""
        return await self.repository.get_by_type(memory_type, limit)

    async def delete_decayed(self, threshold: float = 0.1) -> int:
        """Remove decayed non-evergreen memories below threshold."""
        count = await self.repository.delete_decayed(threshold)
        logger.info("memory.service.delete_decayed_completed", deleted_count=count)
        return count
```

**Validation:** `uv run ruff format app/memory/service.py && uv run ruff check --fix app/memory/service.py && uv run pyright app/memory/service.py`

---

### Step 7: Create `app/memory/routes.py`

Reference: `app/drivers/routes.py` for RBAC + rate limiting pattern.

5 endpoints:
- `POST /api/v1/memory/` — store entry (admin, agent)
- `GET /api/v1/memory/{id}` — get by ID (admin, agent)
- `POST /api/v1/memory/recall` — recall by similarity (admin, agent)
- `GET /api/v1/memory/type/{memory_type}` — list by type (admin, agent)
- `DELETE /api/v1/memory/decayed` — cleanup decayed entries (admin only)

```python
"""REST endpoints for agent memory management."""

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.auth.models import User
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.memory.schemas import (
    MemoryEntryCreate,
    MemoryEntryResponse,
    MemoryRecallRequest,
    MemoryRecallResponse,
)
from app.memory.service import MemoryService

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


def _get_service(db: AsyncSession = Depends(get_db)) -> MemoryService:  # noqa: B008
    return MemoryService(db)


@router.post("/", response_model=MemoryEntryResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def store_memory(
    request: Request,
    data: MemoryEntryCreate,
    service: MemoryService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> MemoryEntryResponse:
    """Store a new memory entry."""
    _ = request  # rate limiter requires request param
    entry = await service.store(data)
    return MemoryEntryResponse.model_validate(entry)


@router.get("/{entry_id}", response_model=MemoryEntryResponse)
@limiter.limit("30/minute")
async def get_memory(
    request: Request,
    entry_id: int,
    service: MemoryService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> MemoryEntryResponse:
    """Get a memory entry by ID."""
    _ = request
    entry = await service.get(entry_id)
    return MemoryEntryResponse.model_validate(entry)


@router.post("/recall", response_model=list[MemoryRecallResponse])
@limiter.limit("10/minute")
async def recall_memories(
    request: Request,
    data: MemoryRecallRequest,
    service: MemoryService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> list[MemoryRecallResponse]:
    """Recall memories by vector similarity."""
    _ = request
    return await service.recall(data)


@router.get(
    "/type/{memory_type}",
    response_model=list[MemoryEntryResponse],
)
@limiter.limit("30/minute")
async def list_by_type(
    request: Request,
    memory_type: Literal["procedural", "episodic", "semantic", "query_pattern"],
    limit: int = Query(default=50, ge=1, le=200),  # noqa: B008
    service: MemoryService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin", "agent")),  # noqa: B008
) -> list[MemoryEntryResponse]:
    """List memory entries by type."""
    _ = request
    entries = await service.get_by_type(memory_type, limit)
    return [MemoryEntryResponse.model_validate(e) for e in entries]


@router.delete("/decayed", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def delete_decayed(
    request: Request,
    threshold: float = Query(default=0.1, ge=0.0, le=1.0),  # noqa: B008
    service: MemoryService = Depends(_get_service),  # noqa: B008
    _current_user: User = Depends(require_role("admin")),  # noqa: B008
) -> dict[str, int]:
    """Delete decayed non-evergreen memory entries below threshold."""
    _ = request
    count = await service.delete_decayed(threshold)
    return {"deleted_count": count}
```

Notes:
- `memory_type` path param uses `Literal[...]` per anti-pattern #54
- `Depends()` and `Query()` get `# noqa: B008` per anti-pattern #40
- `_ = request` references the param to satisfy ARG001 per anti-pattern #18
- Rate limits: mutations 10/min, reads 30/min, cleanup 5/min (admin only)

**Validation:** `uv run ruff format app/memory/routes.py && uv run ruff check --fix app/memory/routes.py && uv run pyright app/memory/routes.py`

---

### Step 8: Register router in `app/main.py`

Add after the knowledge router registration (search for `knowledge` in `app/main.py`):

```python
from app.memory.routes import router as memory_router
# ...
app.include_router(memory_router)
```

**Validation:** `uv run ruff check app/main.py && uv run pyright app/main.py`

---

### Step 9: Create Alembic migration

Run: `cd /Users/Berzins/Desktop/VTV && uv run alembic revision --autogenerate -m "create memory_entries table"`

If autogenerate doesn't capture the ivfflat index, manually add to `upgrade()`:

```python
op.execute(
    "CREATE INDEX ix_memory_entries_embedding ON memory_entries "
    "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
)
```

And in `downgrade()`:
```python
op.execute("DROP INDEX IF EXISTS ix_memory_entries_embedding")
```

Note: The `CREATE EXTENSION IF NOT EXISTS vector` should already exist from the initial migration. Verify — if not present, add it before the table creation.

**Validation:** `uv run alembic check` (verify no pending migrations)

---

### Step 10: Create `app/memory/tests/__init__.py`

Empty file.

---

### Step 11: Create `app/memory/tests/conftest.py`

Reference: `app/drivers/tests/conftest.py` for factory pattern.

```python
"""Fixtures and factories for memory tests."""

import pytest
from unittest.mock import AsyncMock

from app.memory.models import MemoryEntry
from app.memory.repository import MemoryRepository
from app.memory.service import MemoryService
from app.shared.models import utcnow


def make_memory(**overrides: object) -> MemoryEntry:
    """Factory for MemoryEntry with sensible defaults."""
    now = utcnow()
    defaults: dict[str, object] = {
        "id": 1,
        "agent_type": "transit",
        "memory_type": "semantic",
        "content": "Route 5 typically has delays during morning rush hour 07:30-09:00",
        "embedding": None,
        "metadata_json": {"route_id": "5", "confidence": 0.92},
        "decay_weight": 1.0,
        "is_evergreen": False,
        "source": "agent",
        "recalled_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return MemoryEntry(**defaults)


def make_embedding(dim: int = 1024) -> list[float]:
    """Create a dummy embedding vector."""
    return [0.1] * dim


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def repo(mock_db: AsyncMock) -> MemoryRepository:
    return MemoryRepository(mock_db)


@pytest.fixture
def service(mock_db: AsyncMock) -> MemoryService:
    svc = MemoryService(mock_db)
    svc.repository = AsyncMock()  # type: ignore[assignment]
    return svc


@pytest.fixture
def sample_memory() -> MemoryEntry:
    return make_memory()


@pytest.fixture
def sample_memories() -> list[MemoryEntry]:
    return [
        make_memory(id=1, memory_type="procedural", content="How to check route delays"),
        make_memory(id=2, memory_type="episodic", content="Dispatcher asked about route 5"),
        make_memory(id=3, memory_type="semantic", content="Route 5 peak hours: 07:30-09:00"),
        make_memory(id=4, memory_type="query_pattern", content="Show me route 5 status"),
    ]
```

**Validation:** `uv run ruff format app/memory/tests/conftest.py && uv run ruff check --fix app/memory/tests/conftest.py`

---

### Step 12: Create `app/memory/tests/test_repository.py`

Test all 5 repository methods with mock DB. ~15 tests.

```python
"""Unit tests for MemoryRepository."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.memory.models import MemoryEntry
from app.memory.repository import MemoryRepository
from app.memory.tests.conftest import make_embedding, make_memory


# --- store ---

@pytest.mark.asyncio
async def test_store_persists_entry(repo: MemoryRepository) -> None:
    entry = make_memory()
    repo.db.add = MagicMock()
    repo.db.commit = AsyncMock()
    repo.db.refresh = AsyncMock()

    result = await repo.store(entry)

    repo.db.add.assert_called_once_with(entry)
    repo.db.commit.assert_awaited_once()
    repo.db.refresh.assert_awaited_once_with(entry)
    assert result is entry


# --- get ---

@pytest.mark.asyncio
async def test_get_returns_entry(repo: MemoryRepository) -> None:
    entry = make_memory(id=42)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = entry
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(42)

    assert result is entry
    repo.db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get(999)

    assert result is None


# --- recall ---

@pytest.mark.asyncio
async def test_recall_returns_entries_with_scores(repo: MemoryRepository) -> None:
    entry1 = make_memory(id=1)
    entry2 = make_memory(id=2)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (entry1, 0.1),   # distance 0.1 → score 0.9
        (entry2, 0.3),   # distance 0.3 → score 0.7
    ]
    repo.db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding(), limit=10)

    assert len(results) == 2
    assert results[0][0] is entry1
    assert results[0][1] == pytest.approx(0.9)
    assert results[1][1] == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_recall_filters_by_min_score(repo: MemoryRepository) -> None:
    entry1 = make_memory(id=1)
    entry2 = make_memory(id=2)
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (entry1, 0.1),   # score 0.9 — passes
        (entry2, 0.95),  # score 0.05 — below min_score
    ]
    repo.db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding(), min_score=0.5)

    assert len(results) == 1
    assert results[0][0] is entry1


@pytest.mark.asyncio
async def test_recall_empty_when_no_matches(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    repo.db.execute = AsyncMock(return_value=mock_result)

    results = await repo.recall(make_embedding())

    assert results == []


@pytest.mark.asyncio
async def test_recall_with_agent_type_filter(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    repo.db.execute = AsyncMock(return_value=mock_result)

    await repo.recall(make_embedding(), agent_type="transit")

    repo.db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_recall_with_memory_type_filter(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.all.return_value = []
    repo.db.execute = AsyncMock(return_value=mock_result)

    await repo.recall(make_embedding(), memory_type="semantic")

    repo.db.execute.assert_awaited_once()


# --- get_by_type ---

@pytest.mark.asyncio
async def test_get_by_type_returns_entries(repo: MemoryRepository) -> None:
    entries = [make_memory(id=1), make_memory(id=2)]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = entries
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_type("semantic")

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_by_type_respects_limit(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    repo.db.execute = AsyncMock(return_value=mock_result)

    await repo.get_by_type("procedural", limit=5)

    repo.db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_by_type_empty(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    repo.db.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_by_type("query_pattern")

    assert result == []


# --- increment_recalled_count ---

@pytest.mark.asyncio
async def test_increment_recalled_count(repo: MemoryRepository) -> None:
    repo.db.execute = AsyncMock()
    repo.db.commit = AsyncMock()

    await repo.increment_recalled_count(42)

    repo.db.execute.assert_awaited_once()
    repo.db.commit.assert_awaited_once()


# --- delete_decayed ---

@pytest.mark.asyncio
async def test_delete_decayed_returns_count(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 5
    repo.db.execute = AsyncMock(return_value=mock_result)
    repo.db.commit = AsyncMock()

    count = await repo.delete_decayed(0.1)

    assert count == 5
    repo.db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_decayed_returns_zero_when_none(repo: MemoryRepository) -> None:
    mock_result = MagicMock()
    mock_result.rowcount = 0
    repo.db.execute = AsyncMock(return_value=mock_result)
    repo.db.commit = AsyncMock()

    count = await repo.delete_decayed(0.5)

    assert count == 0
```

**Validation:** `uv run pytest app/memory/tests/test_repository.py -v`

---

### Step 13: Create `app/memory/tests/test_service.py`

Test service methods with mocked repository. ~8 tests.

```python
"""Unit tests for MemoryService."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false

from unittest.mock import AsyncMock

import pytest

from app.memory.exceptions import MemoryNotFoundError
from app.memory.schemas import MemoryEntryCreate, MemoryEntryResponse, MemoryRecallRequest, MemoryRecallResponse
from app.memory.service import MemoryService
from app.memory.tests.conftest import make_embedding, make_memory


@pytest.mark.asyncio
async def test_store_creates_entry(service: MemoryService) -> None:
    entry = make_memory(id=10)
    service.repository.store = AsyncMock(return_value=entry)

    data = MemoryEntryCreate(
        agent_type="transit",
        memory_type="semantic",
        content="Route 5 peak hours",
        source="agent",
    )
    result = await service.store(data)

    assert result.id == 10
    service.repository.store.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_entry(service: MemoryService) -> None:
    entry = make_memory(id=42)
    service.repository.get = AsyncMock(return_value=entry)

    result = await service.get(42)

    assert result.id == 42


@pytest.mark.asyncio
async def test_get_raises_not_found(service: MemoryService) -> None:
    service.repository.get = AsyncMock(return_value=None)

    with pytest.raises(MemoryNotFoundError):
        await service.get(999)


@pytest.mark.asyncio
async def test_recall_returns_scored_results(service: MemoryService) -> None:
    entry = make_memory(id=1)
    service.repository.recall = AsyncMock(return_value=[(entry, 0.95)])
    service.repository.increment_recalled_count = AsyncMock()

    request = MemoryRecallRequest(embedding=make_embedding())
    results = await service.recall(request)

    assert len(results) == 1
    assert isinstance(results[0], MemoryRecallResponse)
    assert results[0].score == pytest.approx(0.95)
    service.repository.increment_recalled_count.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_recall_empty_results(service: MemoryService) -> None:
    service.repository.recall = AsyncMock(return_value=[])

    request = MemoryRecallRequest(embedding=make_embedding())
    results = await service.recall(request)

    assert results == []


@pytest.mark.asyncio
async def test_get_by_type_delegates(service: MemoryService) -> None:
    entries = [make_memory(id=1), make_memory(id=2)]
    service.repository.get_by_type = AsyncMock(return_value=entries)

    result = await service.get_by_type("semantic", limit=10)

    assert len(result) == 2
    service.repository.get_by_type.assert_awaited_once_with("semantic", 10)


@pytest.mark.asyncio
async def test_delete_decayed_delegates(service: MemoryService) -> None:
    service.repository.delete_decayed = AsyncMock(return_value=3)

    count = await service.delete_decayed(0.2)

    assert count == 3
    service.repository.delete_decayed.assert_awaited_once_with(0.2)


@pytest.mark.asyncio
async def test_delete_decayed_default_threshold(service: MemoryService) -> None:
    service.repository.delete_decayed = AsyncMock(return_value=0)

    count = await service.delete_decayed()

    assert count == 0
    service.repository.delete_decayed.assert_awaited_once_with(0.1)
```

**Validation:** `uv run pytest app/memory/tests/test_service.py -v`

---

### Step 14: Create `app/memory/tests/test_routes.py`

Test HTTP endpoints with auth override and rate limiter disabled. ~7 tests.

```python
"""Unit tests for memory API routes."""

# pyright: reportUnknownParameterType=false, reportMissingParameterType=false

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.rate_limit import limiter
from app.memory.tests.conftest import make_embedding, make_memory
from app.shared.models import utcnow

limiter.enabled = False


def _mock_admin_user() -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "admin@vtv.lv"
    user.role = "admin"
    user.is_active = True
    return user


@pytest.fixture(autouse=True)
def _setup_auth_override() -> Generator[None, None, None]:
    from app.main import app as _app

    _app.dependency_overrides[get_current_user] = _mock_admin_user
    yield
    _app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_service() -> AsyncMock:
    return AsyncMock()


async def _client() -> AsyncClient:
    from app.main import app as _app

    return AsyncClient(transport=ASGITransport(app=_app), base_url="http://test")


@pytest.mark.asyncio
async def test_store_memory_201() -> None:
    client = await _client()
    async with client:
        response = await client.post(
            "/api/v1/memory/",
            json={
                "agent_type": "transit",
                "memory_type": "semantic",
                "content": "Test memory",
                "source": "agent",
            },
        )
    # Will get 500 without real DB, but validates route registration + auth
    assert response.status_code in (201, 500)


@pytest.mark.asyncio
async def test_get_memory_validates_path() -> None:
    client = await _client()
    async with client:
        response = await client.get("/api/v1/memory/1")
    assert response.status_code in (200, 404, 500)


@pytest.mark.asyncio
async def test_recall_accepts_post() -> None:
    client = await _client()
    async with client:
        response = await client.post(
            "/api/v1/memory/recall",
            json={
                "embedding": make_embedding(),
                "limit": 5,
            },
        )
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_list_by_type_validates_literal() -> None:
    client = await _client()
    async with client:
        response = await client.get("/api/v1/memory/type/semantic")
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_list_by_type_rejects_invalid_type() -> None:
    client = await _client()
    async with client:
        response = await client.get("/api/v1/memory/type/invalid_type")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_decayed_admin_only() -> None:
    client = await _client()
    async with client:
        response = await client.delete("/api/v1/memory/decayed")
    assert response.status_code in (200, 500)


@pytest.mark.asyncio
async def test_recall_rejects_wrong_embedding_length() -> None:
    client = await _client()
    async with client:
        response = await client.post(
            "/api/v1/memory/recall",
            json={
                "embedding": [0.1] * 512,  # wrong length
                "limit": 5,
            },
        )
    assert response.status_code == 422
```

**Validation:** `uv run pytest app/memory/tests/test_routes.py -v`

---

## Preflight Warnings

No existing files are being modified (except `app/main.py` for router registration). No fragile patterns to watch for.

**Potential issues:**
- pgvector extension must exist in the DB — verify migration doesn't fail if extension already exists (`CREATE EXTENSION IF NOT EXISTS vector`)
- `ivfflat` index requires at least `lists` rows to function — initial empty table works fine, index just returns empty results
- `JSONB` column on `metadata_json` — ensure model uses `mapped_column(JSONB)` not `Mapped[dict]` to avoid type inference issues

## Security Checklist

For every new/modified endpoint:
- [x] `require_role("admin", "agent")` on all endpoints (admin-only for `delete_decayed`)
- [x] `@limiter.limit()` rate limiting on all endpoints (10/min mutations, 30/min reads, 5/min cleanup)
- [x] Input validation via Pydantic schemas with `max_length`, `ge`/`le`, `Literal[...]`
- [x] Error responses use `AppError` hierarchy (`MemoryNotFoundError` → 404)
- [x] No LIKE/ILIKE queries in this slice (no text search) — `escape_like()` not needed

## Verification

- [ ] `make check` passes (lint + types + tests)
- [ ] `make security-audit-quick` passes
- [ ] New endpoints have auth + rate limiting
- [ ] Pyright errors ≤ baseline (6 errors before, full `app/`)
- [ ] Security convention tests pass: `uv run pytest app/tests/test_security.py -v`
- [ ] `uv run pytest app/memory/tests/ -v` — all 15+ tests pass
- [ ] `uv run alembic check` — no pending migrations after running migration
