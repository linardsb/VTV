# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false
"""Tests for per-user rate limit bucketing (OPS-4.1).

Tests cover:
- User-or-IP key function logic
- Dynamic tier limit selection
- Sub-bucket key functions
- RateLimitIdentityMiddleware request.state population
- Fallback to IP on invalid/missing JWT
"""

from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request

from app.core.rate_limit import (
    _analytics_subbucket_key,
    _chat_subbucket_key,
    _dynamic_tier_limit,
    _user_or_ip_key,
)


def _make_request(
    *,
    user_id: int | None = None,
    role: str | None = None,
    client_host: str = "203.0.113.50",
) -> MagicMock:
    """Build a mock Request with optional rate-limit identity on state.

    Args:
        user_id: If set, populates request.state.rate_limit_user_id.
        role: If set, populates request.state.rate_limit_role.
        client_host: Client IP for fallback.

    Returns:
        A MagicMock with spec=Request.
    """
    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client = MagicMock()
    mock_request.client.host = client_host

    state = MagicMock()
    if user_id is not None:
        state.rate_limit_user_id = user_id
    else:
        del state.rate_limit_user_id
    if role is not None:
        state.rate_limit_role = role
    else:
        del state.rate_limit_role
    mock_request.state = state
    return mock_request


class TestUserOrIpKey:
    """Tests for _user_or_ip_key function."""

    def test_anonymous_ip_bucketing(self) -> None:
        """No auth -> key is ip:{remote_addr}:anonymous."""
        req = _make_request()
        key = _user_or_ip_key(req)
        assert key == "ip:203.0.113.50:anonymous"

    def test_authenticated_user_bucketing(self) -> None:
        """Valid JWT -> key is user:{user_id}:{role}."""
        req = _make_request(user_id=42, role="admin")
        key = _user_or_ip_key(req)
        assert key == "user:42:admin"

    def test_authenticated_different_users_separate_buckets(self) -> None:
        """Two users get independent bucket keys."""
        req1 = _make_request(user_id=1, role="viewer")
        req2 = _make_request(user_id=2, role="viewer")
        assert _user_or_ip_key(req1) != _user_or_ip_key(req2)

    def test_missing_role_defaults_to_anonymous(self) -> None:
        """User with no role attribute falls back to anonymous in key."""
        req = _make_request(user_id=99)
        key = _user_or_ip_key(req)
        assert key == "user:99:anonymous"


class TestDynamicTierLimit:
    """Tests for _dynamic_tier_limit function."""

    def test_tier_selection_admin(self) -> None:
        """Admin role -> 1000/minute limit."""
        result = _dynamic_tier_limit("user:42:admin")
        assert result == "1000/minute"

    def test_tier_selection_dispatcher(self) -> None:
        """Dispatcher role -> 300/minute limit."""
        result = _dynamic_tier_limit("user:5:dispatcher")
        assert result == "300/minute"

    def test_tier_selection_editor(self) -> None:
        """Editor role -> 100/minute limit."""
        result = _dynamic_tier_limit("user:10:editor")
        assert result == "100/minute"

    def test_tier_selection_viewer(self) -> None:
        """Viewer role -> 50/minute limit."""
        result = _dynamic_tier_limit("user:7:viewer")
        assert result == "50/minute"

    def test_anonymous_tier(self) -> None:
        """Anonymous IP key -> 30/minute limit."""
        result = _dynamic_tier_limit("ip:1.2.3.4:anonymous")
        assert result == "30/minute"

    def test_unknown_role_defaults_to_anonymous_tier(self) -> None:
        """Unrecognized role string -> anonymous tier limit."""
        result = _dynamic_tier_limit("user:99:superuser")
        assert result == "30/minute"


class TestSubBucketKeys:
    """Tests for sub-bucket key functions."""

    def test_chat_subbucket_key_authenticated(self) -> None:
        """Chat sub-bucket for authenticated user -> chat:user:{id}."""
        req = _make_request(user_id=42, role="admin")
        assert _chat_subbucket_key(req) == "chat:user:42"

    def test_chat_subbucket_key_anonymous(self) -> None:
        """Chat sub-bucket for anonymous -> chat:ip:{ip}."""
        req = _make_request()
        assert _chat_subbucket_key(req) == "chat:ip:203.0.113.50"

    def test_analytics_subbucket_key_authenticated(self) -> None:
        """Analytics sub-bucket for authenticated user -> analytics:user:{id}."""
        req = _make_request(user_id=7, role="viewer")
        assert _analytics_subbucket_key(req) == "analytics:user:7"

    def test_analytics_subbucket_key_anonymous(self) -> None:
        """Analytics sub-bucket for anonymous -> analytics:ip:{ip}."""
        req = _make_request()
        assert _analytics_subbucket_key(req) == "analytics:ip:203.0.113.50"


class TestMiddlewareIdentity:
    """Tests for RateLimitIdentityMiddleware request.state population."""

    @pytest.mark.anyio
    async def test_middleware_populates_request_state(self) -> None:
        """Middleware sets rate_limit_user_id and rate_limit_role on valid JWT."""
        import datetime

        from app.auth.token import TokenPayload
        from app.core.rate_limit import RateLimitIdentityMiddleware

        mock_payload = TokenPayload(
            sub=42,
            role="admin",
            exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
            type="access",
            jti="abc123",
        )

        captured_state: dict[str, object] = {}

        async def mock_app(scope: object, receive: object, send: object) -> None:
            _ = scope
            _ = receive
            _ = send

        middleware = RateLimitIdentityMiddleware(mock_app)

        async def fake_call_next(request: Request) -> MagicMock:
            captured_state["user_id"] = getattr(request.state, "rate_limit_user_id", None)
            captured_state["role"] = getattr(request.state, "rate_limit_role", None)
            return MagicMock()

        req = MagicMock(spec=Request)
        req.headers = {"authorization": "Bearer valid-token"}
        req.state = MagicMock()

        with patch("app.auth.token.decode_token", return_value=mock_payload):
            await middleware.dispatch(req, fake_call_next)

        assert captured_state["user_id"] == 42
        assert captured_state["role"] == "admin"

    @pytest.mark.anyio
    async def test_missing_auth_fallback_to_ip(self) -> None:
        """No auth header -> middleware does not set state attributes."""
        from app.core.rate_limit import RateLimitIdentityMiddleware

        async def mock_app(scope: object, receive: object, send: object) -> None:
            _ = scope
            _ = receive
            _ = send

        middleware = RateLimitIdentityMiddleware(mock_app)

        state_before: dict[str, bool] = {}

        async def fake_call_next(request: Request) -> MagicMock:
            state_before["has_user_id"] = hasattr(request.state, "rate_limit_user_id")
            return MagicMock()

        req = MagicMock(spec=Request)
        req.headers = {}
        req.state = MagicMock(spec=[])  # Empty spec - no attributes

        await middleware.dispatch(req, fake_call_next)
        assert not state_before.get("has_user_id", False)

    @pytest.mark.anyio
    async def test_invalid_jwt_fallback(self) -> None:
        """Invalid JWT -> middleware silently falls back, no state set."""
        from app.core.rate_limit import RateLimitIdentityMiddleware

        async def mock_app(scope: object, receive: object, send: object) -> None:
            _ = scope
            _ = receive
            _ = send

        middleware = RateLimitIdentityMiddleware(mock_app)
        state_set = False

        async def fake_call_next(request: Request) -> MagicMock:
            nonlocal state_set
            state_set = hasattr(request.state, "rate_limit_user_id")
            return MagicMock()

        req = MagicMock(spec=Request)
        req.headers = {"authorization": "Bearer invalid-garbage"}
        req.state = MagicMock(spec=[])

        with patch("app.auth.token.decode_token", return_value=None):
            await middleware.dispatch(req, fake_call_next)

        assert not state_set
