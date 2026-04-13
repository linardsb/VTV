"""Type stubs for google.transit.gtfs_realtime_pb2.

Covers only the attributes used by app/core/agents/tools/transit/client.py.
Scalar fields use non-optional types because protobuf always returns defaults
for unset fields (0 for int, "" for str, 0.0 for float).
"""

from google.protobuf.internal.containers import RepeatedCompositeFieldContainer
from google.protobuf.message import Message

class FeedHeader(Message):
    gtfs_realtime_version: str
    timestamp: int

class Translation(Message):
    text: str

class TranslatedString(Message):
    translation: RepeatedCompositeFieldContainer[Translation]

class Position(Message):
    latitude: float
    longitude: float
    bearing: float
    speed: float

class VehicleDescriptor(Message):
    id: str
    label: str

class TripDescriptor(Message):
    trip_id: str
    route_id: str

class StopTimeEvent(Message):
    delay: int
    time: int

class StopTimeUpdate(Message):
    stop_sequence: int
    stop_id: str
    arrival: StopTimeEvent
    departure: StopTimeEvent

class VehiclePosition(Message):
    vehicle: VehicleDescriptor
    trip: TripDescriptor
    position: Position
    current_stop_sequence: int
    current_status: int
    stop_id: str
    timestamp: int

class TripUpdate(Message):
    trip: TripDescriptor
    vehicle: VehicleDescriptor
    stop_time_update: RepeatedCompositeFieldContainer[StopTimeUpdate]
    timestamp: int

class EntitySelector(Message):
    route_id: str
    stop_id: str

class Alert(Message):
    header_text: TranslatedString
    description_text: TranslatedString
    cause: int
    effect: int
    informed_entity: RepeatedCompositeFieldContainer[EntitySelector]

class FeedEntity(Message):
    id: str
    vehicle: VehiclePosition
    trip_update: TripUpdate
    alert: Alert

class FeedMessage(Message):
    header: FeedHeader
    entity: RepeatedCompositeFieldContainer[FeedEntity]
