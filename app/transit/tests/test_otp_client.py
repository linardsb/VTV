# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
"""Unit tests for the OTP HTTP client (LV-3.3)."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.agents.exceptions import TransitDataError
from app.core.config import Settings
from app.transit.otp_client import OTPClient


def _make_settings() -> MagicMock:
    """Create a mock Settings object with OTP defaults."""
    s = MagicMock(spec=Settings)
    s.otp_base_url = "http://otp:8080"
    s.otp_router_id = "default"
    return s


def _make_otp_response(data: dict[str, object] | None = None) -> MagicMock:
    """Create a mock httpx Response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = data or {"plan": {"itineraries": []}}
    return resp


@pytest.mark.asyncio
async def test_plan_success() -> None:
    """OTP client returns parsed JSON on success."""
    http = AsyncMock(spec=httpx.AsyncClient)
    response = _make_otp_response({"plan": {"itineraries": [{"id": 1}]}})
    http.get.return_value = response

    client = OTPClient(http_client=http, settings=_make_settings())
    result = await client.plan({"fromPlace": "56.9,24.1", "toPlace": "56.8,24.0"})

    assert result["plan"]["itineraries"][0]["id"] == 1
    http.get.assert_awaited_once()
    call_args = http.get.call_args
    assert "otp/routers/default/plan" in call_args[0][0]


@pytest.mark.asyncio
async def test_plan_http_error() -> None:
    """OTP client raises TransitDataError on HTTP error."""
    http = AsyncMock(spec=httpx.AsyncClient)
    mock_request = MagicMock(spec=httpx.Request)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 500
    http.get.return_value = MagicMock()
    http.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error",
        request=mock_request,
        response=mock_response,
    )

    client = OTPClient(http_client=http, settings=_make_settings())
    with pytest.raises(TransitDataError, match="HTTP 500"):
        await client.plan({})


@pytest.mark.asyncio
async def test_plan_connection_error() -> None:
    """OTP client raises TransitDataError on connection failure."""
    http = AsyncMock(spec=httpx.AsyncClient)
    http.get.side_effect = httpx.ConnectError("Connection refused")

    client = OTPClient(http_client=http, settings=_make_settings())
    with pytest.raises(TransitDataError, match="connection failed"):
        await client.plan({})


@pytest.mark.asyncio
async def test_plan_timeout() -> None:
    """OTP client raises TransitDataError on timeout."""
    http = AsyncMock(spec=httpx.AsyncClient)
    http.get.side_effect = httpx.TimeoutException("timed out")

    client = OTPClient(http_client=http, settings=_make_settings())
    with pytest.raises(TransitDataError, match="connection failed"):
        await client.plan({})


@pytest.mark.asyncio
@patch("app.transit.otp_client.CircuitBreaker")
async def test_circuit_breaker_open(mock_breaker_cls: MagicMock) -> None:
    """OTP client raises TransitDataError when circuit is open."""
    from app.core.resilience import CircuitOpenError

    mock_breaker = MagicMock()
    mock_breaker.__aenter__ = AsyncMock(side_effect=CircuitOpenError("otp-planner", 30.0))
    mock_breaker.__aexit__ = AsyncMock(return_value=False)
    mock_breaker_cls.return_value = mock_breaker

    http = AsyncMock(spec=httpx.AsyncClient)
    settings = _make_settings()
    client = OTPClient(http_client=http, settings=settings)
    client._breaker = mock_breaker

    with pytest.raises(TransitDataError, match="failed"):
        await client.plan({})
