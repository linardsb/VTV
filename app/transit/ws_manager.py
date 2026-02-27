"""WebSocket connection manager for real-time vehicle position streaming.

Tracks active WebSocket connections with per-client subscription filters
and handles fan-out broadcasting of vehicle position updates.
"""

from dataclasses import dataclass

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.core.logging import get_logger
from app.transit.ws_schemas import WsVehicleUpdate

logger = get_logger(__name__)


@dataclass
class _ClientSubscription:
    """Internal tracking of a WebSocket client and its filters."""

    websocket: WebSocket
    route_id: str | None
    feed_id: str | None


class ConnectionManager:
    """Manages WebSocket connections and broadcasts vehicle updates.

    Each connection has optional route_id and feed_id filters.
    Broadcast checks filters before sending to each client.
    Thread-safe via asyncio single event loop (no locks needed).

    Args:
        max_connections: Hard cap on concurrent WebSocket connections.
    """

    def __init__(self, max_connections: int) -> None:
        self._max_connections = max_connections
        self._clients: dict[int, _ClientSubscription] = {}

    async def connect(
        self,
        websocket: WebSocket,
        route_id: str | None,
        feed_id: str | None,
    ) -> bool:
        """Register a new WebSocket connection.

        Returns False if max_connections limit is reached.
        """
        if len(self._clients) >= self._max_connections:
            logger.warning(
                "transit.ws.connection_limit_reached",
                max_connections=self._max_connections,
                active_count=len(self._clients),
            )
            return False

        self._clients[id(websocket)] = _ClientSubscription(
            websocket=websocket,
            route_id=route_id,
            feed_id=feed_id,
        )
        return True

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from tracking."""
        ws_id = id(websocket)
        if ws_id in self._clients:
            del self._clients[ws_id]

    def update_filters(
        self,
        websocket: WebSocket,
        route_id: str | None,
        feed_id: str | None,
    ) -> None:
        """Update subscription filters for an existing connection."""
        ws_id = id(websocket)
        if ws_id in self._clients:
            self._clients[ws_id].route_id = route_id
            self._clients[ws_id].feed_id = feed_id

    async def broadcast(
        self,
        feed_id: str,
        vehicles: list[dict[str, object]],
        timestamp: str,
    ) -> None:
        """Send vehicle update to all matching clients.

        Match logic:
        - Client matches feed if client.feed_id is None OR client.feed_id == feed_id
        - Client matches route if client.route_id is None (all routes)
          OR vehicle["route_id"] matches client.route_id
        """
        disconnected: list[int] = []

        for ws_id, sub in self._clients.items():
            # Feed filter
            if sub.feed_id is not None and sub.feed_id != feed_id:
                continue

            # Route filter: narrow vehicle list if client has a route filter
            if sub.route_id is not None:
                filtered = [v for v in vehicles if v.get("route_id") == sub.route_id]
            else:
                filtered = vehicles

            if not filtered:
                continue

            update = WsVehicleUpdate(
                feed_id=feed_id,
                count=len(filtered),
                vehicles=filtered,
                timestamp=timestamp,
            )

            try:
                await sub.websocket.send_json(update.model_dump())
            except WebSocketDisconnect:
                disconnected.append(ws_id)
                logger.info(
                    "transit.ws.broadcast_client_disconnected",
                    ws_id=ws_id,
                )
            except Exception as e:
                disconnected.append(ws_id)
                logger.warning(
                    "transit.ws.broadcast_client_error",
                    ws_id=ws_id,
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Clean up disconnected clients
        for ws_id in disconnected:
            if ws_id in self._clients:
                del self._clients[ws_id]

        if self._clients:
            logger.debug(
                "transit.ws.broadcast_completed",
                feed_id=feed_id,
                client_count=len(self._clients),
                vehicle_count=len(vehicles),
            )

    @property
    def active_count(self) -> int:
        """Number of active connections."""
        return len(self._clients)
