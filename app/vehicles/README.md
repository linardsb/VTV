# Vehicle Management

Fleet vehicle management — CRUD operations, maintenance tracking, driver assignment, and route qualification. Fleet numbers map to GTFS-RT `vehicle_id` for linking real-time positions to fleet metadata.

## Key Flows

### Create Vehicle

1. Validate input (Pydantic schema with Literal types for vehicle_type)
2. Check fleet_number uniqueness via `get_by_fleet_number()`
3. Persist to database
4. Return VehicleResponse

### Assign Driver

1. Validate vehicle exists
2. If assigning (driver_id not None):
   - Validate driver exists via cross-feature `DriverRepository.get()`
   - Check no other active vehicle has this driver via `get_vehicles_by_driver()`
3. Set `current_driver_id` on vehicle
4. Single commit + refresh

### Add Maintenance Record

1. Validate vehicle exists
2. Create MaintenanceRecord via `flush()` (no commit yet)
3. Side effects on parent vehicle:
   - If `mileage_at_service > vehicle.mileage_km` → update vehicle mileage
   - If `next_scheduled_date` provided → update `vehicle.next_maintenance_date`
4. Single atomic commit for both record and vehicle changes
5. Refresh both record and vehicle

### Search Vehicles

1. Parse search/filter parameters (type, status, active_only)
2. ILIKE search on fleet_number, license_plate, manufacturer, model_name (with `escape_like()`)
3. Return paginated results ordered by fleet_number ASC

## Database Schema

### Table: `vehicles`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `fleet_number` | String(20) | Unique, indexed, not null | Maps to GTFS-RT vehicle_id |
| `vehicle_type` | String(20) | Not null, CHECK(bus/trolleybus/tram) | Vehicle type |
| `license_plate` | String(20) | Not null | License plate number |
| `manufacturer` | String(100) | Nullable | Vehicle manufacturer |
| `model_name` | String(100) | Nullable | Vehicle model |
| `model_year` | Integer | Nullable | Year of manufacture |
| `capacity` | Integer | Nullable | Passenger capacity |
| `status` | String(20) | Not null, CHECK(active/inactive/maintenance) | Operational status |
| `current_driver_id` | Integer | FK → drivers.id (SET NULL), nullable | Currently assigned driver |
| `mileage_km` | Integer | Not null, default 0 | Odometer reading |
| `qualified_route_ids` | String(500) | Nullable | CSV of GTFS route IDs |
| `registration_expiry` | Date | Nullable | Registration expiry date |
| `next_maintenance_date` | Date | Nullable | Next scheduled service |
| `notes` | Text | Nullable | Free-text notes |
| `is_active` | Boolean | Not null, default true | Soft delete flag |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

### Table: `maintenance_records`

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | Integer | PK, indexed | Primary key |
| `vehicle_id` | Integer | FK → vehicles.id (CASCADE), indexed | Parent vehicle |
| `maintenance_type` | String(20) | Not null, CHECK(scheduled/unscheduled/inspection/repair) | Service type |
| `description` | Text | Not null | Work description |
| `performed_date` | Date | Not null | Service date |
| `mileage_at_service` | Integer | Nullable | Odometer at service |
| `cost_eur` | Float | Nullable | Cost in EUR |
| `next_scheduled_date` | Date | Nullable | Next scheduled service |
| `performed_by` | String(200) | Nullable | Technician or workshop |
| `notes` | Text | Nullable | Additional notes |
| `created_at` | DateTime | Not null | Auto-set on create |
| `updated_at` | DateTime | Not null | Auto-set on update |

## Business Rules

1. Fleet number must be unique across all vehicles
2. Vehicle type constrained to: bus, trolleybus, tram (Literal type + DB CHECK)
3. Status constrained to: active, inactive, maintenance (Literal type + DB CHECK)
4. Maintenance type constrained to: scheduled, unscheduled, inspection, repair (Literal type + DB CHECK)
5. A driver can only be assigned to one active vehicle at a time
6. Driver assignment validates driver exists via cross-feature DriverRepository
7. Maintenance records cascade-delete when parent vehicle is deleted
8. Deleting a driver sets `current_driver_id` to NULL (SET NULL FK)
9. Adding maintenance with higher mileage auto-updates vehicle's `mileage_km`
10. Adding maintenance with `next_scheduled_date` auto-updates vehicle's `next_maintenance_date`
11. PATCH requests must include at least one field (rejected via `model_validator`)

## Integration Points

- **Drivers**: Cross-feature read via `DriverRepository` for driver assignment validation (existence + conflict check)
- **Transit (future)**: `fleet_number` matches GTFS-RT `vehicle_id` — enables linking real-time vehicle positions to fleet metadata and maintenance history

## API Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/vehicles/` | List vehicles (paginated, searchable, filterable) | Any authenticated |
| GET | `/api/v1/vehicles/{id}` | Get vehicle by ID | Any authenticated |
| POST | `/api/v1/vehicles/` | Create vehicle (201) | admin, editor |
| PATCH | `/api/v1/vehicles/{id}` | Update vehicle | admin, editor |
| DELETE | `/api/v1/vehicles/{id}` | Delete vehicle (204) | admin |
| POST | `/api/v1/vehicles/{id}/assign-driver` | Assign/unassign driver | admin, dispatcher |
| POST | `/api/v1/vehicles/{id}/maintenance` | Add maintenance record (201) | admin, editor |
| GET | `/api/v1/vehicles/{id}/maintenance` | Get maintenance history (paginated) | Any authenticated |
