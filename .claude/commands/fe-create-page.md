---
description: Scaffold a new Next.js page with i18n, RBAC, sidebar nav, and design system integration
argument-hint: [page-name] e.g. routes, stops, schedules
allowed-tools: Read, Write, Edit
---

Scaffold a new VTV frontend page named "$ARGUMENTS" with i18n, RBAC, sidebar nav entry, and design tokens.

@cms/design-system/vtv/MASTER.md

## Steps

1. **Validate the page name**: Must be lowercase, alphanumeric with hyphens (e.g., `routes`, `bus-stops`). This becomes the URL segment and directory name.

2. **Read existing patterns** before creating anything:
   - `cms/apps/web/src/app/[locale]/(dashboard)/page.tsx` — dashboard page pattern (server component, i18n, semantic tokens)
   - `cms/apps/web/src/app/[locale]/layout.tsx` — sidebar nav structure
   - `cms/apps/web/middleware.ts` — RBAC route matchers
   - `cms/apps/web/messages/lv.json` — i18n key structure
   - `cms/apps/web/messages/en.json` — English translations
   - `cms/packages/ui/src/tokens.css` — available design tokens

3. **Create the page component** at `cms/apps/web/src/app/[locale]/(dashboard)/{page-name}/page.tsx`:
   - Server component (default) with `useTranslations` from `next-intl`
   - Import and use semantic tokens from design system (no hardcoded colors)
   - Include proper TypeScript types
   - Follow the dashboard page pattern:
     ```tsx
     import { useTranslations } from 'next-intl';

     export default function PageName() {
       const t = useTranslations('pageName');
       return (
         <div className="flex flex-1 flex-col gap-6 p-6">
           <h1 className="text-2xl font-bold" style={{ color: 'var(--color-text-primary)' }}>
             {t('title')}
           </h1>
           {/* Placeholder content */}
           <div className="rounded-lg border p-8 text-center" style={{
             borderColor: 'var(--color-border-default)',
             backgroundColor: 'var(--color-surface-secondary)'
           }}>
             <p style={{ color: 'var(--color-text-secondary)' }}>
               {t('placeholder')}
             </p>
           </div>
         </div>
       );
     }
     ```
   - Add `aria-label` on the main container for accessibility

4. **Add i18n keys** to `cms/apps/web/messages/lv.json`:
   - Add a `"{page-name}"` section with at minimum:
     - `"title"` — Page title in Latvian
     - `"nav"` — Sidebar nav label in Latvian
     - `"placeholder"` — Placeholder text in Latvian (e.g., "Šī lapa ir izstrādes stadijā")
   - Add nav label under `"navigation"` section

5. **Add i18n keys** to `cms/apps/web/messages/en.json`:
   - Mirror the exact same key structure as `lv.json`
   - `"title"` — Page title in English
   - `"nav"` — Sidebar nav label in English
   - `"placeholder"` — Placeholder text in English (e.g., "This page is under development")

6. **Add sidebar nav entry** in `cms/apps/web/src/app/[locale]/layout.tsx`:
   - Add a nav link in the sidebar matching existing pattern
   - Use appropriate Lucide icon
   - Link to `/{locale}/{page-name}`
   - Respect existing nav ordering

7. **Update middleware** in `cms/apps/web/middleware.ts`:
   - Add the new route to the matcher config
   - Set appropriate role permissions (default: all authenticated users)
   - Follow the existing matcher pattern

8. **Report what was created** and remind the user to:
   - Review the placeholder page and fill in real content
   - Run `/fe-validate` to verify all quality gates
   - Consider running `/fe-planning {page-name} details` for a full implementation plan
   - Run `/commit` when ready

**Next steps:**
1. Fill in page content, data fetching, and components
2. Run `/fe-validate` to check all quality gates
3. Run `/commit` when ready
