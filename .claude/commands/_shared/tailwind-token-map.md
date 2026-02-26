# Tailwind Semantic Token Rules

## Forbidden Primitive Classes — Use Semantic Alternatives

NEVER use Tailwind primitive color classes. Use semantic tokens from `cms/packages/ui/src/tokens.css`.

### Common Mapping Table

| Forbidden | Use Instead |
|-----------|-------------|
| `text-gray-500`, `text-slate-500` | `text-foreground-muted` |
| `text-gray-400`, `text-slate-400` | `text-foreground-subtle` |
| `text-white` (on colored bg) | `text-interactive-foreground` / `text-primary-foreground` |
| `bg-blue-600`, `bg-blue-500` | `bg-primary` or `bg-interactive` |
| `bg-red-500`, `bg-red-600` | `bg-destructive` or `bg-error` |
| `bg-green-500`, `bg-emerald-500` | `bg-success` or `bg-status-ontime` |
| `bg-amber-500`, `bg-yellow-500` | `bg-warning` or `bg-status-delayed` |
| `border-gray-200` | `border-border` |
| `border-red-200` | `border-error-border` |
| `bg-gray-100`, `bg-slate-100` | `bg-surface` or `bg-surface-secondary` |
| `bg-red-50` | `bg-error-bg` |
| `text-red-700`, `text-red-600` | `text-error` |
| `bg-blue-400` | `bg-category-maintenance` |
| `bg-amber-400` | `bg-category-route-change` |
| `bg-emerald-500` | `bg-category-driver-shift` or `bg-transport-trolleybus` |
| `bg-purple-600` | `bg-transport-tram` |
| `text-blue-600` | `text-transport-bus` or `text-interactive` |
| `text-emerald-500` | `text-transport-trolleybus` or `text-status-ontime` |
| `text-purple-600` | `text-transport-tram` |

If unsure about the correct semantic token, check `cms/packages/ui/src/tokens.css` before writing the class.

**Exception:** Inline HTML strings (e.g., Leaflet `L.divIcon` html) may use hex colors since Tailwind classes don't work there. GTFS route color data values (hex stored in DB) are also acceptable.

### Full Forbidden Classes by Category

- **Neutral text**: `text-gray-`, `text-slate-`, `text-zinc-`, `text-neutral-` → `text-foreground-*`
- **Colored text**: `text-blue-`, `text-red-`, `text-green-`, `text-amber-`, `text-emerald-`, `text-purple-`, `text-orange-` → `text-primary`, `text-error`, `text-success`, `text-transport-*`, `text-category-*`
- **White text**: `text-white` paired with colored backgrounds → `text-interactive-foreground`, `text-primary-foreground`, `text-destructive-foreground`
- **Primary backgrounds**: `bg-blue-`, `bg-red-`, `bg-green-`, `bg-yellow-`, `bg-gray-`, `bg-slate-` → `bg-primary`, `bg-destructive`, `bg-success`, `bg-warning`, `bg-surface-*`, `bg-muted`
- **Domain backgrounds**: `bg-amber-`, `bg-emerald-`, `bg-purple-`, `bg-orange-` → `bg-category-*`, `bg-transport-*`
- **Error states**: `bg-red-50` → `bg-error-bg`, `border-red-200` → `border-error-border`, `text-red-700` → `text-error`
- **Primary borders**: `border-gray-`, `border-slate-` → `border-border`
- **Colored borders**: `border-blue-`, `border-red-`, `border-amber-`, `border-emerald-`, `border-purple-` → `border-error-border`, `border-transport-*`, `border-category-*`

### Semantic Token Reference

- **Surface**: `bg-surface`, `bg-surface-raised`, `bg-background`
- **Interactive**: `bg-interactive`, `text-interactive`, `text-interactive-foreground`
- **Error**: `bg-error-bg`, `border-error-border`, `text-error`
- **Status**: `text-status-ontime`, `text-status-delayed`, `text-status-critical`
- **Transport**: `bg-transport-bus`, `bg-transport-trolleybus`, `bg-transport-tram` (+ `text-` and `border-` variants)
- **Calendar**: `bg-category-maintenance`, `bg-category-route-change`, `bg-category-driver-shift`, `bg-category-service-alert`

## Design System Compliance Scan

When validating `.tsx` files, check for these violations:

- Hardcoded hex colors (`#[0-9a-fA-F]{3,8}`) — except inline HTML for Leaflet
- Hardcoded `rgb()`, `hsl()`, `oklch()` values
- `style={{ color:` with string literals (should use `var(--color-*)`)
- ALL Tailwind primitive color classes listed above
- Hardcoded spacing via inline `style` with pixel values
- Verify semantic tokens used: `--color-surface-*`, `--color-text-*`, `--color-border-*`
