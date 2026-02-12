# VSA Patterns for VTV

Async-adapted Vertical Slice Architecture patterns for VTV's FastAPI + PostgreSQL stack. All patterns use async SQLAlchemy 2.0 with `select()` syntax matching `app/core/database.py`.

---

## Feature Slice Structure

Every feature follows this layout under `app/{feature}/`:

```
app/{feature}/
├── __init__.py
├── models.py          # SQLAlchemy models (inherit Base + TimestampMixin)
├── schemas.py         # Pydantic request/response models
├── repository.py      # Async database operations
├── service.py         # Business logic + structured logging
├── exceptions.py      # Feature-specific exceptions
├── routes.py          # FastAPI endpoints
├── tests/
│   ├── __init__.py
│   ├── conftest.py    # Feature-specific fixtures
│   ├── test_service.py
│   └── test_routes.py
└── README.md          # Feature documentation (see reference/feature-readme-template.md)
```

**Not every feature needs every file.** Start with schemas, service, and routes. Add repository + models when you need a database. Add exceptions when you need custom error handling.

**Creation order:** schemas → models → repository → service → exceptions → routes → tests

---

## Async Repository Pattern

Repositories handle all database operations. They receive an `AsyncSession` and use `select()` (never `.query()`).

```python
# {feature}/repository.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.{feature}.models import Thing
from app.{feature}.schemas import ThingCreate, ThingUpdate


class ThingRepository:
    """Data access layer for things."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, thing_id: int) -> Thing | None:
        """Get thing by ID."""
        result = await self.db.execute(select(Thing).where(Thing.id == thing_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Thing | None:
        """Get thing by unique slug."""
        result = await self.db.execute(select(Thing).where(Thing.slug == slug))
        return result.scalar_one_or_none()

    async def list(
        self, *, offset: int = 0, limit: int = 100, active_only: bool = True
    ) -> list[Thing]:
        """List things with pagination."""
        query = select(Thing)
        if active_only:
            query = query.where(Thing.is_active.is_(True))
        result = await self.db.execute(query.offset(offset).limit(limit))
        return list(result.scalars().all())

    async def create(self, data: ThingCreate) -> Thing:
        """Create a new thing."""
        thing = Thing(**data.model_dump())
        self.db.add(thing)
        await self.db.commit()
        await self.db.refresh(thing)
        return thing

    async def update(self, thing: Thing, data: ThingUpdate) -> Thing:
        """Update an existing thing."""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(thing, field, value)
        await self.db.commit()
        await self.db.refresh(thing)
        return thing
```

**Key conventions:**
- Constructor takes `AsyncSession` — same session shared across repositories in a request
- All methods are `async` — use `await` for every database call
- Use `select()` + `scalar_one_or_none()` for single results
- Use `scalars().all()` for lists
- Repository commits its own transactions (simple case); for cross-feature orchestration, see below

---

## Async Service Pattern

Services contain business logic. They create repositories, apply business rules, and handle structured logging.

```python
# {feature}/service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.{feature}.exceptions import ThingNotFoundError, ThingAlreadyExistsError
from app.{feature}.repository import ThingRepository
from app.{feature}.schemas import ThingCreate, ThingResponse

logger = get_logger(__name__)


class ThingService:
    """Business logic for things."""

    def __init__(self, db: AsyncSession) -> None:
        self.repository = ThingRepository(db)

    async def get_thing(self, thing_id: int) -> ThingResponse:
        """Get a thing by ID."""
        logger.info("thing.fetch_started", thing_id=thing_id)

        thing = await self.repository.get(thing_id)
        if not thing:
            logger.warning("thing.fetch_failed", thing_id=thing_id, reason="not_found")
            raise ThingNotFoundError(f"Thing {thing_id} not found")

        return ThingResponse.model_validate(thing)

    async def create_thing(self, data: ThingCreate) -> ThingResponse:
        """Create a new thing."""
        logger.info("thing.create_started", slug=data.slug)

        existing = await self.repository.get_by_slug(data.slug)
        if existing:
            logger.warning("thing.create_failed", slug=data.slug, reason="duplicate")
            raise ThingAlreadyExistsError(f"Thing with slug {data.slug} already exists")

        thing = await self.repository.create(data)
        logger.info("thing.create_completed", thing_id=thing.id, slug=thing.slug)

        return ThingResponse.model_validate(thing)
```

**Logging conventions:**
- Format: `{feature}.{action}_{state}` (e.g., `thing.create_started`, `thing.create_completed`)
- States: `_started`, `_completed`, `_failed`, `_validated`, `_rejected`
- Always include identifiers (IDs, slugs) as structured kwargs
- On failure: include `reason=` for expected failures, `exc_info=True` for unexpected exceptions

---

## Feature Exceptions Pattern

Feature exceptions inherit from `app.core.exceptions` base classes so the global handler maps them to HTTP status codes automatically.

```python
# {feature}/exceptions.py
from app.core.exceptions import DatabaseError, NotFoundError, ValidationError


class ThingError(DatabaseError):
    """Base exception for thing-related errors."""
    pass


class ThingNotFoundError(NotFoundError):
    """Raised when a thing is not found."""
    pass


class ThingAlreadyExistsError(ValidationError):
    """Raised when creating a thing that already exists."""
    pass
```

**Why inherit from core exceptions:** The global handler in `app/main.py` already maps `NotFoundError → 404`, `ValidationError → 422`, `DatabaseError → 500`. Feature exceptions get HTTP status codes for free.

---

## Async Routes Pattern

Routes are thin — they wire up dependencies, call the service, and handle HTTP concerns.

```python
# {feature}/routes.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.{feature}.schemas import ThingCreate, ThingResponse
from app.{feature}.service import ThingService

router = APIRouter(prefix="/{feature}", tags=["{feature}"])


def get_service(db: AsyncSession = Depends(get_db)) -> ThingService:
    """Dependency to get ThingService instance."""
    return ThingService(db)


@router.post("/", response_model=ThingResponse, status_code=status.HTTP_201_CREATED)
async def create_thing(
    data: ThingCreate,
    service: ThingService = Depends(get_service),
) -> ThingResponse:
    """Create a new thing."""
    return await service.create_thing(data)


@router.get("/{thing_id}", response_model=ThingResponse)
async def get_thing(
    thing_id: int,
    service: ThingService = Depends(get_service),
) -> ThingResponse:
    """Get a thing by ID."""
    return await service.get_thing(thing_id)
```

**Key conventions:**
- `get_service()` dependency creates the service with the request-scoped session
- Routes are `async def` — they await service methods
- No try/except in routes — let feature exceptions bubble to the global handler
- Return type annotations match `response_model`

**Wiring into main.py:**
```python
# In app/main.py, add:
from app.{feature}.routes import router as {feature}_router
app.include_router({feature}_router)
```

---

## Cross-Feature Orchestration

When a service needs data from another feature, it imports that feature's **repository** (not service). All repositories share the same async session = single transaction.

```python
# orders/service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.products.repository import ProductRepository
from app.inventory.repository import InventoryRepository
from app.orders.repository import OrderRepository
from app.orders.exceptions import InsufficientInventoryError
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrderService:
    """Orchestrates order creation across multiple features."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.products = ProductRepository(db)    # Same session
        self.inventory = InventoryRepository(db)  # Same session
        self.orders = OrderRepository(db)          # Same session

    async def create_order(self, data: OrderCreate) -> OrderResponse:
        """Create order spanning multiple features in one transaction."""
        logger.info("order.create_started", item_count=len(data.items))

        for item in data.items:
            product = await self.products.get(item.product_id)
            if not product:
                raise ProductNotFoundError(f"Product {item.product_id} not found")

            available = await self.inventory.check_availability(product.sku, item.quantity)
            if not available:
                raise InsufficientInventoryError(f"Not enough stock for {product.sku}")

            await self.inventory.reserve(product.sku, item.quantity)

        order = await self.orders.create(data)
        await self.db.commit()

        logger.info("order.create_completed", order_id=order.id)
        return OrderResponse.model_validate(order)
```

**Cross-feature rules:**
1. **Read** from other features' repositories freely
2. **Never write** to another feature's tables directly — use that feature's repository methods
3. **Document dependencies** in both feature READMEs
4. All repositories share the same `AsyncSession` — one commit = one transaction

---

## Agent Module Structure

VTV's primary feature is a Pydantic AI agent. This follows the feature slice pattern but with a `tools/` subdirectory for agent tools.

```
app/agent/
├── __init__.py
├── routes.py          # /v1/chat/completions, /v1/models
├── service.py         # Agent orchestration, model building
├── schemas.py         # OpenAI-compatible request/response schemas
├── config.py          # LLM provider settings (model names, tokens, timeouts)
├── exceptions.py      # Agent-specific exceptions
├── tools/
│   ├── __init__.py
│   ├── transit/       # 5 read-only transit tools (stops, routes, schedules, etc.)
│   └── obsidian/      # 4 vault tools (search, read, create, patch)
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_service.py
    └── test_routes.py
```

**Why `config.py` separate from `core/config.py`:** LLM settings (model names, token limits, provider keys) are agent-specific, not universal infrastructure. They belong with the feature.

**Tool organization:** Tools are grouped by domain (transit, obsidian) under `tools/`. Each tool module contains the tool function and its docstring optimized for LLM selection (see CLAUDE.md "Tool Docstrings for Agents").

---

## Model Pattern

Models inherit from both `Base` (from core) and `TimestampMixin` (from shared). Use SQLAlchemy 2.0 `Mapped[]` annotations for type safety.

```python
# {feature}/models.py
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.shared.models import TimestampMixin


class Thing(Base, TimestampMixin):
    """Thing database model."""

    __tablename__ = "things"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
```

**After creating/modifying models:**
1. `uv run alembic revision --autogenerate -m "add things table"`
2. Review the generated migration in `alembic/versions/`
3. `uv run alembic upgrade head`

---

## Schema Pattern

```python
# {feature}/schemas.py
from datetime import datetime
from pydantic import BaseModel, Field


class ThingBase(BaseModel):
    """Shared thing attributes."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=50)
    description: str | None = None


class ThingCreate(ThingBase):
    """Schema for creating a thing."""
    pass


class ThingUpdate(BaseModel):
    """Schema for updating a thing (all fields optional)."""
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class ThingResponse(ThingBase):
    """Schema for thing responses."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

---

## Three-Feature Rule

1. **First feature:** Write the code inline in the feature
2. **Second feature:** Duplicate it (add `# NOTE: duplicated from {other_feature}`)
3. **Third feature:** Extract to `app/shared/` and refactor all three to use it

Current shared utilities (already extracted): `TimestampMixin`, `PaginationParams`, `PaginatedResponse`, `ErrorResponse`, `utcnow()`.
