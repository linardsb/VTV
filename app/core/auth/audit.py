"""Auth denial audit helper and repository (OPS-4.3).

Emits structured log events and persists authorization denials to a
TimescaleDB hypertable for compliance audit trails.
"""

import asyncio
import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.core.auth.models import AuthAuditEvent
from app.core.config import get_settings
from app.core.database import get_db_context
from app.core.logging import get_logger, get_request_id

logger = get_logger(__name__)

# Keys that must never appear in audit event ``extra`` dict
_PII_KEYS = frozenset({"password", "token", "authorization", "cookie", "secret", "api_key"})


class AuthAuditRepository:
    """Repository for auth audit event persistence and queries."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def insert(self, event: AuthAuditEvent) -> None:
        """Persist a single audit event."""
        self._db.add(event)
        await self._db.flush()

    async def list(
        self,
        *,
        user_id: int | None = None,
        from_date: datetime.datetime | None = None,
        to_date: datetime.datetime | None = None,
        enforcement_layer: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[AuthAuditEvent]:
        """Query audit events with optional filters."""
        stmt = select(AuthAuditEvent).order_by(AuthAuditEvent.recorded_at.desc())
        stmt = self._apply_filters(
            stmt,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            enforcement_layer=enforcement_layer,
        )
        stmt = stmt.offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count(
        self,
        *,
        user_id: int | None = None,
        from_date: datetime.datetime | None = None,
        to_date: datetime.datetime | None = None,
        enforcement_layer: str | None = None,
    ) -> int:
        """Count audit events matching filters."""
        stmt = select(func.count(AuthAuditEvent.id))
        stmt = self._apply_filters(
            stmt,
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
            enforcement_layer=enforcement_layer,
        )
        result = await self._db.execute(stmt)
        return int(result.scalar_one())

    @staticmethod
    def _apply_filters(
        stmt: Any,  # noqa: ANN401
        *,
        user_id: int | None,
        from_date: datetime.datetime | None,
        to_date: datetime.datetime | None,
        enforcement_layer: str | None,
    ) -> Any:  # noqa: ANN401
        """Apply common filters to a query statement."""
        if user_id is not None:
            stmt = stmt.where(AuthAuditEvent.user_id == user_id)
        if from_date is not None:
            stmt = stmt.where(AuthAuditEvent.recorded_at >= from_date)
        if to_date is not None:
            stmt = stmt.where(AuthAuditEvent.recorded_at <= to_date)
        if enforcement_layer is not None:
            stmt = stmt.where(AuthAuditEvent.enforcement_layer == enforcement_layer)
        return stmt


def _sanitize_extra(extra: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip PII keys from extra dict before persistence."""
    if extra is None:
        return None
    return {k: v for k, v in extra.items() if k.lower() not in _PII_KEYS}


def _extract_request_context(request: Request | None) -> dict[str, str | None]:
    """Extract request metadata for the audit event."""
    if request is None:
        return {
            "request_id": get_request_id() or "unknown",
            "path": "unknown",
            "method": "unknown",
            "client_ip": None,
        }
    client_ip: str | None = None
    if request.client is not None:
        client_ip = request.client.host
    return {
        "request_id": get_request_id() or "unknown",
        "path": str(request.url.path),
        "method": request.method,
        "client_ip": client_ip,
    }


async def _persist_audit_event(
    *,
    request_id: str,
    user_id: int | None,
    path: str,
    method: str,
    status_code: int,
    reason: str,
    enforcement_layer: str,
    client_ip: str | None,
    user_role: str | None,
    extra: dict[str, Any] | None,
) -> None:
    """Fire-and-forget DB write. Exceptions are logged, never raised."""
    try:
        async with get_db_context() as db:
            event = AuthAuditEvent(
                request_id=request_id,
                user_id=user_id,
                path=path,
                method=method,
                status_code=status_code,
                reason=reason,
                enforcement_layer=enforcement_layer,
                client_ip=client_ip,
                user_role=user_role,
                extra=extra,
            )
            db.add(event)
            await db.commit()
    except Exception:
        logger.debug("auth.audit.persist_failed", exc_info=True)


async def emit_auth_denial(
    *,
    request: Request | None,
    user_id: int | None,
    status_code: int,
    reason: str,
    enforcement_layer: str,
    user_role: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a structured auth denial log and optionally persist to DB.

    Always emits a structured log event. When ``auth_audit_enabled`` is
    True, also fires a background task to persist the event to the audit
    hypertable. The DB write is fire-and-forget — failures are logged
    but never propagated.
    """
    ctx = _extract_request_context(request)
    sanitized_extra = _sanitize_extra(extra)

    logger.warning(
        "auth.audit.denied",
        request_id=ctx["request_id"],
        user_id=user_id,
        path=ctx["path"],
        method=ctx["method"],
        status_code=status_code,
        reason=reason,
        enforcement_layer=enforcement_layer,
    )

    settings = get_settings()
    if not settings.auth_audit_enabled:
        return

    _task = asyncio.create_task(
        _persist_audit_event(
            request_id=ctx["request_id"] or "unknown",
            user_id=user_id,
            path=ctx["path"] or "unknown",
            method=ctx["method"] or "unknown",
            status_code=status_code,
            reason=reason,
            enforcement_layer=enforcement_layer,
            client_ip=ctx["client_ip"],
            user_role=user_role,
            extra=sanitized_extra,
        )
    )
    _ = _task  # fire-and-forget; reference kept to avoid GC
