# @vtv/sdk

Auto-generated TypeScript API client from the FastAPI backend's OpenAPI schema. Provides type-safe SDK functions for all 47 backend endpoints with 68 generated types.

## Key Flows

### Generate SDK from Schema

1. Backend running on `localhost:8123` exposes `/openapi.json`
2. `pnpm refresh` fetches schema → saves to `openapi.json` → runs `@hey-api/openapi-ts`
3. Generated files written to `src/client/` (types, SDK functions, client singleton)
4. Web app imports SDK functions via `@vtv/sdk` workspace dependency

### Consume SDK in Web App

1. Import `@/lib/sdk` as side-effect (configures client singleton with auth + base URL)
2. Import SDK functions from `@vtv/sdk`
3. SDK functions return `{ data, error, response }` — check `error` before using `data`

## Generated Files

| File | Contents | Size |
|------|----------|------|
| `src/client/types.gen.ts` | 68 TypeScript types from OpenAPI schemas | ~76KB |
| `src/client/sdk.gen.ts` | 47 typed SDK functions (one per endpoint) | ~57KB |
| `src/client/client.gen.ts` | Singleton HTTP client instance | ~1KB |
| `src/client/index.ts` | Barrel re-export of types + SDK | ~0.1KB |

## Configuration

| File | Purpose |
|------|---------|
| `openapi-ts.config.ts` | Generation config (input: local `openapi.json`, plugins: typescript + client-fetch + sdk) |
| `openapi.json` | Local copy of backend schema (committed for reproducible builds) |
| `package.json` | Exports: `.` (types + SDK), `./client` (client singleton) |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `@hey-api/client-fetch` | ^0.13.1 | Fetch-based HTTP client with interceptors |
| `@hey-api/openapi-ts` | ^0.64.0 | Code generator (dev dependency) |

## Integration Points

- **FastAPI backend**: Source of truth — OpenAPI schema at `/openapi.json`
- **Web app (`@vtv/web`)**: Consumer — `src/lib/sdk.ts` configures client, domain wrappers call SDK functions
- **Auth.js**: JWT tokens injected via request interceptor in `sdk.ts` (dual server/client context)

## Commands

```bash
pnpm --filter @vtv/sdk generate-sdk   # Regenerate from local openapi.json
pnpm --filter @vtv/sdk refresh        # Fetch fresh schema + regenerate (requires running backend)
```

## Migration Status

All 8 domain clients migrated from hand-written `authFetch` wrappers to SDK wrappers (commit b9e34f0, 2026-02-26).

| Legacy Client | SDK Wrapper |
|---------------|-------------|
| `events-client.ts` | `events-sdk.ts` |
| `stops-client.ts` | `stops-sdk.ts` |
| `drivers-client.ts` | `drivers-sdk.ts` |
| `users-client.ts` | `users-sdk.ts` |
| `schedules-client.ts` | `schedules-sdk.ts` |
| `documents-client.ts` | `documents-sdk.ts` |
| `gtfs-client.ts` | `gtfs-sdk.ts` |
| `agent-client.ts` | `agent-sdk.ts` |
