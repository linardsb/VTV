# GTFS & Transit CMS Research
## Comprehensive Technical Reference for City Bus Operations

**Date:** 2026-02-11
**Scope:** GTFS specification, real-time tracking, Rigas Satiksme data, transit CMS features, EU compliance, open-source tools, live mapping technologies

---

## Table of Contents

1. [GTFS Static Format](#1-gtfs-static-format)
2. [GTFS Realtime](#2-gtfs-realtime)
3. [Rigas Satiksme Data & APIs](#3-rigas-satiksme-data--apis)
4. [Transit CMS Features](#4-transit-cms-features)
5. [EU/GDPR Compliance for Transit](#5-eugdpr-compliance-for-transit)
6. [Open Source Transit Tools](#6-open-source-transit-tools)
7. [Live Tracking Map Technologies](#7-live-tracking-map-technologies)

---

## 1. GTFS Static Format

**Specification:** https://gtfs.org/documentation/schedule/reference/
**Format:** ZIP archive containing CSV-like `.txt` files (comma-delimited, UTF-8 encoded)

### 1.1 File Overview

| File | Status | Purpose |
|------|--------|---------|
| `agency.txt` | **Required** | Transit agencies with service represented in dataset |
| `stops.txt` | **Conditionally Required** | Stops, stations, station entrances, generic nodes, boarding areas |
| `routes.txt` | **Required** | Transit routes (a route is a group of trips displayed as a single service) |
| `trips.txt` | **Required** | Trips for each route (a trip is a sequence of stops at specific times) |
| `stop_times.txt` | **Required** | Times a vehicle arrives/departs from stops for each trip |
| `calendar.txt` | **Conditionally Required** | Service dates specified using weekly schedule with start/end dates |
| `calendar_dates.txt` | **Conditionally Required** | Exceptions for services defined in calendar.txt |
| `fare_attributes.txt` | Optional | Fare information for a transit agency's routes |
| `fare_rules.txt` | Optional | Rules to apply fares for itineraries |
| `timeframes.txt` | Optional | Date/time periods for fare rules |
| `fare_media.txt` | Optional | Fare media (tickets, smart cards, etc.) |
| `fare_products.txt` | Optional | Types of tickets or fares purchasable |
| `fare_leg_rules.txt` | Optional | Fare rules for individual legs of travel |
| `fare_transfer_rules.txt` | Optional | Fare rules for transfers between legs |
| `areas.txt` | Optional | Area grouping of locations |
| `stop_areas.txt` | Optional | Rules for assigning stops to areas |
| `networks.txt` | Optional | Network grouping of routes |
| `route_networks.txt` | Optional | Rules for assigning routes to networks |
| `shapes.txt` | Optional | Rules for mapping vehicle travel paths (route geometry) |
| `frequencies.txt` | Optional | Headway (time between trips) for headway-based service |
| `transfers.txt` | Optional | Rules for making connections at transfer points |
| `pathways.txt` | Optional | In-station pathways linking locations |
| `levels.txt` | Optional | Levels within stations |
| `translations.txt` | Optional | Translations of customer-facing dataset values |
| `feed_info.txt` | Optional | Dataset metadata (publisher, version, expiration) |
| `attributions.txt` | Optional | Dataset attributions |
| `locations.geojson` | Optional | Zone-based demand-responsive areas |

### 1.2 Core File Schemas

#### agency.txt (PK: agency_id)
```
agency_id           Unique ID               Conditionally Required
agency_name         Text                    Required
agency_url          URL                     Required
agency_timezone     Timezone (e.g. "Europe/Riga")  Required
agency_lang         Language code (e.g. "lv")      Optional
agency_phone        Phone number            Optional
agency_fare_url     URL                     Optional
agency_email        Email                   Optional
```

#### routes.txt (PK: route_id)
```
route_id            Unique ID               Required
agency_id           Foreign ID → agency.txt Conditionally Required
route_short_name    Text (e.g. "15")        Conditionally Required
route_long_name     Text (e.g. "Centrāltirgus - Jugla")  Conditionally Required
route_desc          Text                    Optional
route_type          Enum (see below)        Required
route_url           URL                     Optional
route_color         Color (hex, e.g. "FF0000")  Optional
route_text_color    Color (hex)             Optional
route_sort_order    Non-negative integer    Optional
continuous_pickup   Enum (0-3)              Conditionally Forbidden
continuous_drop_off Enum (0-3)              Conditionally Forbidden
network_id          ID                      Conditionally Forbidden
```

**route_type values (standard):**
| Value | Mode |
|-------|------|
| 0 | Tram, Streetcar, Light Rail |
| 1 | Subway, Metro |
| 2 | Rail (intercity/long-distance) |
| 3 | **Bus** |
| 4 | Ferry |
| 5 | Cable Tram |
| 6 | Aerial Lift (gondola, etc.) |
| 7 | Funicular |
| 11 | **Trolleybus** |
| 12 | Monorail |

**Extended route_type values (Google-defined, commonly used):**
| Range | Mode Category |
|-------|---------------|
| 100-199 | Railway Service |
| 200-299 | Coach Service |
| 400-499 | Urban Railway Service |
| 700-799 | **Bus Service** (700=generic, 702=express, 704=local) |
| 800-899 | **Trolleybus Service** |
| 900-999 | **Tram Service** |

#### trips.txt (PK: trip_id)
```
route_id            Foreign ID → routes.txt Required
service_id          Foreign ID → calendar.txt  Required
trip_id             Unique ID               Required
trip_headsign       Text (e.g. "Jugla")     Optional
trip_short_name     Text                    Optional
direction_id        Enum (0 or 1)           Optional
block_id            ID (links trips sharing a vehicle)  Optional
shape_id            Foreign ID → shapes.txt Conditionally Required
wheelchair_accessible  Enum (0/1/2)         Optional
bikes_allowed       Enum (0/1/2)            Optional
```

#### stops.txt (PK: stop_id)
```
stop_id             Unique ID               Required
stop_code           Text (passenger-facing) Optional
stop_name           Text                    Conditionally Required
tts_stop_name       Text (TTS pronunciation) Optional
stop_desc           Text                    Optional
stop_lat            Latitude (WGS-84)       Conditionally Required
stop_lon            Longitude (WGS-84)      Conditionally Required
zone_id             ID (fare zone)          Optional
stop_url            URL                     Optional
location_type       Enum (see below)        Optional
parent_station      Foreign ID → stops.txt  Conditionally Required
stop_timezone       Timezone                Optional
wheelchair_boarding Enum (0/1/2)            Optional
level_id            Foreign ID → levels.txt Optional
platform_code       Text                    Optional
```

**location_type values:**
| Value | Type |
|-------|------|
| 0/blank | Stop/Platform |
| 1 | Station (contains stops) |
| 2 | Entrance/Exit |
| 3 | Generic Node (pathway intersections) |
| 4 | Boarding Area |

#### stop_times.txt (PK: trip_id + stop_sequence)
```
trip_id             Foreign ID → trips.txt  Required
arrival_time        Time (HH:MM:SS, can exceed 24h)  Conditionally Required
departure_time      Time (HH:MM:SS)         Conditionally Required
stop_id             Foreign ID → stops.txt  Conditionally Required
stop_sequence       Non-negative integer    Required
stop_headsign       Text                    Optional
pickup_type         Enum (0-3)              Conditionally Forbidden
drop_off_type       Enum (0-3)              Conditionally Forbidden
continuous_pickup   Enum (0-3)              Conditionally Forbidden
continuous_drop_off Enum (0-3)              Conditionally Forbidden
shape_dist_traveled Non-negative float      Optional
timepoint           Enum (0/1)              Optional
```

**Note on times:** Values like "25:30:00" represent 1:30 AM the next day, enabling trips that span midnight.

#### calendar.txt (PK: service_id)
```
service_id          Unique ID               Required
monday              Enum (0/1)              Required
tuesday             Enum (0/1)              Required
wednesday           Enum (0/1)              Required
thursday            Enum (0/1)              Required
friday              Enum (0/1)              Required
saturday            Enum (0/1)              Required
sunday              Enum (0/1)              Required
start_date          Date (YYYYMMDD)         Required
end_date            Date (YYYYMMDD)         Required
```

#### calendar_dates.txt (PK: service_id + date)
```
service_id          Foreign ID              Required
date                Date (YYYYMMDD)         Required
exception_type      Enum: 1=added, 2=removed  Required
```

#### shapes.txt (PK: shape_id + shape_pt_sequence)
```
shape_id            Unique ID               Required
shape_pt_lat        Latitude (WGS-84)       Required
shape_pt_lon        Longitude (WGS-84)      Required
shape_pt_sequence   Non-negative integer    Required
shape_dist_traveled Non-negative float      Optional
```

#### frequencies.txt (PK: trip_id + start_time)
```
trip_id             Foreign ID → trips.txt  Required
start_time          Time                    Required
end_time            Time                    Required
headway_secs        Positive integer (seconds between departures)  Required
exact_times         Enum: 0=frequency-based, 1=schedule-based  Optional
```

### 1.3 Entity Relationship Diagram

```
agency.txt ──(1:N)──> routes.txt ──(1:N)──> trips.txt ──(1:N)──> stop_times.txt
                                                │                       │
                                                │                       └──> stops.txt
                                                │
                                                ├──> calendar.txt / calendar_dates.txt
                                                │
                                                └──> shapes.txt

stops.txt ←──(parent_station)── stops.txt  (self-referencing hierarchy)

fare_attributes.txt ──> fare_rules.txt ──> routes.txt / stops.txt (zones)
```

**Key relationships:**
- A **route** belongs to an **agency** and has many **trips**
- A **trip** follows a **service** schedule and an optional **shape**
- A **trip** has an ordered sequence of **stop_times** at **stops**
- **calendar** + **calendar_dates** define when a **service** operates
- **shapes** provide the geographic path a trip follows on a map

---

## 2. GTFS Realtime

**Specification:** https://gtfs.org/documentation/realtime/reference/
**Format:** Protocol Buffers (binary serialization)
**Proto file:** https://github.com/google/transit/blob/master/gtfs-realtime/proto/gtfs-realtime.proto

### 2.1 Protocol Buffers Overview

GTFS-RT uses Google Protocol Buffers for efficient binary serialization. The `.proto` file defines the message structure, and libraries are auto-generated for any language (Java, Python, JavaScript, Go, C#, etc.).

```protobuf
// Top-level container
message FeedMessage {
  required FeedHeader header = 1;
  repeated FeedEntity entity = 2;
}

message FeedHeader {
  required string gtfs_realtime_version = 1;  // Currently "2.0"
  optional Incrementality incrementality = 2;  // FULL_DATASET or DIFFERENTIAL
  optional uint64 timestamp = 3;               // POSIX time
}

message FeedEntity {
  required string id = 1;
  optional bool is_deleted = 2;
  optional TripUpdate trip_update = 3;
  optional VehiclePosition vehicle = 4;
  optional Alert alert = 5;
  optional Shape shape = 6;           // Experimental
  optional Stop stop = 7;             // Experimental
  optional TripModifications trip_modifications = 8; // Experimental
}
```

### 2.2 Feed Types

#### TripUpdate — Real-time arrival/departure predictions

```protobuf
message TripUpdate {
  required TripDescriptor trip = 1;
  optional VehicleDescriptor vehicle = 3;
  repeated StopTimeUpdate stop_time_update = 2;
  optional uint64 timestamp = 4;
  optional int32 delay = 5;  // Seconds (positive = late, negative = early)

  message StopTimeUpdate {
    optional uint32 stop_sequence = 1;
    optional string stop_id = 4;
    optional StopTimeEvent arrival = 2;
    optional StopTimeEvent departure = 3;
    optional ScheduleRelationship schedule_relationship = 5;

    enum ScheduleRelationship {
      SCHEDULED = 0;
      SKIPPED = 1;
      NO_DATA = 2;
      UNSCHEDULED = 3;
    }
  }

  message StopTimeEvent {
    optional int32 delay = 1;      // Seconds relative to schedule
    optional int64 time = 2;       // Absolute POSIX time
    optional int32 uncertainty = 3; // Seconds of uncertainty
  }
}
```

**Use case:** Predict when buses will arrive at stops. Each TripUpdate links to a static GTFS trip via `trip_id` and provides predicted arrival/departure times for upcoming stops.

#### VehiclePosition — Real-time vehicle locations

```protobuf
message VehiclePosition {
  optional TripDescriptor trip = 1;
  optional VehicleDescriptor vehicle = 8;
  optional Position position = 2;
  optional uint32 current_stop_sequence = 3;
  optional string stop_id = 7;
  optional VehicleStopStatus current_status = 4;
  optional uint64 timestamp = 5;
  optional CongestionLevel congestion_level = 6;
  optional OccupancyStatus occupancy_status = 9;

  enum VehicleStopStatus {
    INCOMING_AT = 0;    // Approaching the stop
    STOPPED_AT = 1;     // At the stop
    IN_TRANSIT_TO = 2;  // Left previous stop, heading to next
  }

  enum CongestionLevel {
    UNKNOWN_CONGESTION_LEVEL = 0;
    RUNNING_SMOOTHLY = 1;
    STOP_AND_GO = 2;
    CONGESTION = 3;
    SEVERE_CONGESTION = 4;
  }

  enum OccupancyStatus {
    EMPTY = 0;
    MANY_SEATS_AVAILABLE = 1;
    FEW_SEATS_AVAILABLE = 2;
    STANDING_ROOM_ONLY = 3;
    CRUSHED_STANDING_ROOM_ONLY = 4;
    FULL = 5;
    NOT_ACCEPTING_PASSENGERS = 6;
    NO_DATA_AVAILABLE = 7;
    NOT_BOARDABLE = 8;
  }
}

message Position {
  required float latitude = 1;    // WGS-84
  required float longitude = 2;   // WGS-84
  optional float bearing = 3;     // Degrees clockwise from North (0-360)
  optional double odometer = 4;   // Meters
  optional float speed = 5;       // Meters per second
}
```

**Use case:** Show buses on a map in real time. Poll the vehicle_positions endpoint every 10-30 seconds.

#### Alert — Service alerts and disruptions

```protobuf
message Alert {
  repeated TimeRange active_period = 1;
  repeated EntitySelector informed_entity = 5;
  optional Cause cause = 6;
  optional Effect effect = 7;
  optional TranslatedString url = 8;
  optional TranslatedString header_text = 10;
  optional TranslatedString description_text = 11;
  optional SeverityLevel severity_level = 14;

  enum Cause {
    UNKNOWN_CAUSE = 1;
    OTHER_CAUSE = 2;
    TECHNICAL_PROBLEM = 3;
    STRIKE = 4;
    DEMONSTRATION = 5;
    ACCIDENT = 6;
    HOLIDAY = 7;
    WEATHER = 8;
    MAINTENANCE = 9;
    CONSTRUCTION = 10;
    POLICE_ACTIVITY = 11;
    MEDICAL_EMERGENCY = 12;
  }

  enum Effect {
    NO_SERVICE = 1;
    REDUCED_SERVICE = 2;
    SIGNIFICANT_DELAYS = 3;
    DETOUR = 4;
    ADDITIONAL_SERVICE = 5;
    MODIFIED_SERVICE = 6;
    OTHER_EFFECT = 7;
    UNKNOWN_EFFECT = 8;
    STOP_MOVED = 9;
    NO_EFFECT = 10;
    ACCESSIBILITY_ISSUE = 11;
  }

  enum SeverityLevel {
    UNKNOWN_SEVERITY = 1;
    INFO = 2;
    WARNING = 3;
    SEVERE = 4;
  }
}

message EntitySelector {
  optional string agency_id = 1;
  optional string route_id = 2;
  optional int32 route_type = 3;
  optional TripDescriptor trip = 4;
  optional string stop_id = 5;
  optional int32 direction_id = 6;
}
```

### 2.3 Common Descriptors

```protobuf
message TripDescriptor {
  optional string trip_id = 1;
  optional string route_id = 5;
  optional uint32 direction_id = 6;
  optional string start_time = 2;   // HH:MM:SS format
  optional string start_date = 3;   // YYYYMMDD format

  enum ScheduleRelationship {
    SCHEDULED = 0;
    ADDED = 1;        // Deprecated
    UNSCHEDULED = 2;
    CANCELED = 3;
    REPLACEMENT = 5;
    DUPLICATED = 6;
    DELETED = 7;      // Experimental
    NEW = 8;          // Experimental
  }
}

message VehicleDescriptor {
  optional string id = 1;             // Internal system identifier
  optional string label = 2;          // User-visible label
  optional string license_plate = 3;  // Vehicle registration plate
  optional WheelchairAccessible wheelchair_accessible = 4;
}
```

### 2.4 How Real-Time Tracking Works

**Architecture:**
```
[GPS on Bus] → [Onboard Unit] → [Central Server / AVL System]
                                        │
                                        ▼
                              [GTFS-RT Feed Generator]
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
            trip_updates.pb    vehicle_positions.pb    alerts.pb
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        ▼
                              [Consumer Applications]
                         (Maps, Apps, Passenger Info Displays)
```

**Polling pattern:**
1. Consumer fetches the `.pb` feed via HTTP GET (typically every 10-30 seconds)
2. Parses the Protocol Buffer binary response
3. Matches entities to static GTFS data via `trip_id`, `route_id`, `stop_id`
4. Updates UI (map markers, arrival predictions, alerts)

**Feed delivery options:**
- `FULL_DATASET` (most common): Each response contains the complete current state
- `DIFFERENTIAL`: Only changed entities since last fetch (less common, requires state management)

---

## 3. Rigas Satiksme Data & APIs

### 3.1 Static GTFS Feed

| Property | Value |
|----------|-------|
| **Download URL** | https://saraksti.rigassatiksme.lv/gtfs.zip |
| **Legacy URL** | https://saraksti.rigassatiksme.lv/riga/gtfs.zip |
| **Format** | Standard GTFS ZIP |
| **Update frequency** | Regularly updated (100+ versions archived) |
| **Service date range** | Oct 21, 2024 - Feb 1, 2027 (in latest version) |
| **Last verified** | February 7, 2026 |
| **Transitland ID** | f-ud1h-rigassatiksme |
| **Network** | 6 tram routes, 22 trolleybus routes, 52 bus routes |

### 3.2 GTFS Realtime Feeds

| Feed | URL | Format |
|------|-----|--------|
| **Combined (all data)** | `https://saraksti.rigassatiksme.lv/gtfs_realtime.pb` | Protocol Buffers |
| **Trip Updates** | `https://saraksti.rigassatiksme.lv/trip_updates.pb` | Protocol Buffers |
| **Vehicle Positions** | `https://saraksti.rigassatiksme.lv/vehicle_positions.pb` | Protocol Buffers |
| **Raw GPS** | `https://saraksti.rigassatiksme.lv/gps.txt` | Plain text |

### 3.3 Additional APIs

| Endpoint | Purpose | Format |
|----------|---------|--------|
| `https://saraksti.rigassatiksme.lv/siri-stop-departures.php?stopid={STOP_ID}` | Real-time departures for a specific stop (SIRI format) | XML/JSON |
| `https://saraksti.rigassatiksme.lv/departures2.php?stopid={STOP_ID}` | Alternative departures endpoint | JSON |
| `https://saraksti.lv/gpsdata.ashx?stopid={STOP_ID}` | GPS data for vehicles approaching a stop | Custom |
| `https://saraksti.lv/gpsdata.ashx?vehicleid={VEHICLE_ID}` | GPS data for a specific vehicle | Custom |

### 3.4 Additional Open Data

**E-ticket validation data:**
- URL: https://data.gov.lv/dati/lv/dataset/e-talonu-validaciju-dati-rigas-satiksme-sabiedriskajos-transportlidzeklos
- Content: Anonymized e-ticket registration data (park/depot, vehicle type, route name, direction, e-ticket ID)
- Format: Daily TXT files organized by time period
- License: Open data, freely usable

**Latvia Open Data Portal:**
- URL: https://data.gov.lv/dati/lv/dataset/marsrutu-saraksti-rigas-satiksme-sabiedriskajam-transportam
- Contains archived GTFS schedule data

### 3.5 Test/Development Endpoints

| Feed | URL |
|------|-----|
| Test GTFS static | https://stops.lt/rigatest/gtfs.zip |
| Test GTFS-RT | https://stops.lt/rigatest/gtfs_realtime.pb |
| Test GPS full | https://stops.lt/rigatest/gps_full.txt |

### 3.6 Mobile App

Rigas Satiksme provides an official mobile app with:
- Real-time vehicle positions on map
- Timetable viewing
- Arrival time predictions
- Route planning

---

## 4. Transit CMS Features

### 4.1 Core Module Breakdown

Professional transit management systems (Optibus, Trapeze, TripSpark, etc.) typically include:

#### Route Planning & Network Design
- Network topology editor with map-based route design
- Stop placement and catchment area analysis
- Route optimization algorithms (minimize deadhead, maximize coverage)
- Demand analysis (ridership patterns, origin-destination matrices)
- Scenario comparison (what-if analysis for route changes)
- GTFS import/export for interoperability

#### Schedule Management (Timetabling)
- Timetable creation with running times, layover, recovery time
- Frequency-based and schedule-based service patterns
- Calendar/service date management (weekday, weekend, holiday)
- Interlining (linking trips across routes for vehicle efficiency)
- Block building (assigning trips to vehicles to minimize fleet size)
- Time point management and schedule adherence targets

#### Vehicle Scheduling (Blocking)
- Vehicle assignment optimization (minimize fleet requirements)
- Deadheading optimization (non-revenue movements)
- Depot allocation (assign vehicles to garages)
- Vehicle type constraints (low-floor, articulated, electric range)
- Maintenance window integration
- Fuel/charging schedule coordination (critical for electric buses)

#### Crew/Driver Management (Rostering)
- Duty/run cutting (split blocks into driver shifts)
- Roster generation and optimization
- Labor rule compliance (max hours, break requirements, rest periods)
- Qualification tracking (license types, route certifications)
- Leave management and absence tracking
- Driver bidding/preference systems
- Payroll integration

#### Dispatch & Operations Control
- Real-time vehicle tracking (CAD/AVL)
- Schedule adherence monitoring (early/late detection)
- Headway management (bunching prevention)
- Incident management and response
- Driver communication (MDT - Mobile Data Terminals)
- Service adjustments on-the-fly (short-turns, express runs, deadhead)
- Passenger information updates
- Automatic passenger counting (APC) integration

#### Fleet Management
- Vehicle inventory and lifecycle tracking
- Preventive maintenance scheduling
- Work order management
- Parts inventory and procurement
- Fuel/energy consumption monitoring
- Inspection and compliance tracking (DOT, EU regulations)
- Warranty tracking

#### Passenger Information
- Real-time departure displays (at stops, online, in-app)
- Journey planning / trip planner
- Service alerts and disruption communication
- Occupancy/crowding information
- Accessibility information

#### Reporting & Analytics
- On-time performance (OTP) reports
- Ridership analytics
- Revenue and farebox data
- Driver performance metrics
- Fleet utilization and efficiency
- Cost per kilometer/passenger metrics
- Regulatory compliance reports

### 4.2 Industry-Standard Software Landscape

| System | Vendor | Strengths |
|--------|--------|-----------|
| **Optibus** | Optibus | Cloud-native, AI-optimized planning/scheduling/rostering |
| **Trapeze** | Modaxo (Trapeze Group) | Comprehensive CAD/AVL, scheduling, dispatch, paratransit |
| **TripSpark** | TripSpark | CAD/AVL, fixed-route & demand-response |
| **HASTUS** | GIRO | Industry standard for scheduling & rostering |
| **Remix** | Via | Network planning and transit design |
| **Passio** | Passio Technologies | CAD/AVL with real-time passenger info |
| **IVU.suite** | IVU Traffic Technologies | Planning, dispatch, ticketing (strong in EU) |
| **INIT** | INIT | Integrated planning, dispatch, ticketing, passenger info |
| **Modeshift** | Modeshift | CAD/AVL with analytics focus |

### 4.3 Technical Architecture Patterns

Modern transit CMS systems follow this general architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                    BACK OFFICE (Web UI)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Planning  │ │Scheduling│ │ Rostering│ │  Fleet Mgmt  │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    MIDDLEWARE / API LAYER                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │GTFS Mgmt │ │  Rules   │ │Optimizer │ │  Integration │   │
│  │ Engine   │ │  Engine  │ │  Engine  │ │    Layer     │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    REAL-TIME LAYER                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ CAD/AVL  │ │ GTFS-RT  │ │  Alert   │ │  Passenger   │   │
│  │ System   │ │Generator │ │  System  │ │  Info System │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
├─────────────────────────────────────────────────────────────┤
│                    DATA LAYER                                │
│  ┌──────────────────────┐ ┌──────────────────────────────┐  │
│  │  PostgreSQL/PostGIS  │ │ TimescaleDB / InfluxDB       │  │
│  │  (schedules, routes) │ │ (GPS telemetry, time-series) │  │
│  └──────────────────────┘ └──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    ONBOARD SYSTEMS                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │GPS/GNSS  │ │   MDT    │ │   APC    │ │  Farebox /   │   │
│  │Tracker   │ │(Driver UI)│ │(Counter) │ │  Validator   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. EU/GDPR Compliance for Transit

### 5.1 Key Regulations

#### GDPR (General Data Protection Regulation) - Regulation (EU) 2016/679
- **Applies to:** Any processing of personal data of EU residents
- **Penalties:** Up to EUR 20 million or 4% of worldwide annual turnover
- **Key article:** Article 6 - Lawfulness of processing (requires legal basis)

#### ePrivacy Directive (2002/58/EC, amended by 2009/136/EC)
- Applies to electronic communications, including location data from connected vehicles/devices
- Relevant when tracking GPS location of drivers through onboard devices

#### ITS Directive (2010/40/EU) + Delegated Regulation (EU) 2017/1926 (MMTIS)
- Requires Member States to set up National Access Points (NAPs) for multimodal travel data
- Amended by Delegated Regulation (EU) 2024/490 to mandate accessibility of dynamic travel data
- Latvia NAP: data.gov.lv
- Mandates data sharing in standardized formats (NeTEx, SIRI, GTFS accepted in practice)

#### Delegated Regulation (EU) 2024/490
- Extends MMTIS requirements to include real-time data types
- Requires accessibility information, bike carriage information
- Mandates data availability via National Access Points

### 5.2 Driver Data Compliance

**Data classified as personal data under GDPR:**
- Driver GPS location during shifts
- Driver identification and login records
- Driving behavior metrics (speed, braking, etc.)
- Work/rest time records
- Communication logs

**Requirements:**
| Requirement | Details |
|-------------|---------|
| **Legal basis** | Legitimate interest or employment contract necessity (Art. 6(1)(b) or (f)) |
| **Purpose limitation** | Track for operational purposes only (dispatch, scheduling), not surveillance |
| **Location during rest** | **Must NOT** record driver location during rest/break periods |
| **Private journeys** | **Must NOT** track when vehicle used for personal travel |
| **Data minimization** | Collect only what is necessary; no permanent position tracking beyond operational need |
| **Retention limits** | Define and enforce maximum retention periods (typically 30-90 days for GPS, longer for compliance records) |
| **Access control** | Only authorized personnel (dispatchers, management) can view driver data |
| **Transparency** | Drivers must be informed: what data, why, how long, who accesses it (Art. 13/14) |
| **DPIA** | Data Protection Impact Assessment required for systematic monitoring (Art. 35) |
| **DPO** | Data Protection Officer likely required for transit agencies |
| **Subject rights** | Drivers can request access, correction, deletion of their data |

### 5.3 Passenger Data Compliance

**Data classified as personal data:**
- E-ticket/smart card transaction data (can identify individuals even if "anonymized")
- Journey patterns (origin-destination pairs linked to a card)
- CCTV footage on vehicles/at stops
- Mobile app usage data
- Wi-Fi probe data (MAC addresses)

**Requirements:**
| Requirement | Details |
|-------------|---------|
| **Anonymization** | Rigas Satiksme already anonymizes e-ticket data before publication - this is the correct approach |
| **Pseudonymization** | For internal analytics, replace identifiers with pseudonyms |
| **Consent or legal basis** | For smart card data, typically legitimate interest with opt-out |
| **CCTV** | Must have signage, limited retention (typically 72h-30 days), DPIA required |
| **Real-time passenger info** | Aggregate data (vehicle occupancy) is fine; individual tracking is not |
| **Cookie consent** | Any web-based passenger info tools must comply with cookie regulations |

### 5.4 Real-Time Tracking Data

**Vehicle position data published via GTFS-RT:**
- Vehicle positions (lat/lon) are generally NOT personal data if they identify vehicles, not people
- However, if vehicle positions can be linked to specific drivers (through schedules), they become personal data
- **Recommendation:** Publish vehicle IDs/labels that cannot easily be linked to driver identity in public feeds

**Best practices:**
1. Separate public vehicle tracking from internal driver tracking systems
2. Vehicle IDs in GTFS-RT should be fleet numbers, not driver-linked
3. Real-time feeds should have reasonable update intervals (15-30s, not continuous)
4. Maintain audit logs of who accesses real-time operational data
5. Implement data retention policies for historical GPS data

### 5.5 Data Processing Records (Art. 30)

Transit agencies must maintain records of processing activities including:
- Categories of data subjects (drivers, passengers, staff)
- Categories of personal data
- Purposes of processing
- Recipients of data (including GTFS-RT consumers)
- Retention periods
- Technical and organizational security measures

---

## 6. Open Source Transit Tools

### 6.1 Trip Planning & Routing

| Tool | Language | Description | GitHub |
|------|----------|-------------|--------|
| **OpenTripPlanner (OTP)** | Java | Multi-modal trip planner (transit + walk + bike + car). Industry standard. Uses GTFS + OSM. REST API + GraphQL. | [opentripplanner/OpenTripPlanner](https://github.com/opentripplanner/OpenTripPlanner) |
| **Navitia** | C++/Python | Multi-modal journey planner with real-time support. Used by Kisio Digital. | [hove-io/navitia](https://github.com/hove-io/navitia) |
| **r5** | Java | Rapid Realistic Routing on Real-world and Reimagined networks. By Conveyal. Designed for accessibility analysis. | [conveyal/r5](https://github.com/conveyal/r5) |
| **MOTIS** | C++ | Multi Objective Travel Information System. Fast routing with real-time updates. | [motis-project/motis](https://github.com/motis-project/motis) |
| **Valhalla** | C++ | Open-source routing engine for road networks. Can be combined with transit. | [valhalla/valhalla](https://github.com/valhalla/valhalla) |

### 6.2 GTFS Validators & Quality Tools

| Tool | Language | Description | Link |
|------|----------|-------------|------|
| **MobilityData GTFS Validator** | Java | Canonical GTFS Schedule validator. The standard for quality checking. | [MobilityData/gtfs-validator](https://github.com/MobilityData/gtfs-validator) |
| **GTFS Realtime Validator** | Java | Validates GTFS-RT feeds against static GTFS and best practices. | [MobilityData/gtfs-realtime-validator](https://github.com/MobilityData/gtfs-realtime-validator) |
| **transitfeed** | Python | Google's original GTFS reader/validator. Mature but less maintained. | [google/transitfeed](https://github.com/google/transitfeed) |
| **gtfsvtor** | Java | Open-source GTFS validator by Mecatran (GPLv3). | N/A |
| **Web Validator** | Web | Online GTFS validation at gtfs-validator.mobilitydata.org | [gtfs-validator.mobilitydata.org](https://gtfs-validator.mobilitydata.org/) |

### 6.3 GTFS Libraries & Utilities

| Tool | Language | Description | Link |
|------|----------|-------------|------|
| **gtfs-utils** | JavaScript | Utilities to process GTFS data (flatten calendar, compute times). | npm: gtfs-utils |
| **gtfstools** | R | Tools for editing and analyzing GTFS feeds in R. | [ipeagit/gtfstools](https://ipeagit.github.io/gtfstools/) |
| **gtfs-lib** | Java | Conveyal's GTFS library for loading and validating. | [conveyal/gtfs-lib](https://github.com/conveyal/gtfs-lib) |
| **node-gtfs** | JavaScript | Import GTFS data into SQLite, query with Node.js. | [blinktaginc/node-gtfs](https://github.com/blinktaginc/node-gtfs) |
| **gtfs-to-geojson** | JavaScript | Convert GTFS shapes and stops to GeoJSON. | [blinktaginc/gtfs-to-geojson](https://github.com/blinktaginc/gtfs-to-geojson) |
| **gtfs-to-html** | JavaScript | Generate human-readable HTML timetables from GTFS. | [blinktaginc/gtfs-to-html](https://github.com/blinktaginc/gtfs-to-html) |
| **gtfs-realtime-bindings** | Multi | Official Protocol Buffer bindings for GTFS-RT (Java, .NET, Python, JS, Go, PHP, Ruby). | [MobilityData/gtfs-realtime-bindings](https://github.com/MobilityData/gtfs-realtime-bindings) |
| **transitland-lib** | Go | Library for reading and processing transit data. | [interline-io/transitland-lib](https://github.com/interline-io/transitland-lib) |

### 6.4 GTFS Editors & Creators

| Tool | Description | Link |
|------|-------------|------|
| **GTFS Builder** | Web-based GTFS creation tool (RTAP). | [gtfsbuilder.com](https://gtfsbuilder.com) |
| **IBI GTFS Editor** | Web-based GTFS editor. | [ibi-group/gtfs-editor](https://github.com/ibi-group/gtfs-editor) |
| **Conveyal Analysis** | Web platform for transport scenario modeling. | [conveyal.com](https://conveyal.com) |

### 6.5 Transit Data Platforms & Registries

| Platform | Description | URL |
|----------|-------------|-----|
| **Mobility Database** | Global catalog of 4000+ GTFS/GTFS-RT/GBFS feeds. Successor to TransitFeeds/OpenMobilityData. | [mobilitydatabase.org](https://mobilitydatabase.org/) |
| **Transitland** | Open transit data platform with API. Indexes feeds worldwide. | [transit.land](https://www.transit.land/) |
| **OpenMobilityData** | Deprecated (Dec 2025). Redirects to Mobility Database. | [transitfeeds.com](https://transitfeeds.com/) |

### 6.6 CAD/AVL & Operations (Open Source)

| Tool | Description | Link |
|------|-------------|------|
| **Resgrid Core** | Open-source CAD, personnel management, shift management, AVL. Originally for first responders but adaptable. | [Resgrid/Core](https://github.com/Resgrid/Core) |
| **Traccar** | Open-source GPS tracking platform. Supports 200+ GPS protocols. Good for vehicle fleet tracking. | [traccar.org](https://www.traccar.org/) |

**Note:** There is no comprehensive open-source transit CMS equivalent to Optibus/Trapeze. Building a custom system is common for agencies with specific needs.

---

## 7. Live Tracking Map Technologies

### 7.1 Mapping Library Comparison

| Feature | Mapbox GL JS | MapLibre GL JS | Leaflet | deck.gl |
|---------|-------------|----------------|---------|---------|
| **Rendering** | WebGL (vector tiles) | WebGL (vector tiles) | Canvas/SVG (raster) | WebGL (GPU-accelerated) |
| **License** | Proprietary (free tier) | BSD-3-Clause (open source) | BSD-2-Clause (open source) | MIT (open source) |
| **Vehicle markers** | Excellent (1000s) | Excellent (1000s) | Good (<500 without clustering) | Excellent (10,000s) |
| **3D support** | Yes (pitch/bearing) | Yes (pitch/bearing) | No | Yes (full 3D) |
| **Custom styling** | Mapbox Studio | MapTiler / custom | CSS-based | Programmatic |
| **Bundle size** | ~230KB gzip | ~230KB gzip | ~40KB gzip | ~300KB+ gzip |
| **Tile source** | Mapbox tiles (paid) | Any vector tiles | Any raster tiles | Any (overlay layer) |
| **React integration** | react-map-gl | react-map-gl | react-leaflet | @deck.gl/react |
| **Real-time perf** | High | High | Medium | Very High |
| **Pricing** | Free <50K loads/mo | Free (open source) | Free (open source) | Free (open source) |

### 7.2 Recommended Stack for Riga Transit

**Primary recommendation: MapLibre GL JS + deck.gl overlay**

Rationale:
- **MapLibre GL JS** is the open-source fork of Mapbox GL JS — no vendor lock-in, no API key costs at scale
- **deck.gl** can be layered on top for high-performance vehicle rendering (ScatterplotLayer or IconLayer for buses)
- Free vector tile sources: OpenMapTiles, MapTiler (free tier), or self-hosted with tileserver-gl
- For Riga's scale (~80 routes, ~500 vehicles), MapLibre alone is sufficient; deck.gl is insurance for future scale

**Alternative: Leaflet (for simpler requirements)**
- Lighter weight, easier to learn
- Sufficient for <200 simultaneous vehicle markers with clustering
- Good plugin ecosystem (Leaflet.markercluster, Leaflet.Realtime)

### 7.3 Real-Time Update Patterns

#### Pattern 1: HTTP Polling (Simplest — recommended for GTFS-RT)

```
Client                    Server                    RS Feed
  │                         │                         │
  │── GET /api/vehicles ──> │                         │
  │                         │── GET vehicle_pos.pb ──>│
  │                         │<── Protocol Buffer ─────│
  │<── JSON response ──────│                         │
  │                         │                         │
  │ (wait 10-15 seconds)    │                         │
  │── GET /api/vehicles ──> │                         │
  │                         │── (cached/fresh) ──────>│
  ...
```

**Pros:** Simple, works with existing GTFS-RT feeds, easy to cache
**Cons:** Not instant; 10-30s delay is standard and acceptable for transit
**Implementation:** `setInterval(() => fetch('/api/vehicles'), 15000)`

#### Pattern 2: Server-Sent Events (Better UX)

```
Client                    Server                    RS Feed
  │                         │                         │
  │── GET /api/stream ────> │                         │
  │  (Accept: text/event-stream)                      │
  │                         │── poll every 10s ──────>│
  │<── event: vehicles ────│<── Protocol Buffer ─────│
  │    data: {json}         │                         │
  │                         │── poll every 10s ──────>│
  │<── event: vehicles ────│<── Protocol Buffer ─────│
  │    data: {json}         │                         │
  ...
```

**Implementation:**
```javascript
// Server (Node.js/Express)
app.get('/api/stream', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const interval = setInterval(async () => {
    const vehicles = await fetchGtfsRtVehiclePositions();
    res.write(`event: vehicles\ndata: ${JSON.stringify(vehicles)}\n\n`);
  }, 10000);

  req.on('close', () => clearInterval(interval));
});

// Client
const source = new EventSource('/api/stream');
source.addEventListener('vehicles', (e) => {
  const vehicles = JSON.parse(e.data);
  updateMapMarkers(vehicles);
});
```

**Pros:** Automatic reconnection, simple protocol, works through proxies/firewalls
**Cons:** Unidirectional (server → client), limited to text data
**Best for:** Transit tracking where client just receives updates

#### Pattern 3: WebSocket (Full bidirectional)

```
Client                    Server                    RS Feed
  │                         │                         │
  │── WS handshake ────────>│                         │
  │<── WS connected ───────│                         │
  │                         │── poll every 10s ──────>│
  │<── binary/json msg ────│<── Protocol Buffer ─────│
  │                         │                         │
  │── subscribe:{route:15}─>│  (client can filter)    │
  │                         │── poll every 10s ──────>│
  │<── filtered vehicles ──│<── Protocol Buffer ─────│
  ...
```

**Implementation:**
```javascript
// Server (ws library or Socket.IO)
const wss = new WebSocket.Server({ port: 8080 });
wss.on('connection', (ws) => {
  let subscribedRoutes = new Set();

  ws.on('message', (msg) => {
    const { action, routeId } = JSON.parse(msg);
    if (action === 'subscribe') subscribedRoutes.add(routeId);
    if (action === 'unsubscribe') subscribedRoutes.delete(routeId);
  });

  const interval = setInterval(async () => {
    const vehicles = await fetchGtfsRtVehiclePositions();
    const filtered = subscribedRoutes.size > 0
      ? vehicles.filter(v => subscribedRoutes.has(v.routeId))
      : vehicles;
    ws.send(JSON.stringify({ type: 'vehicles', data: filtered }));
  }, 10000);

  ws.on('close', () => clearInterval(interval));
});

// Client
const ws = new WebSocket('ws://localhost:8080');
ws.onopen = () => ws.send(JSON.stringify({ action: 'subscribe', routeId: '15' }));
ws.onmessage = (e) => {
  const { type, data } = JSON.parse(e.data);
  if (type === 'vehicles') updateMapMarkers(data);
};
```

**Pros:** Bidirectional, allows client-side filtering/subscriptions, binary data support
**Cons:** More complex, needs WebSocket server, connection management
**Best for:** Interactive applications where users filter routes, track specific vehicles

### 7.4 Recommendation for VTV

**For a city transit CMS targeting Riga:**

1. **Map rendering:** MapLibre GL JS (or Mapbox GL JS if budget allows)
2. **Vehicle layer:** Native MapLibre markers for <200 vehicles; deck.gl IconLayer for >200
3. **Data flow:** SSE for public-facing maps, WebSocket for dispatch/operations console
4. **Update frequency:** 10-15 seconds (matches GTFS-RT feed refresh rates)
5. **Data pipeline:**
   ```
   Rigas Satiksme GTFS-RT (.pb)
     → Backend (Node.js/Python) parses protobuf
     → Caches in Redis (15s TTL)
     → Serves via REST API + SSE/WebSocket
     → Frontend renders on MapLibre/deck.gl
   ```

### 7.5 Map Animation Techniques

**Smooth marker movement (interpolation):**
```javascript
// Instead of jumping markers, animate between positions
function animateMarker(marker, fromPos, toPos, duration) {
  const start = performance.now();
  function frame(time) {
    const progress = Math.min((time - start) / duration, 1);
    const lat = fromPos.lat + (toPos.lat - fromPos.lat) * progress;
    const lng = fromPos.lng + (toPos.lng - fromPos.lng) * progress;
    marker.setLngLat([lng, lat]);
    if (progress < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
```

**Bearing/rotation:** Use the `bearing` field from VehiclePosition to rotate bus icons in the direction of travel.

**Clustering:** For zoomed-out views, use Supercluster or MapLibre's built-in clustering to group nearby vehicles.

---

## Summary of Key Recommendations

| Area | Recommendation |
|------|---------------|
| **GTFS management** | Use MobilityData's canonical validator; store in PostgreSQL with PostGIS |
| **Rigas Satiksme integration** | Consume GTFS static from `saraksti.rigassatiksme.lv/gtfs.zip` and GTFS-RT from `.pb` endpoints |
| **Trip planning** | OpenTripPlanner 2 for journey planning component |
| **Real-time map** | MapLibre GL JS + SSE for public; WebSocket for operations |
| **GDPR compliance** | Separate public vehicle data from internal driver data; implement DPIA; anonymize passenger data |
| **Data pipeline** | Protobuf parsing → Redis cache → REST/SSE/WS API → Map frontend |
| **EU data sharing** | Ensure GTFS feed is published to Latvia's NAP (data.gov.lv) per MMTIS regulation |
