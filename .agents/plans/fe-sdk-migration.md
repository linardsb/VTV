# Plan: Migrate Hand-Written API Clients to @vtv/sdk

## Feature Metadata
**Feature Type**: Refactor
**Estimated Complexity**: High
**Auth Required**: N/A (internal refactor)
**Allowed Roles**: N/A

## Feature Description

The VTV frontend has 8 hand-written API client files under `cms/apps/web/src/lib/*-client.ts`. Each duplicates boilerplate: `BASE_URL` construction, `authFetch` calls, `URLSearchParams` assembly, `handleResponse` wrappers, and per-domain error classes. Meanwhile, `@vtv/sdk` already has a fully auto-generated TypeScript client with type-safe functions for every endpoint, configured with JWT auth interceptor in `sdk.ts`.

The events domain was already migrated as a reference (`events-sdk.ts` replaces `events-client.ts`). This plan migrates the remaining 7 active domains: **drivers**, **stops**, **users**, **documents**, **schedules**, **agent (chat)**, and **gtfs**. Each gets a new `*-sdk.ts` wrapper, consumers update their imports, and old `*-client.ts` files are deleted.

**Benefits**: Single source of truth for API types, automatic endpoint sync when SDK regenerates, ~60% less hand-written fetch code, zero drift between backend schema and frontend calls.

## Migration Strategy

For each domain:
1. CREATE a new `*-sdk.ts` file that wraps `@vtv/sdk` functions (following `events-sdk.ts` pattern)
2. UPDATE consumer files to import from the new `*-sdk.ts`
3. DELETE the old `*-client.ts` after all consumers are migrated

**Binary responses** (document download, GTFS export): The generated SDK returns `unknown` for file-download endpoints. These functions will keep using `authFetch` for the binary response, but import the configured `client` from `@vtv/sdk/client` for the base URL to avoid duplicating env var logic.

**GTFS stats aggregation**: `fetchGTFSStats()` calls multiple endpoints. It will use the new SDK wrappers rather than raw `authFetch`.

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Reference Pattern (Already Migrated)
- `cms/apps/web/src/lib/events-sdk.ts` — THE reference pattern for all migrations
- `cms/apps/web/src/lib/sdk.ts` — SDK client config (base URL + JWT interceptor)

### SDK Generated Files
- `cms/packages/sdk/src/client/sdk.gen.ts` — All generated SDK functions
- `cms/packages/sdk/src/client/types.gen.ts` — All generated types
- `cms/packages/sdk/src/client/index.ts` — Re-exports

### Files to Create (7 new SDK wrappers)
- `cms/apps/web/src/lib/drivers-sdk.ts`
- `cms/apps/web/src/lib/stops-sdk.ts`
- `cms/apps/web/src/lib/users-sdk.ts`
- `cms/apps/web/src/lib/documents-sdk.ts`
- `cms/apps/web/src/lib/schedules-sdk.ts`
- `cms/apps/web/src/lib/agent-sdk.ts`
- `cms/apps/web/src/lib/gtfs-sdk.ts`

### Files to Modify (14 consumer files — update imports)
- `cms/apps/web/src/app/[locale]/(dashboard)/drivers/page.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/users/page.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/documents/page.tsx`
- `cms/apps/web/src/components/documents/document-detail.tsx`
- `cms/apps/web/src/components/documents/document-upload-form.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx`
- `cms/apps/web/src/components/schedules/trip-detail.tsx`
- `cms/apps/web/src/components/schedules/gtfs-import.tsx`
- `cms/apps/web/src/components/schedules/calendar-dialog.tsx`
- `cms/apps/web/src/components/dashboard/goals-form.tsx`
- `cms/apps/web/src/components/gtfs/gtfs-export.tsx`
- `cms/apps/web/src/hooks/use-chat-agent.ts`

### Files to Delete (8 old clients)
- `cms/apps/web/src/lib/drivers-client.ts`
- `cms/apps/web/src/lib/stops-client.ts`
- `cms/apps/web/src/lib/users-client.ts`
- `cms/apps/web/src/lib/documents-client.ts`
- `cms/apps/web/src/lib/schedules-client.ts`
- `cms/apps/web/src/lib/agent-client.ts`
- `cms/apps/web/src/lib/gtfs-client.ts`
- `cms/apps/web/src/lib/events-client.ts` (legacy, already unused)

## SDK Function Mapping

Reference mapping from hand-written functions → generated SDK functions:

### Drivers
| Old Function | SDK Function |
|---|---|
| `fetchDrivers(params)` | `listDriversApiV1DriversGet({ query })` |
| `fetchDriver(id)` | `getDriverApiV1DriversDriverIdGet({ path: { driver_id } })` |
| `createDriver(data)` | `createDriverApiV1DriversPost({ body })` |
| `updateDriver(id, data)` | `updateDriverApiV1DriversDriverIdPatch({ path, body })` |
| `deleteDriver(id)` | `deleteDriverApiV1DriversDriverIdDelete({ path: { driver_id } })` |

### Stops
| Old Function | SDK Function |
|---|---|
| `fetchStops(params)` | `listStopsApiV1StopsGet({ query })` |
| `fetchStop(id)` | `getStopApiV1StopsStopIdGet({ path: { stop_id } })` |
| `createStop(data)` | `createStopApiV1StopsPost({ body })` |
| `updateStop(id, data)` | `updateStopApiV1StopsStopIdPatch({ path, body })` |
| `deleteStop(id)` | `deleteStopApiV1StopsStopIdDelete({ path: { stop_id } })` |
| `fetchAllStopsForMap()` | `listAllStopsForMapApiV1StopsMapGet()` |
| `fetchTerminalStopIds()` | `listTerminalStopIdsApiV1StopsTerminalsGet()` |
| `fetchNearbyStops(params)` | `nearbyStopsApiV1StopsNearbyGet({ query })` |

### Users
| Old Function | SDK Function |
|---|---|
| `fetchUsers(params)` | `listUsersApiV1AuthUsersGet({ query })` |
| `fetchUser(id)` | `getUserApiV1AuthUsersUserIdGet({ path: { user_id } })` |
| `createUser(data)` | `createUserApiV1AuthUsersPost({ body })` |
| `updateUser(id, data)` | `updateUserApiV1AuthUsersUserIdPatch({ path, body })` |
| `deleteUser(id)` | `deleteUserDataApiV1AuthUsersUserIdDelete({ path: { user_id } })` |
| `resetUserPassword(userId, pw)` | `resetPasswordApiV1AuthResetPasswordPost({ body })` |

### Documents
| Old Function | SDK Function |
|---|---|
| `fetchDocuments(params)` | `listDocumentsApiV1KnowledgeDocumentsGet({ query })` |
| `fetchDocument(id)` | `getDocumentApiV1KnowledgeDocumentsDocumentIdGet({ path })` |
| `uploadDocument(data)` | `uploadDocumentApiV1KnowledgeDocumentsPost({ body })` |
| `updateDocument(id, data)` | `updateDocumentApiV1KnowledgeDocumentsDocumentIdPatch({ path, body })` |
| `deleteDocument(id)` | `deleteDocumentApiV1KnowledgeDocumentsDocumentIdDelete({ path })` |
| `fetchDocumentContent(id)` | `getDocumentContentApiV1KnowledgeDocumentsDocumentIdContentGet({ path })` |
| `downloadDocument(id)` | **Keep authFetch** — returns binary blob, SDK returns `unknown` |
| `fetchDomains()` | `listDomainsApiV1KnowledgeDomainsGet()` |

### Schedules (routes, calendars, trips, agencies, import/validate)
| Old Function | SDK Function |
|---|---|
| `fetchAgencies()` | `listAgenciesApiV1SchedulesAgenciesGet()` |
| `createAgency(data)` | `createAgencyApiV1SchedulesAgenciesPost({ body })` |
| `fetchRoutes(params)` | `listRoutesApiV1SchedulesRoutesGet({ query })` |
| `fetchRoute(id)` | `getRouteApiV1SchedulesRoutesRouteIdGet({ path: { route_id } })` |
| `createRoute(data)` | `createRouteApiV1SchedulesRoutesPost({ body })` |
| `updateRoute(id, data)` | `updateRouteApiV1SchedulesRoutesRouteIdPatch({ path, body })` |
| `deleteRoute(id)` | `deleteRouteApiV1SchedulesRoutesRouteIdDelete({ path: { route_id } })` |
| `fetchCalendars(params)` | `listCalendarsApiV1SchedulesCalendarsGet({ query })` |
| `fetchCalendar(id)` | `getCalendarApiV1SchedulesCalendarsCalendarIdGet({ path })` |
| `createCalendar(data)` | `createCalendarApiV1SchedulesCalendarsPost({ body })` |
| `updateCalendar(id, data)` | `updateCalendarApiV1SchedulesCalendarsCalendarIdPatch({ path, body })` |
| `deleteCalendar(id)` | `deleteCalendarApiV1SchedulesCalendarsCalendarIdDelete({ path })` |
| `addCalendarException(calId, data)` | `addCalendarExceptionApiV1SchedulesCalendarsCalendarIdExceptionsPost({ path, body })` |
| `deleteCalendarException(excId)` | `removeCalendarExceptionApiV1SchedulesCalendarExceptionsExceptionIdDelete({ path })` |
| `fetchTrips(params)` | `listTripsApiV1SchedulesTripsGet({ query })` |
| `fetchTrip(id)` | `getTripApiV1SchedulesTripsTripIdGet({ path: { trip_id } })` |
| `createTrip(data)` | `createTripApiV1SchedulesTripsPost({ body })` |
| `updateTrip(id, data)` | `updateTripApiV1SchedulesTripsTripIdPatch({ path, body })` |
| `deleteTrip(id)` | `deleteTripApiV1SchedulesTripsTripIdDelete({ path: { trip_id } })` |
| `replaceStopTimes(tripId, data)` | `replaceStopTimesApiV1SchedulesTripsTripIdStopTimesPut({ path, body })` |
| `importGTFS(file)` | `importGtfsApiV1SchedulesImportPost({ body: { file } })` |
| `validateSchedule()` | `validateScheduleApiV1SchedulesValidatePost()` |

### Agent (Chat)
| Old Function | SDK Function |
|---|---|
| `sendChatMessage(messages)` | `chatCompletionsV1ChatCompletionsPost({ body: { messages } })` |
| `chatWithAgent(message)` | Thin wrapper around `sendChatMessage` |
| `listModels()` | `listModelsV1ModelsGet()` |

### GTFS
| Old Function | SDK Function |
|---|---|
| `fetchGTFSStats()` | Aggregator — calls SDK wrappers for agencies, routes, calendars, trips, stops |
| `fetchFeeds()` | `getFeedsApiV1TransitFeedsGet()` |
| `exportGTFS(agencyId?)` | `exportGtfsApiV1SchedulesExportGet({ query })` — **needs authFetch for binary blob + browser download trigger** |

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

### Task 1: Create drivers-sdk.ts
**File:** `cms/apps/web/src/lib/drivers-sdk.ts` (create)
**Action:** CREATE

Follow `events-sdk.ts` pattern exactly:
- `import "@/lib/sdk"` for side-effect SDK config
- Import 5 SDK functions from `@vtv/sdk`: `listDriversApiV1DriversGet`, `getDriverApiV1DriversDriverIdGet`, `createDriverApiV1DriversPost`, `updateDriverApiV1DriversDriverIdPatch`, `deleteDriverApiV1DriversDriverIdDelete`
- Import frontend types from `@/types/driver`: `Driver`, `DriverCreate`, `DriverUpdate`, `PaginatedDrivers`
- Create `DriversApiError` class (same pattern as `EventsApiError`)
- Wrap each SDK function: `fetchDrivers`, `fetchDriver`, `createDriver`, `updateDriver`, `deleteDriver`
- Each wrapper: destructure `{ data, error, response }`, throw `DriversApiError` on error, cast `data as unknown as FrontendType`
- For `fetchDrivers`, pass query params: `page`, `page_size`, `search`, `active_only`, `status`, `shift`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 2: Update drivers page imports
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/drivers/page.tsx` (modify)
**Action:** UPDATE

Change import from `@/lib/drivers-client` to `@/lib/drivers-sdk`. The exported function names are identical so no other changes needed.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 3: Delete drivers-client.ts
**File:** `cms/apps/web/src/lib/drivers-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 4: Create stops-sdk.ts
**File:** `cms/apps/web/src/lib/stops-sdk.ts` (create)
**Action:** CREATE

Same pattern. Import 8 SDK functions:
- `listStopsApiV1StopsGet`, `getStopApiV1StopsStopIdGet`, `createStopApiV1StopsPost`, `updateStopApiV1StopsStopIdPatch`, `deleteStopApiV1StopsStopIdDelete`, `listAllStopsForMapApiV1StopsMapGet`, `listTerminalStopIdsApiV1StopsTerminalsGet`, `nearbyStopsApiV1StopsNearbyGet`

Import types from `@/types/stop`: `Stop`, `StopCreate`, `StopUpdate`, `PaginatedStops`, `NearbyParams`

Wrap 8 functions: `fetchStops`, `fetchStop`, `createStop`, `updateStop`, `deleteStop`, `fetchAllStopsForMap`, `fetchTerminalStopIds`, `fetchNearbyStops`

For `fetchNearbyStops`, pass query: `latitude`, `longitude`, `radius_meters`, `limit`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 5: Update stops page imports
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/stops/page.tsx` (modify)
**Action:** UPDATE

Change import from `@/lib/stops-client` to `@/lib/stops-sdk`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 6: Delete stops-client.ts
**File:** `cms/apps/web/src/lib/stops-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 7: Create users-sdk.ts
**File:** `cms/apps/web/src/lib/users-sdk.ts` (create)
**Action:** CREATE

Import 6 SDK functions: `listUsersApiV1AuthUsersGet`, `getUserApiV1AuthUsersUserIdGet`, `createUserApiV1AuthUsersPost`, `updateUserApiV1AuthUsersUserIdPatch`, `deleteUserDataApiV1AuthUsersUserIdDelete`, `resetPasswordApiV1AuthResetPasswordPost`

Import types from `@/types/user`: `User`, `UserCreate`, `UserUpdate`, `PaginatedUsers`

Wrap 6 functions: `fetchUsers`, `fetchUser`, `createUser`, `updateUser`, `deleteUser`, `resetUserPassword`

For `resetUserPassword(userId, newPassword)`, pass body: `{ user_id: userId, new_password: newPassword }`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 8: Update users page imports
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/users/page.tsx` (modify)
**Action:** UPDATE

Change import from `@/lib/users-client` to `@/lib/users-sdk`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 9: Delete users-client.ts
**File:** `cms/apps/web/src/lib/users-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 10: Create documents-sdk.ts
**File:** `cms/apps/web/src/lib/documents-sdk.ts` (create)
**Action:** CREATE

Import SDK functions: `listDocumentsApiV1KnowledgeDocumentsGet`, `getDocumentApiV1KnowledgeDocumentsDocumentIdGet`, `uploadDocumentApiV1KnowledgeDocumentsPost`, `updateDocumentApiV1KnowledgeDocumentsDocumentIdPatch`, `deleteDocumentApiV1KnowledgeDocumentsDocumentIdDelete`, `getDocumentContentApiV1KnowledgeDocumentsDocumentIdContentGet`, `listDomainsApiV1KnowledgeDomainsGet`

Also import `downloadDocumentApiV1KnowledgeDocumentsDocumentIdDownloadGet` for the download endpoint.

Import types from `@/types/document`: `DocumentItem`, `DocumentContentResponse`, `DocumentUpdateData`, `DocumentUploadData`, `DomainList`, `PaginatedDocuments`

Wrap all functions. Special cases:
- `uploadDocument(data)`: Pass `body: { file: data.file, domain: data.domain, language: data.language, title: data.title ?? undefined, description: data.description ?? undefined }`. The SDK uses `formDataBodySerializer` automatically for this endpoint.
- `downloadDocument(id)`: Use `authFetch` for this one — the SDK function returns `unknown` for file downloads. Import `authFetch` from `@/lib/auth-fetch` and keep the existing blob-based implementation. Get base URL from `process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123"`.
- `fetchDomains()`: Maps to `listDomainsApiV1KnowledgeDomainsGet()`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 11: Update documents consumer imports (3 files)
**Files:** (modify all 3)
- `cms/apps/web/src/app/[locale]/(dashboard)/documents/page.tsx` — change `@/lib/documents-client` to `@/lib/documents-sdk`
- `cms/apps/web/src/components/documents/document-detail.tsx` — change `@/lib/documents-client` to `@/lib/documents-sdk`
- `cms/apps/web/src/components/documents/document-upload-form.tsx` — change `@/lib/documents-client` to `@/lib/documents-sdk`
**Action:** UPDATE

Function names are identical — only the import path changes.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 12: Delete documents-client.ts
**File:** `cms/apps/web/src/lib/documents-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 13: Create schedules-sdk.ts
**File:** `cms/apps/web/src/lib/schedules-sdk.ts` (create)
**Action:** CREATE

This is the largest wrapper — 22 functions across 5 sub-domains.

Import from `@vtv/sdk`:
- Agencies: `listAgenciesApiV1SchedulesAgenciesGet`, `createAgencyApiV1SchedulesAgenciesPost`
- Routes: `listRoutesApiV1SchedulesRoutesGet`, `getRouteApiV1SchedulesRoutesRouteIdGet`, `createRouteApiV1SchedulesRoutesPost`, `updateRouteApiV1SchedulesRoutesRouteIdPatch`, `deleteRouteApiV1SchedulesRoutesRouteIdDelete`
- Calendars: `listCalendarsApiV1SchedulesCalendarsGet`, `getCalendarApiV1SchedulesCalendarsCalendarIdGet`, `createCalendarApiV1SchedulesCalendarsPost`, `updateCalendarApiV1SchedulesCalendarsCalendarIdPatch`, `deleteCalendarApiV1SchedulesCalendarsCalendarIdDelete`, `addCalendarExceptionApiV1SchedulesCalendarsCalendarIdExceptionsPost`, `removeCalendarExceptionApiV1SchedulesCalendarExceptionsExceptionIdDelete`
- Trips: `listTripsApiV1SchedulesTripsGet`, `getTripApiV1SchedulesTripsTripIdGet`, `createTripApiV1SchedulesTripsPost`, `updateTripApiV1SchedulesTripsTripIdPatch`, `deleteTripApiV1SchedulesTripsTripIdDelete`, `replaceStopTimesApiV1SchedulesTripsTripIdStopTimesPut`
- Import/Validate: `importGtfsApiV1SchedulesImportPost`, `validateScheduleApiV1SchedulesValidatePost`

Import types from `@/types/schedule` and `@/types/route` — same types the old client used.

Preserve the same exported function names: `fetchAgencies`, `createAgency`, `fetchRoutes`, `fetchRoute`, `createRoute`, `updateRoute`, `deleteRoute`, `fetchCalendars`, `fetchCalendar`, `createCalendar`, `updateCalendar`, `deleteCalendar`, `addCalendarException`, `deleteCalendarException`, `fetchTrips`, `fetchTrip`, `createTrip`, `updateTrip`, `deleteTrip`, `replaceStopTimes`, `importGTFS`, `validateSchedule`

For `importGTFS(file: File)`: pass `body: { file }` — the SDK's `formDataBodySerializer` handles multipart encoding.

For `replaceStopTimes(tripId, stopTimes)`: pass `path: { trip_id: tripId }` and `body: { stop_times: stopTimes }`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 14: Update schedules consumer imports (7 files)
**Files:** (modify all 7)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
- `cms/apps/web/src/app/[locale]/(dashboard)/schedules/page.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk` (imports `fetchAgencies`)
- `cms/apps/web/src/components/schedules/trip-detail.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
- `cms/apps/web/src/components/schedules/gtfs-import.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
- `cms/apps/web/src/components/schedules/calendar-dialog.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
- `cms/apps/web/src/components/dashboard/goals-form.tsx` — change `@/lib/schedules-client` to `@/lib/schedules-sdk`
**Action:** UPDATE

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 15: Delete schedules-client.ts
**File:** `cms/apps/web/src/lib/schedules-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 16: Create agent-sdk.ts
**File:** `cms/apps/web/src/lib/agent-sdk.ts` (create)
**Action:** CREATE

Import SDK functions: `chatCompletionsV1ChatCompletionsPost`, `listModelsV1ModelsGet`

Import types from `@/types/chat`: `ChatCompletionResponse`, `MessageRole`

Wrap 3 functions: `sendChatMessage`, `chatWithAgent` (legacy wrapper), `listModels`

For `sendChatMessage(messages)`: pass `body: { messages }`
For `chatWithAgent(message)`: call `sendChatMessage([{ role: "user", content: message }])`
For `listModels()`: call `listModelsV1ModelsGet()`, return `data`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 17: Update agent consumer imports
**File:** `cms/apps/web/src/hooks/use-chat-agent.ts` (modify)
**Action:** UPDATE

Change import from `@/lib/agent-client` to `@/lib/agent-sdk`.

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 18: Delete agent-client.ts
**File:** `cms/apps/web/src/lib/agent-client.ts` (delete)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 19: Create gtfs-sdk.ts
**File:** `cms/apps/web/src/lib/gtfs-sdk.ts` (create)
**Action:** CREATE

Import SDK functions: `getFeedsApiV1TransitFeedsGet`

Import from `@/lib/schedules-sdk` (the new SDK wrapper): `fetchAgencies`
Import from `@/lib/stops-sdk`: `fetchStops`

Import types from `@/types/gtfs`: `GTFSStats`, `GTFSFeed`

Also import `authFetch` from `@/lib/auth-fetch` for the `exportGTFS` binary download.

Wrap 3 functions:
- `fetchGTFSStats()`: Use `listAgenciesApiV1SchedulesAgenciesGet()` for agencies count (or import `fetchAgencies` from schedules-sdk). For routes/calendars/trips counts, use `listRoutesApiV1SchedulesRoutesGet({ query: { page: 1, page_size: 1 } })` etc. and extract `.total` from the paginated response. For stops count, use `listStopsApiV1StopsGet({ query: { page: 1, page_size: 1 } })`. Wrap each in try/catch returning 0 on failure. Run all in `Promise.all`.
- `fetchFeeds()`: Wrap `getFeedsApiV1TransitFeedsGet()`
- `exportGTFS(agencyId?)`: Keep using `authFetch` — this function triggers a browser file download via `document.createElement('a')` and needs raw blob access. Use same `BASE_URL` pattern.

NOTE: For `fetchGTFSStats`, the SDK functions return `{ data, error }` — extract `data.total` for paginated endpoints, or `data.length` for agencies array. Since these are optional/fallible calls, wrap each in try/catch.

Alternatively, to keep it simpler: import the wrapper functions from `schedules-sdk` and `stops-sdk` which already handle error/casting, then just read `.total` from paginated results. This avoids double-wrapping SDK calls.

Simplest approach for `fetchGTFSStats`:
```typescript
import { fetchAgencies, fetchRoutes, fetchCalendars, fetchTrips } from "@/lib/schedules-sdk";
import { fetchStops } from "@/lib/stops-sdk";

export async function fetchGTFSStats(): Promise<GTFSStats> {
  const [agencies, routes, calendars, trips, stops] = await Promise.all([
    fetchAgencies().catch(() => []),
    fetchRoutes({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchCalendars({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchTrips({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
    fetchStops({ page: 1, page_size: 1 }).catch(() => ({ total: 0 })),
  ]);
  return {
    agencies: Array.isArray(agencies) ? agencies.length : 0,
    routes: "total" in routes ? routes.total : 0,
    calendars: "total" in calendars ? calendars.total : 0,
    trips: "total" in trips ? trips.total : 0,
    stops: "total" in stops ? stops.total : 0,
  };
}
```

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 20: Update gtfs consumer imports (2 files)
**Files:** (modify both)
- `cms/apps/web/src/app/[locale]/(dashboard)/gtfs/page.tsx` — change `@/lib/gtfs-client` to `@/lib/gtfs-sdk`
- `cms/apps/web/src/components/gtfs/gtfs-export.tsx` — change `@/lib/gtfs-client` to `@/lib/gtfs-sdk`
**Action:** UPDATE

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 21: Delete gtfs-client.ts and events-client.ts
**Files:** (delete both)
- `cms/apps/web/src/lib/gtfs-client.ts`
- `cms/apps/web/src/lib/events-client.ts` (legacy, unused)
**Action:** DELETE via `rm`

**Per-task validation:**
- `cd cms && pnpm --filter @vtv/web type-check`

---

### Task 22: Full validation and lint
**Action:** Run full frontend validation suite

```bash
cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint && pnpm --filter @vtv/web build
```

Fix any type errors, lint warnings, or build failures. Common issues:
- Mismatched SDK response types vs frontend types — use `as unknown as FrontendType` cast (same as events-sdk.ts)
- Unused imports in deleted files — consumers should only reference new `-sdk.ts` modules
- If type-check complains about missing query params, check the SDK's `*Data` type in `types.gen.ts` for the exact param names

**Per-task validation:**
- All 3 checks pass with 0 errors

---

## Final Validation (3-Level Pyramid)

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

- [ ] All 7 new `*-sdk.ts` files created and follow events-sdk.ts pattern
- [ ] All 14 consumer files import from new `*-sdk.ts` modules
- [ ] All 8 old `*-client.ts` files deleted (including unused events-client.ts)
- [ ] No remaining imports of `*-client` anywhere in `cms/apps/web/src/`
- [ ] type-check passes with 0 errors
- [ ] lint passes with 0 errors/warnings
- [ ] build succeeds
- [ ] Grep for `from "@/lib/.*-client"` returns 0 results in `cms/apps/web/src/`

## Acceptance Criteria

This refactor is complete when:
- [ ] All API domains use `@vtv/sdk` via thin wrapper modules
- [ ] Zero hand-written `authFetch` URL construction (except binary downloads)
- [ ] All quality gates pass (type-check, lint, build)
- [ ] No regressions — same function signatures exported, consumers unchanged
- [ ] Ready for `/commit`
