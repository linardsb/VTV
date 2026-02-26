# Plan: Routes Management Page

## Feature Metadata
**Feature Type**: New Page
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/routes`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (viewer = read-only)

## Feature Description

A comprehensive routes management page for the VTV transit operations CMS, enabling administrators and editors to view, create, edit, and delete bus, trolleybus, and tram routes. The page implements a 3-panel layout: a left filter sidebar with type/status filters and search, a center data table displaying all routes with sorting and pagination, and a right detail/edit panel that slides in when a route is selected.

Mock data is based on real Latvian transit routes — intercity routes from Autotransporta Direkcija (ATD) connecting major cities (Rīga–Liepāja, Rīga–Daugavpils, Rīga–Ventspils, etc.) and Rīgas Satiksme urban routes (bus, trolleybus, tram). Data follows the GTFS `routes.txt` schema with fields: id, agencyId, shortName, longName, type, color, textColor, description, isActive. The GTFS route type codes are: 0 = Tram, 3 = Bus, 11 = Trolleybus.

RBAC is enforced: admin and editor roles can perform full CRUD operations; dispatcher and viewer roles have read-only access (create/edit/delete buttons are hidden). The page supports both Latvian and English via next-intl.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend for headings, Source Sans 3 for body text
- Spacing: Use compact dashboard-density tokens (`--spacing-page`, `--spacing-card`, `--spacing-grid`)
- Colors: Semantic tokens only — `--color-foreground`, `--color-surface`, `--color-border`, `--color-interactive`
- Shadows: `--shadow-sm` for cards, `--shadow-md` for elevated elements
- Buttons: 8px border-radius, 600 font-weight, 200ms transitions
- Accessibility: 4.5:1 contrast minimum, visible focus rings, keyboard navigation, ARIA labels
- Anti-patterns: No emojis as icons, no hardcoded colors, no layout-shifting hovers

### Page Override
- None exists — the executing agent should apply MASTER.md rules directly. No page override file needed for this standard CRUD page.

### Tokens Used
- `--color-surface`, `--color-surface-raised` — panel backgrounds
- `--color-foreground`, `--color-foreground-muted` — text colors
- `--color-border`, `--color-border-subtle` — panel/table borders
- `--color-interactive`, `--color-interactive-hover` — buttons, links
- `--color-brand`, `--color-brand-muted` — route type badges
- `--color-status-ontime` (emerald) — active status
- `--color-status-delayed` (amber) — inactive/suspended status
- `--spacing-page`, `--spacing-card`, `--spacing-grid`, `--spacing-section` — layout spacing
- `--radius-md`, `--radius-lg` — border-radius
- `--font-heading`, `--font-body` — typography

## Components Needed

### Existing (shadcn/ui — already installed)
- `Button` — CRUD action buttons (create, edit, delete, cancel, save)
- `Badge` — route type labels (Bus, Trolleybus, Tram) and status (Active/Inactive)
- `Input` — search field, form inputs for route fields
- `Select` — route type dropdown, agency dropdown
- `Card` — route detail panel wrapper
- `Sheet` — sliding detail/edit panel on the right side
- `Separator` — visual dividers between sections
- `Skeleton` — loading states
- `Tooltip` — action button tooltips
- `DropdownMenu` — row action menus (edit, delete, duplicate)

### New shadcn/ui to Install
- `Table` — `npx shadcn@latest add table` (route data table)
- `Dialog` — `npx shadcn@latest add dialog` (delete confirmation)
- `Label` — `npx shadcn@latest add label` (form field labels)
- `Textarea` — `npx shadcn@latest add textarea` (route description field)
- `Switch` — `npx shadcn@latest add switch` (isActive toggle)
- `Pagination` — `npx shadcn@latest add pagination` (table pagination)

### Custom Components to Create
- `RouteFilters` at `cms/apps/web/src/components/routes/route-filters.tsx` — Left panel: vehicle type toggle, status filter, search input
- `RouteTable` at `cms/apps/web/src/components/routes/route-table.tsx` — Center panel: data table with columns, sorting, pagination
- `RouteDetail` at `cms/apps/web/src/components/routes/route-detail.tsx` — Right panel: route detail view with edit capability
- `RouteForm` at `cms/apps/web/src/components/routes/route-form.tsx` — Create/edit form used in Sheet panel
- `RouteTypeBadge` at `cms/apps/web/src/components/routes/route-type-badge.tsx` — Colored badge for Bus/Trolleybus/Tram
- `DeleteRouteDialog` at `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — Confirmation dialog for route deletion

### Data Files to Create
- `cms/apps/web/src/lib/mock-routes-data.ts` — Realistic Latvian route mock data (intercity + urban)
- `cms/apps/web/src/types/route.ts` — TypeScript types for Route, RouteType, RouteFormData

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "routes": {
    "title": "Maršrutu pārvaldība",
    "description": "Pārvaldiet autobusu, trolejbusu un tramvaju maršrutus",
    "search": "Meklēt maršrutus...",
    "filters": {
      "allTypes": "Visi veidi",
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs",
      "allStatuses": "Visi statusi",
      "active": "Aktīvs",
      "inactive": "Neaktīvs"
    },
    "table": {
      "routeNumber": "Nr.",
      "name": "Nosaukums",
      "type": "Veids",
      "agency": "Operators",
      "status": "Statuss",
      "color": "Krāsa",
      "actions": "Darbības",
      "noResults": "Nav atrasti maršruti",
      "showing": "Rāda {from}–{to} no {total}"
    },
    "detail": {
      "routeInfo": "Maršruta informācija",
      "shortName": "Īsais nosaukums",
      "longName": "Pilnais nosaukums",
      "description": "Apraksts",
      "routeType": "Maršruta veids",
      "agency": "Operators",
      "routeColor": "Maršruta krāsa",
      "textColor": "Teksta krāsa",
      "isActive": "Aktīvs",
      "createdAt": "Izveidots",
      "updatedAt": "Atjaunināts"
    },
    "actions": {
      "create": "Jauns maršruts",
      "edit": "Rediģēt",
      "delete": "Dzēst",
      "duplicate": "Dublēt",
      "save": "Saglabāt",
      "cancel": "Atcelt",
      "close": "Aizvērt"
    },
    "form": {
      "createTitle": "Izveidot jaunu maršrutu",
      "editTitle": "Rediģēt maršrutu",
      "shortNamePlaceholder": "piem., 22",
      "longNamePlaceholder": "piem., Rīga — Liepāja",
      "descriptionPlaceholder": "Maršruta apraksts...",
      "colorPlaceholder": "#FF0000",
      "textColorPlaceholder": "#FFFFFF",
      "required": "Obligāts lauks",
      "shortNameHelp": "Maršruta numurs vai īsais apzīmējums",
      "longNameHelp": "Pilns maršruta nosaukums ar galapunktiem"
    },
    "delete": {
      "title": "Dzēst maršrutu",
      "confirmation": "Vai tiešām vēlaties dzēst maršrutu \"{name}\"?",
      "warning": "Šī darbība ir neatgriezeniska. Tiks dzēsti visi saistītie grafiki un pieturvietu dati.",
      "confirm": "Dzēst",
      "cancel": "Atcelt"
    },
    "toast": {
      "created": "Maršruts veiksmīgi izveidots",
      "updated": "Maršruts veiksmīgi atjaunināts",
      "deleted": "Maršruts veiksmīgi dzēsts"
    },
    "agencies": {
      "rs": "Rīgas Satiksme",
      "atd": "Autotransporta direkcija",
      "lap": "Liepājas autobusu parks",
      "dap": "Daugavpils autobusu parks",
      "nordeka": "Nordeka"
    }
  }
}
```

### English (`en.json`)
```json
{
  "routes": {
    "title": "Route Management",
    "description": "Manage bus, trolleybus, and tram routes",
    "search": "Search routes...",
    "filters": {
      "allTypes": "All Types",
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram",
      "allStatuses": "All Statuses",
      "active": "Active",
      "inactive": "Inactive"
    },
    "table": {
      "routeNumber": "No.",
      "name": "Name",
      "type": "Type",
      "agency": "Operator",
      "status": "Status",
      "color": "Color",
      "actions": "Actions",
      "noResults": "No routes found",
      "showing": "Showing {from}–{to} of {total}"
    },
    "detail": {
      "routeInfo": "Route Information",
      "shortName": "Short Name",
      "longName": "Full Name",
      "description": "Description",
      "routeType": "Route Type",
      "agency": "Operator",
      "routeColor": "Route Color",
      "textColor": "Text Color",
      "isActive": "Active",
      "createdAt": "Created",
      "updatedAt": "Updated"
    },
    "actions": {
      "create": "New Route",
      "edit": "Edit",
      "delete": "Delete",
      "duplicate": "Duplicate",
      "save": "Save",
      "cancel": "Cancel",
      "close": "Close"
    },
    "form": {
      "createTitle": "Create New Route",
      "editTitle": "Edit Route",
      "shortNamePlaceholder": "e.g., 22",
      "longNamePlaceholder": "e.g., Rīga — Liepāja",
      "descriptionPlaceholder": "Route description...",
      "colorPlaceholder": "#FF0000",
      "textColorPlaceholder": "#FFFFFF",
      "required": "Required field",
      "shortNameHelp": "Route number or short identifier",
      "longNameHelp": "Full route name with endpoints"
    },
    "delete": {
      "title": "Delete Route",
      "confirmation": "Are you sure you want to delete route \"{name}\"?",
      "warning": "This action cannot be undone. All associated schedules and stop data will be removed.",
      "confirm": "Delete",
      "cancel": "Cancel"
    },
    "toast": {
      "created": "Route created successfully",
      "updated": "Route updated successfully",
      "deleted": "Route deleted successfully"
    },
    "agencies": {
      "rs": "Rīgas Satiksme",
      "atd": "Transport Directorate",
      "lap": "Liepāja Bus Company",
      "dap": "Daugavpils Bus Company",
      "nordeka": "Nordeka"
    }
  }
}
```

## Data Model

### TypeScript Types (`cms/apps/web/src/types/route.ts`)

```typescript
/** GTFS route_type codes */
export type RouteType = 0 | 3 | 11; // 0=Tram, 3=Bus, 11=Trolleybus

export type RouteTypeLabel = "tram" | "bus" | "trolleybus";

export interface Route {
  id: string;
  agencyId: string;
  shortName: string;
  longName: string;
  type: RouteType;
  color: string;
  textColor: string;
  description: string;
  isActive: boolean;
  createdAt: string; // ISO date string
  updatedAt: string;
}

export interface RouteFormData {
  shortName: string;
  longName: string;
  type: RouteType;
  agencyId: string;
  color: string;
  textColor: string;
  description: string;
  isActive: boolean;
}

export const ROUTE_TYPE_MAP: Record<RouteType, RouteTypeLabel> = {
  0: "tram",
  3: "bus",
  11: "trolleybus",
};
```

### Mock Data (`cms/apps/web/src/lib/mock-routes-data.ts`)

Create 25+ realistic routes covering:
- **Intercity buses** (ATD): Rīga–Liepāja, Rīga–Daugavpils, Rīga–Ventspils, Rīga–Jelgava, Rīga–Cēsis, Rīga–Sigulda, Rīga–Tukums, Rīga–Kuldīga, Rīga–Ogre, Rīga–Rēzekne
- **Urban buses** (RS): Route 3 (Ziepniekkalns–Jugla), Route 15 (Jugla–VEF), Route 22 (Jugla–Centrs), Route 30 (Iļģuciems–Daugavgrīva), Route 53 (Imanta–Centrs)
- **Trolleybuses** (RS): Line 5 (Iļģuciems–Alfa), Line 11 (Centrāltirgus–Šmerlis), Line 14 (Centrs–Daugavgrīva), Line 18 (Centrs–Kengarags)
- **Trams** (RS): Line 1 (Jugla–Imanta), Line 2 (Čiekurkalns–Zasulauks), Line 5 (Mīlgrāvis–Iļģuciems), Line 7 (Bolderāja Extension)

Each route has a unique hex color matching RS branding conventions. Agency IDs map to `rs` (Rīgas Satiksme) or `atd` (Autotransporta direkcija) or other operators.

## Data Fetching

- **API endpoints**: None — mock data with in-memory state management via React `useState`
- **Server vs Client**: This is a client component (`"use client"`) because it requires interactive state (filters, selection, CRUD operations)
- **Loading states**: `Skeleton` components for table rows and detail panel during initial render
- **Future migration path**: Replace mock data import with tRPC/API calls when backend is ready. The component interfaces (`Route`, `RouteFormData`) are designed to match GTFS schema exactly, making the swap seamless.

## RBAC Integration

- **Middleware matcher**: Update `"(routes|stops|schedules|gtfs|users|chat)"` — routes is already included
- **Role permissions**: Already defined in `middleware.ts`:
  - admin: full CRUD access
  - dispatcher: read-only access
  - editor: full CRUD access
  - viewer: read-only access
- **UI enforcement**: CRUD buttons (create, edit, delete) are conditionally rendered based on user role. Read-only users see the table and detail panel but no mutation controls.

Note: The middleware already includes `/routes` in the matcher pattern. No middleware changes needed.

## Sidebar Navigation

- **Label key**: `nav.routes` (already exists: "Routes" / "Maršruti")
- **Icon**: `Route` from lucide-react (or `Bus` for more specificity)
- **Position**: Second item after Dashboard (already in position)
- **Role visibility**: All authenticated roles
- **Change required**: Set `enabled: true` for the routes nav item in `layout.tsx`

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules
- `cms/packages/ui/src/tokens.css` — Design token definitions

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — Dashboard page pattern (client component, useTranslations, semantic tokens)
- `cms/apps/web/src/app/[locale]/login/page.tsx` — Client component with form pattern
- `cms/apps/web/src/app/[locale]/layout.tsx` — Sidebar nav structure (enable routes link)
- `cms/apps/web/src/lib/mock-dashboard-data.ts` — Mock data pattern to follow
- `cms/apps/web/src/components/dashboard/metric-card.tsx` — Custom component pattern

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add `routes` translation key block
- `cms/apps/web/messages/en.json` — Add `routes` translation key block
- `cms/apps/web/src/app/[locale]/layout.tsx` — Enable routes nav link (`enabled: true`)

### Files to Create
- `cms/apps/web/src/types/route.ts` — Route TypeScript types
- `cms/apps/web/src/lib/mock-routes-data.ts` — Mock route data
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — Routes page
- `cms/apps/web/src/components/routes/route-filters.tsx` — Filter sidebar
- `cms/apps/web/src/components/routes/route-table.tsx` — Data table
- `cms/apps/web/src/components/routes/route-detail.tsx` — Detail panel
- `cms/apps/web/src/components/routes/route-form.tsx` — Create/edit form
- `cms/apps/web/src/components/routes/route-type-badge.tsx` — Type badge component
- `cms/apps/web/src/components/routes/delete-route-dialog.tsx` — Delete confirmation

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD, INSTALL

### Task 1: Install Required shadcn/ui Components
**Action:** INSTALL

Run the following commands from the `cms/apps/web` directory:
```bash
cd cms && npx shadcn@latest add table dialog label textarea switch pagination --yes
```

This installs: Table, Dialog, Label, Textarea, Switch, Pagination components into `src/components/ui/`.

**Per-task validation:**
- Verify files exist in `cms/apps/web/src/components/ui/`
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Create Route TypeScript Types
**File:** `cms/apps/web/src/types/route.ts` (create)
**Action:** CREATE

Create the file with the types defined in the "Data Model" section above. Include:
- `RouteType` union type (0 | 3 | 11)
- `RouteTypeLabel` union type
- `Route` interface with all GTFS fields + internal fields
- `RouteFormData` interface for form state
- `ROUTE_TYPE_MAP` constant mapping type codes to labels
- `AGENCY_IDS` constant for known agencies

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Create Mock Routes Data
**File:** `cms/apps/web/src/lib/mock-routes-data.ts` (create)
**Action:** CREATE

Create 25+ realistic Latvian transit routes. Include a mix of:

**Intercity Bus Routes (ATD — agencyId: "atd"):**
| shortName | longName | color |
|-----------|----------|-------|
| 7101 | Rīga — Liepāja | #E53935 |
| 7201 | Rīga — Daugavpils | #1E88E5 |
| 7301 | Rīga — Ventspils | #43A047 |
| 7401 | Rīga — Jelgava | #FB8C00 |
| 7501 | Rīga — Cēsis | #8E24AA |
| 7601 | Rīga — Sigulda | #00ACC1 |
| 7701 | Rīga — Tukums | #5D4037 |
| 7801 | Rīga — Kuldīga | #546E7A |
| 7901 | Rīga — Rēzekne | #D81B60 |
| 7010 | Rīga — Ogre | #6D4C41 |

**Urban Bus Routes (RS — agencyId: "rs"):**
| shortName | longName | type |
|-----------|----------|------|
| 3 | Ziepniekkalns — Jugla | 3 (bus) |
| 15 | Jugla — VEF | 3 |
| 22 | Jugla — Centrs | 3 |
| 30 | Iļģuciems — Daugavgrīva | 3 |
| 53 | Imanta — Centrs | 3 |

**Trolleybus Routes (RS — agencyId: "rs"):**
| shortName | longName | type |
|-----------|----------|------|
| 5 | Iļģuciems — Alfa | 11 |
| 11 | Centrāltirgus — Šmerlis | 11 |
| 14 | Centrs — Daugavgrīva | 11 |
| 18 | Centrs — Kengarags | 11 |

**Tram Routes (RS — agencyId: "rs"):**
| shortName | longName | type |
|-----------|----------|------|
| 1 | Jugla — Imanta | 0 |
| 2 | Čiekurkalns — Zasulauks | 0 |
| 5 | Mīlgrāvis — Iļģuciems | 0 |
| 7 | Bolderāja — Centrs (Extension) | 0 |

Each route has realistic `color`, `textColor`, `description`, `isActive` (most true, 2-3 inactive), `createdAt`, `updatedAt`.

Export as `MOCK_ROUTES: Route[]` and `MOCK_AGENCIES` map.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: Add Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add the entire `"routes"` key block from the Latvian i18n section above. Insert it after the `"dashboard"` key at the top level of the JSON object.

**Per-task validation:**
- JSON is valid (no syntax errors)
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Add English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add the entire `"routes"` key block from the English i18n section above. Insert it after the `"dashboard"` key at the top level of the JSON object. Ensure all keys match the Latvian file exactly.

**Per-task validation:**
- JSON is valid
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Create RouteTypeBadge Component
**File:** `cms/apps/web/src/components/routes/route-type-badge.tsx` (create)
**Action:** CREATE

A small presentational component that renders a colored `Badge` for route type:
- Bus: blue badge with Bus icon
- Trolleybus: green badge with Zap icon (electric)
- Tram: purple badge with Train icon

Props: `type: RouteType` and optional `className`.

Use `useTranslations("routes.filters")` for labels ("Autobuss", "Trolejbuss", "Tramvajs").
Use lucide-react icons: `Bus`, `Zap`, `Train`.
Use semantic tokens for colors (e.g., `bg-blue-100 text-blue-700` mapped from the design tokens).
Mark as `"use client"` since it uses `useTranslations`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Create RouteFilters Component (Left Panel)
**File:** `cms/apps/web/src/components/routes/route-filters.tsx` (create)
**Action:** CREATE

Left sidebar filter panel containing:
1. **Search input** — `Input` with search icon, filters routes by shortName or longName
2. **Type filter** — `ToggleGroup` with options: All, Bus, Trolleybus, Tram (single select, "All" is default)
3. **Status filter** — `Select` with options: All Statuses, Active, Inactive
4. **Route count** — Text showing "X routes" matching current filters

Props interface:
```typescript
interface RouteFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: RouteType | null;
  onTypeFilterChange: (type: RouteType | null) => void;
  statusFilter: "all" | "active" | "inactive";
  onStatusFilterChange: (status: "all" | "active" | "inactive") => void;
  resultCount: number;
}
```

Use `useTranslations("routes")` for all labels.
Use compact spacing: `p-(--spacing-card)`, `gap-(--spacing-grid)`.
Width: fixed 240px sidebar with border-right.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Create RouteTable Component (Center Panel)
**File:** `cms/apps/web/src/components/routes/route-table.tsx` (create)
**Action:** CREATE

Data table displaying filtered routes with columns:
1. **No.** — `shortName` displayed as bold text with route color swatch (small colored circle)
2. **Name** — `longName`
3. **Type** — `RouteTypeBadge` component
4. **Operator** — agency name from `agencyId` lookup (translated)
5. **Status** — `Badge` (green "Active" / amber "Inactive")
6. **Actions** — `DropdownMenu` with Edit, Duplicate, Delete (hidden for viewer/dispatcher roles)

Features:
- Click a row to select it and open the detail panel
- Selected row has `bg-surface-raised` highlight
- Column headers are sortable (click to toggle asc/desc)
- Pagination at the bottom (10 routes per page)
- Empty state: "No routes found" message with description

Props interface:
```typescript
interface RouteTableProps {
  routes: Route[];
  selectedRouteId: string | null;
  onSelectRoute: (routeId: string) => void;
  onEditRoute: (route: Route) => void;
  onDeleteRoute: (route: Route) => void;
  onDuplicateRoute: (route: Route) => void;
  isReadOnly: boolean;
}
```

Use the shadcn/ui `Table` components. Use `useTranslations("routes.table")` for headers.
Use semantic tokens for row hover (`hover:bg-surface`) and selected state.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Create RouteDetail Component (Right Panel)
**File:** `cms/apps/web/src/components/routes/route-detail.tsx` (create)
**Action:** CREATE

Sliding detail panel that appears when a route is selected. Uses the `Sheet` component (already installed) anchored to the right side.

Content:
1. **Header**: Route shortName + longName, close button
2. **Type badge**: `RouteTypeBadge`
3. **Color preview**: Small rectangle showing route color with hex value
4. **Info grid**: Description, Agency, Status (active/inactive), Created date, Updated date
5. **Action buttons** (if not read-only): Edit, Delete

Props:
```typescript
interface RouteDetailProps {
  route: Route | null;
  isOpen: boolean;
  onClose: () => void;
  onEdit: (route: Route) => void;
  onDelete: (route: Route) => void;
  isReadOnly: boolean;
}
```

Use `Sheet` with `side="right"` and width ~400px.
Format dates using `Intl.DateTimeFormat` with the current locale from `useLocale()`.
Use `useTranslations("routes.detail")` for all labels.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Create RouteForm Component
**File:** `cms/apps/web/src/components/routes/route-form.tsx` (create)
**Action:** CREATE

Form for creating and editing routes. Rendered inside a `Sheet` panel.

Fields:
1. **Short Name** (required) — `Input` with `Label`, placeholder "e.g., 22"
2. **Long Name** (required) — `Input`, placeholder "e.g., Rīga — Liepāja"
3. **Route Type** (required) — `Select` with options: Bus, Trolleybus, Tram
4. **Agency** (required) — `Select` with agency options (RS, ATD, etc.)
5. **Route Color** — `Input` type="color" + text input showing hex value
6. **Text Color** — `Input` type="color" + text input showing hex value
7. **Description** — `Textarea`
8. **Active** — `Switch` toggle

Props:
```typescript
interface RouteFormProps {
  mode: "create" | "edit";
  initialData?: RouteFormData;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: RouteFormData) => void;
}
```

Form state managed with React `useState`. Basic client-side validation:
- shortName: required, max 10 chars
- longName: required, max 200 chars
- color/textColor: valid hex format

Use `useTranslations("routes.form")` for all labels and placeholders.
Use `Label` component with `htmlFor` for accessibility.
Submit and Cancel buttons at the bottom.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Create DeleteRouteDialog Component
**File:** `cms/apps/web/src/components/routes/delete-route-dialog.tsx` (create)
**Action:** CREATE

Confirmation dialog for route deletion using the `Dialog` component.

Shows:
- Warning icon (AlertTriangle from lucide-react)
- Title: "Delete Route"
- Message: "Are you sure you want to delete route '{name}'?"
- Warning text about cascading deletion
- Cancel and Delete (destructive) buttons

Props:
```typescript
interface DeleteRouteDialogProps {
  route: Route | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (routeId: string) => void;
}
```

Delete button uses destructive variant (red). Use `useTranslations("routes.delete")`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 12: Create Routes Page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` (create)
**Action:** CREATE

The main routes page component. This is a `"use client"` component.

**Layout (3-panel):**
```
┌──────────┬───────────────────────────────┬─────────────┐
│ Filters  │     Route Data Table          │  Detail     │
│ (240px)  │     (flex-1)                  │  Sheet      │
│          │                               │  (400px)    │
│ Search   │  [+ New Route]  (header)      │             │
│ Type     │  ┌──────────────────────┐     │  Route      │
│ Status   │  │ Table with routes... │     │  Info       │
│          │  │                      │     │             │
│ X routes │  │                      │     │  [Edit]     │
│          │  └──────────────────────┘     │  [Delete]   │
│          │  Pagination                   │             │
└──────────┴───────────────────────────────┴─────────────┘
```

State management:
```typescript
const [routes, setRoutes] = useState<Route[]>(MOCK_ROUTES);
const [search, setSearch] = useState("");
const [typeFilter, setTypeFilter] = useState<RouteType | null>(null);
const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
const [selectedRouteId, setSelectedRouteId] = useState<string | null>(null);
const [isFormOpen, setIsFormOpen] = useState(false);
const [formMode, setFormMode] = useState<"create" | "edit">("create");
const [editingRoute, setEditingRoute] = useState<Route | null>(null);
const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
const [deletingRoute, setDeletingRoute] = useState<Route | null>(null);
```

Filtering logic:
- Filter by `search` (case-insensitive match on shortName + longName)
- Filter by `typeFilter` (null = all types)
- Filter by `statusFilter` (all/active/inactive)

CRUD handlers:
- `handleCreate(data: RouteFormData)` — Add new route with generated ID, current timestamps
- `handleEdit(data: RouteFormData)` — Update existing route in state, update `updatedAt`
- `handleDelete(routeId: string)` — Remove from state array
- `handleDuplicate(route: Route)` — Copy route with new ID and "(Copy)" appended to name

RBAC: For now, since there's no auth session in mock mode, default to `isReadOnly = false`. Add a comment noting where to wire in `useSession()` for real RBAC.

Page header:
- Title: `t("routes.title")`
- Description: `t("routes.description")`
- "New Route" button (hidden if read-only)

Compose: `RouteFilters` + `RouteTable` + `RouteDetail` (Sheet) + `RouteForm` (Sheet) + `DeleteRouteDialog`

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 13: Enable Routes Nav Link in Sidebar
**File:** `cms/apps/web/src/app/[locale]/layout.tsx` (modify)
**Action:** UPDATE

In the `navItems` array, change the routes entry from `enabled: false` to `enabled: true`:

```typescript
{ key: "routes", href: "/routes", enabled: true },
```

This activates the sidebar link so users can navigate to the routes page.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes

---

## Final Validation (3-Level Pyramid)

Run each level in order — every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors, zero warnings (per Zero-Warning Policy).

## Post-Implementation Checks

- [ ] Page renders at `/lv/routes` and `/en/routes`
- [ ] 3-panel layout visible: filters left, table center, detail right
- [ ] Type filter works: selecting "Bus" shows only bus routes
- [ ] Status filter works: "Active" / "Inactive" filters correctly
- [ ] Search filters by route number and name
- [ ] Clicking a table row opens the detail panel
- [ ] "New Route" button opens the create form
- [ ] Create form submits and adds a new route to the table
- [ ] Edit form pre-fills data and updates the route
- [ ] Delete confirmation dialog works and removes the route
- [ ] Duplicate creates a copy with "(Copy)" suffix
- [ ] Pagination shows 10 routes per page
- [ ] i18n: switching locale shows Latvian/English translations correctly
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] Accessibility: all form fields have labels, buttons have aria-labels
- [ ] Keyboard navigation: Tab through filters, table rows, form fields
- [ ] Sidebar "Maršruti" / "Routes" link is active and navigates correctly

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/routes`
- [ ] RBAC enforced — middleware already handles `/routes` path
- [ ] Both languages have complete translations (100+ keys each)
- [ ] Design system rules followed (MASTER.md tokens, no hardcoded colors)
- [ ] All 3 validation levels pass (type-check, lint, build) with 0 errors/warnings
- [ ] 25+ realistic Latvian transit routes displayed in the table
- [ ] Full CRUD operations work (create, read, update, delete)
- [ ] 3-panel layout with filters, table, and detail panel functional
- [ ] No regressions in existing pages (dashboard still works)
- [ ] Ready for `/commit`

## Data Sources Referenced

The mock route data is based on real Latvian transit data from:
- [Latvia Open Data Portal — ATD GTFS](https://data.gov.lv/dati/lv/dataset/atd-gtfs) — Intercity bus routes
- [Rīgas Satiksme Open Data](https://www.rigassatiksme.lv/en/about-us/publishable-information/open-data/) — Urban bus, trolleybus, tram routes
- [1188.lv Transport Schedules](https://www.1188.lv/en/transport/buses) — Route reference data
- ATD GTFS direct download: `https://www.atd.lv/sites/default/files/GTFS/gtfs-latvia-lv.zip`
