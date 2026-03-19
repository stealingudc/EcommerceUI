# UI/UX Design Guidelines — V3 Rebuild

> Distilled from *"The Architecture of Digital Experiences: A 2026 Paradigm for UI/UX Design"*. Every rule here is actionable for our e-commerce BI platform.

---

## 1. Design Token System (3-Tier)

Build all styling on a token hierarchy — never hardcode colors, spacing, or fonts directly.

### Tier 1 — Primitive Tokens (Raw Values)
```
--color-slate-950: #020617
--color-slate-900: #0f172a
--color-slate-800: #1e293b
--color-slate-700: #334155
--color-slate-600: #475569
--color-slate-400: #94a3b8
--color-indigo-600: #4f46e5
--color-indigo-500: #6366f1
--color-emerald-500: #10b981
--color-emerald-400: #34d399
--color-amber-500: #f59e0b
--color-amber-400: #fbbf24
--color-red-500: #ef4444
--color-red-400: #f87171
--color-cyan-500: #06b6d4
--color-white: #ffffff
--spacing-unit: 4px
--radius-sm: 6px
--radius-md: 8px
--radius-lg: 12px
--radius-xl: 16px
```

### Tier 2 — Semantic Tokens (Intent)
```
--color-bg-primary: var(--color-slate-950)
--color-bg-surface: var(--color-slate-900)
--color-bg-card: var(--color-slate-800)
--color-bg-hover: var(--color-slate-700)
--color-text-primary: var(--color-white)
--color-text-secondary: var(--color-slate-400)
--color-text-muted: var(--color-slate-600)
--color-accent-primary: var(--color-indigo-600)
--color-accent-hover: var(--color-indigo-500)
--color-status-success: var(--color-emerald-500)
--color-status-warning: var(--color-amber-500)
--color-status-error: var(--color-red-500)
--color-status-info: var(--color-cyan-500)
--color-border-default: rgba(51, 65, 85, 0.5)
```

### Tier 3 — Component Tokens (Specific)
```
--button-primary-bg: var(--color-accent-primary)
--button-primary-bg-hover: var(--color-accent-hover)
--card-bg: var(--color-bg-card)
--card-border: var(--color-border-default)
--card-radius: var(--radius-xl)
--sidebar-bg: var(--color-bg-surface)
--sidebar-active-bg: var(--color-accent-primary)
--table-row-hover: var(--color-bg-hover)
--badge-healthy-bg: rgba(16, 185, 129, 0.2)
--badge-healthy-text: var(--color-emerald-400)
--badge-warning-bg: rgba(245, 158, 11, 0.2)
--badge-warning-text: var(--color-amber-400)
--badge-error-bg: rgba(239, 68, 68, 0.2)
--badge-error-text: var(--color-red-400)
```

> **Rule**: Changing a primitive token must cascade correctly. Changing `--color-indigo-600` should update every button, active nav, and accent element across the entire app.

---

## 2. Color Rules

| Rule | Requirement |
|---|---|
| **Never use pure black on white** | Use dark grays on off-whites (reduces eye strain, especially for dyslexia/astigmatism) |
| **WCAG AA contrast** | Minimum 4.5:1 for normal text, 3:1 for large text (18pt+) and UI graphics |
| **Never rely on color alone** | Every status indicator must pair color with text label AND icon (for colorblind users — 300M globally) |
| **Color meanings** | Red = error/danger/urgency, Green = success/confirmation, Amber = warning, Blue/Indigo = trust/primary action, Cyan = info |
| **CTA prominence** | CTAs must have high contrast against background, never blend in. Use hover states + micro-animations to signal clickability |

### Status Color Mapping for Our App:
| Status | Color | Use Case |
|---|---|---|
| Healthy / Active / In Stock | Emerald | Margin health, parser status, stock presence |
| Warning / Partial | Amber | Margin "Average", parser "Partial" |
| Error / Inactive / Low | Red | Margin "Low", parser "Inactive", stock out |
| Info / Pipeline | Cyan | Pipeline status, informational |
| Primary Action | Indigo | Buttons, active nav, links |
| Neutral | Slate-400 | Secondary text, muted elements |

---

## 3. Typography Stack

| Element | Size | Weight | Font |
|---|---|---|---|
| Page title (h1) | clamp(1.5rem, 2vw, 2rem) | 700 (Bold) | Inter / system-ui |
| Section heading (h2) | clamp(1.125rem, 1.5vw, 1.5rem) | 600 (Semibold) | Inter / system-ui |
| Table header | 0.75rem (12px) | 600, uppercase, tracking-wide | Inter / system-ui |
| Body text | 0.875rem (14px) | 400 | Inter / system-ui |
| Small / caption | 0.75rem (12px) | 400 | Inter / system-ui |
| Monospace (code, IDs) | 0.8125rem (13px) | 400 | JetBrains Mono / monospace |

### Rules:
- Use `font-display: swap` for custom fonts (prevent invisible text during load)
- Limit to **2 font families max** (1 sans-serif + 1 monospace)
- Use WOFF2 format exclusively (best compression)
- Line-height: 1.5 for body text, 1.3 for headings
- Left-align all body text (never justify)
- Use `clamp()` for fluid typography — zero breakpoints needed

---

## 4. Layout System

### Bento Grid Approach
Use a modular grid with distinct, rounded compartments for dense data:
```css
.bento-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: var(--spacing-4);
}
```

### Container Queries (NOT viewport queries)
Components must respond to their container, not the viewport:
```css
.card-container { container-type: inline-size; }
@container (min-width: 400px) { /* horizontal layout */ }
@container (max-width: 399px) { /* stacked layout */ }
```

### Mobile-First Mandate
- **Build for mobile first**, expand for desktop via `min-width` queries
- 62% of web traffic is mobile — never treat it as an afterthought
- 80.2% mobile cart abandonment rate when mobile UX is poor

### Spacing Scale (4px base)
```
--spacing-1: 4px    --spacing-2: 8px    --spacing-3: 12px
--spacing-4: 16px   --spacing-5: 20px   --spacing-6: 24px
--spacing-8: 32px   --spacing-10: 40px  --spacing-12: 48px
```

---

## 5. Navigation Rules

| Rule | Detail |
|---|---|
| **Position** | Anchored at left (sidebar) — never hidden behind hamburger on desktop |
| **Top-level items** | Maximum 5-7 overarching items to prevent decision fatigue |
| **Naming** | Plain, obvious language — no branded jargon |
| **Current state** | Always visually highlight the active page (active nav state) |
| **Breadcrumbs** | Provide on deep pages (Product Detail, Pipeline) |
| **Consistency** | Never change navigation structure between pages |
| **Grouping** | Group by user intent, not internal structure |
| **Collapsible sections** | Use for parser categories (progressive disclosure) |
| **Count badges** | Show product counts on navigation links for context |

---

## 6. Loading & Perceived Performance

### Skeleton Screens (Mandatory)
**Replace ALL loading spinners with skeleton screens:**
- Pre-render gray placeholder blocks exactly where content will appear
- Add subtle pulsating animation (indicates activity)
- **Prevents layout shift** (CLS improvement)
- **Reduces bounce 9-20%** even with identical actual load times
- Use for: Dashboard table, Bestsellers table, Pipeline form, Chart areas

### Optimistic Updates
When user changes pipeline status or toggles shortlist:
1. Update UI immediately (don't wait for server response)
2. Update sidebar counts client-side
3. Revert on server error

### Micro-Interactions (5 Rules)
1. **Understand the need**: Only animate when it serves a purpose
2. **Immediate feedback**: Button press → brief color change or depression
3. **Simplicity**: Never slow the user down to watch an animation
4. **Consistency**: Same interaction = same animation everywhere
5. **Humanized**: Feel natural, not mechanical

### Specific Interactions for Our App:
- Button click → brief scale-down + color shift (50ms)
- Heart toggle → fill animation with subtle bounce
- Status dropdown change → smooth color transition
- Save success → brief emerald flash on saved section
- Table sort → column header highlight + smooth re-render
- Tab switch → slide or cross-fade transition (150ms max)
- Data refresh → pulse indicator on refresh button while loading

---

## 7. Accessibility Checklist (WCAG AA)

### Must-Have:
- [ ] **Contrast ratios**: 4.5:1 normal text, 3:1 large text + icons
- [ ] **Touch targets**: Minimum 44x44px for all interactive elements
- [ ] **Keyboard navigation**: Full app usable with Tab/Enter/Escape only
- [ ] **Visible focus indicators**: High-contrast outline on focused element
- [ ] **Skip navigation link**: Hidden link that appears on first Tab press → jumps to main content
- [ ] **No keyboard traps**: Escape always exits modals/dropdowns
- [ ] **Semantic HTML**: Proper `<button>`, `<nav>`, `<main>`, `<table>`, heading hierarchy (single `<h1>`)
- [ ] **ARIA attributes**: Announce state of dynamic elements (expanded/collapsed dropdowns, loading states)
- [ ] **Never use color alone**: Pair status colors with text labels AND icons
- [ ] **Form errors**: Place immediately adjacent to input field, use plain language + icon
- [ ] **No auto-playing media or auto-timeouts**
- [ ] **Alt text** on all images

---

## 8. Frontend Performance Rules

### Asset Optimization
| Asset | Rule |
|---|---|
| **JavaScript** | Code-split by route. Tree-shake dead code. Keep tasks <50ms (avoid main thread blocking) |
| **CSS** | Minify. Use WOFF2 for fonts. Limit to 2 font families |
| **Images** | Serve AVIF/WebP. Use `srcset` for responsive sizes. Below-fold: `loading="lazy"` |
| **Compression** | Brotli or GZIP on all text assets (HTML, CSS, JS) |
| **HTTP** | Use HTTP/2+ for multiplexing. `<link rel="preload">` for critical assets |

### Core Web Vitals Targets
| Metric | Target | What it measures |
|---|---|---|
| **LCP** (Largest Contentful Paint) | <2.5s | Time to render the largest visible element |
| **INP** (Interaction to Next Paint) | <200ms | Responsiveness to user input throughout session |
| **CLS** (Cumulative Layout Shift) | <0.1 | Visual stability (no jumping elements) |

### INP Optimization (3 Phases)
1. **Input Delay**: Defer non-critical 3rd party scripts. Break long JS tasks into <50ms chunks
2. **Processing Duration**: Event handlers do minimum work → trigger visual feedback first, heavy processing in Web Workers
3. **Presentation Delay**: Minimize DOM depth. Use `content-visibility: auto` for off-screen content

### Predictive Loading
- Use Speculation Rules API for likely next pages
- Prerender checkout/pipeline-details on hover (200ms intent signal)
- Auto-suppress on Data Saver / Battery Saver mode

---

## 9. Anti-Patterns to Avoid

| # | Anti-Pattern | Correct Practice |
|---|---|---|
| 1 | **Overcrowded interfaces** — showing everything at once | Progressive disclosure: reveal advanced features on demand |
| 2 | **Inconsistent visual language** — different button styles, clashing colors across pages | Strict design token governance |
| 3 | **Desktop-first design scaled down for mobile** | Mobile-first: build constrained then expand |
| 4 | **Generic error messages at top of page** | Inline errors next to the field + icon + plain language |
| 5 | **Passive CTAs**: "Click Here", "Submit" | Contextual: "Save & Process", "Generate Seasonality", "Export to Excel" |
| 6 | **Color-only status indicators** | Color + text label + icon |
| 7 | **Spinning loaders** | Skeleton screens with pulsating animation |
| 8 | **Pure black on pure white** | Dark grays on off-whites |
| 9 | **Hiding desktop nav behind hamburger** | Visible sidebar at all times on desktop |
| 10 | **Animations that slow users down** | Fast, purposeful micro-interactions (under 200ms) |

---

## 10. Data Visualization Rules

### Charts (Stock, Price, Seasonality, Analytics)
- Use clean, minimal chart styles — no 3D effects, no excessive gridlines
- Color-code lines/bars using semantic tokens
- Always show tooltips on hover with exact values
- Provide date range filters (All / 7d / 30d / 90d / Custom)
- Use `content-visibility: auto` for charts below the fold

### Tables (Dashboard, Bestsellers, Pipeline)
- Alternate row shading or hover highlight for scannability
- Sticky headers on scroll
- Sort indicators (▲/▼) on active column
- Pagination with page count + per-page size option
- Inline actions (dropdowns, toggles) — never redirect for simple state changes

### Badges & Status Indicators
- Small rounded pills with semantic background + text color
- Always include text, not just color
- Consistent sizing across all pages
