"""Update vehicle statuses on production for realistic analytics data."""

import json
import urllib.request

BASE = "http://204.168.156.137"


def api_call(method: str, path: str, data: dict | None = None, token: str = "") -> dict | None:
    url = f"{BASE}{path}"
    if not url.startswith(("http://", "https://")):
        raise ValueError(f"Invalid URL scheme: {url}")
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)  # noqa: S310
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read()) if resp.status == 200 else None
    except urllib.error.HTTPError as e:
        # Follow 307 redirects
        if e.code == 307:
            location = e.headers.get("Location", "")
            if location:
                return api_call(method, location.replace(BASE, ""), data, token)
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None


def main() -> None:
    # Login
    result = api_call("POST", "/api/v1/auth/login", {"email": "admin@vtv.lv", "password": "admin"})
    if not result:
        print("Login failed")
        return
    token = result["access_token"]
    print("Logged in")

    # Get all vehicles
    vehicles = api_call("GET", "/api/v1/vehicles/", token=token)
    if not vehicles or "items" not in vehicles:
        print("No vehicles found")
        return

    items = vehicles["items"]
    print(f"Found {len(items)} vehicles")

    # Set realistic mix: 3 inactive, 2 maintenance, rest active
    updates = []
    for i, v in enumerate(items):
        vid = v["id"]
        name = v.get("fleet_number", vid)
        if i in (3, 7, 12):  # 3 vehicles inactive
            updates.append((vid, name, "inactive"))
        elif i in (5, 15):  # 2 vehicles in maintenance
            updates.append((vid, name, "maintenance"))

    for vid, name, status in updates:
        result = api_call("PATCH", f"/api/v1/vehicles/{vid}", {"status": status}, token=token)
        if result:
            print(f"  {name} → {status}")
        else:
            print(f"  Failed: {name} → {status}")

    print("\nDone! Refresh the analytics page to see updated data.")


if __name__ == "__main__":
    main()
