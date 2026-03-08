"""Check what vehicle data the transit API returns (run on server or locally)."""

import json
import urllib.request

BASE = "http://204.168.156.137"

# Login
req = urllib.request.Request(  # noqa: S310
    f"{BASE}/api/v1/auth/login",
    data=json.dumps({"email": "admin@vtv.lv", "password": "admin"}).encode(),
    method="POST",
)
req.add_header("Content-Type", "application/json")
with urllib.request.urlopen(req) as resp:  # noqa: S310
    token = json.loads(resp.read())["access_token"]

# Fetch vehicles
req2 = urllib.request.Request(f"{BASE}/api/v1/transit/vehicles/")  # noqa: S310
req2.add_header("Authorization", f"Bearer {token}")
with urllib.request.urlopen(req2) as resp:  # noqa: S310
    data = json.loads(resp.read())

print(f"Total vehicles: {data.get('count', 0)}")
print(f"{'route_id':<15} {'route_short_name':<20} {'trip_id':<25}")
print("-" * 60)
for v in data.get("vehicles", [])[:10]:
    print(
        f"{v.get('route_id', 'EMPTY'):<15} {v.get('route_short_name', 'EMPTY'):<20} {v.get('trip_id', 'EMPTY'):<25}"
    )
