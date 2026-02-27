"""Tests for the WebSocket vehicle streaming endpoint."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportArgumentType=false

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.token import TokenPayload
from app.main import app


def _valid_token_payload() -> TokenPayload:
    return TokenPayload(
        sub=1,
        role="admin",
        exp=datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
        type="access",
        jti="test-jti-123",
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ws_connect_without_token_rejected(client: TestClient) -> None:
    """Connection without token query param is rejected."""
    with pytest.raises(Exception):  # noqa: B017
        with client.websocket_connect("/ws/transit/vehicles"):
            pass


def test_ws_connect_with_invalid_token_rejected(client: TestClient) -> None:
    """Connection with invalid token is rejected."""
    with patch("app.transit.ws_routes.decode_token", return_value=None):
        with pytest.raises(Exception):  # noqa: B017
            with client.websocket_connect("/ws/transit/vehicles?token=invalid"):
                pass


@patch("app.transit.ws_routes.is_token_revoked", new_callable=AsyncMock, return_value=False)
@patch("app.transit.ws_routes.decode_token")
def test_ws_connect_with_valid_token_accepted(
    mock_decode: AsyncMock,
    mock_revoked: AsyncMock,
    client: TestClient,
) -> None:
    """Valid token leads to accepted connection and ack message."""
    mock_decode.return_value = _valid_token_payload()

    with client.websocket_connect("/ws/transit/vehicles?token=valid-jwt") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "ack"
        assert msg["action"] == "connected"
        assert "route_id" in msg["filters"]


@patch("app.transit.ws_routes.is_token_revoked", new_callable=AsyncMock, return_value=False)
@patch("app.transit.ws_routes.decode_token")
def test_ws_subscribe_updates_filters(
    mock_decode: AsyncMock,
    mock_revoked: AsyncMock,
    client: TestClient,
) -> None:
    """Subscribe message updates filters and returns ack."""
    mock_decode.return_value = _valid_token_payload()

    with client.websocket_connect("/ws/transit/vehicles?token=valid-jwt") as ws:
        # Read initial ack
        ws.receive_json()
        # Send subscribe
        ws.send_json({"action": "subscribe", "route_id": "22", "feed_id": "riga"})
        msg = ws.receive_json()
        assert msg["type"] == "ack"
        assert msg["action"] == "subscribe"
        assert msg["filters"]["route_id"] == "22"
        assert msg["filters"]["feed_id"] == "riga"


@patch("app.transit.ws_routes.is_token_revoked", new_callable=AsyncMock, return_value=False)
@patch("app.transit.ws_routes.decode_token")
def test_ws_unsubscribe_resets_filters(
    mock_decode: AsyncMock,
    mock_revoked: AsyncMock,
    client: TestClient,
) -> None:
    """Unsubscribe resets filters to None."""
    mock_decode.return_value = _valid_token_payload()

    with client.websocket_connect("/ws/transit/vehicles?token=valid-jwt") as ws:
        ws.receive_json()  # initial ack
        ws.send_json({"action": "subscribe", "route_id": "22"})
        ws.receive_json()  # subscribe ack
        ws.send_json({"action": "unsubscribe"})
        msg = ws.receive_json()
        assert msg["type"] == "ack"
        assert msg["action"] == "unsubscribe"
        assert msg["filters"]["route_id"] is None


@patch("app.transit.ws_routes.is_token_revoked", new_callable=AsyncMock, return_value=False)
@patch("app.transit.ws_routes.decode_token")
def test_ws_unknown_action_returns_error(
    mock_decode: AsyncMock,
    mock_revoked: AsyncMock,
    client: TestClient,
) -> None:
    """Unknown action returns error message."""
    mock_decode.return_value = _valid_token_payload()

    with client.websocket_connect("/ws/transit/vehicles?token=valid-jwt") as ws:
        ws.receive_json()  # initial ack
        ws.send_json({"action": "unknown"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "unknown_action"


@patch("app.transit.ws_routes.is_token_revoked", new_callable=AsyncMock, return_value=False)
@patch("app.transit.ws_routes.decode_token")
def test_ws_invalid_json_returns_error(
    mock_decode: AsyncMock,
    mock_revoked: AsyncMock,
    client: TestClient,
) -> None:
    """Non-JSON text returns parse error."""
    mock_decode.return_value = _valid_token_payload()

    with client.websocket_connect("/ws/transit/vehicles?token=valid-jwt") as ws:
        ws.receive_json()  # initial ack
        ws.send_text("not-json{{{")
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert msg["code"] == "parse_error"
