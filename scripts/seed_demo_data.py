"""Seed demo data for production deployment — drivers, vehicles, events, alerts, maintenance."""
import json
import sys
import urllib.request
from datetime import datetime, timedelta

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
    {"fleet_number": "T205", "vehicle_type": "trolleybus", "license_plate": "RS-2005", "manufacturer": "Solaris", "model_name": "Trollino 18", "model_year": 2023, "capacity": 160},
    {"fleet_number": "R301", "vehicle_type": "tram", "license_plate": "RS-3001", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2020, "capacity": 200},
    {"fleet_number": "R302", "vehicle_type": "tram", "license_plate": "RS-3002", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2020, "capacity": 200},
    {"fleet_number": "R303", "vehicle_type": "tram", "license_plate": "RS-3003", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2021, "capacity": 200},
    {"fleet_number": "R304", "vehicle_type": "tram", "license_plate": "RS-3004", "manufacturer": "Škoda", "model_name": "15T ForCity", "model_year": 2022, "capacity": 200},
    {"fleet_number": "B109", "vehicle_type": "bus", "license_plate": "RS-1009", "manufacturer": "Solaris", "model_name": "Urbino 12 Electric", "model_year": 2024, "capacity": 85},
    {"fleet_number": "B110", "vehicle_type": "bus", "license_plate": "RS-1010", "manufacturer": "Solaris", "model_name": "Urbino 12 Electric", "model_year": 2024, "capacity": 85},
    {"fleet_number": "B111", "vehicle_type": "bus", "license_plate": "RS-1011", "manufacturer": "Mercedes-Benz", "model_name": "eCitaro", "model_year": 2024, "capacity": 88},
]

ALERT_RULES = [
    {"name": "Kavēšanās brīdinājums", "rule_type": "delay_threshold", "description": "Brīdinājums, ja transportlīdzeklis kavējas vairāk par 10 minūtēm", "severity": "high", "threshold_config": {"delay_minutes": 10}, "enabled": True},
    {"name": "Apkopes termiņš tuvojas", "rule_type": "maintenance_due", "description": "Brīdinājums 7 dienas pirms plānotās apkopes", "severity": "medium", "threshold_config": {"days_before": 7}, "enabled": True},
    {"name": "Reģistrācija beidzas", "rule_type": "registration_expiry", "description": "Brīdinājums 30 dienas pirms reģistrācijas beigām", "severity": "high", "threshold_config": {"days_before": 30}, "enabled": True},
    {"name": "Vadītāja licences termiņš", "rule_type": "manual", "description": "Manuāls brīdinājums par vadītāja licences termiņu", "severity": "medium", "enabled": True},
]


def _now() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt(days_offset: int, hour: int = 8, minute: int = 0) -> str:
    dt = datetime.utcnow() + timedelta(days=days_offset)
    dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _date(days_offset: int) -> str:
    dt = datetime.utcnow() + timedelta(days=days_offset)
    return dt.strftime("%Y-%m-%d")


def get_events(driver_ids: list[int]) -> list[dict]:
    """Generate operational events for the current week."""
    return [
        {"title": "Rīta maiņas sākums", "start_datetime": _dt(0, 5, 30), "end_datetime": _dt(0, 14, 0), "priority": "medium", "category": "driver-shift", "driver_id": driver_ids[0] if driver_ids else None, "description": "Rīta maiņa — maršruti 3, 7, 22"},
        {"title": "Pēcpusdienas maiņa", "start_datetime": _dt(0, 13, 30), "end_datetime": _dt(0, 22, 0), "priority": "medium", "category": "driver-shift", "driver_id": driver_ids[2] if len(driver_ids) > 2 else None, "description": "Pēcpusdienas maiņa — maršruti 15, 18"},
        {"title": "B103 plānota apkope", "start_datetime": _dt(1, 8, 0), "end_datetime": _dt(1, 16, 0), "priority": "high", "category": "maintenance", "description": "Solaris Urbino 18 — bremžu sistēmas pārbaude un eļļas maiņa"},
        {"title": "Maršruta 22 novirzīšana", "start_datetime": _dt(1, 6, 0), "end_datetime": _dt(3, 22, 0), "priority": "high", "category": "route-change", "description": "Ceļu būvdarbi K.Barona ielā — pagaidu maršruts caur Elizabetes ielu"},
        {"title": "T201 trolejbusa diagnostika", "start_datetime": _dt(2, 9, 0), "end_datetime": _dt(2, 12, 0), "priority": "medium", "category": "maintenance", "description": "Elektriskās sistēmas diagnostika — Škoda 27Tr"},
        {"title": "Vakara maiņa", "start_datetime": _dt(0, 21, 30), "end_datetime": _dt(1, 6, 0), "priority": "low", "category": "driver-shift", "driver_id": driver_ids[4] if len(driver_ids) > 4 else None, "description": "Nakts maiņa — maršruti 2, 9"},
        {"title": "GTFS datu atjaunošana", "start_datetime": _dt(3, 10, 0), "end_datetime": _dt(3, 11, 0), "priority": "low", "category": "service-alert", "description": "Iknedēļas GTFS statisko datu atjaunošana no Rīgas Satiksme"},
        {"title": "R301 tramvaja apkope", "start_datetime": _dt(4, 7, 0), "end_datetime": _dt(4, 15, 0), "priority": "high", "category": "maintenance", "description": "Škoda 15T ForCity — riteņu pāru pārbaude un sliežu bremžu regulēšana"},
        {"title": "Rīta maiņa (sestdiena)", "start_datetime": _dt(5, 6, 0), "end_datetime": _dt(5, 14, 30), "priority": "medium", "category": "driver-shift", "driver_id": driver_ids[5] if len(driver_ids) > 5 else None, "description": "Brīvdienas samazināts grafiks"},
        {"title": "Pasažieru skaitīšana", "start_datetime": _dt(2, 7, 0), "end_datetime": _dt(2, 19, 0), "priority": "low", "category": "service-alert", "description": "Ikmēneša pasažieru plūsmas uzskaite — maršruti 1, 3, 7, 11, 22"},
    ]


def get_alerts(rule_ids: list[int]) -> list[dict]:
    """Generate sample alert instances."""
    return [
        {"title": "B105 kavējas 12 min uz maršruta 7", "severity": "high", "alert_type": "delay_threshold", "source_entity_type": "vehicle", "source_entity_id": "B105", "details": {"delay_minutes": 12, "route": "7", "stop": "Centrāltirgus"}, "rule_id": rule_ids[0] if rule_ids else None},
        {"title": "T203 apkopes termiņš pēc 5 dienām", "severity": "medium", "alert_type": "maintenance_due", "source_entity_type": "vehicle", "source_entity_id": "T203", "details": {"days_remaining": 5, "maintenance_type": "scheduled"}, "rule_id": rule_ids[1] if len(rule_ids) > 1 else None},
        {"title": "B108 reģistrācija beidzas pēc 25 dienām", "severity": "high", "alert_type": "registration_expiry", "source_entity_type": "vehicle", "source_entity_id": "B108", "details": {"days_remaining": 25, "expiry_date": _date(25)}, "rule_id": rule_ids[2] if len(rule_ids) > 2 else None},
        {"title": "Vadītāja D011 licence beidzas 2027-05-01", "severity": "medium", "alert_type": "manual", "source_entity_type": "driver", "source_entity_id": "D011", "details": {"driver_name": "Kārlis Siliņš", "expiry_date": "2027-05-01"}, "rule_id": rule_ids[3] if len(rule_ids) > 3 else None},
        {"title": "R302 kavējas 8 min uz tramvaja maršruta 1", "severity": "medium", "alert_type": "delay_threshold", "source_entity_type": "vehicle", "source_entity_id": "R302", "details": {"delay_minutes": 8, "route": "1", "stop": "Ausekļa iela"}, "rule_id": rule_ids[0] if rule_ids else None},
    ]


def get_maintenance(vehicle_ids: dict[str, int]) -> list[dict]:
    """Generate maintenance records for vehicles. vehicle_ids maps fleet_number -> id."""
    records = []
    if "B101" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["B101"], "maintenance_type": "scheduled", "description": "Regulārā 50 000 km apkope — eļļas maiņa, filtru nomaiņa, bremžu pārbaude", "performed_date": _date(-14), "mileage_at_service": 48500, "cost_eur": 450.0, "next_scheduled_date": _date(76), "performed_by": "SIA AutoServiss"})
    if "B103" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["B103"], "maintenance_type": "repair", "description": "Pneimatiskās durvju sistēmas remonts — cilindra nomaiņa", "performed_date": _date(-7), "mileage_at_service": 92300, "cost_eur": 1200.0, "performed_by": "Solaris Latvia"})
    if "T201" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["T201"], "maintenance_type": "inspection", "description": "Ikgadējā tehniskā apskate — elektriskā sistēma, bremzes, virsbūve", "performed_date": _date(-30), "mileage_at_service": 156000, "cost_eur": 280.0, "next_scheduled_date": _date(335), "performed_by": "CSDD"})
    if "R301" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["R301"], "maintenance_type": "scheduled", "description": "Riteņu pāru pārbaude un profilēšana, sliežu bremžu regulēšana", "performed_date": _date(-21), "cost_eur": 3500.0, "next_scheduled_date": _date(69), "performed_by": "Rīgas Satiksme depo"})
    if "B109" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["B109"], "maintenance_type": "inspection", "description": "Akumulatoru veselības pārbaude — SOH 94%, visi moduļi normā", "performed_date": _date(-3), "mileage_at_service": 12400, "cost_eur": 150.0, "next_scheduled_date": _date(87), "performed_by": "Solaris Latvia"})
    if "B105" in vehicle_ids:
        records.append({"vehicle_id": vehicle_ids["B105"], "maintenance_type": "unscheduled", "description": "Kondicionieru kompresora nomaiņa — avārijas remonts", "performed_date": _date(-2), "mileage_at_service": 187600, "cost_eur": 2800.0, "performed_by": "Mercedes-Benz Serviss"})
    return records


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
    print("Logged in as admin@vtv.lv")

    # --- Drivers ---
    created_drivers = 0
    driver_ids: list[int] = []
    for d in DRIVERS:
        result = api_call("POST", "/api/v1/drivers/", d, token)
        if result:
            created_drivers += 1
            driver_ids.append(result["id"])
            print(f"  Driver: {d['first_name']} {d['last_name']} ({d['employee_number']})")
        else:
            driver_ids.append(0)
    print(f"Created {created_drivers}/{len(DRIVERS)} drivers\n")

    # --- Vehicles ---
    created_vehicles = 0
    vehicle_id_map: dict[str, int] = {}
    for v in VEHICLES:
        result = api_call("POST", "/api/v1/vehicles/", v, token)
        if result:
            created_vehicles += 1
            vehicle_id_map[v["fleet_number"]] = result["id"]
            print(f"  Vehicle: {v['fleet_number']} — {v.get('manufacturer', '')} {v.get('model_name', '')} ({v['vehicle_type']})")
    print(f"Created {created_vehicles}/{len(VEHICLES)} vehicles\n")

    # --- Alert Rules ---
    created_rules = 0
    rule_ids: list[int] = []
    for r in ALERT_RULES:
        result = api_call("POST", "/api/v1/alerts/rules/", r, token)
        if result:
            created_rules += 1
            rule_ids.append(result["id"])
            print(f"  Rule: {r['name']} ({r['severity']})")
        else:
            rule_ids.append(0)
    print(f"Created {created_rules}/{len(ALERT_RULES)} alert rules\n")

    # --- Alert Instances ---
    alerts = get_alerts([rid for rid in rule_ids if rid])
    created_alerts = 0
    for a in alerts:
        result = api_call("POST", "/api/v1/alerts/", a, token)
        if result:
            created_alerts += 1
            print(f"  Alert: {a['title']}")
    print(f"Created {created_alerts}/{len(alerts)} alerts\n")

    # --- Events ---
    valid_driver_ids = [did for did in driver_ids if did]
    events = get_events(valid_driver_ids)
    created_events = 0
    for ev in events:
        # Remove None driver_id
        if ev.get("driver_id") is None:
            ev.pop("driver_id", None)
        result = api_call("POST", "/api/v1/events/", ev, token)
        if result:
            created_events += 1
            print(f"  Event: {ev['title']}")
    print(f"Created {created_events}/{len(events)} events\n")

    # --- Maintenance Records ---
    maintenance = get_maintenance(vehicle_id_map)
    created_maint = 0
    for m in maintenance:
        vid = m.pop("vehicle_id")
        result = api_call("POST", f"/api/v1/vehicles/{vid}/maintenance/", m, token)
        if result:
            created_maint += 1
            print(f"  Maintenance: {m['description'][:60]}...")
    print(f"Created {created_maint}/{len(maintenance)} maintenance records\n")

    print("Done! Refresh the CMS to see all data.")


if __name__ == "__main__":
    main()
