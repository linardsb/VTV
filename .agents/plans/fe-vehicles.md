# Plan: Vehicles Management Page

## Feature Metadata
**Feature Type**: New Page
**Estimated Complexity**: High
**Route**: `/[locale]/(dashboard)/vehicles`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer

## Feature Description

The Vehicles page provides a fleet management interface for Latvia's public transit vehicles. It displays a paginated, filterable table of all vehicles (buses, trolleybuses, trams) with full CRUD operations, inline maintenance history tracking, and driver assignment via dropdown.

The backend is fully implemented with 8 REST endpoints at `/api/v1/vehicles/` (commit a374ee5). This plan creates the frontend page following the exact same architecture as the Drivers page — client component with filters sidebar, data table, detail dialog, create/edit form dialog, and delete confirmation dialog. Additionally, the vehicle detail dialog includes a maintenance history section with the ability to add new maintenance records, and a driver assignment dropdown.

RBAC: All four roles can view the page. Viewers are read-only. Editors can create/update vehicles and add maintenance records. Dispatchers can assign drivers. Admins have full access including delete.

## Design System

### Master Rules (from MASTER.md)
- Border radius: 0 on all components (except avatars, switches, scrollbar thumbs, status dots)
- Typography: Lexend (headings), Source Sans 3 (body), JetBrains Mono (mono)
- Spacing: Use CSS variable tokens via `p-(--spacing-card)`, `gap-(--spacing-grid)`, etc.
- Colors: Semantic tokens only, never Tailwind primitives

### Page Override
- None exists in `cms/design-system/vtv/pages/` — no override needed for this standard CRUD page

### Tokens Used
- `--spacing-page`, `--spacing-card`, `--spacing-grid`, `--spacing-inline`, `--spacing-tight`
- `text-foreground`, `text-foreground-muted`, `text-foreground-subtle`, `text-label-text`
- `bg-surface`, `bg-surface-secondary`, `bg-selected-bg`, `bg-muted`
- `border-border`
- `bg-status-ontime/10 text-status-ontime` (active status)
- `bg-surface-secondary text-foreground-muted` (inactive status)
- `bg-status-delayed/10 text-status-delayed` (maintenance status)
- `bg-status-critical/10 text-status-critical` (destructive actions)
- `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (vehicle type badges)

## Components Needed

### Existing (shadcn/ui) — already installed
- `Button` — create, edit, delete, save, cancel actions
- `Table`, `TableBody`, `TableCell`, `TableHead`, `TableHeader`, `TableRow` — vehicle list
- `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogDescription`, `DialogFooter` — detail, form, delete, maintenance form
- `Badge` — status and vehicle type indicators
- `Input` — search, form fields
- `Label` — form field labels
- `Select`, `SelectContent`, `SelectItem`, `SelectTrigger`, `SelectValue` — filters, type/status selects
- `Separator` — section dividers
- `Textarea` — notes field
- `Skeleton` — loading state
- `Pagination`, `PaginationContent`, `PaginationEllipsis`, `PaginationItem`, `PaginationLink`, `PaginationNext`, `PaginationPrevious` — table pagination
- `DropdownMenu`, `DropdownMenuContent`, `DropdownMenuItem`, `DropdownMenuTrigger` — row actions
- `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle` — mobile filter sidebar
- `Tabs`, `TabsContent`, `TabsList`, `TabsTrigger` — maintenance history in detail dialog
- `ScrollArea` — maintenance history list scrolling

### New shadcn/ui to Install
- None required

### Custom Components to Create
- `vehicle-table.tsx` at `cms/apps/web/src/components/vehicles/vehicle-table.tsx`
- `vehicle-filters.tsx` at `cms/apps/web/src/components/vehicles/vehicle-filters.tsx`
- `vehicle-form.tsx` at `cms/apps/web/src/components/vehicles/vehicle-form.tsx`
- `vehicle-detail.tsx` at `cms/apps/web/src/components/vehicles/vehicle-detail.tsx`
- `delete-vehicle-dialog.tsx` at `cms/apps/web/src/components/vehicles/delete-vehicle-dialog.tsx`
- `maintenance-form.tsx` at `cms/apps/web/src/components/vehicles/maintenance-form.tsx`

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "vehicles": {
    "title": "Transportlidzekli",
    "description": "Parku parvaldiba, tehniska apkope un vaditaju piesaiste",
    "search": "Meklet transportlidzeklus...",
    "filters": {
      "allTypes": "Visi tipi",
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs",
      "allStatuses": "Visi statusi",
      "active": "Aktivs",
      "inactive": "Neaktivs",
      "maintenance": "Apkope",
      "type": "Tips",
      "status": "Statuss"
    },
    "table": {
      "fleetNumber": "Parka Nr.",
      "type": "Tips",
      "licensePlate": "Numura zime",
      "status": "Statuss",
      "manufacturer": "Razotajs",
      "capacity": "Ietilpiba",
      "driver": "Vaditajs",
      "actions": "Darbibas",
      "noResults": "Transportlidzekli nav atrasti",
      "showing": "transportlidzekli"
    },
    "types": {
      "bus": "Autobuss",
      "trolleybus": "Trolejbuss",
      "tram": "Tramvajs"
    },
    "statuses": {
      "active": "Aktivs",
      "inactive": "Neaktivs",
      "maintenance": "Apkope"
    },
    "detail": {
      "vehicleInfo": "Transportlidzekla informacija",
      "fleetNumber": "Parka numurs",
      "type": "Tips",
      "licensePlate": "Numura zime",
      "manufacturer": "Razotajs",
      "model": "Modelis",
      "modelYear": "Izlaiduma gads",
      "capacity": "Ietilpiba",
      "mileage": "Nobraukums (km)",
      "qualifiedRoutes": "Kvalificetie marsruti",
      "registrationExpiry": "Registracijas derigs lidz",
      "nextMaintenance": "Nakama apkope",
      "notes": "Piezimes",
      "driver": "Piesaistits vaditajs",
      "noDriver": "Nav piesaistits",
      "metadata": "Ieraksta informacija",
      "createdAt": "Izveidots",
      "updatedAt": "Atjaunots",
      "inactive": "Neaktivs",
      "tabs": {
        "info": "Informacija",
        "maintenance": "Apkope"
      }
    },
    "maintenance": {
      "title": "Apkopes vesture",
      "addRecord": "Pievienot ierakstu",
      "noRecords": "Nav apkopes ierakstu",
      "type": "Tips",
      "description": "Apraksts",
      "performedDate": "Izpildes datums",
      "mileageAtService": "Nobraukums pie apkopes",
      "cost": "Izmaksas (EUR)",
      "nextScheduledDate": "Nakamais planotais datums",
      "performedBy": "Izpildija",
      "notes": "Piezimes",
      "types": {
        "scheduled": "Planotais",
        "unscheduled": "Neplanotais",
        "inspection": "Inspekcija",
        "repair": "Remonts"
      },
      "formTitle": "Pievienot apkopes ierakstu",
      "toast": {
        "created": "Apkopes ieraksts pievienots",
        "createError": "Neizdevas pievienot apkopes ierakstu"
      }
    },
    "driverAssignment": {
      "title": "Vaditaja piesaiste",
      "assign": "Piesaistit vaditaju",
      "unassign": "Atsaistit vaditaju",
      "selectDriver": "Izvelieties vaditaju...",
      "noDrivers": "Nav pieejamu vaditaju",
      "toast": {
        "assigned": "Vaditajs piesaistits",
        "unassigned": "Vaditajs atsaistits",
        "assignError": "Neizdevas piesaistit vaditaju"
      }
    },
    "form": {
      "createTitle": "Pievienot transportlidzekli",
      "editTitle": "Rediget transportlidzekli",
      "vehicleInfo": "Transportlidzekla informacija",
      "fleetNumber": "Parka numurs",
      "vehicleType": "Tips",
      "licensePlate": "Numura zime",
      "specifications": "Specifikacijas",
      "manufacturer": "Razotajs",
      "modelName": "Modela nosaukums",
      "modelYear": "Izlaiduma gads",
      "capacity": "Ietilpiba",
      "operations": "Ekspluatacija",
      "status": "Statuss",
      "mileage": "Nobraukums (km)",
      "registrationExpiry": "Registracijas derigs lidz",
      "nextMaintenance": "Nakama apkope",
      "qualifiedRoutes": "Kvalificetie marsruti",
      "notesSection": "Piezimes",
      "notes": "Piezimes",
      "isActive": "Aktivs"
    },
    "actions": {
      "create": "Pievienot",
      "edit": "Rediget",
      "delete": "Dzest",
      "save": "Saglabat",
      "cancel": "Atcelt"
    },
    "delete": {
      "title": "Dzest transportlidzekli",
      "confirmation": "Vai tiesam velaties dzest {fleetNumber}?",
      "warning": "So darbibu nevar atsaukt. Visi saistities apkopes ieraksti tiks dzesti.",
      "confirm": "Dzest",
      "cancel": "Atcelt"
    },
    "toast": {
      "created": "Transportlidzeklis pievienots",
      "updated": "Transportlidzeklis atjaunots",
      "deleted": "Transportlidzeklis dzests",
      "loadError": "Neizdevas ieladet transportlidzeklus",
      "createError": "Neizdevas pievienot transportlidzekli",
      "updateError": "Neizdevas atjaunot transportlidzekli",
      "deleteError": "Neizdevas dzest transportlidzekli"
    },
    "mobile": {
      "showFilters": "Radit filtrus"
    }
  }
}
```

### English (`en.json`)
```json
{
  "vehicles": {
    "title": "Fleet Management",
    "description": "Manage fleet vehicles, maintenance, and driver assignments",
    "search": "Search vehicles...",
    "filters": {
      "allTypes": "All Types",
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram",
      "allStatuses": "All Statuses",
      "active": "Active",
      "inactive": "Inactive",
      "maintenance": "Maintenance",
      "type": "Type",
      "status": "Status"
    },
    "table": {
      "fleetNumber": "Fleet #",
      "type": "Type",
      "licensePlate": "License Plate",
      "status": "Status",
      "manufacturer": "Manufacturer",
      "capacity": "Capacity",
      "driver": "Driver",
      "actions": "Actions",
      "noResults": "No vehicles found",
      "showing": "vehicles"
    },
    "types": {
      "bus": "Bus",
      "trolleybus": "Trolleybus",
      "tram": "Tram"
    },
    "statuses": {
      "active": "Active",
      "inactive": "Inactive",
      "maintenance": "Maintenance"
    },
    "detail": {
      "vehicleInfo": "Vehicle Information",
      "fleetNumber": "Fleet Number",
      "type": "Type",
      "licensePlate": "License Plate",
      "manufacturer": "Manufacturer",
      "model": "Model",
      "modelYear": "Model Year",
      "capacity": "Capacity",
      "mileage": "Mileage (km)",
      "qualifiedRoutes": "Qualified Routes",
      "registrationExpiry": "Registration Expiry",
      "nextMaintenance": "Next Maintenance",
      "notes": "Notes",
      "driver": "Assigned Driver",
      "noDriver": "Unassigned",
      "metadata": "Record Info",
      "createdAt": "Created",
      "updatedAt": "Updated",
      "inactive": "Inactive",
      "tabs": {
        "info": "Information",
        "maintenance": "Maintenance"
      }
    },
    "maintenance": {
      "title": "Maintenance History",
      "addRecord": "Add Record",
      "noRecords": "No maintenance records",
      "type": "Type",
      "description": "Description",
      "performedDate": "Date Performed",
      "mileageAtService": "Mileage at Service",
      "cost": "Cost (EUR)",
      "nextScheduledDate": "Next Scheduled Date",
      "performedBy": "Performed By",
      "notes": "Notes",
      "types": {
        "scheduled": "Scheduled",
        "unscheduled": "Unscheduled",
        "inspection": "Inspection",
        "repair": "Repair"
      },
      "formTitle": "Add Maintenance Record",
      "toast": {
        "created": "Maintenance record added",
        "createError": "Failed to add maintenance record"
      }
    },
    "driverAssignment": {
      "title": "Driver Assignment",
      "assign": "Assign Driver",
      "unassign": "Unassign Driver",
      "selectDriver": "Select a driver...",
      "noDrivers": "No available drivers",
      "toast": {
        "assigned": "Driver assigned",
        "unassigned": "Driver unassigned",
        "assignError": "Failed to assign driver"
      }
    },
    "form": {
      "createTitle": "Add Vehicle",
      "editTitle": "Edit Vehicle",
      "vehicleInfo": "Vehicle Information",
      "fleetNumber": "Fleet Number",
      "vehicleType": "Type",
      "licensePlate": "License Plate",
      "specifications": "Specifications",
      "manufacturer": "Manufacturer",
      "modelName": "Model Name",
      "modelYear": "Model Year",
      "capacity": "Capacity",
      "operations": "Operations",
      "status": "Status",
      "mileage": "Mileage (km)",
      "registrationExpiry": "Registration Expiry",
      "nextMaintenance": "Next Maintenance",
      "qualifiedRoutes": "Qualified Routes",
      "notesSection": "Notes",
      "notes": "Notes",
      "isActive": "Active"
    },
    "actions": {
      "create": "Add Vehicle",
      "edit": "Edit",
      "delete": "Delete",
      "save": "Save",
      "cancel": "Cancel"
    },
    "delete": {
      "title": "Delete Vehicle",
      "confirmation": "Are you sure you want to delete {fleetNumber}?",
      "warning": "This action cannot be undone. All associated maintenance records will be deleted.",
      "confirm": "Delete",
      "cancel": "Cancel"
    },
    "toast": {
      "created": "Vehicle added",
      "updated": "Vehicle updated",
      "deleted": "Vehicle deleted",
      "loadError": "Failed to load vehicles",
      "createError": "Failed to add vehicle",
      "updateError": "Failed to update vehicle",
      "deleteError": "Failed to delete vehicle"
    },
    "mobile": {
      "showFilters": "Show Filters"
    }
  }
}
```

## Data Fetching

- **API endpoints used:**
  - `GET /api/v1/vehicles/` — list with pagination, search, type/status filters
  - `GET /api/v1/vehicles/{id}` — single vehicle (not used separately; detail uses list data)
  - `POST /api/v1/vehicles/` — create
  - `PATCH /api/v1/vehicles/{id}` — update
  - `DELETE /api/v1/vehicles/{id}` — delete
  - `POST /api/v1/vehicles/{id}/assign-driver?driver_id={id|null}` — assign/unassign driver
  - `POST /api/v1/vehicles/{id}/maintenance` — add maintenance record
  - `GET /api/v1/vehicles/{id}/maintenance` — maintenance history (paginated)
  - `GET /api/v1/drivers/?active_only=true&page_size=100` — driver list for assignment dropdown
- **Server vs Client:** All client-side (page is `"use client"` like Drivers page)
- **Loading states:** Skeleton rows while loading table data
- **SDK strategy:** Use `authFetch` from `src/lib/auth-fetch.ts` directly (SDK does not yet have vehicle management endpoints). Create `vehicles-sdk.ts` with the same wrapper pattern as `drivers-sdk.ts` but using `authFetch` instead of `@vtv/sdk` imports. When the SDK is regenerated later, this file can be migrated to use SDK functions.
- **CRITICAL — Server/client boundary:** `authFetch` handles dual-context internally. No static imports of `auth()`.

## RBAC Integration

- **Middleware matcher:** Add `vehicles` to the matcher regex
- **Role permissions:** Add `/vehicles` to all four roles in `ROLE_PERMISSIONS`
- **UI gating:**
  - `viewer` — read-only (no create/edit/delete buttons, no driver assignment, no add maintenance)
  - `editor` — can create/update vehicles, add maintenance records
  - `dispatcher` — can assign/unassign drivers (but NOT create/update/delete vehicles)
  - `admin` — full access including delete

## Sidebar Navigation

- **Label key:** `nav.vehicles` (add to both `lv.json` and `en.json`)
- **Position:** After `drivers` entry in the `navItems` array (before `gtfs`)
- **Role visibility:** All roles (filtered by middleware, not sidebar)

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/drivers/page.tsx` — **PRIMARY PATTERN** — client page with CRUD, filters, dialogs
- `cms/apps/web/src/components/drivers/driver-table.tsx` — Table with status badges, pagination, row actions
- `cms/apps/web/src/components/drivers/driver-filters.tsx` — Sidebar/sheet filter pattern (desktop sidebar + mobile sheet)
- `cms/apps/web/src/components/drivers/driver-form.tsx` — Create/edit dialog form with sections
- `cms/apps/web/src/components/drivers/driver-detail.tsx` — Detail dialog with sections and DetailRow
- `cms/apps/web/src/components/drivers/delete-driver-dialog.tsx` — Delete confirmation dialog
- `cms/apps/web/src/lib/drivers-sdk.ts` — SDK wrapper pattern (adapt for authFetch)
- `cms/apps/web/src/types/driver.ts` — TypeScript type definition pattern
- `cms/apps/web/src/lib/pagination-utils.ts` — `getPageRange()` utility for pagination

### Files to Modify
- `cms/apps/web/messages/lv.json` — Add Latvian translations
- `cms/apps/web/messages/en.json` — Add English translations
- `cms/apps/web/middleware.ts` — Add route matcher + role permissions
- `cms/apps/web/src/components/app-sidebar.tsx` — Add sidebar nav entry

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet) may use hex colors. GTFS route color data values are acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body.
- **No named Tailwind container sizes** — use explicit rem: `sm:max-w-[28rem]`, `sm:max-w-[32rem]`, `sm:max-w-[36rem]`

## TypeScript Security Rules

- **Never use `as` casts on JWT token claims without runtime validation** — validate with `Array.includes()` and safe fallback.
- **Clear `.next` cache when module resolution errors persist** — `rm -rf cms/apps/web/.next`

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: TypeScript Type Definitions
**File:** `cms/apps/web/src/types/vehicle.ts` (create)
**Action:** CREATE

Create type definitions matching the backend schemas exactly:

```typescript
export interface Vehicle {
  id: number;
  fleet_number: string;
  vehicle_type: "bus" | "trolleybus" | "tram";
  license_plate: string;
  manufacturer: string | null;
  model_name: string | null;
  model_year: number | null;
  capacity: number | null;
  status: "active" | "inactive" | "maintenance";
  current_driver_id: number | null;
  mileage_km: number;
  qualified_route_ids: string | null;
  registration_expiry: string | null;
  next_maintenance_date: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleCreate {
  fleet_number: string;
  vehicle_type: "bus" | "trolleybus" | "tram";
  license_plate: string;
  manufacturer?: string | null;
  model_name?: string | null;
  model_year?: number | null;
  capacity?: number | null;
  qualified_route_ids?: string | null;
  notes?: string | null;
}

export interface VehicleUpdate {
  fleet_number?: string;
  vehicle_type?: "bus" | "trolleybus" | "tram";
  license_plate?: string;
  manufacturer?: string | null;
  model_name?: string | null;
  model_year?: number | null;
  capacity?: number | null;
  status?: "active" | "inactive" | "maintenance";
  current_driver_id?: number | null;
  mileage_km?: number;
  qualified_route_ids?: string | null;
  registration_expiry?: string | null;
  next_maintenance_date?: string | null;
  notes?: string | null;
}

export interface MaintenanceRecord {
  id: number;
  vehicle_id: number;
  maintenance_type: "scheduled" | "unscheduled" | "inspection" | "repair";
  description: string;
  performed_date: string;
  mileage_at_service: number | null;
  cost_eur: number | null;
  next_scheduled_date: string | null;
  performed_by: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MaintenanceRecordCreate {
  maintenance_type: "scheduled" | "unscheduled" | "inspection" | "repair";
  description: string;
  performed_date: string;
  mileage_at_service?: number | null;
  cost_eur?: number | null;
  next_scheduled_date?: string | null;
  performed_by?: string | null;
  notes?: string | null;
}

export interface PaginatedVehicles {
  items: Vehicle[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PaginatedMaintenanceRecords {
  items: MaintenanceRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Vehicles SDK Wrapper
**File:** `cms/apps/web/src/lib/vehicles-sdk.ts` (create)
**Action:** CREATE

Create SDK wrapper using `authFetch` from `src/lib/auth-fetch.ts`. Follow the pattern of `drivers-sdk.ts` but using `authFetch` instead of `@vtv/sdk` imports.

The wrapper must export these functions:
- `fetchVehicles(params)` — `GET /api/v1/vehicles/` with query params: `page`, `page_size`, `search`, `vehicle_type`, `status`, `active_only`
- `fetchVehicle(id)` — `GET /api/v1/vehicles/{id}`
- `createVehicle(data)` — `POST /api/v1/vehicles/`
- `updateVehicle(id, data)` — `PATCH /api/v1/vehicles/{id}`
- `deleteVehicle(id)` — `DELETE /api/v1/vehicles/{id}`
- `assignDriver(vehicleId, driverId)` — `POST /api/v1/vehicles/{id}/assign-driver?driver_id={id}` (pass `null` to unassign)
- `fetchMaintenanceHistory(vehicleId, params)` — `GET /api/v1/vehicles/{id}/maintenance` with `page`, `page_size`
- `createMaintenanceRecord(vehicleId, data)` — `POST /api/v1/vehicles/{id}/maintenance`

Pattern for each function:
```typescript
import { authFetch } from "@/lib/auth-fetch";
import type { Vehicle, VehicleCreate, VehicleUpdate, PaginatedVehicles, MaintenanceRecord, MaintenanceRecordCreate, PaginatedMaintenanceRecords } from "@/types/vehicle";

const BASE = process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export class VehiclesApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "VehiclesApiError";
    this.status = status;
  }
}

// Example for fetchVehicles:
export async function fetchVehicles(params: {
  page?: number;
  page_size?: number;
  search?: string;
  vehicle_type?: string;
  status?: string;
  active_only?: boolean;
}): Promise<PaginatedVehicles> {
  const query = new URLSearchParams();
  if (params.page) query.set("page", String(params.page));
  if (params.page_size) query.set("page_size", String(params.page_size));
  if (params.search) query.set("search", params.search);
  if (params.vehicle_type) query.set("vehicle_type", params.vehicle_type);
  if (params.status) query.set("status", params.status);
  if (params.active_only !== undefined) query.set("active_only", String(params.active_only));
  const res = await authFetch(`${BASE}/api/v1/vehicles/?${query.toString()}`);
  if (!res.ok) throw new VehiclesApiError(res.status, "Failed to fetch vehicles");
  return res.json() as Promise<PaginatedVehicles>;
}
```

Follow this pattern for all 8 functions. For `assignDriver`, use query parameter `driver_id`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Latvian i18n Keys
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Read the file first. Add the `vehicles` key block from the i18n Keys section above. Also add `"vehicles": "Transportlidzekli"` to the `nav` object.

Insert the `vehicles` block after the `drivers` block (alphabetical isn't required; keep feature blocks grouped logically).

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 4: English i18n Keys
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Read the file first. Add the `vehicles` key block from the i18n Keys section above. Also add `"vehicles": "Vehicles"` to the `nav` object.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 5: Vehicle Filters Component
**File:** `cms/apps/web/src/components/vehicles/vehicle-filters.tsx` (create)
**Action:** CREATE

Follow `driver-filters.tsx` pattern exactly. Create:
- `FilterContent` sub-component (extracted to module scope, NOT inside another component)
- `VehicleFilters` component with `asSheet` prop for mobile

Filters:
1. **Search** — text input with Search icon, placeholder from i18n
2. **Type filter** — Select with options: All Types, Bus, Trolleybus, Tram
3. **Status filter** — Select with options: All Statuses, Active, Inactive, Maintenance

Props interface:
```typescript
interface VehicleFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  typeFilter: string;
  onTypeFilterChange: (value: string) => void;
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  resultCount: number;
  asSheet?: boolean;
  sheetOpen?: boolean;
  onSheetOpenChange?: (open: boolean) => void;
}
```

Use `useTranslations("vehicles")` for all labels.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 6: Vehicle Table Component
**File:** `cms/apps/web/src/components/vehicles/vehicle-table.tsx` (create)
**Action:** CREATE

Follow `driver-table.tsx` pattern exactly. Create:
- `StatusBadge` sub-component (module scope) with color mapping:
  - `active` → `"bg-status-ontime/10 text-status-ontime border-status-ontime/20"`
  - `inactive` → `"bg-surface-secondary text-foreground-muted border-border"`
  - `maintenance` → `"bg-status-delayed/10 text-status-delayed border-status-delayed/20"`
- `TypeBadge` sub-component (module scope) with color mapping:
  - `bus` → `"bg-transport-bus/10 text-transport-bus border-transport-bus/20"`
  - `trolleybus` → `"bg-transport-trolleybus/10 text-transport-trolleybus border-transport-trolleybus/20"`
  - `tram` → `"bg-transport-tram/10 text-transport-tram border-transport-tram/20"`

Columns:
1. Fleet Number (font-mono text-xs)
2. Type (TypeBadge)
3. License Plate
4. Status (StatusBadge)
5. Manufacturer (hidden on mobile: `hidden lg:table-cell`)
6. Capacity (hidden on mobile: `hidden lg:table-cell`)
7. Actions (DropdownMenu with edit/delete, admin-only delete)

Props interface:
```typescript
interface VehicleTableProps {
  vehicles: Vehicle[];
  totalItems: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  selectedVehicle: Vehicle | null;
  onSelectVehicle: (vehicle: Vehicle) => void;
  onEditVehicle: (vehicle: Vehicle) => void;
  onDeleteVehicle: (vehicle: Vehicle) => void;
  isLoading: boolean;
  isReadOnly: boolean;
  canDelete: boolean;
}
```

Note: `canDelete` is separate from `isReadOnly` because editors can edit but not delete. Only admins can delete.

Include loading skeleton state and empty state, matching driver-table patterns. Include pagination using `getPageRange` from `@/lib/pagination-utils`.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 7: Vehicle Detail Component
**File:** `cms/apps/web/src/components/vehicles/vehicle-detail.tsx` (create)
**Action:** CREATE

Follow `driver-detail.tsx` pattern but with **tabs** for Info and Maintenance.

Use `Dialog` with `sm:max-w-[32rem]` (wider than driver detail because of maintenance tab).

Structure:
- Header: fleet_number as title, vehicle_type badge + status badge
- `Tabs` with two tabs:
  - **Info tab:** DetailRow sections (Vehicle Info, Operations, Notes, Metadata) — same pattern as driver-detail
  - **Maintenance tab:** List of maintenance records with ScrollArea, "Add Record" button (visible to admin/editor only)
- Footer: Edit/Delete/Assign Driver buttons (role-gated)

Props interface:
```typescript
interface VehicleDetailProps {
  vehicle: Vehicle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
  onAssignDriver: () => void;
  maintenanceRecords: MaintenanceRecord[];
  maintenanceLoading: boolean;
  onAddMaintenance: () => void;
  isReadOnly: boolean;
  canDelete: boolean;
  canAssignDriver: boolean;
  canAddMaintenance: boolean;
}
```

For maintenance records list, show each record as a compact card:
- Type badge + performed_date on the first line
- Description on the second line
- Cost and performed_by as subtle metadata

Date formatting: use `new Intl.DateTimeFormat("en-CA").format(new Date(...))` matching driver-detail pattern.

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Vehicle Form Component
**File:** `cms/apps/web/src/components/vehicles/vehicle-form.tsx` (create)
**Action:** CREATE

Follow `driver-form.tsx` pattern exactly. Dialog with `sm:max-w-[32rem]`.

Sections (separated by `<Separator />`):
1. **Vehicle Information** — fleet_number (required, readonly in edit), vehicle_type Select (required), license_plate (required)
2. **Specifications** — manufacturer, model_name, model_year (type="number"), capacity (type="number")
3. **Operations** (edit mode only) — status Select, mileage_km (type="number"), registration_expiry (type="date"), next_maintenance_date (type="date"), qualified_route_ids
4. **Notes** — notes Textarea
5. **Active toggle** (edit mode only) — Switch

Create mode: only shows sections 1, 2, 4 (operations fields come via update).
Edit mode: shows all sections including operations and active toggle.

Form submission builds delta for edit mode (only changed fields sent to PATCH), full object for create mode.

Required fields marked with `*`: fleet_number, vehicle_type, license_plate.

Props interface:
```typescript
interface VehicleFormProps {
  mode: "create" | "edit";
  vehicle?: Vehicle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: VehicleCreate | VehicleUpdate) => void;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Delete Vehicle Dialog
**File:** `cms/apps/web/src/components/vehicles/delete-vehicle-dialog.tsx` (create)
**Action:** CREATE

Follow `delete-driver-dialog.tsx` pattern exactly. Use `AlertTriangle` icon with `bg-status-critical/10`.

Interpolation: `t("confirmation", { fleetNumber: vehicle.fleet_number })`.

Warning text notes that maintenance records will be cascade-deleted.

Props interface:
```typescript
interface DeleteVehicleDialogProps {
  vehicle: Vehicle | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Maintenance Form Component
**File:** `cms/apps/web/src/components/vehicles/maintenance-form.tsx` (create)
**Action:** CREATE

A smaller dialog form for adding maintenance records. Dialog with `sm:max-w-[28rem]`.

Fields:
1. maintenance_type — Select (required): scheduled, unscheduled, inspection, repair
2. description — Textarea (required)
3. performed_date — Input type="date" (required)
4. mileage_at_service — Input type="number"
5. cost_eur — Input type="number" step="0.01"
6. next_scheduled_date — Input type="date"
7. performed_by — Input
8. notes — Textarea

Props interface:
```typescript
interface MaintenanceFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: MaintenanceRecordCreate) => void;
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Vehicles Page Component
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/vehicles/page.tsx` (create)
**Action:** CREATE

Follow `drivers/page.tsx` as the primary pattern. This is the main page orchestrating all components.

**State management:**

Data state:
- `vehicles: Vehicle[]` + `totalItems: number` + `page: number` + `isLoading: boolean`
- `maintenanceRecords: MaintenanceRecord[]` + `maintenanceLoading: boolean`

Filter state:
- `search` + `debouncedSearch` (300ms debounce via useEffect + setTimeout)
- `typeFilter: string` (default: "all")
- `statusFilter: string` (default: "all")
- `filterSheetOpen: boolean` (mobile)

UI state:
- `selectedVehicle: Vehicle | null`
- `detailOpen: boolean`
- `formOpen: boolean` + `formMode: "create" | "edit"` + `formKey: number`
- `deleteOpen: boolean` + `deleteTarget: Vehicle | null`
- `maintenanceFormOpen: boolean`
- `driverAssignOpen: boolean`

**RBAC logic:**
```typescript
const userRole: string = session?.user?.role ?? "viewer";
const IS_READ_ONLY = userRole === "viewer";
const CAN_DELETE = userRole === "admin";
const CAN_EDIT = userRole === "admin" || userRole === "editor";
const CAN_ASSIGN_DRIVER = userRole === "admin" || userRole === "dispatcher";
const CAN_ADD_MAINTENANCE = userRole === "admin" || userRole === "editor";
```

NOTE: `userRole` must be typed as `string` (not inferred as literal) to avoid TS2367 when comparing.

**Data loading:**
- `loadVehicles` callback: fetches via `fetchVehicles()`, sets `vehicles` + `totalItems`
- `loadMaintenance` callback: fetches via `fetchMaintenanceHistory()` when detail opens, sets `maintenanceRecords`
- Session gate: `if (status !== "authenticated") return;`

**Handlers:**
- `handleSelectVehicle(vehicle)` — set selected, open detail, load maintenance history
- `handleCreateClick()` — reset selected, set mode create, increment formKey, open form
- `handleEditVehicle(vehicle)` — set selected, set mode edit, increment formKey, open form, close detail
- `handleDeleteVehicle(vehicle)` — set delete target, open delete dialog, close detail
- `handleFormSubmit(data)` — create or update, toast, close form, reload
- `handleDeleteConfirm()` — delete, toast, clear selection if deleted was selected, reload
- `handleAssignDriver(driverId: number | null)` — call `assignDriver()`, toast, reload, update detail
- `handleAddMaintenance(data)` — call `createMaintenanceRecord()`, toast, reload maintenance

**Driver assignment:**
The driver assignment should be a Select dropdown inside the detail dialog (in the Info tab), showing available drivers fetched from `GET /api/v1/drivers/?active_only=true&page_size=100`. Use `fetchDrivers` from `@/lib/drivers-sdk`. Show current driver name or "Unassigned". Only visible to admin/dispatcher roles.

**Layout (same as drivers page):**
```
<div className="flex h-full flex-col">
  {/* Header: title + description + mobile filter toggle + create button */}
  <div className="flex flex-1 overflow-hidden">
    {/* Desktop filters sidebar */}
    {/* Mobile filter sheet */}
    {/* Table area */}
  </div>
  {/* Detail Dialog */}
  {/* Form Dialog */}
  {/* Delete Dialog */}
  {/* Maintenance Form Dialog */}
</div>
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 12: Middleware Update
**File:** `cms/apps/web/middleware.ts` (modify)
**Action:** UPDATE

Read the file first. Make two changes:

1. Add `/vehicles` to each role's permissions array in `ROLE_PERMISSIONS`:
```typescript
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ["/routes", "/stops", "/schedules", "/drivers", "/vehicles", "/gtfs", "/users", "/chat", "/documents"],
  dispatcher: ["/routes", "/stops", "/schedules", "/drivers", "/vehicles", "/chat", "/documents"],
  editor: ["/routes", "/stops", "/schedules", "/drivers", "/vehicles", "/gtfs", "/documents"],
  viewer: ["/routes", "/stops", "/schedules", "/drivers", "/vehicles", "/documents"],
};
```

2. Add `vehicles` to the matcher regex:
```typescript
export const config = {
  matcher: ["/(lv|en)/(routes|stops|schedules|drivers|vehicles|gtfs|users|chat|documents)/:path*"],
};
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 13: Sidebar Navigation Entry
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Read the file first. Add the vehicles nav item to the `navItems` array after `drivers` and before `gtfs`:

```typescript
const navItems = [
  { key: "dashboard", href: "", enabled: true },
  { key: "routes", href: "/routes", enabled: true },
  { key: "stops", href: "/stops", enabled: true },
  { key: "schedules", href: "/schedules", enabled: true },
  { key: "drivers", href: "/drivers", enabled: true },
  { key: "vehicles", href: "/vehicles", enabled: true },  // ADD THIS LINE
  { key: "gtfs", href: "/gtfs", enabled: true },
  { key: "users", href: "/users", enabled: true },
  { key: "documents", href: "/documents", enabled: true },
  { key: "chat", href: "/chat", enabled: true },
] as const;
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
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

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Page renders at `/lv/vehicles` and `/en/vehicles`
- [ ] i18n keys present in both `lv.json` and `en.json` — `vehicles` namespace + `nav.vehicles`
- [ ] Middleware updated — `vehicles` in matcher regex and all 4 role arrays
- [ ] Sidebar nav link added between `drivers` and `gtfs`
- [ ] Vehicle list loads with pagination, search, and type/status filters
- [ ] Create dialog works (admin/editor only)
- [ ] Edit dialog works with delta updates (admin/editor only)
- [ ] Delete dialog works (admin only)
- [ ] Vehicle detail shows info tab and maintenance tab
- [ ] Maintenance history loads in detail dialog
- [ ] Add maintenance record works (admin/editor only)
- [ ] Driver assignment dropdown works (admin/dispatcher only)
- [ ] Viewers see read-only page (no create/edit/delete/assign buttons)
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] No `rounded-*` classes except on avatars, switches, scrollbar thumbs, status dots
- [ ] Accessibility: all interactive elements have labels, images have alt text
- [ ] Design tokens from tokens.css used (not arbitrary Tailwind values)

## Security Checklist

- [ ] No hardcoded API URLs (uses `NEXT_PUBLIC_AGENT_URL` env var via `authFetch`)
- [ ] No auth tokens in localStorage (uses httpOnly cookies via Auth.js)
- [ ] No `dangerouslySetInnerHTML` without DOMPurify
- [ ] No hardcoded credentials
- [ ] All cookies set with `SameSite=Lax`
- [ ] Redirects preserve user's current locale
- [ ] External links use `rel="noopener noreferrer"`
- [ ] User input displayed via React JSX (auto-escaped)

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/vehicles`
- [ ] RBAC enforced — unauthorized roles redirected, role-based UI gating works
- [ ] Both languages have complete translations
- [ ] Design system rules followed (MASTER.md)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`
