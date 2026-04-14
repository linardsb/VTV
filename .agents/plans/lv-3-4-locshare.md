# Plan: LV-3.4 Shareable Tracking Links (LocShare)

## Context

Passengers and operations staff need "where is my bus?" links they can share without VTV accounts. LocShare generates signed JWT tracking links with configurable expiry (1h-24h) and QR codes for physical posting at stops. Public-facing equivalent of the internal `/map`.

## Security Context Assessment

| Context | Active | Reason |
|---------|--------|--------|
| CTX-AUTH | **Yes** | JWT signing/validation for share tokens (separate from user auth) |
| CTX-RBAC | **Yes** | POST create requires admin/dispatcher; GET is public |
| CTX-INPUT | **Yes** | Token path param validation, expiry_hours constraint |
| CTX-INFRA | No | No Docker/nginx changes |
| CTX-FILE | No | No file uploads |
| CTX-AGENT | No | No agent tools |

## Research Summary

**Reference pattern:** LV-3.1 Phone Assignments in `app/transit/` — same module, same router, similar CRUD endpoints.

**JWT library:** `python-jose` (imported as `from jose import jwt`) — already used for auth tokens in `app/auth/token.py:8`. Share link tokens use the same library but with a `"share"` type claim and `vehicle_id` as subject.

**PyJWT:** Also available (`pyjwt>=2.12.0`), but jose is the established pattern. Use jose for consistency.

**QR code:** `qrcode` not in `pyproject.toml` — needs adding. `qrcode[pil]>=8.0` with Pillow (already a dependency).

**Public endpoint pattern:** `get_gtfs_rt_vehicle_positions` at `routes.py:243-261` — no auth dependency, `@limiter.limit("60/minute")`, added to `PUBLIC_ALLOWLIST` in `test_security.py:718`.

**Vehicle position fetching:** `TransitService.get_vehicle_positions()` in `service.py:60-99` — returns `VehiclePositionsResponse` with list of `VehiclePosition`. Filter by vehicle_id client-side (no direct single-vehicle lookup exists).

**Migration pattern:** `t4u5v6w7x8y9_add_vehicle_phone_assignments.py` — down_revision `s3t4u5v6w7x8`.

## Test Landscape

- Transit tests in `app/transit/tests/` — 23 files
- Auth override pattern: `app.dependency_overrides[get_current_user] = _mock_admin_user` in fixture
- Rate limiter disabled at module level: `limiter.enabled = False`
- Public endpoint: no auth override, added to `PUBLIC_ALLOWLIST`
- Service mocking: `@patch("app.transit.routes.get_transit_service")` with `AsyncMock`
- Factory pattern: inline `_make_response()` helpers with `VehiclePosition` construction

## Type Check Baseline

| Tool | Errors | Source files |
|------|--------|--------------|
| Pyright | **0** | 50 |
| Mypy | **0** | 50 |

Target: 0 new errors after implementation.

## Files to Create/Modify

| Action | File | Purpose |
|--------|------|---------|
| CREATE | `app/transit/locshare.py` | JWT sign/verify, QR generation, share link logic |
| CREATE | `alembic/versions/u5v6w7x8y9z0_add_share_links.py` | `share_links` table migration |
| UPDATE | `app/transit/models.py` | `ShareLink` ORM model |
| UPDATE | `app/transit/schemas.py` | Request/response schemas |
| UPDATE | `app/transit/routes.py` | Two new endpoints |
| UPDATE | `app/core/config.py` | `share_link_secret_key`, `share_link_max_expiry_hours` settings |
| UPDATE | `pyproject.toml` | Add `qrcode[pil]>=8.0` dependency |
| UPDATE | `.env.example` | Document new env vars |
| CREATE | `app/transit/tests/test_locshare.py` | Unit tests for JWT + QR logic |
| CREATE | `app/transit/tests/test_share_routes.py` | Route handler tests |
| UPDATE | `app/tests/test_security.py` | Add `resolve_share_link` to `PUBLIC_ALLOWLIST` |

## Implementation Steps

### Step 1: Add `qrcode` dependency

**File:** `pyproject.toml`

Add `"qrcode[pil]>=8.0"` to `dependencies` array. Then run `uv lock`.

**Validation:** `uv lock --check`

### Step 2: Add config settings

**File:** `app/core/config.py`

Add to `Settings` class (near JWT settings ~line 162):
```python
# Share links (LV-3.4)
share_link_secret_key: str | None = None  # Falls back to jwt_secret_key
share_link_max_expiry_hours: int = 24
share_link_default_expiry_hours: int = 1
```

Add `@computed_field` or use validator to default `share_link_secret_key` to `jwt_secret_key`.

**File:** `.env.example`

Add:
```
# Share links (LV-3.4)
# SHARE_LINK_SECRET_KEY=  # Defaults to JWT_SECRET_KEY if unset
# SHARE_LINK_MAX_EXPIRY_HOURS=24
```

**Validation:** `uv run ruff check app/core/config.py && uv run pyright app/core/config.py`

### Step 3: Create `ShareLink` model

**File:** `app/transit/models.py`

Append after `VehiclePhoneAssignment`:

```python
class ShareLink(Base, TimestampMixin):
    """A shareable tracking link for a single vehicle position (LV-3.4)."""

    __tablename__ = "share_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    vehicle_id: Mapped[str] = mapped_column(String(100), nullable=False)
    route_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    feed_id: Mapped[str] = mapped_column(String(50), nullable=False, server_default="riga")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
```

Notes:
- `token_hash` = SHA-256 of the JWT (never store raw token)
- `vehicle_id` is `str` — matches GTFS-RT `vehicle.id` (not DB FK)
- `route_id` is `str | None` — matches GTFS-RT `route_id`
- `view_count` tracks access count

**Validation:** `uv run pyright app/transit/models.py`

### Step 4: Create schemas

**File:** `app/transit/schemas.py`

Append after `PhoneAssignmentResponse`:

```python
# ── Share Link schemas (LV-3.4) ───────────────────────────────────

ShareLinkExpiryHours: TypeAlias = Literal[1, 2, 4, 6, 12, 24]

class ShareLinkCreate(BaseModel):
    """Request body for creating a shareable tracking link."""
    vehicle_id: str = Field(..., max_length=100, pattern=r"^[\w\-.:]+$")
    route_id: str | None = Field(None, max_length=50, pattern=r"^[\w\-]+$")
    feed_id: str = Field("riga", max_length=50, pattern=r"^[\w\-]+$")
    expiry_hours: ShareLinkExpiryHours = 1

class ShareLinkResponse(BaseModel):
    """Response after creating a share link."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    token: str  # The raw JWT (only returned at creation time)
    share_url: str  # Full URL: /share/{token}
    qr_code_base64: str  # Base64-encoded PNG
    vehicle_id: str
    route_id: str | None
    feed_id: str
    expires_at: datetime.datetime
    created_at: datetime.datetime

class ShareLinkData(BaseModel):
    """Public response when resolving a share link."""
    vehicle_id: str
    route_id: str | None
    feed_id: str
    position: VehiclePosition | None  # None if vehicle has no current data
    expires_at: datetime.datetime
    share_link_id: int
```

Import `TypeAlias` from `typing`, `Literal` from `typing`.

**Validation:** `uv run pyright app/transit/schemas.py`

### Step 5: Create `locshare.py` — JWT + QR logic

**File:** `app/transit/locshare.py` (CREATE)

```python
"""Shareable tracking link JWT signing, verification, and QR code generation (LV-3.4)."""

import base64
import datetime
import hashlib
import io
import uuid
from typing import Any

import qrcode  # type: ignore[import-untyped]  # noqa: ...
from jose import JWTError, jwt  # pyright: ignore[reportMissingTypeStubs]
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShareTokenPayload(BaseModel):
    """Decoded share link JWT claims."""
    sub: str  # vehicle_id
    route_id: str | None
    feed_id: str
    exp: datetime.datetime
    type: str  # "share"
    jti: str


def create_share_token(
    vehicle_id: str,
    route_id: str | None,
    feed_id: str,
    expiry_hours: int,
) -> tuple[str, str]:
    """Sign a share link JWT. Returns (token, token_hash)."""
    settings = get_settings()
    secret = settings.share_link_secret_key or settings.jwt_secret_key
    expire = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=expiry_hours)
    jti = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": vehicle_id,
        "route_id": route_id,
        "feed_id": feed_id,
        "exp": expire,
        "type": "share",
        "jti": jti,
    }
    token: str = jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def decode_share_token(token: str) -> ShareTokenPayload | None:
    """Decode and validate a share link JWT. Returns None if invalid/expired."""
    settings = get_settings()
    secret = settings.share_link_secret_key or settings.jwt_secret_key
    try:
        data = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
        )
        if data.get("type") != "share":
            logger.warning("transit.share_link.invalid_type", token_type=data.get("type"))
            return None
        return ShareTokenPayload(**data)
    except JWTError:
        return None


def generate_qr_code_base64(url: str) -> str:
    """Generate a QR code PNG as a base64 string."""
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def hash_token(token: str) -> str:
    """SHA-256 hash of a token for DB storage."""
    return hashlib.sha256(token.encode()).hexdigest()
```

Add mypy override for `qrcode` in `pyproject.toml` `[[tool.mypy.overrides]]`:
```toml
[[tool.mypy.overrides]]
module = "qrcode.*"
ignore_missing_imports = true
```

Add pyright file-level directive at top of `locshare.py`:
```python
# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false
```

**Validation:** `uv run ruff check app/transit/locshare.py && uv run pyright app/transit/locshare.py && uv run mypy app/transit/locshare.py`

### Step 6: Create migration

**File:** `alembic/versions/u5v6w7x8y9z0_add_share_links.py` (CREATE)

```python
"""Add share_links table (LV-3.4).

Revision ID: u5v6w7x8y9z0
Revises: t4u5v6w7x8y9
Create Date: 2026-04-13
"""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "u5v6w7x8y9z0"
down_revision: str | None = "t4u5v6w7x8y9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("vehicle_id", sa.String(100), nullable=False),
        sa.Column("route_id", sa.String(50), nullable=True),
        sa.Column("feed_id", sa.String(50), nullable=False, server_default="riga"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_share_links_token_hash", "share_links", ["token_hash"])
    op.create_index("ix_share_links_expires_at", "share_links", ["expires_at"])

def downgrade() -> None:
    op.drop_index("ix_share_links_expires_at")
    op.drop_index("ix_share_links_token_hash")
    op.drop_table("share_links")
```

**Validation:** `uv run ruff check alembic/versions/u5v6w7x8y9z0_add_share_links.py`

### Step 7: Add route endpoints

**File:** `app/transit/routes.py`

Add imports at top:
```python
from app.transit.locshare import create_share_token, decode_share_token, generate_qr_code_base64, hash_token
from app.transit.models import ShareLink  # add to existing import
from app.transit.schemas import ShareLinkCreate, ShareLinkData, ShareLinkResponse  # add to existing
```

Append after phone assignment endpoints (after line 363):

```python
# ── Share Link endpoints (LV-3.4) ─────────────────────────────────


@router.post(
    "/share",
    response_model=ShareLinkResponse,
    status_code=201,
)
@limiter.limit("30/minute")
async def create_share_link(
    request: Request,
    body: ShareLinkCreate,
    db: AsyncSession = Depends(get_db),  # noqa: B008
    current_user: User = Depends(  # noqa: B008
        require_role("admin", "dispatcher")  # noqa: B008
    ),
) -> ShareLinkResponse:
    """Create a shareable vehicle tracking link with QR code."""
    _ = request
    settings = get_settings()

    # Clamp expiry to server max
    max_hours = settings.share_link_max_expiry_hours
    expiry_hours = min(body.expiry_hours, max_hours)

    logger.info(
        "transit.share_link.create_started",
        vehicle_id=body.vehicle_id,
        expiry_hours=expiry_hours,
    )

    token, token_hash = create_share_token(
        vehicle_id=body.vehicle_id,
        route_id=body.route_id,
        feed_id=body.feed_id,
        expiry_hours=expiry_hours,
    )

    link = ShareLink(
        token_hash=token_hash,
        vehicle_id=body.vehicle_id,
        route_id=body.route_id,
        feed_id=body.feed_id,
        created_by=current_user.id,
        expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=expiry_hours),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    share_url = f"/share/{token}"
    qr_base64 = generate_qr_code_base64(share_url)

    logger.info(
        "transit.share_link.create_completed",
        share_link_id=link.id,
        vehicle_id=body.vehicle_id,
    )

    return ShareLinkResponse(
        id=link.id,
        token=token,
        share_url=share_url,
        qr_code_base64=qr_base64,
        vehicle_id=link.vehicle_id,
        route_id=link.route_id,
        feed_id=link.feed_id,
        expires_at=link.expires_at,
        created_at=link.created_at,
    )


@router.get("/share/{token}")
@limiter.limit("60/minute")
async def resolve_share_link(
    request: Request,
    token: str = Path(max_length=2048),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> ShareLinkData:
    """Resolve a share link token to vehicle position data.

    Public endpoint — no authentication required. Returns 410 Gone for
    expired links, 404 for invalid tokens.
    """
    _ = request

    # Decode JWT
    payload = decode_share_token(token)
    if payload is None:
        logger.info("transit.share_link.resolve_invalid_token")
        raise HTTPException(status_code=404, detail="Share link not found")

    # Verify link exists and is active in DB
    th = hash_token(token)
    result = await db.execute(
        select(ShareLink).where(
            ShareLink.token_hash == th,
            ShareLink.is_active.is_(True),
        )
    )
    link = result.scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=404, detail="Share link not found")

    # Check expiry (JWT already checks, but double-check DB)
    if link.expires_at < datetime.datetime.now(datetime.UTC):
        logger.info("transit.share_link.resolve_expired", share_link_id=link.id)
        raise HTTPException(status_code=410, detail="Share link has expired")

    # Increment view count (fire-and-forget, don't fail on error)
    try:
        link.view_count += 1
        await db.commit()
    except Exception:
        logger.warning("transit.share_link.view_count_increment_failed", share_link_id=link.id)
        await db.rollback()

    # Fetch current vehicle position
    from app.transit.service import get_transit_service

    service = get_transit_service()
    positions = await service.get_vehicle_positions(
        route_id=payload.route_id, feed_id=payload.feed_id
    )
    vehicle_pos = next(
        (v for v in positions.vehicles if v.vehicle_id == payload.sub), None
    )

    return ShareLinkData(
        vehicle_id=payload.sub,
        route_id=payload.route_id,
        feed_id=payload.feed_id,
        position=vehicle_pos,
        expires_at=link.expires_at,
        share_link_id=link.id,
    )
```

Add `import datetime` if not already at top (check — currently `import datetime as dt`, so use `dt` consistently or add standard `datetime`). The existing file uses `import datetime as dt` at line 11, so use `dt.datetime`, `dt.timedelta`, `dt.UTC`.

**Validation:** `uv run ruff check app/transit/routes.py && uv run pyright app/transit/routes.py`

### Step 8: Update security convention tests

**File:** `app/tests/test_security.py`

Add `"resolve_share_link"` to `PUBLIC_ALLOWLIST` (line ~718):
```python
PUBLIC_ALLOWLIST: ClassVar[set[str]] = {
    "login",
    "refresh_token",
    "read_root",
    "health_check",
    "database_health_check",
    "health_redis",
    "readiness_check",
    "ws_vehicle_stream",
    "traccar_webhook",
    "get_gtfs_rt_vehicle_positions",
    "resolve_share_link",  # LV-3.4: public share link resolution
}
```

**Validation:** `uv run pytest app/tests/test_security.py::TestAllEndpointsRequireAuth -v`

### Step 9: Create route tests

**File:** `app/transit/tests/test_share_routes.py` (CREATE)

Tests to write:
1. `test_create_share_link_success` — POST with admin user, verify 201 + response shape
2. `test_create_share_link_unauthorized_role` — viewer gets 403
3. `test_create_share_link_unauthenticated` — no auth gets 401
4. `test_resolve_share_link_success` — GET with valid token, verify position data
5. `test_resolve_share_link_invalid_token` — garbage token → 404
6. `test_resolve_share_link_expired` — expired JWT → 404 (JWT decode fails)
7. `test_resolve_share_link_expired_in_db` — valid JWT but DB says expired → 410
8. `test_resolve_share_link_deactivated` — `is_active=False` → 404
9. `test_resolve_share_link_vehicle_not_found` — valid link but no position → response with `position: null`
10. `test_resolve_share_link_increments_view_count` — verify view_count incremented

Mock patterns:
- Auth: `app.dependency_overrides[get_current_user]` fixture
- DB: `_FakeDBSession` or `@patch` on `db.execute`
- Transit service: `@patch("app.transit.routes.get_transit_service")`
- Share token: `@patch("app.transit.routes.decode_share_token")`
- Disable limiter: `limiter.enabled = False` at module level

**Validation:** `uv run pytest app/transit/tests/test_share_routes.py -v`

### Step 10: Create locshare unit tests

**File:** `app/transit/tests/test_locshare.py` (CREATE)

Tests to write:
1. `test_create_share_token_returns_valid_jwt` — sign + decode round-trip
2. `test_create_share_token_hash_is_sha256` — verify hash length = 64 hex chars
3. `test_decode_share_token_valid` — decode a freshly signed token
4. `test_decode_share_token_expired` — token with past expiry → None
5. `test_decode_share_token_wrong_type` — access token (type="access") → None
6. `test_decode_share_token_tampered` — modified token → None
7. `test_generate_qr_code_base64_valid_png` — decode base64, verify PNG magic bytes
8. `test_generate_qr_code_base64_encodes_url` — verify QR contains the URL
9. `test_hash_token_deterministic` — same input → same output
10. `test_hash_token_different_inputs` — different tokens → different hashes

Mock `get_settings()` to provide test JWT secret.

**Validation:** `uv run pytest app/transit/tests/test_locshare.py -v`

### Step 11: Update `pyproject.toml` mypy overrides

**File:** `pyproject.toml`

Add to `[[tool.mypy.overrides]]` section:
```toml
[[tool.mypy.overrides]]
module = "qrcode.*"
ignore_missing_imports = true
```

**Validation:** `uv run mypy app/transit/locshare.py`

### Step 12: Run `uv lock` to sync lockfile

```bash
uv lock
```

**Validation:** `uv lock --check`

## Preflight Warnings

- `app/transit/routes.py` uses `import datetime as dt` (line 11) — new code must use `dt.datetime`, `dt.timedelta`, `dt.UTC` consistently
- Phone assignment endpoints do inline DB queries in routes (no repository layer) — follow same pattern for share links
- `VehiclePosition` schema uses `str` for vehicle_id, route_id — share link fields must match (not int FK)
- `PUBLIC_ALLOWLIST` uses function names, not URL paths — add `"resolve_share_link"` not `"/share/{token}"`
- QR code `qrcode.make()` returns an untyped `StyledPilImage` — need pyright suppression
- The `view_count += 1` pattern on a detached ORM object needs a fresh query or `await db.refresh(link)` before increment

## Security Checklist

- [x] POST `/share` uses `require_role("admin", "dispatcher")`
- [x] POST `/share` has `@limiter.limit("30/minute")`
- [x] GET `/share/{token}` is public but rate-limited (`60/minute`)
- [x] GET `/share/{token}` added to `PUBLIC_ALLOWLIST`
- [x] Token stored as SHA-256 hash, never raw JWT in DB
- [x] Token not logged in plaintext (only `share_link_id` logged)
- [x] JWT secret from config (not hardcoded)
- [x] Expiry clamped to server max (`share_link_max_expiry_hours`)
- [x] `vehicle_id` input validated via regex pattern `^[\w\-.:]+$`
- [x] Token path param has `max_length=2048`
- [x] 410 Gone for expired (not 404, so clients can distinguish)
- [x] View count update wrapped in try/except (anti-pattern #50)
- [x] `share_link_secret_key` defaults to `jwt_secret_key` but can be rotated independently

## Verification

- [ ] `uv run ruff format app/transit/ && uv run ruff check --fix app/transit/` — 0 errors
- [ ] `uv run pyright app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run mypy app/transit/` — 0 errors (baseline: 0)
- [ ] `uv run pytest app/transit/tests/test_locshare.py app/transit/tests/test_share_routes.py -v` — all pass
- [ ] `uv run pytest app/tests/test_security.py::TestAllEndpointsRequireAuth -v` — passes with new allowlist entry
- [ ] `make check` passes (full suite)
- [ ] `make security-audit-quick` passes
