# Frontend Review: SDK Integration (`@vtv/sdk`)

**Date:** 2026-02-25
**Scope:** All files created/modified for the `@vtv/sdk` generation and events-client migration.

**Files reviewed:**
1. `cms/packages/sdk/openapi-ts.config.ts` (modified)
2. `cms/packages/sdk/package.json` (modified)
3. `cms/packages/sdk/src/client/client.gen.ts` (generated)
4. `cms/packages/sdk/src/client/index.ts` (generated)
5. `cms/apps/web/src/lib/sdk.ts` (created)
6. `cms/apps/web/src/lib/events-sdk.ts` (created)
7. `cms/apps/web/src/hooks/use-calendar-events.ts` (modified)

**Summary:** Clean infrastructure integration with correct auth patterns, proper TypeScript types, and good separation of concerns. The side-effect import pattern for client configuration is unconventional but necessary given the generated code's singleton architecture. Two minor issues found — both Low priority.

## Findings

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `events-sdk.ts:56` | TypeScript | `as unknown as PaginatedEvents` double cast on generated type that is structurally compatible | Consider removing cast once hand-written types are retired; safe for now since shapes match | Low |
| `events-sdk.ts:96-103` | TypeScript | Manual `?? null` mapping for every field in `updateEvent` body is verbose | Could pass `eventData` directly if generated `EventUpdate` type aligns with hand-written one | Low |

## Standard-by-Standard Assessment

### 1. TypeScript Quality — PASS
- All functions have full type annotations (params + return types)
- No `any`, no `@ts-ignore`, no `@ts-expect-error`
- `'use client'` correctly applied only on the hook file
- `sdk.ts` is correctly a plain module (no `'use client'`) since it configures a singleton used in both contexts
- The `as unknown as` casts in `events-sdk.ts` are justified — bridging generated types to hand-written types during migration; structurally compatible shapes

### 2. Design System Compliance — N/A
- No UI components in scope — all files are data-fetching infrastructure
- No className, no Tailwind, no colors

### 3. Component Patterns — N/A
- No React components in the changed files
- Hook (`use-calendar-events.ts`) change is a single import swap — no pattern issues

### 4. Internationalization — N/A
- No user-visible text in any reviewed file
- Error messages in `EventsApiError` are developer-facing (thrown in catch blocks, not rendered to UI)

### 5. Accessibility — N/A
- No UI rendering in any reviewed file

### 6. RBAC & Auth — PASS
- `sdk.ts` auth interceptor correctly uses dual-context pattern:
  - Server: `auth()` via dynamic import (no network call, just JWT decode)
  - Client: `getSession()` via dynamic import
- Dynamic imports prevent server-only modules from breaking client bundle
- Bearer token injected into request headers (same pattern as battle-tested `authFetch`)
- No credentials hardcoded — base URL from `NEXT_PUBLIC_AGENT_URL` env var with localhost fallback

### 7. Data Fetching & Performance — PASS
- Side-effect import (`import "@/lib/sdk"`) ensures client is configured before any SDK call
- Singleton pattern means configuration runs once per module evaluation, not per request
- `use-calendar-events.ts` polling pattern unchanged — still 60s interval with cleanup
- No unnecessary re-renders introduced

### 8. Security — PASS
- Auth tokens via httpOnly cookies (Auth.js), not localStorage
- Dynamic imports for server-only modules — no client bundle contamination
- No hardcoded credentials or API keys
- `EventsApiError` error messages are generic (no role names, no internal details leaked)
- `response.status` propagated correctly for proper HTTP error handling
- No `dangerouslySetInnerHTML`, no XSS vectors

## Architecture Notes

**Singleton Client Pattern:** The generated `client.gen.ts` creates a module-level singleton via `createClient()`. The `sdk.ts` module configures this same instance (via `setConfig()` + interceptor). SDK functions in `sdk.gen.ts` import the same singleton as `_heyApiClient`. This means:
- Configuration is guaranteed to run before first use (JavaScript module evaluation order)
- All SDK functions share the same auth interceptor
- No risk of multiple client instances with different configs

**Side-effect Import Trade-off:** `import "@/lib/sdk"` is a side-effect import — it doesn't import any named exports, just triggers module evaluation. This is the correct pattern for configuring a singleton, but it's non-obvious. The JSDoc comment in `sdk.ts` documents this clearly.

## Stats
- Files reviewed: 7
- Issues: 2 total — 0 Critical, 0 High, 0 Medium, 2 Low
