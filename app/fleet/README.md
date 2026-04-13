# Fleet Device Management

Manages GPS tracking devices (Teltonika, Queclink, etc.) linked to VTV fleet vehicles, and ingests real-time hardware telemetry via Traccar webhook bridge. Route-assigned devices are bridged to the transit map alongside GTFS-RT and OwnTracks sources (LV-3.2).

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
4. If device has `route_id` assigned, look up `route_short_name` from schedules.Route
5. Parse OBD-II attributes (speed, RPM, fuel, coolant temp, odometer, engine load, battery)
6. Convert units (knots -> km/h, meters -> km)
7. Write to Redis cache (key: `vehicle:{feed_id}:{vehicle_id}`, TTL 120s)
8. Add vehicle to Redis SET `feed:fleet:vehicles` (TTL 120s)
9. Publish to Redis Pub/Sub `vehicle_positions` channel (always)
10. If route assigned: publish transit payload to `transit:vehicles:fleet` channel (enables transit map display)
11. Write to TimescaleDB vehicle_positions hypertable (source="hardware")

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
| `route_id` | Integer | FK(routes.id), SET NULL, indexed | Assigned transit route (LV-3.2) |
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
7. Route assignment (`route_id`) is optional; when set, the device's positions appear on the transit map
8. Non-route-assigned devices still write to fleet telemetry (Redis + TimescaleDB) but do not publish to the transit channel

## Integration Points

- **vehicles** - FK reference to vehicles.id for device-vehicle linking; cross-feature read via VehicleRepository
- **schedules** - FK reference to routes.id for transit route assignment (LV-3.2); cross-feature read for route_short_name lookup
- **transit** - Writes to shared vehicle_positions hypertable (VehiclePositionRecord model); publishes to `transit:vehicles:fleet` Pub/Sub for route-assigned devices
- **Redis** - Cache key pattern `vehicle:fleet:{vehicle_id}`, SET `feed:fleet:vehicles`, Pub/Sub on `vehicle_positions` (always) + `transit:vehicles:fleet` (route-assigned only)

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/fleet/devices` | Authenticated | List devices (paginated, search, status filter) |
| GET | `/api/v1/fleet/devices/{id}` | Authenticated | Get device by ID |
| POST | `/api/v1/fleet/devices` | Admin/Editor | Create device |
| PATCH | `/api/v1/fleet/devices/{id}` | Admin/Editor | Update device (including route_id assignment) |
| DELETE | `/api/v1/fleet/devices/{id}` | Admin | Delete device |
| POST | `/api/v1/fleet/webhook/traccar` | Token auth | Receive Traccar position events |
