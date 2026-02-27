"""Tests for the WebSocket ConnectionManager."""

# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.transit.ws_manager import ConnectionManager


def _mock_websocket() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_connect_and_disconnect() -> None:
    """Connect increments count, disconnect decrements."""
    manager = ConnectionManager(max_connections=10)
    ws = _mock_websocket()

    result = await manager.connect(ws, route_id=None, feed_id=None)

    assert result is True
    assert manager.active_count == 1

    manager.disconnect(ws)
    assert manager.active_count == 0


@pytest.mark.asyncio
async def test_connect_respects_max_connections() -> None:
    """Third connection is rejected when max is 2."""
    manager = ConnectionManager(max_connections=2)
    ws1 = _mock_websocket()
    ws2 = _mock_websocket()
    ws3 = _mock_websocket()

    assert await manager.connect(ws1, route_id=None, feed_id=None) is True
    assert await manager.connect(ws2, route_id=None, feed_id=None) is True
    assert await manager.connect(ws3, route_id=None, feed_id=None) is False
    assert manager.active_count == 2


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_unfiltered_clients() -> None:
    """Unfiltered clients receive all broadcasts."""
    manager = ConnectionManager(max_connections=10)
    ws1 = _mock_websocket()
    ws2 = _mock_websocket()

    await manager.connect(ws1, route_id=None, feed_id=None)
    await manager.connect(ws2, route_id=None, feed_id=None)

    vehicles: list[dict[str, object]] = [
        {"vehicle_id": "v1", "route_id": "22"},
        {"vehicle_id": "v2", "route_id": "7"},
    ]
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:00Z")

    assert ws1.send_json.call_count == 1
    assert ws2.send_json.call_count == 1

    sent_data = ws1.send_json.call_args[0][0]
    assert sent_data["type"] == "vehicle_update"
    assert sent_data["feed_id"] == "riga"
    assert sent_data["count"] == 2


@pytest.mark.asyncio
async def test_broadcast_filters_by_feed_id() -> None:
    """Client with feed filter only receives matching feed."""
    manager = ConnectionManager(max_connections=10)
    ws_riga = _mock_websocket()
    ws_jurmala = _mock_websocket()

    await manager.connect(ws_riga, route_id=None, feed_id="riga")
    await manager.connect(ws_jurmala, route_id=None, feed_id="jurmala")

    vehicles: list[dict[str, object]] = [{"vehicle_id": "v1", "route_id": "22"}]
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:00Z")

    assert ws_riga.send_json.call_count == 1
    assert ws_jurmala.send_json.call_count == 0


@pytest.mark.asyncio
async def test_broadcast_filters_by_route_id() -> None:
    """Client with route filter only receives matching route vehicles."""
    manager = ConnectionManager(max_connections=10)
    ws = _mock_websocket()

    await manager.connect(ws, route_id="22", feed_id=None)

    vehicles: list[dict[str, object]] = [
        {"vehicle_id": "v1", "route_id": "22"},
        {"vehicle_id": "v2", "route_id": "7"},
        {"vehicle_id": "v3", "route_id": "22"},
    ]
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:00Z")

    assert ws.send_json.call_count == 1
    sent_data = ws.send_json.call_args[0][0]
    assert sent_data["count"] == 2  # Only route 22 vehicles
    assert len(sent_data["vehicles"]) == 2


@pytest.mark.asyncio
async def test_broadcast_handles_disconnected_client() -> None:
    """Disconnected client is removed; other clients still receive."""
    from starlette.websockets import WebSocketDisconnect

    manager = ConnectionManager(max_connections=10)
    ws_bad = _mock_websocket()
    ws_good = _mock_websocket()

    ws_bad.send_json = AsyncMock(side_effect=WebSocketDisconnect())

    await manager.connect(ws_bad, route_id=None, feed_id=None)
    await manager.connect(ws_good, route_id=None, feed_id=None)

    vehicles: list[dict[str, object]] = [{"vehicle_id": "v1", "route_id": "22"}]
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:00Z")

    # ws_good got the message
    assert ws_good.send_json.call_count == 1
    # ws_bad was removed
    assert manager.active_count == 1


@pytest.mark.asyncio
async def test_update_filters() -> None:
    """Updating filters changes what client receives."""
    manager = ConnectionManager(max_connections=10)
    ws = _mock_websocket()

    await manager.connect(ws, route_id=None, feed_id=None)

    vehicles: list[dict[str, object]] = [
        {"vehicle_id": "v1", "route_id": "22"},
        {"vehicle_id": "v2", "route_id": "7"},
    ]

    # Initially no filter — gets all
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:00Z")
    sent1 = ws.send_json.call_args[0][0]
    assert sent1["count"] == 2

    # Update to filter route 22 only
    manager.update_filters(ws, route_id="22", feed_id=None)
    await manager.broadcast("riga", vehicles, "2026-01-01T00:00:01Z")
    sent2 = ws.send_json.call_args[0][0]
    assert sent2["count"] == 1
