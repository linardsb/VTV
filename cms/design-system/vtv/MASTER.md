# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** VTV
**Generated:** 2026-02-16 15:59:21
**Category:** Government/Public Service

---

## Global Rules

### Color Palette

| Role | Hex | CSS Variable |
|------|-----|--------------|
| Primary | `#0F172A` | `--color-primary` |
| Secondary | `#334155` | `--color-secondary` |
| CTA/Accent | `#0369A1` | `--color-cta` |
| Background | `#F8FAFC` | `--color-background` |
| Text | `#020617` | `--color-text` |

**Color Notes:** High contrast navy + blue

### Typography

- **Heading Font:** Lexend
- **Body Font:** Source Sans 3
- **Mono Font:** JetBrains Mono
- **Mood:** corporate trust, clean, professional, data-driven
- **Google Fonts:** [Lexend + Source Sans 3](https://fonts.google.com/share?selection.family=Lexend:wght@400;500;600;700|Source+Sans+3:wght@300;400;500;600;700)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;500;600;700&display=swap');
```

**CSS Variables (from tokens.css):**
```css
--font-heading: "Lexend", system-ui, sans-serif;
--font-body: "Source Sans 3", system-ui, sans-serif;
--font-mono: "JetBrains Mono", ui-monospace, monospace;
```

### Spacing Variables (Base Scale)

| Token | Value | Usage |
|-------|-------|-------|
| `--spacing-xs` | `4px` / `0.25rem` | Tight gaps |
| `--spacing-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--spacing-md` | `16px` / `1rem` | Standard padding |
| `--spacing-lg` | `24px` / `1.5rem` | Section padding |
| `--spacing-xl` | `32px` / `2rem` | Large gaps |
| `--spacing-2xl` | `48px` / `3rem` | Section margins |

### Compact Spacing Tokens (Dashboard Density)

Purpose-named tokens for data-dense UIs. Use via Tailwind: `p-(--spacing-card)`, `gap-(--spacing-grid)`, etc.

| Token | Value | Usage |
|-------|-------|-------|
| `--spacing-page` | `16px` / `1rem` | Main content area padding |
| `--spacing-section` | `16px` / `1rem` | Gap between major sections |
| `--spacing-card` | `12px` / `0.75rem` | Card internal padding |
| `--spacing-cell` | `6px` / `0.375rem` | Calendar cell padding |
| `--spacing-inline` | `6px` / `0.375rem` | Icon-to-text, button gaps |
| `--spacing-grid` | `12px` / `0.75rem` | Grid gap between cards/columns |
| `--spacing-tight` | `4px` / `0.25rem` | Micro gaps (badges, dots) |
| `--spacing-row` | `48px` / `3rem` | Week-view hour row height |

**Usage pattern:** Always reference these tokens via Tailwind arbitrary value syntax — `p-(--spacing-card)` not `p-3`. This allows global adjustment by changing the token value in `tokens.css`.

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.1)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.1)` | Modals, dropdowns |
| `--shadow-xl` | `0 20px 25px rgba(0,0,0,0.15)` | Hero images, featured cards |

---

## Component Specs

### Buttons

```css
/* Primary Button */
.btn-primary {
  background: #0369A1;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}

.btn-primary:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Secondary Button */
.btn-secondary {
  background: transparent;
  color: #0F172A;
  border: 2px solid #0F172A;
  padding: 12px 24px;
  border-radius: 8px;
  font-weight: 600;
  transition: all 200ms ease;
  cursor: pointer;
}
```

### Cards

```css
.card {
  background: #F8FAFC;
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-md);
  transition: all 200ms ease;
  cursor: pointer;
}

.card:hover {
  box-shadow: var(--shadow-lg);
  transform: translateY(-2px);
}
```

### Inputs

```css
.input {
  padding: 12px 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
  font-size: 16px;
  transition: border-color 200ms ease;
}

.input:focus {
  border-color: #0F172A;
  outline: none;
  box-shadow: 0 0 0 3px #0F172A20;
}
```

### Modals

```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
}

.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  box-shadow: var(--shadow-xl);
  max-width: 500px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Accessible & Ethical

**Keywords:** High contrast, large text (16px+), keyboard navigation, screen reader friendly, WCAG compliant, focus state, semantic

**Best For:** Government, healthcare, education, inclusive products, large audience, legal compliance, public

**Key Effects:** Clear focus rings (3-4px), ARIA labels, skip links, responsive design, reduced motion, 44x44px touch targets

### Page Pattern

**Pattern Name:** Minimal & Direct

- **CTA Placement:** Above fold
- **Section Order:** Hero > Features > CTA

---

## Anti-Patterns (Do NOT Use)

- ❌ Ornate design
- ❌ Low contrast
- ❌ Motion effects
- ❌ AI purple/pink gradients

### Additional Forbidden Patterns

- ❌ **Emojis as icons** — Use SVG icons (Heroicons, Lucide, Simple Icons)
- ❌ **Missing cursor:pointer** — All clickable elements must have cursor:pointer
- ❌ **Layout-shifting hovers** — Avoid scale transforms that shift layout
- ❌ **Low contrast text** — Maintain 4.5:1 minimum contrast ratio
- ❌ **Instant state changes** — Always use transitions (150-300ms)
- ❌ **Invisible focus states** — Focus states must be visible for a11y

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis used as icons (use SVG instead)
- [ ] All icons from consistent icon set (Heroicons/Lucide)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover states with smooth transitions (150-300ms)
- [ ] Light mode: text contrast 4.5:1 minimum
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed navbars
- [ ] No horizontal scroll on mobile
