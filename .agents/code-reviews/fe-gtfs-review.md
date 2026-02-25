# Frontend Review: `cms/apps/web/src/components/gtfs/`

**Date:** 2026-02-25
**Reviewer:** Claude (automated)
**Target:** GTFS Data Management page components + page + client

**Summary:** Well-built components following VTV conventions. Strong i18n, design system compliance, and accessibility. A few medium/low issues around error handling robustness in the API client.

| File:Line | Standard | Issue | Suggestion | Priority |
|-----------|----------|-------|------------|----------|
| `gtfs-client.ts:28-43` | Data Fetching | `fetchGTFSStats` makes 5 API calls; no error handling per-call — one 404 crashes all stats | Add `.catch(() => ({ total: 0 }))` per request so partial data still renders | Medium |
| `gtfs-client.ts:28-43` | Data Fetching | `authFetch` responses not checked for `!response.ok` before `.json()` — 4xx/5xx causes confusing parse error | Add `.ok` check or wrap with a helper like `fetchFeeds` does | Medium |
| `gtfs/page.tsx:1` | Performance | Entire page is `'use client'` — header and tabs could be server-rendered | Split into server page shell + client `GTFSContent`. Low urgency (matches other VTV pages) | Low |
| `gtfs-client.ts:9` | Component Patterns | `fetchAgencies` imported but only used inside `fetchGTFSStats` — page imports it directly from `schedules-client` | Remove unused import from `gtfs-client.ts` | Low |
| `data-overview.tsx:69` | Design System | `text-status-ontime` — verify token exists in `tokens.css` | If missing, use `text-success` | Low |
| `data-overview.tsx:110` | Component Patterns | Template literal for conditional class instead of `cn()` | Use `cn("size-4 mr-1", isLoading && "animate-spin")` | Low |
| `gtfs-client.ts:81-86` | Security | Export download uses hardcoded filename `"gtfs.zip"` | Consider reading Content-Disposition header | Low |

**Stats:**
- Files reviewed: 5 (data-overview.tsx, gtfs-export.tsx, page.tsx, gtfs-client.ts, gtfs.ts)
- Issues: 7 total — 0 Critical, 0 High, 2 Medium, 5 Low

**What's done well:**
- 27 i18n keys fully matched lv/en
- Semantic design tokens throughout, zero Tailwind primitives
- Session gate pattern applied correctly
- React 19 compliant (module-scope helpers)
- Props interfaces on all components
- Accessibility: aria-hidden on decorative icons, label on select
- RBAC: /gtfs protected in middleware (admin + editor)
- Loading skeletons
- useCallback memoization

**Next step:** To fix issues: `/code-review-fix .agents/code-reviews/fe-gtfs-review.md`
