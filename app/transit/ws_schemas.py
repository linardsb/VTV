"""Pydantic schemas for WebSocket vehicle position streaming.

These define the bidirectional message protocol:
- Client -> Server: subscribe/unsubscribe with optional filters
- Server -> Client: vehicle position updates, errors, acknowledgements
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class WsSubscribeMessage(BaseModel):
    """Client request to subscribe to vehicle position updates.

    Attributes:
        action: Must be "subscribe".
        route_id: Optional route filter (e.g., "22"). None = all routes.
        feed_id: Optional feed filter (e.g., "riga"). None = all feeds.
    """

    model_config = ConfigDict(strict=True)

    action: Literal["subscribe"]
    route_id: str | None = None
    feed_id: str | None = None


class WsUnsubscribeMessage(BaseModel):
    """Client request to unsubscribe from updates.

    Attributes:
        action: Must be "unsubscribe".
    """

    model_config = ConfigDict(strict=True)

    action: Literal["unsubscribe"]


class WsVehicleUpdate(BaseModel):
    """Server push of vehicle position data.

    Attributes:
        type: Message type discriminator.
        feed_id: Which feed this update is from.
        count: Number of vehicles in this update.
        vehicles: List of vehicle position dicts (same shape as REST VehiclePosition).
        timestamp: ISO 8601 server time when update was assembled.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["vehicle_update"] = "vehicle_update"
    feed_id: str
    count: int
    vehicles: list[dict[str, object]]
    timestamp: str


class WsError(BaseModel):
    """Server error message sent to client.

    Attributes:
        type: Message type discriminator.
        code: Machine-readable error code.
        message: Human-readable error description.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["error"] = "error"
    code: str
    message: str


class WsAck(BaseModel):
    """Server acknowledgement of client action.

    Attributes:
        type: Message type discriminator.
        action: Which client action was acknowledged.
        filters: Currently active filters after the action.
    """

    model_config = ConfigDict(strict=True)

    type: Literal["ack"] = "ack"
    action: Literal["connected", "subscribe", "unsubscribe"]
    filters: dict[str, str | None]
