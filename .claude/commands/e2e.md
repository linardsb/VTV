# E2E Test — Exploratory Browser Testing

**Usage:** `/e2e` | `/e2e routes` | `/e2e dashboard stops`

## Pre-flight Checks

### 1. agent-browser Installation

```bash
agent-browser --version
```

If not found:
```bash
npm install -g agent-browser && agent-browser install --with-deps
```

### 2. Services

Verify backend and frontend are running:
```bash
curl -s http://localhost:8123/health | head -c 100   # Backend
curl -s http://localhost:3000 -o /dev/null -w "%{http_code}"  # Frontend
```

If not running:
```bash
make dev  # backend (:8123) + frontend (:3000)
```

Wait for both to be ready before proceeding.

## Project Context

- **Frontend**: http://localhost:3000
- **API base**: http://localhost:8123/api/v1
- **Demo credentials**: `admin@vtv.lv` / `admin`
- **Locales**: `/lv/` (primary), `/en/`

## Scope Selection

Parse `$ARGUMENTS` to determine which pages to test:

| Arguments | Pages to test |
|-----------|---------------|
| *(empty)* | ALL pages |
| `routes` | Routes only |
| `dashboard stops` | Dashboard + Stops |
| `login dashboard routes` | Login + Dashboard + Routes |

## Phase 1: Setup

```bash
mkdir -p e2e-screenshots/{login,dashboard,routes,stops,schedules,drivers,gtfs,documents,users,chat,responsive,dark-mode}
```

Open the app and confirm it loads:
```bash
agent-browser open http://localhost:3000/lv/login
agent-browser screenshot e2e-screenshots/login/01-login-page.png
```

Use `Read` tool to view each screenshot and analyze for visual issues.

## agent-browser CLI Reference

```bash
agent-browser open <url>              # Navigate to a page
agent-browser snapshot -i             # Get interactive elements with refs (@e1, @e2...)
agent-browser click @eN               # Click element by ref
agent-browser fill @eN "text"         # Clear field and type
agent-browser select @eN "option"     # Select dropdown option
agent-browser press Enter             # Press a key
agent-browser press Escape            # Dismiss modal/dropdown
agent-browser screenshot <path>       # Save screenshot
agent-browser set viewport W H        # Set viewport (e.g., 375 812 for mobile)
agent-browser console                 # Check for JS errors
agent-browser errors                  # Check for uncaught exceptions
agent-browser get url                 # Get current URL
agent-browser close                   # End session
```

**IMPORTANT:** Refs become invalid after navigation or DOM changes. Always re-snapshot after page navigation, form submissions, or dynamic content updates.

## Phase 2: Login Flow

1. `agent-browser snapshot -i` — get form field refs
2. Fill email `admin@vtv.lv`, password `admin`
3. Click Sign In button
4. Verify redirect to `/lv/` (dashboard)
5. Screenshot before and after login

## Phase 3: Key Journeys

Test each page (or only those specified in `$ARGUMENTS`). For each: navigate, snapshot, interact with every button/control, screenshot, analyze with Read tool.

### Dashboard (`/lv/`)
- Verify: 4 metric cards (active vehicles, on-time performance, delayed routes, fleet utilization)
- Verify: Live indicator badge pulsing
- Verify: Calendar section with view toggles (Week/Month/3 Months/Year)
- Click: calendar view toggles, navigate dates, hover events for tooltip
- Verify: Driver roster panel with drag hint
- Screenshot: each calendar view mode

### Routes (`/lv/routes`)
- Verify: route table with columns (No., Name, Type, Operator, Status, Color)
- Interact: search box — type "22" and verify filtering
- Interact: type filter (Bus/Trolleybus/Tram), status filter (Active/Inactive)
- Interact: agency filter dropdown
- Click: route row → detail dialog (route info, GTFS ID, dates)
- Click: "New Route" → create form dialog (fill fields, cancel)
- Verify: pagination controls
- Verify: resizable map panel with live vehicle positions
- Verify: WebSocket connection indicator (Live/Polling/Connecting)
- Mobile: `agent-browser set viewport 375 812` → verify Table/Map tab layout

### Stops (`/lv/stops`)
- Verify: stop table with columns (Name, GTFS ID, Location, Type, Wheelchair, Status)
- Interact: search, status filter, location type filter (Stop/Terminus)
- Click: stop row → detail dialog (coordinates, wheelchair, parent station)
- Click: "New Stop" → create form dialog
- Verify: Leaflet map with stop markers, terminus markers differentiated
- Verify: copy GTFS ID button, copy coordinates button
- Mobile: verify Table/Map tab layout

### Schedules (`/lv/schedules`)
- Verify: 3 tabs (Calendars, Trips, Import & Validate)
- **Calendars tab**: table with service IDs, date ranges, operating days badges
  - Click: calendar row → detail with month grid visualization
  - Click: "New Calendar" → form with day checkboxes + presets (Weekdays/Weekend/Daily)
  - Verify: status badges (Active/Expired/Upcoming)
- **Trips tab**: table with trip IDs, routes, headsigns, directions
  - Interact: route filter, calendar filter, direction filter, search
  - Click: trip row → detail with stop times list
- **Import tab**: GTFS ZIP upload dropzone + validation section

### Drivers (`/lv/drivers`)
- Verify: driver table with employee numbers, names, status badges, shift badges
- Interact: search, status filter (Available/On Duty/On Leave/Sick), shift filter
- Click: driver row → detail dialog (personal info, license, medical cert, qualified routes)
- Click: "Add Driver" → multi-section create form
- Verify: license/medical expiry warnings

### GTFS (`/lv/gtfs`)
- Verify: 3 tabs (Overview, Import, Export)
- **Overview**: data stats cards (agencies, routes, calendars, trips, stops) + RT feed status
- **Import**: GTFS ZIP dropzone (shared with Schedules import)
- **Export**: agency filter dropdown + Download GTFS ZIP button

### Documents (`/lv/documents`)
- Verify: document table with columns (Name, Type, Size, Domain, Status, Language)
- Interact: search, type filter (PDF/Word/Excel/CSV/Image/Text), status filter, domain filter, language filter
- Click: document row → detail dialog (file info, content preview, chunks)
- Click: "Upload Document" → upload form with dropzone, domain, language, description
- Verify: download button, delete confirmation dialog

### Users (`/lv/users`)
- Verify: user table with columns (Name, Email, Role, Status, Created)
- Interact: search, role filter (Admin/Dispatcher/Editor/Viewer), status filter
- Click: user row → detail dialog
- Click: "Add User" → create form (name, email, password, role, active toggle)
- Verify: reset password dialog
- Verify: delete confirmation dialog

### Chat (`/lv/chat`)
- Verify: empty state with suggestion chips
- Click: suggestion chip → verify message sent and response streamed
- Type: custom question in input → send
- Verify: assistant response with markdown rendering
- Click: copy button on response, clear conversation button

### Global Features (always test these)
- **Dark mode** — toggle theme in sidebar footer, verify pages render correctly
  - Screenshot dark mode versions of dashboard and one data page
- **Locale switching** — switch to English, verify translations update, switch back to Latvian
- **Sidebar navigation** — verify all nav links, active state highlighting
- **Logout** — click logout, verify redirect to `/lv/login`
- **Responsive** — test at 375px (mobile), 768px (tablet), 1440px (desktop)
  - Mobile: verify hamburger menu, sheet sidebar
  - Screenshot: dashboard at each breakpoint

## Phase 4: Issue Handling

When an issue is found:
1. Document: expected vs actual behavior, screenshot path
2. Check `agent-browser console` and `agent-browser errors` for JS errors
3. Fix the code directly
4. Re-test and screenshot to confirm fix

## Phase 5: Cleanup

```bash
agent-browser close
```

## Phase 6: Report

Present a summary:

```
## E2E Testing Complete

**Pages Tested:** [count]/11
**Screenshots Captured:** [count]
**Issues Found:** [count] ([count] fixed, [count] remaining)

### Pages Tested
| Page | Status | Screenshots | Issues |
|------|--------|-------------|--------|
| Dashboard | PASS | 5 | 0 |
| Routes | PASS | 4 | 1 fixed |
| ... | ... | ... | ... |

### Issues Fixed During Testing
- [Description] — [file:line] — [screenshot before/after]

### Remaining Issues
- [Description] — [severity: high/medium/low] — [screenshot]

### Screenshots
All saved to: `e2e-screenshots/`
```

## API Endpoints for Mutation Verification

```bash
# Routes
curl -s http://localhost:8123/api/v1/schedules/routes | head -c 200

# Stops
curl -s http://localhost:8123/api/v1/stops | head -c 200

# Calendars
curl -s http://localhost:8123/api/v1/schedules/calendars | head -c 200

# Trips
curl -s http://localhost:8123/api/v1/schedules/trips | head -c 200

# Drivers
curl -s http://localhost:8123/api/v1/drivers | head -c 200

# Documents
curl -s http://localhost:8123/api/v1/knowledge/documents | head -c 200

# Users
curl -s http://localhost:8123/api/v1/auth/users | head -c 200

# Events
curl -s http://localhost:8123/api/v1/events | head -c 200

# Health
curl -s http://localhost:8123/health
```
