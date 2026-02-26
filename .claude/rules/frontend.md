---
paths:
  - "cms/**/*.ts"
  - "cms/**/*.tsx"
  - "cms/**/*.css"
---

# Frontend Rules

## React 19 Anti-Patterns

1. **No `setState` in `useEffect`** — use `key` prop remount pattern or data-fetching library
2. **No component defs inside components** — extract to module scope
3. **No `Math.random()` in render** — use `useId()` or generate outside render
4. **Const literal narrowing** — annotate as `string` when comparing to other values

## Tailwind v4 Container Size Anti-Pattern

Named container sizes (`max-w-sm`, `max-w-md`, `max-w-lg`, `max-w-xl`, `max-w-2xl`) use CSS variables NOT defined in the project's `@theme inline` block. Elements using these collapse to ~50px wide.

**Fix:** Always use explicit rem values: `sm:max-w-[28rem]`, `sm:max-w-[32rem]`, `sm:max-w-[36rem]`.

## Dialog Modal Convention

All detail views, create/edit forms, and upload panels use centered `Dialog` (not `Sheet`). Sheet is only for mobile sidebar. Dialog widths: detail=`sm:max-w-[28rem]`, forms=`sm:max-w-[32rem]` (default), wide=`sm:max-w-[36rem]`.

## Server/Client Boundary

- `authFetch` uses dynamic imports for dual-context (server: `auth()`, client: `getSession()`)
- NEVER statically import server-only functions like `auth()` in files that may be imported by `"use client"` components
- For authenticated endpoints, use `authFetch`. For public endpoints from client hooks, plain `fetch()` is simpler
