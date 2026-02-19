# VTV Transit Platform - Implementation Plan

> Created: 2026-02-19
> Updated: 2026-02-19 (baselined against actual codebase)
> Reference: Latvia-Live-Transit-Research.md
> Status: Draft - Pending approval

---

## Current State (What's Already Built)

Before reading the phases below, understand what already exists. The plan was written as a greenfield design, but VTV already has a working transit system with a simpler architecture.

### Existing Transit Infrastructure

| Component | Status | Implementation |
|-----------|--------|---------------|
| **GTFS-RT client** | DONE | `app/core/agents/tools/transit/client.py` - on-demand fetch with 20s in-memory cache. Fetches from 3 Riga feeds (vehicle_positions.pb, trip_updates.pb, gtfs_realtime.pb) |
| **GTFS static cache** | DONE | `app/core/agents/tools/transit/static_cache.py` - in-memory parsing of GTFS ZIP using stdlib csv/zipfile. Parses routes, stops, trips, stop_times, calendar, calendar_dates. 24h TTL |
| **Vehicle positions REST API** | DONE | `app/transit/routes.py` - `GET /api/v1/transit/vehicles` with route_id filter, rate-limited 30/min |
| **Live map in CMS** | DONE | `react-leaflet` v5 + OSM tiles, centered on Riga. HTTP polling at 10s intervals via `useVehiclePositions` hook |
| **Agent transit tools (5)** | DONE | query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability. 104 unit tests |
| **Agent vault tools (4)** | DONE | Obsidian integration. 68 unit tests |
| **Agent knowledge tool (1)** | DONE | RAG search over uploaded documents. pgvector hybrid search |
| **Stop management CRUD** | DONE | `app/stops/` - REST API with Haversine proximity search (plain Float columns, no PostGIS) |
| **DDoS defense** | DONE | nginx rate limiting, slowapi, body size limits, query quotas |
| **Auth + i18n** | DONE | Auth.js v5 RBAC (4 roles), next-intl (LV + EN), Latvian agent language support |

### Architecture Differences from This Plan

| This Plan Assumes | Actual Architecture | Gap to Fill |
|---|---|---|
| Redis for vehicle position cache | In-memory Python `_CacheEntry` (20s TTL) | Add Redis when scaling beyond ~50 concurrent users |
| TimescaleDB for historical positions | No historical storage - positions are ephemeral | Add when historical analytics are needed |
| PostGIS for spatial queries | Plain Float columns + Python Haversine | Add when sub-ms spatial queries are needed at scale |
| Background GTFS-RT poller writing to 3 backends | On-demand fetch triggered by HTTP requests | Convert to background poller for multi-feed |
| WebSocket streaming to frontend | HTTP polling at 10s intervals | Add for real-time UX with >10 concurrent map viewers |
| Multiple GTFS feeds (ATD, Jurmala, Pieriga, etc.) | Single feed: Rigas Satiksme only | Core work remaining in this plan |
| GTFS data in PostgreSQL tables | GTFS data parsed into Python dicts in memory | Needed for multi-feed and cross-feed queries |
| `gtfs-kit` / `partridge` for parsing | stdlib `csv` + `zipfile` | Current approach works; consider gtfs-kit for validation |
| Leaflet.js | `react-leaflet` v5.0.0 (already installed) | No gap - plan text is wrong |
| 6 proposed agent tools | 10 tools actually implemented (more than planned) | Ahead of plan |

### What This Means for Implementation

Phase 1 is **~40% complete** based on Riga-only scope. The remaining work is:
1. **Multi-feed support** - extend beyond Riga to all Latvia (the core deliverable)
2. **Persistent GTFS storage** - move from in-memory to database for cross-feed queries
3. **Infrastructure upgrades** - Redis, TimescaleDB, PostGIS (add incrementally, not all at once)
4. **WebSocket streaming** - replace HTTP polling for better real-time UX
5. **CKAN bridge** - immediate intercity data access while building full import

### Infrastructure Readiness Checklist

To prepare the architecture for Phase 1 completion:

- [ ] **PostGIS extension** - Switch Docker image from `pgvector/pgvector:pg18` to a multi-extension image supporting both pgvector AND PostGIS. Verify existing tables (stops, documents, document_chunks) survive the migration.
- [ ] **Redis container** - Add `redis:7-alpine` to `docker-compose.yml` with health check. Wire into FastAPI app config (`app/core/config.py` needs `REDIS_URL`).
- [ ] **GTFS database tables** - Create Alembic migration for `gtfs_stops`, `gtfs_routes`, `gtfs_trips`, `gtfs_stop_times`, `gtfs_calendar`, `gtfs_feed_info`. PostGIS GIST index on stops geography.
- [ ] **GTFS importer** - Build `app/transit/gtfs_importer.py` to write parsed GTFS into database tables. Keep `static_cache.py` working until agent tools migrate.
- [ ] **Redis write pipeline** - Modify GTFS-RT client to write vehicle positions into Redis alongside the existing in-memory cache (dual-write during migration).
- [ ] **Agent tool migration** - Gradually switch tools from in-memory → Redis/PostgreSQL queries. Each tool can be migrated independently.

**Order matters:** PostGIS first (enables spatial indexes), then Redis (enables real-time caching), then GTFS tables (enables persistent storage), then tool migration.

---

## Prerequisites

Before starting, confirm these are in place:

- [x] VTV backend running (FastAPI + PostgreSQL) -- DONE
- [x] Docker available for PostgreSQL extensions -- DONE (pgvector/pgvector:pg18)
- [ ] Server/VPS for self-hosted services (Traccar, Mosquitto, OSRM)
- [ ] Decision on hosting: existing VTV server vs. separate transit server

---

## Phase 1: Foundation (Weeks 1-4)

**Deliverable: Live bus map for Rīga + static schedule data for all Latvia**

> **Note:** Riga live map already works (react-leaflet + HTTP polling). This phase extends coverage to all Latvia and adds persistent storage.

### Week 1: Database & GTFS Static Import

#### 1.1 Install PostgreSQL Extensions
```
Current: pgvector/pgvector:pg18 image (pgvector only)
Needed:
- Add PostGIS extension (switch to postgis/postgis:18-3.5 or multi-extension image)
- Add TimescaleDB extension (Phase 2 - not needed for Phase 1 MVP)
- Verify both work with existing VTV schema (stops, documents, document_chunks tables)
```

#### 1.2 Create Transit Database Schema
```
Tables to create:
├── gtfs_stops          (from GTFS stops.txt)
├── gtfs_routes         (from GTFS routes.txt)
├── gtfs_trips          (from GTFS trips.txt)
├── gtfs_stop_times     (from GTFS stop_times.txt)
├── gtfs_shapes         (from GTFS shapes.txt)
├── gtfs_calendar       (from GTFS calendar.txt + calendar_dates.txt)
├── gtfs_feed_info      (metadata: which feed, last import, hash)
├── vehicle_positions   (TimescaleDB hypertable)
├── vehicle_latest      (current position per vehicle, also cached in Redis)
└── stop_arrivals       (computed ETAs)

Indexes:
├── gtfs_stops: GIST index on geography(lat, lon)
├── vehicle_positions: time + vehicle_id (TimescaleDB auto-manages)
├── vehicle_latest: vehicle_id (PK)
└── stop_arrivals: stop_id + estimated_at
```

#### 1.3 Build GTFS Static Importer
```python
# EXISTING: app/core/agents/tools/transit/static_cache.py
#   - Already downloads and parses Riga GTFS ZIP (csv + zipfile stdlib)
#   - In-memory only, 24h TTL, single feed
#   - Parses: routes, stops, trips, stop_times, calendar, calendar_dates
#
# NEW module: app/transit/gtfs_importer.py
#
# Responsibilities:
# - Extend existing parsing to write into database tables (not just memory)
# - Compare hash with last import (skip if unchanged)
# - Handle multiple feeds (ATD, Riga, Jurmala, Liepaja, etc.)
# - Keep existing static_cache.py working (agent tools depend on it)
#
# Feeds to import:
# - ATD intercity:    https://atd.lv/sites/default/files/GTFS/gtfs-latvia-lv.zip
# - Rigas Satiksme:   https://saraksti.rigassatiksme.lv/gtfs.zip (already used by static_cache)
# - OR combined:       https://gsvalbe.id.lv/pieturas/dati/latvia.zip
#
# Schedule: Daily cron job at 03:00
#
# Decision: Use stdlib csv (already proven in static_cache.py) rather than
# gtfs-kit/partridge. Add validation separately if needed.

Dependencies to add:
- httpx (already installed - used by agent transit client and obsidian client)
```

#### 1.4 CKAN Datastore SQL API (Immediate Bridge)

While the full GTFS importer is being built, the VTV agent can query ATD data **immediately** via the data.gov.lv CKAN SQL API. This provides day-zero transit query capability with zero infrastructure.

```python
# New module: app/transit/ckan_client.py
#
# Lightweight client for data.gov.lv CKAN Datastore SQL API
# Supports full SQL: SELECT, JOIN, WHERE, GROUP BY, ORDER BY, Haversine
#
# Base URL: https://data.gov.lv/dati/eng/api/action/datastore_search_sql
#
# ATD Resource IDs (intercity + regional bus GTFS tables):
CKAN_RESOURCES = {
    "stops":          "1914e295-8efd-4c66-a54e-4eeaf69273e0",  # 10,000 records
    "routes":         "0863b555-9e4d-48ac-8159-833d41e00082",
    "trips":          "2ef41d7c-e784-47b0-9cc8-fcc23be8be4c",
    "stop_times":     "592c5853-9bc8-4df5-9f81-2d133b5e572c",
    "shapes":         "61c058e1-618a-4dbd-b79c-35b216f155d5",
    "calendar":       "23b7ae75-ba9c-4de2-851c-afd90b004ebd",
    "calendar_dates": "d7d63df9-74a4-4501-8344-5fdc059cc474",
    "fare_attributes":"28941852-0a00-47c6-adc2-83f6b34ab454",
    "fare_rules":     "953e3b40-e955-4db1-8790-ef2d87127110",
    "agency":         "747feb34-e28c-407e-b10e-372273365fc4",
}
#
# Capabilities confirmed working:
# - Cross-table JOINs (routes + trips → busiest routes)
# - Haversine distance (find stops near coordinates)
# - LIKE filtering (search stops by name)
# - GROUP BY + COUNT aggregations
# - Sub-second response times for most queries
#
# Strategy:
# - Phase 1 Week 1: Wire into VTV agent as transit query tool (immediate value)
# - Phase 1 Week 1-2: Build full GTFS importer in parallel
# - After GTFS import is live: CKAN becomes fallback/validation, local DB is primary
#
# Limitations:
# - 32,000 row limit per query (pagination needed for stop_times/shapes)
# - No spatial indexes (Haversine via math, not PostGIS ST_DWithin)
# - Read-only (cannot join with our real-time vehicle_positions)
# - Depends on data.gov.lv uptime

# Example queries:
#
# Find 5 nearest stops to Riga center:
# SELECT stop_id, stop_name, stop_lat, stop_lon,
#   (6371 * acos(cos(radians(56.9496)) * cos(radians(stop_lat))
#   * cos(radians(stop_lon) - radians(24.1052))
#   + sin(radians(56.9496)) * sin(radians(stop_lat)))) AS distance_km
# FROM "1914e295-8efd-4c66-a54e-4eeaf69273e0"
# ORDER BY distance_km LIMIT 5
#
# Busiest intercity routes by trip count:
# SELECT r.route_short_name, r.route_long_name, COUNT(t.trip_id) as trips
# FROM "0863b555-9e4d-48ac-8159-833d41e00082" r
# JOIN "2ef41d7c-e784-47b0-9cc8-fcc23be8be4c" t ON r.route_id = t.route_id
# GROUP BY r.route_id, r.route_short_name, r.route_long_name
# ORDER BY trips DESC LIMIT 10
#
# Routes serving Liepāja:
# SELECT route_short_name, route_long_name
# FROM "0863b555-9e4d-48ac-8159-833d41e00082"
# WHERE route_long_name LIKE '%Liepāja%'
```

**Tasks:**
- [ ] Build `CKANClient` class with `query_sql()` method
- [ ] Register as VTV agent tool: `search_intercity_stops`, `search_intercity_routes`
- [ ] Add response caching (5 min TTL) to avoid hammering data.gov.lv
- [ ] Create Alembic migration for GTFS tables (no hypertable yet - Phase 2)
- [ ] Build `GTFSImporter` class with download, hash-check, parse, import
- [ ] Test with ATD GTFS feed (intercity) - largest feed
- [x] Test with Rigas Satiksme GTFS feed (already working via static_cache.py in-memory)
- [ ] Add management command: `python -m app.transit.import_gtfs`
- [x] Verify stop count for Riga (static_cache.py already parses ~2000 stops)
- [ ] Once local GTFS DB is live, switch agent tools from in-memory cache → local PostgreSQL

**Note:** `find_nearby_stops` already exists as `search_stops` agent tool (Haversine-based).
Existing tools: query_bus_status, get_route_schedule, search_stops, get_adherence_report, check_driver_availability.

---

### Week 2: Real-Time Data Ingestion

#### 2.1 GTFS-RT Poller Service
```python
# EXISTING: app/core/agents/tools/transit/client.py
#   - GTFSRealtimeClient already fetches from 3 Riga GTFS-RT feeds
#   - On-demand fetch with 20s in-memory cache (not a background poller)
#   - Uses gtfs-realtime-bindings for protobuf parsing (already installed)
#   - Returns typed dataclasses: VehiclePositionData, TripUpdateData, AlertData
#
# UPGRADE: app/transit/realtime/gtfs_rt_poller.py
#
# Convert from on-demand fetch to background polling service that:
#   1. Writes to Redis (latest position cache) - NEW
#   2. Writes to TimescaleDB (historical) - Phase 2, skip for Phase 1 MVP
#   3. Publishes to Redis pub/sub (for WebSocket) - NEW
#
# Feeds to poll:
# - Riga vehicle positions:  https://saraksti.rigassatiksme.lv/vehicle_positions.pb  (10s) [EXISTING]
# - Riga trip updates:       https://saraksti.rigassatiksme.lv/trip_updates.pb       (10s) [EXISTING]
# - Jurmala combined:        https://marsruti.lv/jurmala/gtfs_realtime.pb            (15s) [NEW]
# - Pieriga combined:        https://marsruti.lv/pieriga/gtfs_realtime.pb            (15s) [NEW]

Dependencies to add:
- redis[hiredis] (async Redis client) - NEW
- gtfs-realtime-bindings - ALREADY INSTALLED
```

#### 2.2 GPS Text Feed Poller
```python
# New module: app/transit/realtime/gps_text_poller.py
#
# Polls simple GPS text endpoints, parses CSV-like format
# Same output pipeline as GTFS-RT poller
#
# Feeds to poll:
# - Liepāja:   https://marsruti.lv/liepaja/gps.txt        (15s)
# - Rēzekne:   https://marsruti.lv/rezekne/gps.txt        (15s)
# - LSA:       https://marsruti.lv/LSA/gps.txt             (15s)
```

#### 2.3 Redis Setup
```
Keys:
- vehicle:{vehicle_id}     → JSON: {lat, lon, bearing, speed, route_id, trip_id, operator, updated_at}
- TTL: 120 seconds (auto-expire vehicles that stop reporting)

Pub/Sub:
- Channel: transit:vehicle_updates
- Message: JSON of changed vehicle position
- Subscribers: WebSocket handler(s)
```

**Tasks:**
- [x] `gtfs-realtime-bindings` already in pyproject.toml
- [ ] Add `redis[hiredis]` to pyproject.toml
- [ ] Refactor `GTFSRealtimeClient` into background `GTFSRTPoller` (reuse existing protobuf parsing)
- [ ] Build `GPSTextPoller` class with async polling loop
- [ ] Build normalisation layer: all sources -> unified `VehiclePosition` schema (extend existing dataclasses)
- [ ] Set up Redis (add to docker-compose.yml)
- [ ] Build write pipeline: position -> Redis (Phase 1) + TimescaleDB (Phase 2)
- [x] Test with Riga feed - already working via existing client.py
- [ ] Test multi-feed: verify Jurmala + Pieriga positions alongside Riga
- [ ] Add health check: log feed status, last successful poll, entity count

---

### Week 3: API Endpoints & WebSocket

#### 3.1 REST API Endpoints
```python
# EXISTING: app/transit/routes.py
# GET  /api/v1/transit/vehicles           [DONE - rate limited 30/min]
#      → All live vehicles (from GTFS-RT on-demand fetch, will migrate to Redis)
#      → Query params: route_id (operator and bounds NOT yet supported)
#
# Extend app/transit/routes.py with:
#
# GET  /api/v1/transit/vehicles           [UPDATE: add operator, bounds params]
#
# GET  /api/v1/transit/vehicles/{vehicle_id}     [NEW]
#      → Single vehicle current position + trip info
#
# GET  /api/v1/transit/vehicles/{vehicle_id}/history?from=&to=   [NEW - Phase 2]
#      → Historical positions from TimescaleDB (requires Phase 2 infra)
#
# GET  /api/v1/transit/stops/{stop_id}/departures    [NEW]
#      → Proxy to saraksti.rigassatiksme.lv/departures2.php
#      → Enriched with our own ETA data where available
#
# GET  /api/v1/transit/routes/{route_id}/vehicles    [NEW]
#      → All live vehicles on a specific route
```

#### 3.2 WebSocket Endpoint
```python
# New module: app/transit/realtime/websocket.py
#
# WS /api/v1/transit/vehicles/stream
#
# Client sends subscription message:
#   {"type": "subscribe", "bounds": [lat1, lon1, lat2, lon2]}
#   {"type": "subscribe", "routes": ["1", "22", "15"]}
#   {"type": "subscribe", "operators": ["rigas_satiksme"]}
#
# Server streams:
#   {"type": "position", "vehicle_id": "...", "lat": ..., "lon": ..., ...}
#
# Reads from Redis pub/sub, filters by client subscription, sends
```

**Tasks:**
- [ ] Build REST endpoints for vehicles, departures, vehicle history
- [ ] Build WebSocket endpoint with subscription filtering
- [ ] Add viewport-based filtering (only send vehicles in client's map bounds)
- [ ] Test WebSocket with simple HTML/JS client
- [ ] Rate-limit departure proxy to avoid overloading upstream
- [ ] Add OpenAPI docs for all new endpoints

---

### Week 4: Frontend Map & Integration

#### 4.1 Live Map Component
```typescript
// EXISTING: cms/apps/web/src/components/routes/route-map.tsx
//
// Technology: react-leaflet v5.0.0 + OpenStreetMap tiles (already installed)
// Dependencies: leaflet ^1.9.4, react-leaflet ^5.0.0, @types/leaflet ^1.9.21
//
// What works now:
// - Map centered on Riga (56.9496, 24.1052) with OSM tiles
// - Vehicle markers (BusMarker component) with route highlighting
// - HTTP polling at 10s via useVehiclePositions hook
// - Route type filter (bus/trolleybus/tram)
// - Resizable 60/40 split panel on routes page
//
// What needs to be added for full Latvia:
// - Full-screen dedicated map page (not just routes page panel)
// - Click vehicle -> show route, speed, next stop, ETA
// - Click stop -> show upcoming departures
// - Filter by operator (when multi-feed is live)
// - Upgrade to WebSocket (when backend WebSocket is ready)
//
// Performance (needed when showing 500+ vehicles from all Latvia):
// - Add leaflet.markercluster for zoom-out views
// - Canvas renderer (L.canvas) instead of SVG for >100 markers
// - Smooth position interpolation between updates
```

**Tasks:**
- [x] Leaflet dependencies installed (leaflet, react-leaflet, @types/leaflet)
- [x] `RouteMap` component with OSM tile layer - DONE
- [x] Vehicle marker layer with HTTP polling updates - DONE
- [x] Route type filter (bus/trolleybus/tram) - DONE
- [x] Test with live Riga data - DONE
- [ ] Build dedicated full-screen `/map` page (currently map is a panel in routes page)
- [ ] Add `leaflet.markercluster` for zoom-out with 500+ markers
- [ ] Build stop marker layer (from GTFS stops data)
- [ ] Build click-to-inspect panel (vehicle details, stop departures)
- [ ] Build operator filter controls (for multi-feed)
- [ ] Upgrade from HTTP polling to WebSocket (when backend is ready)
- [ ] Performance test with all feeds running simultaneously

**Phase 1 Validation:**
- [x] Live map shows Riga buses moving in real-time
- [ ] Stop departures show real-time ETAs
- [ ] All GTFS static data imported to database (stops, routes, shapes)
- [ ] WebSocket handles 10+ concurrent clients without lag
- [ ] Data pipeline survives feed outage gracefully (circuit breaker)
- [ ] Multi-feed: Jurmala + Pieriga vehicles visible alongside Riga

---

## Phase 2: Full Latvia Coverage (Weeks 5-8)

**Deliverable: All available Latvian real-time feeds + trains + ETAs**

### Week 5: Additional Feeds
- [ ] Add Daugavpils data (scrape from satiksme.daugavpils.lv/transports/karte)
- [ ] Add train positions via WebSocket listener (`wss://trainmap.pv.lv/ws`)
- [ ] Add saraksti.lv custom endpoint (`gpsdata.ashx` with custom header) as fallback
- [ ] Handle feed-specific quirks (different vehicle ID formats, missing fields)
- [ ] Build feed monitoring dashboard (last poll time, entity count, error rate)

### Week 6: Route Matching & ETA
- [ ] Deploy Valhalla (Docker) with Latvia OSM extract
- [ ] Build map-matching service: snap GPS positions to roads
- [ ] Build basic ETA calculator: distance-to-stop / current-speed
- [ ] Compare our ETAs with operator ETAs (from trip_updates.pb)
- [ ] Store ETA predictions in `stop_arrivals` table

### Week 7: Adaptive Polling & Resilience
- [ ] Implement adaptive polling intervals (5s peak / 30s off-peak)
- [ ] Add circuit breaker pattern for each feed
- [ ] Add staleness detection (mark vehicles as "stale" if no update >60s)
- [ ] Add feed status API endpoint for monitoring
- [ ] Set up TimescaleDB compression policy (7 days raw, 90 days compressed)

### Week 8: GTFS-RT Publisher
- [ ] Build GTFS-RT protobuf generator from our combined data
- [ ] Serve at `/api/v1/transit/gtfs-rt/vehicle_positions.pb`
- [ ] Serve at `/api/v1/transit/gtfs-rt/trip_updates.pb`
- [ ] Test with GTFS-RT validator tool
- [ ] Register on PIETURAS / Mobility Database as a data provider

**Phase 2 Validation:**
- [ ] All 6+ Latvian cities with real-time data visible on map
- [ ] Trains visible alongside buses
- [ ] ETAs showing at stops where real-time data exists
- [ ] System survives individual feed outages
- [ ] Combined GTFS-RT feed validates correctly

---

## Phase 3: Intercity Gap-Fill (Weeks 9-16)

**Deliverable: Intercity buses tracked + journey planning**

### Weeks 9-10: OwnTracks Integration (Quick Win)
- [ ] Deploy Mosquitto MQTT broker (Docker)
- [ ] Build MQTT listener: subscribe to OwnTracks position topics
- [ ] Build admin UI: assign phone → driver → vehicle → route
- [ ] Build normaliser: OwnTracks JSON → unified VehiclePosition
- [ ] Recruit 2-3 test drivers on intercity routes
- [ ] Test end-to-end: driver opens OwnTracks → position appears on map

### Weeks 11-12: Traccar Integration (Reliable Hardware)
- [ ] Deploy Traccar server (Docker)
- [ ] Configure Traccar to accept Teltonika Codec 8/8E on TCP port
- [ ] Build Traccar → VTV bridge: poll Traccar REST API for positions
- [ ] Order 3-5 Teltonika FMB920 devices for testing
- [ ] Install on test vehicles, verify data flow
- [ ] Document installation procedure for operators

### Weeks 13-14: OpenTripPlanner (Journey Planning)
- [ ] Deploy OpenTripPlanner with Latvia GTFS + OSM data
- [ ] Build VTV API proxy: `/api/v1/transit/plan?from=&to=&time=`
- [ ] Integrate real-time delay data into OTP (GTFS-RT trip updates)
- [ ] Build journey planner UI in CMS frontend
- [ ] Test multi-modal journeys: walk → bus → train → walk

### Weeks 15-16: Polish & LocShare Feature
- [ ] Build LocShare-style shareable tracking links
  - Generate signed JWT with vehicle_id + expiry
  - Public page shows vehicle position + route on map
  - No auth required to view shared link
- [ ] Build historical analytics views (delay patterns, route performance)
- [ ] Build operator contact list for data-sharing outreach
- [ ] Document API for third-party developers

**Phase 3 Validation:**
- [ ] At least 1 intercity route has live tracking
- [ ] Journey planner returns multi-modal routes
- [ ] Shareable tracking links work without login
- [ ] Analytics show delay patterns per route

---

## Phase 4: Intelligence (Ongoing)

- [ ] ML-based ETA prediction (train on 90+ days of TimescaleDB history)
- [ ] Anomaly detection alerts (off-route, stuck, GPS gap)
- [ ] Passenger load estimation (integrate e-ticket data from data.gov.lv)
- [ ] Route performance dashboards in CMS
- [ ] Schedule adherence monitoring with alerts
- [ ] Public developer API with API keys
- [ ] Mobile app (React Native)
- [ ] Import Rīgas Satiksme historical GTFS archive (64 monthly snapshots, May 2018–Jan 2026) for ML training data and route change analysis

### Historical GTFS Archive (ML Training Data)

Rīgas Satiksme publishes monthly GTFS snapshots on data.gov.lv. **64 months of schedule history** are available:

```
Dataset: Maršrutu saraksti Rīgas Satiksme sabiedriskajam transportam
URL:     https://data.gov.lv/dati/lv/dataset/marsrutu-saraksti-rigas-satiksme-sabiedriskajam-transportam
License: CC0 1.0 (public domain)
Format:  ZIP (GTFS txt files inside)
Span:    May 2018 → January 2026
Count:   64 monthly snapshots
Note:    NOT queryable via CKAN SQL API (datastore_active: false) — download only

Latest:  resource_id=fbd47952-a316-4d42-b8f2-9bd1ad30bc5f (Jan 2026)
```

**Use cases for historical archive:**
- Train ML ETA model on seasonal schedule variations (summer vs winter routes)
- Detect route changes over time (new stops, removed routes, frequency changes)
- Compare scheduled vs actual arrival times (combine with TimescaleDB real-time history)
- Validate schedule adherence trends across years

**Note:** For current schedule data, use `saraksti.rigassatiksme.lv/gtfs.zip` (always latest) — it's the same data but without needing to find the right month's resource ID.

### E-Ticket Validation Data (Passenger Load ML)

The single most valuable ML dataset. **Every e-ticket tap-on in Riga since 2018** — which vehicle, which route, which direction, what time. Combined with GPS positions, this predicts bus crowding.

```
Dataset: E-talonu validāciju dati Rīgas Satiksme sabiedriskajos transportlīdzekļos
URL:     https://data.gov.lv/dati/lv/dataset/e-talonu-validaciju-dati-rigas-satiksme-sabiedriskajos-transportlidzeklos
License: CC0 1.0 (public domain)
Format:  Monthly ZIPs containing daily TXT files
Span:    May 2018 → January 2026
Count:   67 monthly archives
Size:    ~100 MB compressed / ~700 MB uncompressed per month (~6.5 GB total compressed, ~45 GB uncompressed)

Fields per record:
- Ier_ID:           Record ID
- Parks:            Depot affiliation
- TranspVeids:      Vehicle type (bus/tram/trolleybus)
- GarNr:            Vehicle board number
- MarsrNos:         Route name
- TMarsruts:        Route number with transport type code
- Virziens:         Direction (outbound/inbound)
- ValidTalonaId:    E-ticket validation ID
- Laiks:            Timestamp of tap-on

Latest: resource_id=2272d3af-f8f2-4cf0-8430-1d796fd0b37b (Jan 2026, 100 MB)
```

**ML use cases:**
- **Passenger load prediction:** "Bus 22 at 08:15 on Monday typically has 47 passengers by Brīvības bulvāris"
- **Demand forecasting:** Seasonal, daily, hourly ridership patterns per route
- **Crowding alerts:** Predict which buses will be over-capacity before they arrive
- **Route optimization:** Identify underserved routes (high demand, low frequency)
- **Transfer pattern analysis:** Where do passengers switch routes?
- **Agent intelligence:** "Which bus to Mežaparks will be least crowded right now?"

### Weather Data (Delay Prediction ML)

Weather directly impacts bus speeds. Rain = +15% delay, snow = +40% delay. Two sources available:

```
Dataset 1: Hidrometeoroloģiskie novērojumi (Meteorological Observations)
URL:      https://data.gov.lv/dati/dataset/hidrometeorologiskie-noverojumi
License:  CC0 1.0
Format:   CSV (continuously updated)
Coverage: All Latvia weather stations, last 365 days archive + live hourly data

Resources:
- meteo_operativie_dati.csv    → Last 48 hours, hourly readings (LIVE)
- meteo_arhiva_dati_fakt.csv   → Last 365 days, actual measurements
- meteo_arhiva_dati_max.csv    → Last 365 days, AVG/MIN/MAX aggregates
- meteo_stacijas.csv           → Station locations (lat/lon for spatial join)
- meteo_parametri.csv          → Parameter definitions (temp, wind, precip, etc.)
- laika_operativie_dati.csv    → Weather phenomena last 48h (fog, ice, storm)
- laika_arhiva_dati.csv        → Weather phenomena last 365 days

Dataset 2: Aktuālie ceļu meteoroloģisko staciju dati (Road Weather Stations)
URL:      https://data.gov.lv/dati/lv/dataset/aktualie-celu-meteorologisko-staciju-dati
Format:   ArcGIS REST MapService (real-time)
Coverage: Road surface conditions along Latvian highways
```

**ML use cases:**
- **Weather-adjusted ETA:** Increase predicted delay when rain/snow/fog detected
- **Agent context:** "Buses running ~10 minutes late across Riga due to heavy snowfall"
- **Seasonal model calibration:** Train on weather + delay correlations across 365 days

### Traffic Accident Data (Route Risk ML)

```
Dataset: Ceļu satiksmes negadījumu notikuma vietu dati
URL:     https://data.gov.lv/dati/eng/dataset/giswebcais
License: CC0 1.0
Format:  CSV (annual update)
Span:    2013 → present
File:    cais_dati.csv (resource_id=a26832fc-ad60-4aa6-aa68-2f1442732450)

Contains: Accident locations, fatalities, injuries, violations, black spots
```

**ML use cases:**
- **Delay prediction near accident hotspots:** Routes through frequent accident zones → higher delay variance
- **Agent safety context:** "Route through Brīvības/Čaka intersection has elevated accident risk"

### Traffic Count Data (Congestion ML)

```
Dataset: Satiksmes uzskaites dati (Traffic Counting Points)
URL:     https://data.gov.lv/dati/lv/dataset/satiksmes-uzskaites-dati
License: CC0 1.0
Format:  CSV (continuously updated from data.lvceli.lv)
Span:    2011 → present

Resources:
- avg_traffic_data_day.csv   → https://data.lvceli.lv/maps/csv/avg_traffic_data_day.csv
- avg_traffic_data_week.csv  → https://data.lvceli.lv/maps/csv/avg_traffic_data_week.csv

Dataset 2: Gada vidējā satiksmes intensitāte (Annual Average Traffic Intensity)
URL:     https://data.gov.lv/dati/lv/dataset/gada-videja-satiksmes-intensitate
Span:    2008 → 2023 (15 years)
```

**ML use cases:**
- **Congestion-adjusted ETA:** Traffic count spikes at counting points near bus route → predict delay
- **Seasonal traffic patterns:** Summer tourist routes vs. winter commuter routes
- **Long-term demand trends:** 15 years of traffic intensity for forecasting

### Population Data (Demand Modeling)

```
Dataset: Latvijas iedzīvotāju skaits pašvaldībās
URL:     https://data.gov.lv/dati/lv/dataset/latvijas-iedzivotaju-skaits-pasvaldibas
License: CC0 1.0
Format:  CSV
Source:  Fizisko personu reģistrs (Population register)
```

**ML use cases:**
- **Route demand modeling:** Population density × stop proximity → expected ridership
- **Service coverage analysis:** Identify underserved areas

### Complete ML Data Inventory

| Dataset | Size | Time Span | Update Freq | ML Priority |
|---------|------|-----------|-------------|:-----------:|
| **E-ticket validations** | ~6.5 GB (67 ZIPs) | 2018–2026 | Monthly | **Critical** |
| **Historical GTFS schedules** | ~64 ZIPs | 2018–2026 | Monthly | **Critical** |
| **Weather observations** | CSV (~365 days) | Rolling year + live | Hourly | **High** |
| **Road weather stations** | REST API (live) | Real-time | Continuous | **High** |
| **Traffic counts** | CSV | 2011–present | Daily/weekly | **Medium** |
| **Traffic accidents** | CSV | 2013–present | Annual | **Medium** |
| **Annual traffic intensity** | CSV | 2008–2023 | Annual | **Low** |
| **Population by municipality** | CSV | Current | Annual | **Low** |
| **TimescaleDB vehicle positions** | (our own) | Phase 1 onwards | Real-time | **Critical** |

**Total available training data: ~50+ GB of structured transit, weather, traffic, and passenger data spanning 2008–2026. All CC0 licensed. All free.**

### AI Agent Architecture: Agentic Tool-Use RAG

**Key insight: Traditional vector RAG is WRONG for structured transit data.** Embedding GPS coordinates, schedule tables, and stop_times into vectors destroys their relational structure. A query like "next bus from Liepāja to Ventspils after 5 PM" requires JOINs across trips → stop_times → stops with temporal filtering — no vector similarity search can do this.

#### Architecture: Typed SQL Tools + Selective Vector Augmentation

```
TARGET ARCHITECTURE (after Phase 1-2 infrastructure):

┌─────────────────────────────────────────────────┐
│                 VTV Pydantic AI Agent            │
│                                                  │
│   User: "Next bus from Liepāja to Ventspils?"   │
│                      ↓                           │
│            Tool Selection (LLM decides)          │
│         ↙        ↓         ↓          ↘         │
│   query_    find_nearby  get_realtime  search_   │
│   schedule  _stops()     _positions()  alerts()  │
│   ()                                             │
│     ↓          ↓            ↓            ↓       │
│  PostgreSQL  PostGIS     Redis Cache   pgvector  │
│  SQL query   ST_DWithin  GET/HGETALL   cosine    │
│     ↓          ↓            ↓            ↓       │
│         Structured Results → LLM → Natural       │
│                Language Response                  │
└─────────────────────────────────────────────────┘

CURRENT ARCHITECTURE (what works today):

┌─────────────────────────────────────────────────┐
│                 VTV Pydantic AI Agent            │
│                 (10 tools registered)            │
│                      ↓                           │
│            Tool Selection (LLM decides)          │
│     ↙       ↓         ↓        ↓       ↘       │
│  query_   search_   get_route  get_    search_  │
│  bus_     stops()   schedule() adher.  knowledge│
│  status()                      report  _base()  │
│     ↓       ↓         ↓        ↓       ↓       │
│  GTFS-RT  In-mem    In-mem   GTFS-RT  pgvector │
│  protobuf  cache    cache    + cache  + FTS    │
│  (20s TTL) (24h)   (24h)    merge     hybrid   │
│     ↓       ↓         ↓        ↓       ↓       │
│         Structured Results → LLM → Natural       │
│                Language Response                  │
└─────────────────────────────────────────────────┘
```

#### Why NOT Vector RAG

| Problem | Why Vector RAG Fails |
|---------|---------------------|
| Schedule lookup | Can't execute `WHERE departure_time > '17:00'` — needs SQL |
| Route planning | Can't JOIN trips → stop_times → stops → calendar |
| Nearby stops | PostGIS `ST_DWithin(geog, point, 500)` is exact; cosine similarity on lat/lon embeddings is meaningless |
| Real-time positions | 10-second update cycle incompatible with embedding index rebuild |
| Aggregations | Can't `GROUP BY route_id, hour` for delay analysis |
| Passenger load | Can't correlate e-ticket counts with time windows |

#### Pydantic AI Agent Tools

> **Current state:** 10 tools already implemented (see `app/core/agents/agent.py`).
> The tools below show the TARGET architecture with database-backed queries.
> Current tools use in-memory GTFS cache; these will migrate to PostgreSQL when GTFS tables exist.

```python
# EXISTING TOOLS (10 tools, working today):
#
# Transit (5) — in app/core/agents/tools/transit/:
#   1. query_bus_status      — vehicle delay/position (3 actions: status, route_overview, stop_departures)
#   2. get_route_schedule    — timetable queries by route/date/direction/time window
#   3. search_stops          — search by name or proximity (Haversine, not PostGIS)
#   4. get_adherence_report  — on-time performance metrics
#   5. check_driver_availability — driver staffing queries (mock data, Phase 2: CMS API)
#
# Obsidian vault (4) — in app/core/agents/tools/obsidian/:
#   6. obsidian_query_vault      — search, find_by_tags, list, recent, glob
#   7. obsidian_manage_notes     — CRUD + frontmatter/section editing
#   8. obsidian_manage_folders   — folder CRUD with confirm guards
#   9. obsidian_bulk_operations  — batch ops with dry_run
#
# Knowledge base (1) — in app/core/agents/tools/knowledge/:
#   10. search_knowledge_base    — RAG search (pgvector hybrid + fulltext + reranker)
#
# UPGRADE PATH (when GTFS database tables and Redis are built):
#
# - query_bus_status → migrate from GTFS-RT on-demand fetch to Redis cache
# - get_route_schedule → migrate from in-memory static_cache to PostgreSQL queries
# - search_stops → migrate from in-memory Haversine to PostGIS ST_DWithin
# - get_adherence_report → add TimescaleDB historical analysis
#
# NEW TOOLS TO BUILD (Phase 2-4):

@agent.tool
async def query_schedule(
    origin_stop: str,
    destination_stop: str,
    after_time: str | None = None,
    date: str | None = None
) -> list[ScheduleResult]:
    """Find trips between two stops. Queries gtfs_stop_times + gtfs_trips."""
    # → PostgreSQL JOIN query with time/calendar filtering
    # → Replaces current get_route_schedule for cross-feed queries

@agent.tool
async def get_realtime_positions(
    route_id: str | None = None,
    operator: str | None = None,
    bounds: tuple[float, float, float, float] | None = None
) -> list[VehiclePosition]:
    """Get current vehicle positions from Redis cache."""
    # → Redis HGETALL with optional filtering
    # → Extends current query_bus_status with multi-feed + bounds support

@agent.tool
async def query_route_delays(
    route_id: str,
    time_range: str = "7d"
) -> DelayAnalysis:
    """Analyze delay patterns for a route using historical data."""
    # → TimescaleDB query on vehicle_positions hypertable
    # → Materialized view: avg delay by stop, hour, day-of-week

@agent.tool
async def predict_passenger_load(
    route_id: str,
    direction: str,
    time: str
) -> LoadPrediction:
    """Predict crowding level using trained ML model."""
    # → ML model inference (e-ticket trained)

@agent.tool
async def run_analytics_sql(
    sql: str
) -> list[dict]:
    """Execute validated read-only SQL for complex analytics queries."""
    # → Text-to-SQL with schema validation
    # → Only SELECT allowed, query plan cost limit
    # → Schema examples retrieved from pgvector (Schema RAG)
```

#### Where pgvector IS Used (Narrow, Targeted)

pgvector is valuable for **unstructured text** where exact keyword matching fails:

| Use Case | What Gets Embedded | Why |
|----------|-------------------|-----|
| **Service alerts** | Alert text ("Tramvaja līnija 6 nedarbojas") | Users ask "any disruptions today?" — semantic match needed |
| **Schema RAG for Text-to-SQL** | Table descriptions + example SQL queries | When `run_analytics_sql` is called, retrieve similar query examples to improve SQL generation accuracy |
| **Policy/documentation** | Operator contact info, fare rules, accessibility info | "Can I bring a bike on bus 22?" → policy doc retrieval |
| **Stop name fuzzy matching** | Embedded stop names + aliases | "Bus stop near the big market" → semantic match to "Centrāltirgus" |

```python
# pgvector setup — same PostgreSQL, no separate vector DB
# Extension: CREATE EXTENSION vector;

# Table: schema_examples (for Text-to-SQL augmentation)
# - id, question_text (embedded), sql_query, description
# - ~200-500 curated examples covering common transit queries
# - Retrieved at inference time to improve SQL generation

# Table: service_alerts (for disruption queries)
# - id, alert_text (embedded), route_ids, active_from, active_until
# - Updated from GTFS-RT service alerts feed

# Table: transit_docs (for policy/FAQ queries)
# - id, content (embedded), category, source
# - Fare rules, accessibility info, operator policies
```

#### Redis for Real-Time Layer

> **Current state: NOT YET BUILT.** Today, vehicle positions are fetched on-demand from GTFS-RT feeds
> with a 20-second in-memory Python cache (`app/core/agents/tools/transit/client.py`).
> Redis is needed when scaling to multi-feed (500+ vehicles) and WebSocket streaming.

```
TARGET data flow (NOT in PostgreSQL for reads):

GTFS-RT Poller → Redis HSET vehicle:{id} → Redis PUB transit:updates
                                          → WebSocket broadcast to clients
                                          → Agent tool reads from Redis

CURRENT data flow (Riga only, simple):
HTTP request → GTFSRealtimeClient.get_vehicle_positions() → 20s memory cache → response

Why Redis is needed for the target architecture:
- 10-second update cycle across 500+ vehicles = 3000 writes/min
- Agent needs sub-millisecond reads for "where is bus 22 right now?"
- Redis TTL auto-expires stale vehicles (no cleanup queries needed)
- PostgreSQL TimescaleDB stores historical positions (batch inserts every 30s)
- Pub/sub enables WebSocket broadcast without polling the database
```

#### Technology Stack Summary

| Component | Technology | Status | Purpose |
|-----------|-----------|--------|---------|
| Agent framework | Pydantic AI | **DONE** | Typed tools, dependency injection, native async |
| Structured queries | PostgreSQL + PostGIS | **PostgreSQL DONE, PostGIS NEEDED** | GTFS data, spatial queries, schedule lookups |
| Time-series | TimescaleDB | **Phase 2** | Historical vehicle positions, delay analysis |
| Vector search | pgvector (in same PostgreSQL) | **DONE** | RAG search, alerts, fuzzy stop names |
| Real-time cache | Redis | **NEEDED (Phase 1)** | Latest vehicle positions, pub/sub |
| Text-to-SQL | LLM + Schema RAG | **Phase 4** | Complex analytics queries with example augmentation |
| ML inference | Trained models (scikit-learn/XGBoost) | **Phase 4** | ETA prediction, passenger load, delay factors |
| ML inference | Trained models (scikit-learn/XGBoost) | ETA prediction, passenger load, delay factors |

#### What We Avoid (Validated by Current Implementation)

- **No separate vector database** (Pinecone, Qdrant, Weaviate) — pgvector in same PostgreSQL ✅ (already using for RAG knowledge base)
- **No LangChain** — Pydantic AI with typed dependency injection ✅ (10 tools registered)
- **No embedding GPS coordinates** — spatial queries are exact math, not similarity ✅ (Haversine today, PostGIS target)
- **No embedding schedule tables** — SQL/in-memory queries are deterministic ✅ (static_cache.py today, PostgreSQL target)
- **No full RAG pipeline for structured data** — tool-use is 3x more accurate (TransitGPT research, 2025) ✅ (all transit tools use typed queries)

### Phase 4 Implementation Order

1. **ETA model (Month 1):** TimescaleDB history + GTFS schedules → predict delay per stop
2. **Weather adjustment (Month 2):** Add weather observations → improve ETA in bad conditions
3. **Passenger load model (Month 3):** E-ticket data + GTFS + time-of-day → crowding predictions
4. **Congestion factor (Month 4):** Traffic counts + road weather → refine speed estimates
5. **Agent intelligence (Month 5):** Wire all models into VTV agent as context-aware tools
6. **Schema RAG (Month 5):** Curate 200-500 example SQL queries, embed with pgvector for Text-to-SQL augmentation

---

## Dependencies to Add

### Python (pyproject.toml)
```
gtfs-realtime-bindings    # ALREADY INSTALLED — GTFS-RT protobuf parsing
httpx                     # ALREADY INSTALLED — async HTTP client (transit + obsidian clients)
pydantic-ai              # ALREADY INSTALLED — agent framework with typed tool-use
pgvector                  # ALREADY INSTALLED — Python client for pgvector extension
redis[hiredis]            # NEEDED — async Redis client (Phase 1 Week 2)
websockets                # NEEDED — WebSocket client for train data (Phase 2 Week 5)
gtfs-kit                  # OPTIONAL — GTFS static feed validation (current stdlib csv works)
```

### Infrastructure (docker-compose.yml)
```
EXISTING:
  db:           pgvector/pgvector:pg18       (PostgreSQL 18 + pgvector)
  app:          FastAPI (uvicorn)
  cms:          Next.js 16
  nginx:        nginx:1.27-alpine

NEEDED (Phase 1):
  redis:        redis:7-alpine

NEEDED (Phase 2-3):
  valhalla:     ghcr.io/gis-ops/valhalla:latest (Phase 2 - route matching)
  traccar:      traccar/traccar:latest           (Phase 3 - GPS hardware)
  mosquitto:    eclipse-mosquitto:2              (Phase 3 - OwnTracks MQTT)
  otp:          opentripplanner/opentripplanner   (Phase 3 - journey planning)
```

### PostgreSQL Extensions
```
pgvector      INSTALLED — vector embeddings for RAG knowledge base, future Schema RAG
PostGIS       NEEDED (Phase 1) — spatial queries (switch to postgis/postgis:18-3.5 image)
TimescaleDB   NEEDED (Phase 2) — time-series hypertables for historical positions
```

### Frontend (package.json)
```
leaflet                   # ALREADY INSTALLED — map rendering (^1.9.4)
react-leaflet             # ALREADY INSTALLED — React wrapper (^5.0.0)
@types/leaflet            # ALREADY INSTALLED — TypeScript types (^1.9.21)
leaflet.markercluster     # NEEDED — clustering for zoom-out with 500+ markers
```

---

## Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| Operator feeds go offline permanently | High | Low | Multiple source fallbacks, PIETURAS combined feed as backup |
| Feed format changes without notice | Medium | Medium | Schema validation on ingest, alert on parse failures |
| TimescaleDB storage grows too fast | Medium | Medium | Compression policy + 90-day retention + rollups |
| Operators block our polling | High | Low | Respect rate limits, add User-Agent, contact if issues |
| No driver adoption for OwnTracks | Medium | High | Fall back to Teltonika hardware (Option B) |
| Teltonika hardware denied by operators | Medium | Medium | Pursue data-sharing agreements instead |
| WebSocket scaling issues | Medium | Low | Redis pub/sub + horizontal FastAPI workers |

---

## Success Metrics

| Metric | Phase 1 Target | Phase 2 Target | Phase 3 Target |
|--------|:-------------:|:-------------:|:-------------:|
| Live vehicles on map | 200+ (Rīga) | 400+ (all cities) | 500+ (+ intercity) |
| Feed uptime | 95% | 99% | 99.5% |
| Position update latency | <15s | <10s | <5s (own hardware) |
| WebSocket clients supported | 10 | 50 | 200 |
| Stop departure accuracy | Operator-provided | Own ETAs ±2min | ML ETAs ±1min |
| Cities with real-time | 1 (Rīga) | 6+ | 6+ plus intercity |
