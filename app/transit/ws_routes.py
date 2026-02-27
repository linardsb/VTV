# pyright: reportUnknownMemberType=false
"""WebSocket endpoint for real-time vehicle position streaming.

Authentication is via JWT query parameter since the browser WebSocket API
does not support custom headers. The token is validated using the same
decode_token + is_token_revoked logic as HTTP endpoints.
"""

import asyncio
import json

from fastapi import APIRouter, Query, WebSocket
from starlette.websockets import WebSocketDisconnect

from app.auth.token import decode_token, is_token_revoked
from app.core.config import get_settings
from app.core.logging import get_logger
from app.transit.ws_manager import ConnectionManager
from app.transit.ws_schemas import WsAck, WsError, WsSubscribeMessage

logger = get_logger(__name__)

ws_router = APIRouter()

# Module-level singleton
_ws_manager: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    """Get or create the WebSocket ConnectionManager singleton."""
    global _ws_manager
    if _ws_manager is None:
        settings = get_settings()
        _ws_manager = ConnectionManager(max_connections=settings.ws_max_connections)
    return _ws_manager


def close_ws_manager() -> None:
    """Reset the ConnectionManager singleton on shutdown."""
    global _ws_manager
    _ws_manager = None


async def _send_heartbeats(websocket: WebSocket, interval: int) -> None:
    """Send periodic application-level ping messages.

    Clients should respond with {"action": "pong"} to keep the connection alive.
    """
    try:
        while True:
            await asyncio.sleep(interval)
            await websocket.send_json({"type": "ping"})
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except Exception:
        # Heartbeat send failed — connection is broken, task exits
        return


@ws_router.websocket("/ws/transit/vehicles")
async def ws_vehicle_stream(
    websocket: WebSocket,
    token: str | None = Query(None),
) -> None:
    """WebSocket endpoint for live vehicle position streaming.

    Authentication: JWT token via ?token= query parameter.
    Protocol: JSON text messages for subscribe/unsubscribe/pong.
    """
    settings = get_settings()

    # --- Feature flag check ---
    if not settings.ws_enabled:
        await websocket.close(code=1013, reason="WebSocket streaming disabled")
        return

    # --- Authentication (manual, not via Depends) ---
    if token is None:
        await websocket.close(code=4001, reason="Authentication failed")
        logger.info("transit.ws.auth_failed", reason="missing_token")
        return

    payload = decode_token(token)
    if payload is None or payload.type != "access":
        await websocket.close(code=4001, reason="Authentication failed")
        logger.info("transit.ws.auth_failed", reason="invalid_token")
        return

    if await is_token_revoked(payload.jti):
        await websocket.close(code=4001, reason="Authentication failed")
        logger.info("transit.ws.auth_failed", reason="token_revoked", user_id=payload.sub)
        return

    # --- Connection setup (accept before registering to avoid broadcast to un-accepted socket) ---
    await websocket.accept()

    manager = get_ws_manager()
    if not await manager.connect(websocket, route_id=None, feed_id=None):
        await websocket.close(code=1013, reason="Try again later")
        return

    user_id = payload.sub
    logger.info("transit.ws.connected", user_id=user_id, active_count=manager.active_count)

    # Send initial ack
    ack = WsAck(action="connected", filters={"route_id": None, "feed_id": None})
    await websocket.send_json(ack.model_dump())

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(
        _send_heartbeats(websocket, settings.ws_heartbeat_interval_seconds)
    )

    # --- Message loop ---
    try:
        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                error_msg = WsError(code="parse_error", message="Invalid JSON")
                await websocket.send_json(error_msg.model_dump())
                continue

            action = data.get("action")

            if action == "subscribe":
                try:
                    msg = WsSubscribeMessage.model_validate(data)
                    manager.update_filters(websocket, msg.route_id, msg.feed_id)
                    sub_ack = WsAck(
                        action="subscribe",
                        filters={"route_id": msg.route_id, "feed_id": msg.feed_id},
                    )
                    await websocket.send_json(sub_ack.model_dump())
                    logger.info(
                        "transit.ws.subscribe_updated",
                        user_id=user_id,
                        route_id=msg.route_id,
                        feed_id=msg.feed_id,
                    )
                except Exception as e:
                    logger.warning(
                        "transit.ws.subscribe_validation_failed",
                        user_id=user_id,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    error_msg = WsError(
                        code="invalid_subscribe", message="Invalid subscribe message"
                    )
                    await websocket.send_json(error_msg.model_dump())

            elif action == "unsubscribe":
                manager.update_filters(websocket, route_id=None, feed_id=None)
                unsub_ack = WsAck(
                    action="unsubscribe",
                    filters={"route_id": None, "feed_id": None},
                )
                await websocket.send_json(unsub_ack.model_dump())
                logger.info(
                    "transit.ws.subscribe_updated", user_id=user_id, route_id=None, feed_id=None
                )

            elif action == "pong":
                # Client keepalive response to server ping — no action needed
                pass

            else:
                error_msg = WsError(
                    code="unknown_action",
                    message=f"Unknown action: {str(action)[:50]}",
                )
                await websocket.send_json(error_msg.model_dump())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(
            "transit.ws.unexpected_error",
            user_id=user_id,
            error=str(e),
            error_type=type(e).__name__,
        )
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket)
        logger.info(
            "transit.ws.disconnected",
            user_id=user_id,
            active_count=manager.active_count,
        )
