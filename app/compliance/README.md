# Compliance

EU regulatory compliance exports — transforms existing VTV transit data into NeTEx and SIRI XML formats required by EU MMTIS Delegated Regulation 2017/1926 for Latvia's National Access Point (data.gov.lv).

## Key Flows

### NeTEx Static Export

1. Gather all schedule entities (agencies, routes, calendars, trips, stop times, stops) via ScheduleRepository + StopRepository
2. Optionally filter by agency_id
3. Pass to NeTExExporter which builds PublicationDelivery XML with four frames (ResourceFrame, SiteFrame, ServiceFrame, TimetableFrame)
4. Return UTF-8 XML bytes with Content-Disposition attachment header

### SIRI-VM (Vehicle Monitoring)

1. Fetch real-time vehicle positions from TransitService (Redis-cached GTFS-RT data)
2. Optionally filter by route_id or feed_id
3. Pass to SiriVehicleMonitoringBuilder which generates VehicleActivity elements
4. Return SIRI 2.0 ServiceDelivery XML

### SIRI-SM (Stop Monitoring)

1. Fetch all real-time vehicle positions from TransitService
2. Filter to vehicles whose next_stop_name or current_stop_name matches the requested stop
3. Pass to SiriStopMonitoringBuilder which generates MonitoredStopVisit elements
4. Return SIRI 2.0 ServiceDelivery XML

## Business Rules

1. No database tables — pure transformation layer over existing schedule and transit data
2. NeTEx codespace (ID prefix) configurable via `Settings.netex_codespace` (default: "VTV")
3. SIRI participant reference configurable via `Settings.netex_participant_ref` (default: "VTV")
4. NeTEx exports use EPIP (European Passenger Information Profile) v1.2 structure
5. SIRI exports use SIRI 2.0 specification
6. GTFS route_type maps to NeTEx TransportMode (0=tram, 1=metro, 2=rail, 3=bus, etc.)
7. GTFS times > 24:00:00 are preserved (valid in both GTFS and NeTEx)
8. Empty datasets produce valid but empty XML documents

## Integration Points

- **schedules**: Reads agencies, routes, calendars, calendar_dates, trips, stop_times via ScheduleRepository
- **stops**: Reads stops via StopRepository (cross-feature read for NeTEx SiteFrame)
- **transit**: Reads real-time vehicle positions via TransitService singleton (SIRI-VM and SIRI-SM)
- **core/config**: Uses `netex_codespace` and `netex_participant_ref` settings

## API Endpoints

| Method | Path | Description | Rate Limit |
|--------|------|-------------|------------|
| GET | `/api/v1/compliance/netex` | NeTEx EPIP XML export (optional `agency_id` filter) | 3/min |
| GET | `/api/v1/compliance/siri/vm` | SIRI Vehicle Monitoring XML (optional `route_id`, `feed_id`) | 10/min |
| GET | `/api/v1/compliance/siri/sm` | SIRI Stop Monitoring XML (required `stop_name`) | 10/min |
| GET | `/api/v1/compliance/status` | Export status with entity counts (JSON) | 30/min |

All endpoints require authentication via `get_current_user` dependency.
