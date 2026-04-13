# pyright: reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportCallIssue=false
"""Unit tests for auth audit denial logging and query API (OPS-4.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.core.auth.audit import AuthAuditRepository, _sanitize_extra, emit_auth_denial
from app.core.rate_limit import limiter

limiter.enabled = False


def _mock_request() -> MagicMock:
    """Build a mock Request for audit tests."""
    mock = MagicMock(spec=Request)
    mock.url = MagicMock()
    mock.url.path = "/api/v1/test"
    mock.method = "GET"
    mock.client = MagicMock()
    mock.client.host = "10.0.0.1"
    return mock


# --- Denial event emission ---


class TestEmitAuthDenial:
    @pytest.mark.asyncio
    async def test_logs_structured_event(self) -> None:
        with capture_logs() as cap_logs:
            with patch("app.core.auth.audit.get_settings") as mock_gs:
                mock_gs.return_value.auth_audit_enabled = False
                await emit_auth_denial(
                    request=_mock_request(),
                    user_id=42,
                    status_code=401,
                    reason="token_invalid",
                    enforcement_layer="jwt",
                )

        events = [e for e in cap_logs if e.get("event") == "auth.audit.denied"]
        assert len(events) == 1
        evt = events[0]
        assert evt["user_id"] == 42
        assert evt["status_code"] == 401
        assert evt["reason"] == "token_invalid"
        assert evt["enforcement_layer"] == "jwt"

    @pytest.mark.asyncio
    async def test_disabled_skips_db_write(self) -> None:
        with patch("app.core.auth.audit.get_settings") as mock_gs:
            mock_gs.return_value.auth_audit_enabled = False
            with patch("app.core.auth.audit.asyncio") as mock_asyncio:
                await emit_auth_denial(
                    request=_mock_request(),
                    user_id=1,
                    status_code=401,
                    reason="test",
                    enforcement_layer="jwt",
                )
                mock_asyncio.create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_db_error_does_not_raise(self) -> None:
        with patch("app.core.auth.audit.get_db_context") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.commit = AsyncMock(side_effect=RuntimeError("DB down"))
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            from app.core.auth.audit import _persist_audit_event

            # Should not raise
            await _persist_audit_event(
                request_id="req-1",
                user_id=1,
                path="/test",
                method="GET",
                status_code=401,
                reason="test",
                enforcement_layer="jwt",
                client_ip="127.0.0.1",
                user_role=None,
                extra=None,
            )


# --- Repository ---


class TestAuthAuditRepository:
    @pytest.mark.asyncio
    async def test_insert_calls_add_and_flush(self) -> None:
        mock_db = AsyncMock()
        repo = AuthAuditRepository(mock_db)
        event = MagicMock()
        await repo.insert(event)
        mock_db.add.assert_called_once_with(event)
        mock_db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_count_returns_scalar(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_db.execute = AsyncMock(return_value=mock_result)

        repo = AuthAuditRepository(mock_db)
        result = await repo.count()
        assert result == 5


# --- PII redaction ---


class TestSanitizeExtra:
    def test_strips_password(self) -> None:
        result = _sanitize_extra({"password": "secret123", "user_role": "admin"})
        assert result is not None
        assert "password" not in result
        assert result["user_role"] == "admin"

    def test_strips_authorization(self) -> None:
        result = _sanitize_extra({"Authorization": "Bearer xyz", "path": "/test"})
        assert result is not None
        assert "Authorization" not in result
        assert result["path"] == "/test"

    def test_strips_token(self) -> None:
        result = _sanitize_extra({"token": "abc", "reason": "test"})
        assert result is not None
        assert "token" not in result

    def test_none_input(self) -> None:
        assert _sanitize_extra(None) is None


# --- Migration verification ---


class TestMigration:
    def test_retention_policy_in_migration(self) -> None:
        import pathlib

        migration = pathlib.Path(
            "alembic/versions/q1r2s3t4u5v6_add_auth_audit_events_hypertable.py"
        )
        content = migration.read_text()
        assert "add_retention_policy" in content
        assert "90 days" in content

    def test_composite_index_in_migration(self) -> None:
        import pathlib

        migration = pathlib.Path(
            "alembic/versions/q1r2s3t4u5v6_add_auth_audit_events_hypertable.py"
        )
        content = migration.read_text()
        assert "ix_auth_audit_events_user_time" in content
        assert "user_id" in content
        assert "recorded_at DESC" in content


# --- Admin endpoint role gate ---


class TestAuditEndpoint:
    def test_requires_admin_role(self, client: TestClient) -> None:
        """Dispatcher should get 403 on audit endpoint."""
        mock_user = MagicMock(spec=User)
        mock_user.id = 2
        mock_user.role = "dispatcher"
        mock_user.is_active = True

        from app.main import app

        original = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            response = client.get("/api/v1/admin/audit/auth")
            assert response.status_code == 403
        finally:
            app.dependency_overrides = original

    def test_admin_can_access(self, client: TestClient) -> None:
        """Admin should be able to query audit events."""
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.role = "admin"
        mock_user.is_active = True

        from app.main import app

        original = app.dependency_overrides.copy()
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            with patch.object(AuthAuditRepository, "count", new_callable=AsyncMock, return_value=0):
                with patch.object(
                    AuthAuditRepository, "list", new_callable=AsyncMock, return_value=[]
                ):
                    response = client.get("/api/v1/admin/audit/auth")
                    assert response.status_code == 200
                    data = response.json()
                    assert data["total"] == 0
                    assert data["items"] == []
        finally:
            app.dependency_overrides = original
