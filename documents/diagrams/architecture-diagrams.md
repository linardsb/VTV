# Architecture Diagrams — Riga Bus CMS

## 1. System Architecture (C4 Level 1 — Context)

```mermaid
graph TB
    subgraph Actors
        D[Dispatcher<br/>Operations staff]
        A[Admin<br/>System administrators]
        DR[Driver<br/>Bus operators]
        P[Public<br/>Passengers - future]
    end

    subgraph "Riga Bus CMS"
        CMS[CMS Web Portal<br/>Next.js 16 App Router]
    end

    subgraph "External Systems"
        RS[Rīgas Satiksme<br/>GTFS Feed + SIRI API]
        GPS[GPS Hardware<br/>Vehicle AVL units]
        GM[Google Maps<br/>GTFS consumer]
        MA[Moovit / Transit App<br/>GTFS consumers]
        CL[Claude API<br/>AI assistant - Phase 3]
    end

    D --> CMS
    A --> CMS
    DR -.-> GPS
    GPS --> CMS
    RS --> CMS
    CMS --> GM
    CMS --> MA
    CMS <--> CL

    style CMS fill:#3b82f6,color:#fff
    style RS fill:#22c55e,color:#fff
    style CL fill:#8b5cf6,color:#fff
```

## 2. Container Diagram (C4 Level 2)

```mermaid
graph TB
    subgraph "Browser"
        UI[React SPA<br/>Shadcn/ui + Tailwind v4]
        MAP[MapLibre GL JS<br/>Real-time vehicle map]
    end

    subgraph "Next.js 16 Server"
        SC[Server Components<br/>SSR for CRUD pages]
        API[tRPC v11 Router<br/>Type-safe API + SSE]
        GTFS_M[GTFS Module<br/>Import/Export/Validate]
        TRACK[Tracking Module<br/>GPS ingestion + broadcast]
        AI_M[AI Module<br/>Claude integration - Ph3]
    end

    subgraph "Data Stores"
        DB[(PostgreSQL<br/>+ PostGIS<br/>Supabase)]
        REDIS[(Upstash Redis<br/>Cache + Pub/Sub<br/>Phase 2+)]
    end

    subgraph "External"
        TILES[OpenFreeMap<br/>Map tile server]
        CLAUDE[Claude API<br/>Sonnet 4.5]
        RS_FEED[RS GTFS Feed<br/>saraksti.rigassatiksme.lv]
    end

    UI --> SC
    UI --> API
    MAP --> TILES
    API --> DB
    API --> REDIS
    GTFS_M --> DB
    GTFS_M --> RS_FEED
    TRACK --> DB
    TRACK --> REDIS
    AI_M --> CLAUDE
    API -->|SSE| MAP

    style DB fill:#22c55e,color:#fff
    style REDIS fill:#ef4444,color:#fff
    style CLAUDE fill:#8b5cf6,color:#fff
```

## 3. Data Flow — GTFS Import Pipeline

```mermaid
flowchart LR
    A[Download GTFS ZIP<br/>from RS feed] --> B[Extract CSV files<br/>agency, routes, stops,<br/>trips, stop_times,<br/>calendar, shapes]
    B --> C{Validate with<br/>MobilityData<br/>rules}
    C -->|Valid| D[Disable FK constraints]
    C -->|Invalid| E[Return validation<br/>errors to user]
    D --> F[Bulk COPY<br/>into PostgreSQL]
    F --> G[Rebuild indexes<br/>+ spatial indexes]
    G --> H[Enable FK constraints]
    H --> I[Verify data integrity]
    I --> J[Update import<br/>status + timestamp]

    style A fill:#3b82f6,color:#fff
    style F fill:#22c55e,color:#fff
    style E fill:#ef4444,color:#fff
```

## 4. Data Flow — Real-Time Tracking (Phase 2)

```mermaid
flowchart TB
    subgraph "Bus"
        GPS_HW[GPS Hardware<br/>5-10 sec intervals]
    end

    subgraph "Ingestion"
        EP[POST /api/positions<br/>Authenticated endpoint]
        VALID[Validate + Auth<br/>Device certificate]
        DIST[Distance Filter<br/>Skip if < 10m moved]
    end

    subgraph "Storage"
        CP[current_positions<br/>UPSERT latest]
        VP[vehicle_positions<br/>INSERT history]
    end

    subgraph "Broadcast"
        PS[In-process Pub/Sub<br/>or Redis if multi-instance]
        SSE[tRPC SSE<br/>Subscription]
    end

    subgraph "Dashboard"
        ML[MapLibre Map<br/>Symbol layer markers]
        DET[Detail Sidebar<br/>Vehicle info panel]
    end

    GPS_HW -->|HTTP POST| EP
    EP --> VALID
    VALID --> DIST
    DIST -->|Moved > 10m| CP
    DIST -->|Moved > 10m| VP
    CP --> PS
    PS --> SSE
    SSE --> ML
    ML -->|Click| DET

    style GPS_HW fill:#f59e0b,color:#000
    style ML fill:#3b82f6,color:#fff
    style CP fill:#22c55e,color:#fff
```

## 5. Database ER Diagram (Core GTFS)

```mermaid
erDiagram
    AGENCIES ||--o{ ROUTES : "has"
    ROUTES ||--o{ TRIPS : "has"
    CALENDAR ||--o{ TRIPS : "schedules"
    CALENDAR ||--o{ CALENDAR_DATES : "has exceptions"
    TRIPS ||--o{ STOP_TIMES : "contains"
    STOPS ||--o{ STOP_TIMES : "visited by"
    SHAPES ||--o{ TRIPS : "defines path"

    AGENCIES {
        text id PK
        text name
        text url
        text timezone
        text lang
    }

    ROUTES {
        text id PK
        text agency_id FK
        text short_name
        text long_name
        int type
        text color
        bool is_active
    }

    STOPS {
        text id PK
        text name
        text name_lv
        float lat
        float lon
        geometry geom
        bool shelter
        bool electronic_display
    }

    CALENDAR {
        text service_id PK
        bool monday
        bool tuesday
        bool wednesday
        bool thursday
        bool friday
        bool saturday
        bool sunday
        text start_date
        text end_date
    }

    CALENDAR_DATES {
        text service_id FK
        text date
        int exception_type
    }

    TRIPS {
        text id PK
        text route_id FK
        text service_id FK
        text headsign
        int direction_id
        text shape_id FK
    }

    STOP_TIMES {
        text trip_id FK
        text stop_id FK
        text arrival_time
        text departure_time
        int stop_sequence
    }

    SHAPES {
        text id PK
        text encoded_polyline
        geometry geom
    }
```

## 6. Database ER Diagram (Fleet & Tracking — Phase 2)

```mermaid
erDiagram
    VEHICLES ||--o{ CURRENT_POSITIONS : "has"
    VEHICLES ||--o{ VEHICLE_POSITIONS : "tracked at"
    TRIPS ||--o{ CURRENT_POSITIONS : "running"
    DRIVERS ||--o{ SHIFT_ASSIGNMENTS : "works"
    VEHICLES ||--o{ SHIFT_ASSIGNMENTS : "assigned to"

    VEHICLES {
        text id PK
        text registration_number UK
        text type
        text make_model
        int capacity
        bool is_accessible
        text status
        text gps_device_id
    }

    DRIVERS {
        text id PK
        text employee_code UK
        text license_category
        date license_expiry
        text status
    }

    CURRENT_POSITIONS {
        text vehicle_id PK_FK
        text trip_id FK
        text route_id
        float lat
        float lon
        float bearing
        float speed
        timestamp timestamp_tz
        text status
    }

    VEHICLE_POSITIONS {
        serial id PK
        text vehicle_id FK
        text trip_id FK
        float lat
        float lon
        float bearing
        float speed
        timestamp timestamp_tz
        int schedule_adherence_sec
    }

    SHIFT_ASSIGNMENTS {
        serial id PK
        text driver_id FK
        text vehicle_id FK
        date shift_date
        text shift_type
    }
```

## 7. Authentication & Authorization Flow

```mermaid
flowchart TB
    subgraph "Client"
        LOGIN[Login Form]
        DASH[Dashboard]
    end

    subgraph "Auth.js v5"
        MW[Middleware<br/>Route protection]
        JWT_CB[JWT Callback<br/>Add role to token]
        SESS_CB[Session Callback<br/>Expose role]
    end

    subgraph "Protected Routes"
        ADM[/admin/*<br/>role: admin]
        DISP[/tracking/*<br/>role: dispatcher+]
        EDIT[/routes/*, /schedules/*<br/>role: editor+]
        VIEW[/reports/*<br/>role: viewer+]
    end

    LOGIN -->|Credentials| JWT_CB
    JWT_CB -->|Token with role| SESS_CB
    SESS_CB --> MW
    MW -->|role=admin| ADM
    MW -->|role=dispatcher| DISP
    MW -->|role=editor| EDIT
    MW -->|role=viewer| VIEW
    MW -->|Unauthorized| LOGIN

    style ADM fill:#ef4444,color:#fff
    style DISP fill:#f59e0b,color:#000
    style EDIT fill:#3b82f6,color:#fff
    style VIEW fill:#22c55e,color:#fff
```

## 8. Phase Delivery Timeline (AI-Accelerated)

```mermaid
gantt
    title Riga Bus CMS — AI-Accelerated Roadmap (Opus 4.6 + Human Review)
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d

    section Phase 1: Core CMS (2-3 weeks)
    Foundation + Auth + MapLibre          :p1a, 2026-03-01, 5d
    GTFS Import/Export + Data Model       :p1b, after p1a, 5d
    Route & Stop Management               :p1c, after p1b, 4d
    Schedule Editor + i18n + Polish       :p1d, after p1c, 4d

    section Phase 2: Live Operations (2-3 weeks)
    Vehicle & Driver Management           :p2a, after p1d, 5d
    Real-Time Tracking (SSE + Map)        :p2b, after p2a, 5d
    Operational Dashboard                 :p2c, after p2b, 4d
    Analytics + GTFS-RT + GDPR Audit      :p2d, after p2c, 4d

    section Phase 3: Intelligence (2-3 weeks)
    AI Assistant (Claude Integration)     :p3a, after p2d, 5d
    AI Enhancement + Suggestions          :p3b, after p3a, 5d
    NeTEx/SIRI EU Compliance              :p3c, after p3b, 4d
    Advanced Features + Launch            :p3d, after p3c, 4d

    section Milestones
    Phase 1 Demo                          :milestone, after p1d, 0d
    Phase 2 Demo                          :milestone, after p2d, 0d
    Production Launch                     :milestone, after p3d, 0d
```

## 9. AI Agent Decision Flow (Phase 3)

```mermaid
flowchart TB
    USER[Dispatcher types query<br/>"Which buses are late?"]

    subgraph "Query Router"
        CLASS{Classify<br/>Haiku 4.5<br/>$0.001/query}
        SIMPLE[Simple lookup]
        COMPLEX[Complex analysis]
    end

    subgraph "Tool Execution"
        T1[query_bus_status<br/>→ SQL query]
        T2[get_route_schedule<br/>→ SQL query]
        T3[get_adherence_report<br/>→ Aggregation]
    end

    subgraph "Response Generation"
        GEN[Sonnet 4.5<br/>Format response<br/>~$0.03/query]
    end

    subgraph "Display"
        CHAT[Chat response<br/>"3 buses are late:..."]
        ACTION[Quick actions<br/>[View on Map] [Details]]
    end

    USER --> CLASS
    CLASS -->|Simple| SIMPLE --> T1
    CLASS -->|Complex| COMPLEX --> GEN
    T1 --> GEN
    T2 --> GEN
    T3 --> GEN
    GEN --> CHAT
    GEN --> ACTION

    style CLASS fill:#8b5cf6,color:#fff
    style GEN fill:#8b5cf6,color:#fff
    style USER fill:#3b82f6,color:#fff
```
