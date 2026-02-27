# Plan: Enhance Stop List Metadata Display

## Feature Metadata
**Feature Type**: Enhancement
**Estimated Complexity**: Low-Medium
**Route**: `/[locale]/(dashboard)/stops` (existing)
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher, editor, viewer (all roles — viewers see read-only)

## Feature Description

The current stop list table shows minimal metadata per row: stop name, GTFS ID (with copy button), and description as a subtitle. The location type and wheelchair accessibility columns are hidden on viewports narrower than `lg` (1024px), meaning the split-panel layout (55% table / 45% map) often hides these columns entirely since the table panel is ~550px wide.

This enhancement makes all available stop metadata visible in the list view at every breakpoint by restructuring the table row layout. Instead of hiding columns, metadata will be shown as compact inline badges and secondary text within each row. This gives admins and viewers a quick scan of each stop's type, accessibility, status, coordinates, and description without needing to open the detail dialog.

**Available stop fields (all visible to every role):**
- `stop_name` — Primary identifier (currently shown)
- `gtfs_stop_id` — GTFS code with copy button (currently shown)
- `stop_desc` — Direction/description (currently shown as subtle subtitle)
- `location_type` — 0=Stop, 1=Terminus, 2=Entrance/Exit, 3=Generic Node, 4=Boarding Area (hidden <lg)
- `wheelchair_boarding` — 0=Unknown, 1=Accessible, 2=Not Accessible (hidden <lg)
- `is_active` — Active/inactive status (shown as separate column)
- `stop_lat` / `stop_lon` — WGS84 coordinates (only in detail dialog)
- `parent_station_id` — Parent station reference (only in detail dialog)
- `created_at` / `updated_at` — Timestamps (only in detail dialog)

## Design System

### Master Rules (from MASTER.md)
- Font: Lexend (headings), Source Sans 3 (body), JetBrains Mono (monospace/codes)
- Spacing: Use compact dashboard tokens (`--spacing-card: 12px`, `--spacing-inline: 6px`, `--spacing-tight: 4px`)
- Shadows: `--shadow-sm` for subtle lift
- Min 4.5:1 contrast ratio for text
- Transitions: 150-300ms on all interactive elements
- 44x44px minimum touch targets

### Page Override
- None exists — no override needed for this metadata enhancement

### Tokens Used
- `text-foreground` — Primary text (stop name)
- `text-foreground-muted` — Secondary text (description, coordinates, GTFS ID)
- `text-foreground-subtle` — Tertiary text (timestamps-like info)
- `bg-surface` — Hover backgrounds
- `bg-selected-bg` — Selected row background
- `border-border` — Table borders, separators
- `text-status-ontime` / `bg-status-ontime/10` — Active status, wheelchair accessible
- `text-status-delayed` / `bg-status-delayed/10` — Inactive status, not accessible
- `text-foreground-muted` — Unknown wheelchair status
- Spacing: `gap-0.5`, `gap-1`, `gap-(--spacing-tight)`, `gap-(--spacing-inline)`

## Components Needed

### Existing (shadcn/ui)
- `Table` / `TableRow` / `TableCell` / etc. — Already in use
- `Badge` — Already in use for type, wheelchair, status
- `Button` — Already in use
- `DropdownMenu` — Already in use for actions
- `Tooltip` / `TooltipTrigger` / `TooltipContent` — For coordinate copy and compact badge explanations

### New shadcn/ui to Install
- None — all needed components already installed

### Custom Components to Create
- None — all changes are within the existing `stop-table.tsx` component

## i18n Keys

### Latvian (`lv.json`)
Add to existing `stops.table` section:
```json
{
  "stops": {
    "table": {
      "coordinates": "Koordinātas",
      "noCoordinates": "Nav koordinātu",
      "coordinatesCopied": "Koordinātas nokopētas!",
      "copyCoordinates": "Kopēt koordinātas"
    }
  }
}
```

### English (`en.json`)
Add to existing `stops.table` section:
```json
{
  "stops": {
    "table": {
      "coordinates": "Coordinates",
      "noCoordinates": "No coordinates",
      "coordinatesCopied": "Coordinates copied!",
      "copyCoordinates": "Copy coordinates"
    }
  }
}
```

## Data Fetching

- **No API changes needed** — all fields already returned by `GET /api/v1/stops` paginated endpoint
- The `Stop` type already includes all fields: `stop_lat`, `stop_lon`, `location_type`, `wheelchair_boarding`, `is_active`
- No new SDK wrapper functions needed
- No new hooks needed

## RBAC Integration

- **No changes needed** — this is an enhancement to an existing page
- All roles already have access to the stops page
- All stop fields are visible to every role
- Edit/delete actions already gated by `isReadOnly` prop

## Sidebar Navigation

- **No changes needed** — stops page already has a sidebar nav entry

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` — Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` — Design system master rules

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/components/stops/stop-table.tsx` — **THE file being modified** (read this first!)
- `cms/apps/web/src/components/stops/stop-detail.tsx` — Reference for how metadata badges are styled in detail view
- `cms/apps/web/src/types/stop.ts` — Stop TypeScript type definition

### Files to Modify
- `cms/apps/web/src/components/stops/stop-table.tsx` — Main enhancement target
- `cms/apps/web/messages/lv.json` — Add new i18n keys
- `cms/apps/web/messages/en.json` — Add new i18n keys

## Design System Color Rules

The executor MUST use semantic Tailwind classes, NEVER primitive color utilities. Full mapping table and forbidden class list are loaded via `@_shared/tailwind-token-map.md`. Key rules:
- Use the mapping table for all color decisions
- Check `cms/packages/ui/src/tokens.css` for available tokens
- Exception: Inline HTML strings (Leaflet) may use hex colors. GTFS route color data values are acceptable.

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** — use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** — extract all sub-components to module scope or separate files. `CopyGtfsButton` is already extracted at module scope — follow this pattern for any new sub-components
- **No `Math.random()` in render** — use `useId()` or generate outside render
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** — If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body

## TypeScript Security Rules

- No new security concerns — this is read-only data display
- Existing `authFetch` patterns already handle authentication
- No new API calls being introduced

## UI Design Specification

### Current Row Layout (before)
```
| Name (+ desc + GTFS ID)     | Type (hidden <lg) | Wheelchair (hidden <lg) | Status | Actions |
```

### New Row Layout (after)
The table will be simplified to fewer columns that are always visible. Instead of separate columns for type/wheelchair/status that get hidden, pack rich metadata into the Name cell and a compact badges cell.

**New column structure:**
```
| Stop Info (name, desc, GTFS, coords, badges)                        | Actions |
```

**Row inner layout (inside the Name/Info cell):**
```
┌──────────────────────────────────────────────────────────┐
│ Stop Name                                          [●]   │  ← name + active dot
│ Direction / Description text                             │  ← stop_desc (if present)
│ [1025a] ⎘   56.9496, 24.1052                            │  ← GTFS ID + coords
│ [Stop]  [♿ Accessible]                                   │  ← type + wheelchair badges
└──────────────────────────────────────────────────────────┘
```

**Key design decisions:**
1. **Active status** → Small colored dot indicator next to name (green=active, amber=inactive) instead of a separate column. Tooltip shows full text.
2. **Location type** → Inline badge below coordinates, always visible.
3. **Wheelchair** → Inline badge next to type badge, with color coding (green=accessible, red=not, gray=unknown), always visible.
4. **Coordinates** → Compact `lat, lon` (4 decimal places for list, 6 in detail) next to GTFS ID. Show "—" if null.
5. **Actions column** → Stays as-is for non-read-only users.
6. **Remove separate Type, Wheelchair, Status columns** → All info now in the main cell.

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.
Use action keywords: CREATE, UPDATE, ADD

### Task 1: Add i18n Keys — Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add these keys inside the existing `stops.table` object (after the `"copied"` key):

```json
"coordinates": "Koordinātas",
"noCoordinates": "Nav koordinātu",
"coordinatesCopied": "Koordinātas nokopētas!",
"copyCoordinates": "Kopēt koordinātas"
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid (no trailing commas, correct nesting)

---

### Task 2: Add i18n Keys — English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add these keys inside the existing `stops.table` object (after the `"copied"` key):

```json
"coordinates": "Coordinates",
"noCoordinates": "No coordinates",
"coordinatesCopied": "Coordinates copied!",
"copyCoordinates": "Copy coordinates"
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- Verify JSON is valid

---

### Task 3: Restructure Stop Table Component
**File:** `cms/apps/web/src/components/stops/stop-table.tsx` (modify)
**Action:** UPDATE

This is the main task. Read the entire existing file first. Then apply these changes:

#### 3a. Add Tooltip import

Add `Tooltip`, `TooltipTrigger`, `TooltipContent` to imports from `@/components/ui/tooltip`.

#### 3b. Add a `CopyCoordinatesButton` sub-component at module scope

Place it right after the existing `CopyGtfsButton` component (at module scope, NOT inside `StopTable`). Pattern mirrors `CopyGtfsButton`:

```tsx
function CopyCoordinatesButton({
  lat,
  lon,
  label,
  copiedLabel,
}: {
  lat: number;
  lon: number;
  label: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      const coordText = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
      void navigator.clipboard.writeText(coordText).then(() => {
        setCopied(true);
        toast.success(copiedLabel);
        setTimeout(() => setCopied(false), 2000);
      });
    },
    [lat, lon, copiedLabel],
  );

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-1 rounded px-1 py-0.5 text-xs text-foreground-muted transition-colors hover:bg-surface hover:text-foreground"
      title={label}
      aria-label={`${label}: ${lat.toFixed(4)}, ${lon.toFixed(4)}`}
    >
      {lat.toFixed(4)}, {lon.toFixed(4)}
      {copied ? (
        <Check className="size-3 text-status-ontime" />
      ) : (
        <Copy className="size-3 opacity-0 transition-opacity group-hover/row:opacity-100" />
      )}
    </button>
  );
}
```

#### 3c. Replace the table header

Remove the separate Type, Wheelchair, and Status `<TableHead>` columns. The new header should be:

```tsx
<TableHeader>
  <TableRow>
    <TableHead>{t("table.name")}</TableHead>
    {!isReadOnly && (
      <TableHead className="w-16">
        <span className="sr-only">{t("table.actions")}</span>
      </TableHead>
    )}
  </TableRow>
</TableHeader>
```

#### 3d. Replace each table row body

Remove the separate Type, Wheelchair, and Status `<TableCell>` elements. The Name cell becomes the rich info cell. New row structure:

```tsx
<TableRow
  key={stop.id}
  className={cn(
    "group/row cursor-pointer transition-colors",
    selectedStopId === stop.id && "bg-selected-bg",
  )}
  onClick={() => onSelectStop(stop)}
>
  <TableCell>
    <div className="flex flex-col gap-1">
      {/* Row 1: Name + active status dot */}
      <div className="flex items-center gap-(--spacing-inline)">
        <span className="font-medium">{stop.stop_name}</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <span
              className={cn(
                "inline-block size-2 shrink-0 rounded-full",
                stop.is_active
                  ? "bg-status-ontime"
                  : "bg-status-delayed",
              )}
              aria-label={stop.is_active ? t("filters.active") : t("filters.inactive")}
            />
          </TooltipTrigger>
          <TooltipContent side="top" className="text-xs">
            {stop.is_active ? t("filters.active") : t("filters.inactive")}
          </TooltipContent>
        </Tooltip>
      </div>

      {/* Row 2: Description (if present) */}
      {stop.stop_desc && (
        <span className="text-xs text-foreground-muted line-clamp-1">
          {stop.stop_desc}
        </span>
      )}

      {/* Row 3: GTFS ID + Coordinates */}
      <div className="flex items-center gap-(--spacing-inline) flex-wrap">
        <CopyGtfsButton
          gtfsId={stop.gtfs_stop_id}
          label={t("table.copyGtfsId")}
          copiedLabel={t("table.copied")}
        />
        {stop.stop_lat != null && stop.stop_lon != null ? (
          <>
            <span className="text-foreground-subtle text-xs">|</span>
            <CopyCoordinatesButton
              lat={stop.stop_lat}
              lon={stop.stop_lon}
              label={t("table.copyCoordinates")}
              copiedLabel={t("table.coordinatesCopied")}
            />
          </>
        ) : (
          <>
            <span className="text-foreground-subtle text-xs">|</span>
            <span className="text-xs text-foreground-subtle">{t("table.noCoordinates")}</span>
          </>
        )}
      </div>

      {/* Row 4: Type + Wheelchair badges */}
      <div className="flex items-center gap-1.5">
        <Badge variant="outline" className="text-[10px] px-1.5 py-0">
          {tLoc(String(stop.location_type))}
        </Badge>
        <Badge
          variant="outline"
          className={cn(
            "text-[10px] px-1.5 py-0",
            stop.wheelchair_boarding === 1 &&
              "border-status-ontime/30 bg-status-ontime/10 text-status-ontime",
            stop.wheelchair_boarding === 2 &&
              "border-status-delayed/30 bg-status-delayed/10 text-status-delayed",
          )}
        >
          {tWheelchair(String(stop.wheelchair_boarding))}
        </Badge>
      </div>
    </div>
  </TableCell>

  {/* Actions column (unchanged) */}
  {!isReadOnly && (
    <TableCell>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="size-8 p-0"
            aria-label={t("table.actions")}
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="size-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => onEditStop(stop)}>
            <Pencil className="mr-2 size-4" />
            {t("actions.edit")}
          </DropdownMenuItem>
          <DropdownMenuItem
            className="text-status-critical"
            onClick={() => onDeleteStop(stop)}
          >
            <Trash2 className="mr-2 size-4" />
            {t("actions.delete")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </TableCell>
  )}
</TableRow>
```

**IMPORTANT implementation notes:**
- The `CopyCoordinatesButton` component is defined at module scope (not inside `StopTable`) to satisfy React 19 rules
- Use `stop.stop_lat != null` (not `!== null`) to handle both `null` and `undefined`
- Coordinates in the list show 4 decimal places (4dp ≈ 11m accuracy, sufficient for list scanning). The copy action copies 6 decimal places for precision
- Badge `text-[10px]` keeps type/wheelchair compact to avoid row bloat
- Active status uses a small dot indicator with tooltip — avoids a full badge/column while remaining accessible (has `aria-label`)
- `line-clamp-1` on description prevents multi-line overflow in tight list

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check` passes
- `cd cms && pnpm --filter @vtv/web lint` passes
- `cd cms && pnpm --filter @vtv/web build` passes

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

- [ ] Stop list rows show: name, active dot, description, GTFS ID, coordinates, type badge, wheelchair badge
- [ ] All metadata visible on every breakpoint (no hidden columns)
- [ ] Active/inactive dot has tooltip with full text
- [ ] Coordinates show 4 decimal places in list, 6 when copied
- [ ] Null coordinates show "No coordinates" / "Nav koordinātu" text
- [ ] Type and wheelchair badges are compact (`text-[10px]`)
- [ ] Wheelchair badge colors: green for accessible, red for not accessible, no color for unknown
- [ ] GTFS ID copy still works
- [ ] Coordinates copy works with toast feedback
- [ ] Row click still opens detail dialog
- [ ] Actions dropdown still works for non-read-only users
- [ ] Pagination still works correctly
- [ ] No hardcoded colors — all styling uses semantic tokens
- [ ] i18n keys present in both lv.json and en.json
- [ ] No regressions: selected row highlight, loading state, empty state all still work

## Acceptance Criteria

This feature is complete when:
- [ ] All stop metadata fields visible in the list view at every breakpoint
- [ ] Both languages have complete translations for new keys
- [ ] Design system rules followed (semantic tokens, compact spacing tokens)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing stop page functionality (map, detail, form, filters)
- [ ] Ready for `/commit`
