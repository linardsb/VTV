"""Seed demo drivers and vehicles for production deployment."""
import json
import sys
import urllib.request

BASE = "http://localhost:8123"

DRIVERS = [
    {"first_name": "Jānis", "last_name": "Bērziņš", "employee_number": "D001", "phone": "+371 20000001", "email": "janis.b@rs.lv", "default_shift": "morning", "status": "on_duty", "license_categories": "D,D1", "license_expiry_date": "2027-06-15", "medical_cert_expiry": "2026-12-01", "hire_date": "2018-03-10"},
    {"first_name": "Andris", "last_name": "Kalniņš", "employee_number": "D002", "phone": "+371 20000002", "email": "andris.k@rs.lv", "default_shift": "morning", "status": "on_duty", "license_categories": "D,DE", "license_expiry_date": "2028-01-20", "medical_cert_expiry": "2027-03-15", "hire_date": "2019-07-01"},
    {"first_name": "Māris", "last_name": "Liepiņš", "employee_number": "D003", "phone": "+371 20000003", "email": "maris.l@rs.lv", "default_shift": "afternoon", "status": "on_duty", "license_categories": "D", "license_expiry_date": "2027-09-30", "medical_cert_expiry": "2026-11-20", "hire_date": "2020-01-15"},
    {"first_name": "Pēteris", "last_name": "Ozoliņš", "employee_number": "D004", "phone": "+371 20000004", "email": "peteris.o@rs.lv", "default_shift": "afternoon", "status": "available", "license_categories": "D,D1", "license_expiry_date": "2028-04-10", "medical_cert_expiry": "2027-06-30", "hire_date": "2017-11-22"},
    {"first_name": "Aigars", "last_name": "Sproģis", "employee_number": "D005", "phone": "+371 20000005", "email": "aigars.s@rs.lv", "default_shift": "evening", "status": "on_duty", "license_categories": "D,DE", "license_expiry_date": "2027-12-01", "medical_cert_expiry": "2027-01-15", "hire_date": "2021-05-03"},
    {"first_name": "Ivars", "last_name": "Vītols", "employee_number": "D006", "phone": "+371 20000006", "email": "ivars.v@rs.lv", "default_shift": "morning", "status": "on_duty", "license_categories": "D", "license_expiry_date": "2028-02-28", "medical_cert_expiry": "2027-04-20", "hire_date": "2016-09-14"},
    {"first_name": "Gatis", "last_name": "Krūmiņš", "employee_number": "D007", "phone": "+371 20000007", "email": "gatis.k@rs.lv", "default_shift": "morning", "status": "on_duty", "license_categories": "D,D1,DE", "license_expiry_date": "2027-07-15", "medical_cert_expiry": "2026-10-30", "hire_date": "2015-04-01"},
    {"first_name": "Raivis", "last_name": "Zeltiņš", "employee_number": "D008", "phone": "+371 20000008", "email": "raivis.z@rs.lv", "default_shift": "afternoon", "status": "on_duty", "license_categories": "D", "license_expiry_date": "2028-06-20", "medical_cert_expiry": "2027-08-10", "hire_date": "2022-02-01"},
    {"first_name": "Normunds", "last_name": "Celmiņš", "employee_number": "D009", "phone": "+371 20000009", "email": "normunds.c@rs.lv", "default_shift": "evening", "status": "available", "license_categories": "D,D1", "license_expiry_date": "2027-11-10", "medical_cert_expiry": "2027-02-28", "hire_date": "2019-12-15"},
    {"first_name": "Edgars", "last_name": "Dārziņš", "employee_number": "D010", "phone": "+371 20000010", "email": "edgars.d@rs.lv", "default_shift": "night", "status": "on_duty", "license_categories": "D,DE", "license_expiry_date": "2028-03-15", "medical_cert_expiry": "2027-05-25", "hire_date": "2020-08-20"},
    {"first_name": "Kārlis", "last_name": "Siliņš", "employee_number": "D011", "phone": "+371 20000011", "email": "karlis.s@rs.lv", "default_shift": "morning", "status": "on_leave", "license_categories": "D", "license_expiry_date": "2027-05-01", "medical_cert_expiry": "2026-09-15", "hire_date": "2018-06-10"},
    {"first_name": "Artūrs", "last_name": "Balodis", "employee_number": "D012", "phone": "+371 20000012", "email": "arturs.b@rs.lv", "default_shift": "afternoon", "status": "on_duty", "license_categories": "D,D1", "license_expiry_date": "2028-08-30", "medical_cert_expiry": "2027-10-10", "hire_date": "2021-11-01"},
    {"first_name": "Valters", "last_name": "Rudzītis", "employee_number": "D013", "phone": "+371 20000013", "email": "valters.r@rs.lv", "default_shift": "morning", "status": "on_duty", "license_categories": "D,DE", "license_expiry_date": "2027-10-20", "medical_cert_expiry": "2027-01-05", "hire_date": "2017-03-25"},
    {"first_name": "Dainis", "last_name": "Eglītis", "employee_number": "D014", "phone": "+371 20000014", "email": "dainis.e@rs.lv", "default_shift": "evening", "status": "on_duty", "license_categories": "D", "license_expiry_date": "2028-01-10", "medical_cert_expiry": "2027-03-20", "hire_date": "2023-01-15"},
    {"first_name": "Uldis", "last_name": "Jansons", "employee_number": "D015", "phone": "+371 20000015", "email": "uldis.j@rs.lv", "default_shift": "morning", "status": "sick", "license_categories": "D,D1", "license_expiry_date": "2027-08-25", "medical_cert_expiry": "2026-12-15", "hire_date": "2016-02-28"},
]

VEHICLES = [
    {"fleet_number": "B101", "vehicle_type": "bus", "license_plate": "RS-1001", "manufacturer": "Solaris", "model_name": "Urbino 12", "model_year": 2022, "capacity": 95},
    {"fleet_number": "B102", "vehicle_type": "bus", "license_plate": "RS-1002", "manufacturer": "Solaris", "model_name": "Urbino 12", "model_year": 2022, "capacity": 95},
    {"fleet_number": "B103", "vehicle_type": "bus", "license_plate": "RS-1003", "manufacturer": "Solaris", "model_name": "Urbino 18", "model_year": 2021, "capacity": 150},
    {"fleet_number": "B104", "vehicle_type": "bus", "license_plate": "RS-1004", "manufacturer": "Solaris", "model_name": "Urbino 18", "model_year": 2021, "capacity": 150},
    {"fleet_number": "B105", "vehicle_type": "bus", "license_plate": "RS-1005", "manufacturer": "Mercedes-Benz", "model_name": "Citaro G", "model_year": 2020, "capacity": 140},
    {"fleet_number": "B106", "vehicle_type": "bus", "license_plate": "RS-1006", "manufacturer": "Mercedes-Benz", "model_name": "Citaro", "model_year": 2023, "capacity": 90},
    {"fleet_number": "B107", "vehicle_type": "bus", "license_plate": "RS-1007", "manufacturer": "MAN", "model_name": "Lion's City", "model_year": 2022, "capacity": 100},
    {"fleet_number": "B108", "vehicle_type": "bus", "license_plate": "RS-1008", "manufacturer": "MAN", "model_name": "Lion's City G", "model_year": 2021, "capacity": 145},
    {"fleet_number": "T201", "vehicle_type": "trolleybus", "license_plate": "RS-2001", "manufacturer": "Škoda", "model_name": "27Tr", "model_year": 2019, "capacity": 110},
    {"fleet_number": "T202", "vehicle_type": "trolleybus", "license_plate": "RS-2002", "manufacturer": "Škoda", "model_name": "27Tr", "model_year": 2019, "capacity": 110},
    {"fleet_number": "T203", "vehicle_type": "trolleybus", "license_plate": "RS-2003", "manufacturer": "Škoda", "model_name": "26Tr", "model_year": 2020, "capacity": 105},
    {"fleet_number": "T204", "vehicle_type": "trolleybus", "license_plate": "RS-2004", "manufacturer": "Solaris", "model_name": "Trollino 12", "model_year": 2023, "capacity": 100},
    {"fleet_number": "R301", "vehicle_type": "tram", "license_plate": "RS-3001", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2020, "capacity": 200},
    {"fleet_number": "R302", "vehicle_type": "tram", "license_plate": "RS-3002", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2020, "capacity": 200},
    {"fleet_number": "R303", "vehicle_type": "tram", "license_plate": "RS-3003", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2021, "capacity": 200},
    {"fleet_number": "B109", "vehicle_type": "bus", "license_plate": "RS-1009", "manufacturer": "Solaris", "model_name": "Urbino 12 Electric", "model_year": 2024, "capacity": 85},
    {"fleet_number": "B110", "vehicle_type": "bus", "license_plate": "RS-1010", "manufacturer": "Solaris", "model_name": "Urbino 12 Electric", "model_year": 2024, "capacity": 85},
    {"fleet_number": "B111", "vehicle_type": "bus", "license_plate": "RS-1011", "manufacturer": "Mercedes-Benz", "model_name": "eCitaro", "model_year": 2024, "capacity": 88},
    {"first_name": "placeholder"},  # will be skipped
    {"fleet_number": "T205", "vehicle_type": "trolleybus", "license_plate": "RS-2005", "manufacturer": "Solaris", "model_name": "Trollino 18", "model_year": 2023, "capacity": 160},
    {"fleet_number": "R304", "vehicle_type": "tram", "license_plate": "RS-3004", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2022, "capacity": 200},
]

# Remove the accidental placeholder
VEHICLES = [v for v in VEHICLES if "fleet_number" in v]


def api_call(method: str, path: str, data: dict | None = None, token: str = "") -> dict | None:
    url = f"{BASE}{path}"
    if not url.startswith(("http://", "https://")):  # noqa: S310
        raise ValueError(f"Invalid URL scheme: {url}")
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)  # noqa: S310
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        if "already exists" in err.lower() or "duplicate" in err.lower() or e.code == 409:
            return None  # skip duplicates
        print(f"  ERROR {e.code}: {err[:200]}")
        return None


def main() -> None:
    # Login
    login_resp = api_call("POST", "/api/v1/auth/login", {"email": "admin@vtv.lv", "password": "admin"})
    if not login_resp or "access_token" not in login_resp:
        print("ERROR: Could not login")
        sys.exit(1)
    token = login_resp["access_token"]
    print(f"Logged in as admin@vtv.lv")

    # Create drivers
    created_drivers = 0
    for d in DRIVERS:
        result = api_call("POST", "/api/v1/drivers/", d, token)
        if result:
            created_drivers += 1
            print(f"  Driver: {d['first_name']} {d['last_name']} ({d['employee_number']})")
    print(f"Created {created_drivers}/{len(DRIVERS)} drivers")

    # Create vehicles
    created_vehicles = 0
    for v in VEHICLES:
        result = api_call("POST", "/api/v1/vehicles/", v, token)
        if result:
            created_vehicles += 1
            print(f"  Vehicle: {v['fleet_number']} - {v.get('manufacturer', '')} {v.get('model_name', '')} ({v['vehicle_type']})")
    print(f"Created {created_vehicles}/{len(VEHICLES)} vehicles")

    print("\nDone! Refresh the CMS to see the data.")


if __name__ == "__main__":
    main()
