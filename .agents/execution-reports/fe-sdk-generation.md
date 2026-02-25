# Execution Report: @vtv/sdk Generation & Events Migration

**Date:** 2026-02-25
**Plan:** `.agents/plans/fe-sdk-generation.md`
**Status:** Complete

## Summary

Generated a fully-typed TypeScript API client (`@vtv/sdk`) from the FastAPI backend's OpenAPI schema (47 endpoints, 68 types) and migrated the events domain as a proof-of-concept. All validation gates passed (TypeScript, lint, build, security, design system, i18n, accessibility).

## Files Created

| File | Purpose |
|------|---------|
| `cms/packages/sdk/openapi.json` | Local copy of backend OpenAPI schema (reproducible builds) |
| `cms/packages/sdk/src/client/types.gen.ts` | 68 generated TypeScript types (76KB) |
| `cms/packages/sdk/src/client/sdk.gen.ts` | 47 typed SDK functions (57KB) |
| `cms/packages/sdk/src/client/client.gen.ts` | Singleton HTTP client instance |
| `cms/packages/sdk/src/client/index.ts` | Barrel re-export |
| `cms/apps/web/src/lib/sdk.ts` | Client configuration (base URL + JWT auth interceptor) |
| `cms/apps/web/src/lib/events-sdk.ts` | Events domain wrapper (drop-in replacement) |

## Files Modified

| File | Change |
|------|--------|
| `cms/packages/sdk/openapi-ts.config.ts` | Changed input to local file, added client-fetch plugin, removed transformer |
| `cms/packages/sdk/package.json` | Upgraded client-fetch to 0.13.1, added `./client` export, added `refresh` script |
| `cms/apps/web/src/hooks/use-calendar-events.ts` | Import swapped from `events-client` to `events-sdk` |

## Divergences from Plan

| Plan Step | Deviation | Reason |
|-----------|-----------|--------|
| Task 2 | Plan kept `transformer: true` | Removed — requires `@hey-api/transformers` plugin which isn't needed |
| Task 3 | Plan didn't include `@hey-api/client-fetch` plugin | Added — required for SDK generation (codegen needs to know which client) |
| Task 5 | Plan used `createClient()` | Used `client.setConfig()` on existing singleton — generated `client.gen.ts` already creates the singleton that all SDK functions import |
| Task 5 | Plan didn't mention `./client` export | Added `"./client": "./src/client/client.gen.ts"` to package.json exports |

## Bugs Found During Implementation

| Bug | Root Cause | Fix Applied |
|-----|-----------|-------------|
| "client needs to be set to generate SDKs" | `@hey-api/sdk` plugin requires a client plugin to be listed | Added `"@hey-api/client-fetch"` to plugins array |
| "missing plugin - no plugin with tag 'transformer' found" | `transformer: true` requires `@hey-api/transformers` plugin (not installed) | Removed `transformer: true`, used plain string `"@hey-api/sdk"` |
| `Module '"@hey-api/client-fetch"' has no exported member 'ClientOptions'` | Version mismatch: `@hey-api/client-fetch@0.6.0` too old for generated code from `openapi-ts@0.64.15` | Upgraded to `@hey-api/client-fetch@0.13.1` + regenerated |
| SDK functions using unconfigured client | Plan assumed `createClient()` in `sdk.ts` would be used by SDK functions | Used `client.setConfig()` on the existing `client.gen.ts` singleton — SDK functions import from same module |

## Validation Results

```
Frontend Validation Results:
  1. TypeScript:          PASS  [0 errors]
  2. Lint:                PASS  [0 issues]
  3. Build:               PASS  [13 routes]
  4. Security patterns:   PASS  [0 violations]
  5. Design system:       PASS  [0 violations]
  6. i18n completeness:   PASS  [693 keys, 100% parity]
  7. Accessibility:       PASS  [0 issues]
```

## Code Review

Review at `.agents/code-reviews/fe-sdk-integration-review.md`:
- 7 files reviewed against 8 standards
- 2 Low-priority issues (type cast verbosity, manual null mapping)
- 0 Critical, 0 High, 0 Medium

## Next Steps

Migrate remaining 8 hand-written clients following the same pattern:
1. `stops-client.ts` → `stops-sdk.ts`
2. `drivers-client.ts` → `drivers-sdk.ts`
3. `users-client.ts` → `users-sdk.ts`
4. `schedules-client.ts` → `schedules-sdk.ts`
5. `documents-client.ts` → `documents-sdk.ts`
6. `gtfs-client.ts` → `gtfs-sdk.ts`
7. `agent-client.ts` → `agent-sdk.ts`
