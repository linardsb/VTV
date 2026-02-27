# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Background task that subscribes to Redis Pub/Sub and dispatches to WebSocket clients.

Subscribes to transit:vehicles:* channels and fans out vehicle position
updates to all connected WebSocket clients via the ConnectionManager.
"""

import asyncio
import json

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.transit.ws_manager import ConnectionManager

logger = get_logger(__name__)

_subscriber_task: asyncio.Task[None] | None = None

MAX_BACKOFF_SECONDS = 30


async def _subscribe_loop(manager: ConnectionManager) -> None:
    """Subscribe to Redis Pub/Sub channels and dispatch updates."""
    backoff = 1.0

    pubsub = None
    while True:
        try:
            redis_client = await get_redis()
            pubsub = redis_client.pubsub()
            await pubsub.psubscribe("transit:vehicles:*")
            logger.info("transit.ws.subscriber_started")
            backoff = 1.0  # Reset backoff on successful connection

            async for message in pubsub.listen():
                if message["type"] != "pmessage":
                    continue

                try:
                    data = json.loads(message["data"])
                    feed_id: str = data["feed_id"]
                    vehicles: list[dict[str, object]] = data["vehicles"]
                    timestamp: str = data["timestamp"]
                    await manager.broadcast(feed_id, vehicles, timestamp)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning(
                        "transit.ws.subscriber_message_parse_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                    )

        except asyncio.CancelledError:
            # Graceful shutdown
            if pubsub is not None:
                try:
                    await pubsub.punsubscribe("transit:vehicles:*")
                    await pubsub.aclose()  # type: ignore[no-untyped-call]
                except Exception:
                    logger.warning("transit.ws.subscriber_cleanup_error", exc_info=True)
            logger.info("transit.ws.subscriber_stopped")
            return

        except Exception as e:
            logger.warning(
                "transit.ws.subscriber_reconnecting",
                error=str(e),
                error_type=type(e).__name__,
                backoff_seconds=backoff,
            )
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


async def start_ws_subscriber(manager: ConnectionManager) -> asyncio.Task[None]:
    """Create and return the subscriber background task."""
    global _subscriber_task
    _subscriber_task = asyncio.create_task(_subscribe_loop(manager))
    return _subscriber_task


async def stop_ws_subscriber() -> None:
    """Cancel the subscriber task and wait for cleanup."""
    global _subscriber_task
    if _subscriber_task is not None:
        _subscriber_task.cancel()
        try:
            await _subscriber_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("transit.ws.subscriber_stop_error", exc_info=True)
        _subscriber_task = None
