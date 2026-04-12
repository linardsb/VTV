# pyright: reportCallIssue=false
"""Unit tests for API key authentication dependency."""

from unittest.mock import AsyncMock, patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.public_api.auth import get_api_key
from app.public_api.exceptions import (
    APIKeyRateLimitError,
    APIKeyRevokedError,
    InvalidAPIKeyError,
)
from app.public_api.tests.conftest import make_api_key


def _make_test_app() -> FastAPI:
    """Create a minimal FastAPI app with the get_api_key dependency for testing."""
    from app.core.exceptions import (
        api_key_error_handler,
        rate_limit_error_handler,
    )

    test_app = FastAPI()

    @test_app.get("/test")
    async def test_endpoint(api_key: object = depends_api_key) -> dict[str, str]:
        return {"status": "ok"}

    # Register handlers
    from typing import Any, cast

    test_app.add_exception_handler(InvalidAPIKeyError, cast(Any, api_key_error_handler))
    test_app.add_exception_handler(APIKeyRevokedError, cast(Any, api_key_error_handler))
    test_app.add_exception_handler(APIKeyRateLimitError, cast(Any, rate_limit_error_handler))

    return test_app


depends_api_key = Depends(get_api_key)


class TestGetApiKey:
    """Tests for the get_api_key FastAPI dependency."""

    def test_missing_header_returns_401(self) -> None:
        """Request without X-API-Key header returns 401."""
        app = _make_test_app()
        with TestClient(app) as client:
            resp = client.get("/test")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers
        assert resp.headers["WWW-Authenticate"] == "ApiKey"

    def test_invalid_key_returns_401(self) -> None:
        """Request with invalid API key returns 401."""
        app = _make_test_app()
        with (
            TestClient(app) as client,
            patch(
                "app.public_api.auth.PublicAPIService.validate_key",
                new_callable=AsyncMock,
                side_effect=InvalidAPIKeyError("Invalid API key"),
            ),
        ):
            resp = client.get("/test", headers={"X-API-Key": "vtv_pk_bad"})
        assert resp.status_code == 401

    def test_valid_key_returns_200(self) -> None:
        """Request with valid API key passes through to endpoint."""
        app = _make_test_app()
        key = make_api_key()
        with (
            TestClient(app) as client,
            patch(
                "app.public_api.auth.PublicAPIService.validate_key",
                new_callable=AsyncMock,
                return_value=key,
            ),
        ):
            resp = client.get("/test", headers={"X-API-Key": "vtv_pk_valid"})
        assert resp.status_code == 200

    def test_revoked_key_returns_401(self) -> None:
        """Request with revoked API key returns 401."""
        app = _make_test_app()
        with (
            TestClient(app) as client,
            patch(
                "app.public_api.auth.PublicAPIService.validate_key",
                new_callable=AsyncMock,
                side_effect=APIKeyRevokedError("API key has been revoked"),
            ),
        ):
            resp = client.get("/test", headers={"X-API-Key": "vtv_pk_revoked"})
        assert resp.status_code == 401

    def test_rate_limited_returns_429(self) -> None:
        """Request exceeding rate limit returns 429 with Retry-After."""
        # validate_key succeeds but get_api_key doesn't check rate limit
        # We need to raise from validate_key for this test since
        # rate limiting happens in routes, not in auth dependency.
        # Test the handler directly instead.
        from typing import Any, cast

        test_app = FastAPI()

        @test_app.get("/test")
        async def test_endpoint() -> dict[str, str]:
            raise APIKeyRateLimitError(retry_after=60)

        from app.core.exceptions import rate_limit_error_handler

        test_app.add_exception_handler(APIKeyRateLimitError, cast(Any, rate_limit_error_handler))

        with TestClient(test_app) as client:
            resp = client.get("/test")
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "60"
