# Fleet Device Management

Manages GPS tracking devices (Teltonika, Queclink, etc.) linked to VTV fleet vehicles, and ingests real-time hardware telemetry via Traccar webhook bridge.

## Key Flows

### Register Device

1. Validate IMEI format (15 digits)
2. Check IMEI uniqueness
3. If vehicle_id provided, verify vehicle exists and no other device is linked
4. Persist TrackedDevice to database

### Traccar Webhook Ingestion

1. Validate webhook bearer token (separate from JWT auth)
2. Look up device by Traccar's internal deviceId
3. Verify device is linked to a vehicle
4. Parse OBD-II attributes (speed, RPM, fuel, coolant temp, odometer, engine load, battery)
5. Convert units (knots -> km/h, meters -> km)
6. Write to Redis cache (same key pattern as GTFS-RT poller)
7. Write to TimescaleDB vehicle_positions hypertable (source="hardware")
8. Publish to Redis Pub/Sub for WebSocket push

## Database Schema

Table: `tracked_devices`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `imei` | String(15) | Unique, indexed, not null | Device IMEI number |
| `device_name` | String(100) | Nullable | Human-readable name |
| `sim_number` | String(20) | Nullable | SIM card number |
| `protocol_type` | String(20) | CHECK constraint | teltonika/queclink/general/osmand/other |
| `firmware_version` | String(50) | Nullable | Device firmware |
| `vehicle_id` | Integer | FK(vehicles.id), SET NULL, indexed | Linked vehicle |
| `status` | String(20) | CHECK constraint | active/inactive/offline |
| `last_seen_at` | DateTime(tz) | Nullable | Last telemetry timestamp |
| `traccar_device_id` | Integer | Nullable | Traccar internal ID for webhook correlation |
| `notes` | Text | Nullable | Free-text notes |
| `created_at` | DateTime(tz) | Not null | Auto-set on create |
| `updated_at` | DateTime(tz) | Not null | Auto-set on update |

Extended columns on `vehicle_positions`:

| Column | Type | Description |
|--------|------|-------------|
| `source` | String(20) | "gtfs-rt" or "hardware" (server_default="gtfs-rt") |
| `obd_data` | JSONB | OBD-II telemetry (speed_kmh, rpm, fuel_level_pct, etc.) |

## Business Rules

1. IMEI must be exactly 15 digits and unique across all devices
2. Each vehicle can only be linked to one device at a time
3. Device can exist unlinked (vehicle_id=NULL) before being assigned
4. Webhook uses token authentication, not JWT (Traccar is not a VTV user)
5. Position data writes use the shared vehicle_positions hypertable with source="hardware"
6. OBD-II parameters stored as JSONB to handle device variability without schema changes

## Integration Points

- **vehicles** — FK reference to vehicles.id for device-vehicle linking; cross-feature read via VehicleRepository
- **transit** — Writes to shared vehicle_positions hypertable (VehiclePositionRecord model)
- **Redis** — Same cache key pattern as transit poller (vehicle:{feed_id}:{vehicle_id}), Pub/Sub on "vehicle_positions" channel

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/fleet/devices` | Authenticated | List devices (paginated, search, status filter) |
| GET | `/api/v1/fleet/devices/{id}` | Authenticated | Get device by ID |
| POST | `/api/v1/fleet/devices` | Admin/Editor | Create device |
| PATCH | `/api/v1/fleet/devices/{id}` | Admin/Editor | Update device |
| DELETE | `/api/v1/fleet/devices/{id}` | Admin | Delete device |
| POST | `/api/v1/fleet/webhook/traccar` | Token auth | Receive Traccar position events |
