"""Check raw GTFS-RT protobuf feed to see what fields are populated."""

import urllib.request

# Download the protobuf feed
url = "https://saraksti.rigassatiksme.lv/vehicle_positions.pb"
req = urllib.request.Request(url)  # noqa: S310
with urllib.request.urlopen(req) as resp:  # noqa: S310
    raw = resp.read()

# Parse with gtfs-realtime-bindings
try:
    from google.transit import gtfs_realtime_pb2
except ImportError:
    print("Installing gtfs-realtime-bindings...")
    import subprocess

    subprocess.check_call(["pip3", "install", "gtfs-realtime-bindings"])  # noqa: S607
    from google.transit import gtfs_realtime_pb2

feed = gtfs_realtime_pb2.FeedMessage()
feed.ParseFromString(raw)

print(f"Feed has {len(feed.entity)} entities")
print(f"Timestamp: {feed.header.timestamp}")
print()

count = 0
for entity in feed.entity:
    if not entity.HasField("vehicle"):
        continue
    vp = entity.vehicle
    vehicle_id = vp.vehicle.id if vp.HasField("vehicle") else "NONE"
    has_trip = vp.HasField("trip")
    trip_id = vp.trip.trip_id if has_trip else "NO_TRIP"
    route_id = vp.trip.route_id if has_trip else "NO_TRIP"
    label = vp.vehicle.label if vp.HasField("vehicle") else ""

    print(
        f"vehicle_id={vehicle_id!r}  label={label!r}  trip_id={trip_id!r}  route_id={route_id!r}  lat={vp.position.latitude:.4f}"
    )
    count += 1
    if count >= 10:
        break
