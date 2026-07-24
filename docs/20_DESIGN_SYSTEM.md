# 20 — Design System

**Product:** DuckDocs
**Document type:** Visual design system and token specification
**Status:** Draft for team review
**Audience:** Design, frontend engineering, brand/marketing
**Upstream:** [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md) · [19_COMPONENT_LIBRARY.md](./19_COMPONENT_LIBRARY.md)
**Related docs:** [17_FRONTEND_ARCHITECTURE.md](./17_FRONTEND_ARCHITECTURE.md)

---

## 1. Purpose

This document defines DuckDocs' visual identity — the **Waymark** design language — as concrete, implementable tokens: color, type, spacing, radius, elevation, motion, and iconography. It exists so that "polished commercial product, not AI slop" (vision G-05, §7.7) is a set of enforceable decisions, not a vibe.

**Waymark** is named for the product's core interaction: every AI answer leaves a trail marker back to its evidence. The design system's job is to make that trail feel precise, calm, and unmistakably DuckDocs' own — never a purple gradient chat widget, never a cream-and-serif editorial site, never a gray dashboard template.

---

## 2. Scope

### In scope

- Brand direction and what DuckDocs visually rejects
- Color system (neutrals, brand accent, reserved evidence color, semantic colors) for light + dark themes
- Typography system (families, scale, weights, usage rules)
- Spacing, layout grid, and density model
- Radius and elevation tokens
- Iconography rules
- Motion tokens backing the three patterns defined in doc 18 §10
- Full CSS variable block and Tailwind token mapping
- Accessibility/contrast rules

### Out of scope

- Component-level variant catalog → [19_COMPONENT_LIBRARY.md](./19_COMPONENT_LIBRARY.md)
- Screen-level states/flows → [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md)
- Build/rendering implementation → [17_FRONTEND_ARCHITECTURE.md](./17_FRONTEND_ARCHITECTURE.md)

---

## 3. Goals

| Goal ID | Goal |
|---------|------|
| DS-01 | DuckDocs is visually identifiable in a screenshot without a logo — through color, type, and density choices, not generic template defaults |
| DS-02 | Evidence/citation color is semantically reserved and never reused for generic UI accents, so "this is evidence" is unambiguous everywhere |
| DS-03 | Dark theme is the flagship, fully-designed default; light theme is a complete first-class alternative, not an afterthought |
| DS-04 | Every token is expressed as a CSS variable consumed by Tailwind, never hardcoded in components |
| DS-05 | The system supports dense document work (tight but legible density) without feeling cramped or like a generic admin dashboard |
| DS-06 | Motion tokens back exactly the three patterns in doc 18 §10 — no token exists for motion outside that budget |

---

## 4. Brand Direction

### 4.1 What Waymark explicitly rejects

| Rejected direction | Why |
|---------------------|-----|
| Purple-on-white "AI slop" gradients | Signals generic AI-wrapper, not a considered product; purple/violet is deliberately excluded from the palette entirely |
| Cream background + serif display type + terracotta accents | Reads as an editorial/lifestyle brand, not a precision document tool; serif type is excluded from the system entirely |
| Broadsheet/newspaper layout (dense multi-column, rule-heavy, serif headlines) | Wrong metaphor — DuckDocs is a workspace, not a publication |
| Bubbly, heavily-rounded, drop-shadow-everywhere "friendly SaaS" look | Undermines the seriousness of evidence-grounded, high-stakes document work |

### 4.2 What Waymark is

A **dense, ink-and-signal-amber precision workspace**: warm dark graphite surfaces (not pure black, not cold gray), a single disciplined amber brand accent used sparingly for identity and primary emphasis, and a **reserved teal "evidence" color used nowhere else in the system** so citation/evidence affordances are instantly recognizable by color alone, independent of label. Typography is entirely grotesk sans + monospace — monospace specifically marks evidence metadata, IDs, and citations as "precise, machine-verifiable" content, distinct from prose.

The duck motif is used only as a small wordmark/favicon accent — never as a mascot illustration, never as a color driver. The brand is carried by the **ink/amber/evidence-teal system**, not by literal duck imagery.

### 4.3 Brand voice in visual terms

| Trait | Visual expression |
|-------|---------------------|
| Precise | Tight type scale, monospace for verifiable data, sharp-but-not-harsh radii |
| Calm under scrutiny | Muted, low-chroma neutrals; the ungrounded-answer state uses neutral tones, not alarm colors |
| Confident, not flashy | One brand accent, used deliberately; no gradient backgrounds, no glow effects |
| Evidence-forward | The only consistently vivid color in the whole system is reserved for evidence |

---

## 5. Color System

Colors are authored in OKLCH (perceptually uniform, better for generating consistent light/dark pairs) with hex equivalents noted for quick reference. Dark theme is the default (`data-theme="dark"`); light theme is a complete override set.

### 5.1 Ink neutrals (warm graphite scale — not pure gray, not black)

| Token | OKLCH | Approx. hex | Role |
|-------|-------|-------------|------|
| `--dd-ink-25` | `oklch(98% 0.004 75)` | `#FAF9F7` | Light theme page background |
| `--dd-ink-50` | `oklch(96% 0.005 75)` | `#F3F2EF` | Light theme subtle surface |
| `--dd-ink-100` | `oklch(92% 0.006 75)` | `#E6E4DF` | Light theme borders |
| `--dd-ink-200` | `oklch(85% 0.007 75)` | `#CFCCC4` | Light theme muted text on light |
| `--dd-ink-300` | `oklch(72% 0.008 70)` | `#A9A59A` | Disabled text (both themes, adjusted) |
| `--dd-ink-400` | `oklch(58% 0.010 65)` | `#7D786C` | Secondary text (light theme) |
| `--dd-ink-500` | `oklch(46% 0.010 60)` | `#5E5A50` | Mid-tone / icon default |
| `--dd-ink-600` | `oklch(36% 0.010 55)` | `#443F38` | Secondary text (dark theme) |
| `--dd-ink-700` | `oklch(27% 0.010 50)` | `#2E2A25` | Elevated surface (dark theme cards/panels) |
| `--dd-ink-800` | `oklch(20% 0.009 45)` | `#211E1A` | App background base (dark theme) |
| `--dd-ink-900` | `oklch(15% 0.008 40)` | `#181613` | Deepest surface (dark theme sunken panels, preview backdrop) |
| `--dd-ink-950` | `oklch(11% 0.006 35)` | `#100F0D` | Shadow/overlay scrim base |

The slight warm hue bias (hue ≈ 35–75° at low chroma) is what keeps this from reading as generic cold "tech gray" — it is warm charcoal, closer to graphite/slate-brown than to neutral gray or blue-black.

### 5.2 Brand accent — Signal Amber (identity, primary emphasis, active states)

| Token | OKLCH | Approx. hex | Role |
|-------|-------|-------------|------|
| `--dd-amber-100` | `oklch(94% 0.05 75)` | `#F5E6C8` | Amber-tinted subtle background (e.g. active nav item bg) |
| `--dd-amber-300` | `oklch(82% 0.11 72)` | `#E3B665` | Hover state for amber elements |
| `--dd-amber-500` | `oklch(72% 0.15 70)` | `#CC9A34` | **Primary brand accent** — CTAs, active nav, brand mark, streaming-active indicator |
| `--dd-amber-600` | `oklch(62% 0.15 68)` | `#A87C22` | Amber pressed/active state |
| `--dd-amber-800` | `oklch(38% 0.10 65)` | `#5E4A16` | Amber text on light backgrounds (accessible contrast) |

Amber is used deliberately sparingly: brand mark, primary button fill, active nav-rail indicator, "remote provider active" pulse. It is never used for citations/evidence (that is reserved, §5.3) and never used as a full-screen gradient or hero background.

### 5.3 Evidence Teal — reserved, exclusive semantic color

| Token | OKLCH | Approx. hex | Role |
|-------|-------|-------------|------|
| `--dd-evidence-100` | `oklch(93% 0.04 195)` | `#D8ECEA` | Evidence highlight background (preview overlay, low opacity) |
| `--dd-evidence-300` | `oklch(78% 0.08 195)` | `#82C4BE` | Evidence hover/secondary |
| `--dd-evidence-500` | `oklch(62% 0.11 195)` | `#3F9C93` | **Citation chips, evidence borders, "clickable evidence" affordance** |
| `--dd-evidence-700` | `oklch(42% 0.09 195)` | `#245E58` | Evidence text/icon on light backgrounds |

**DS-AD01 (hard rule):** `--dd-evidence-*` tokens are used **only** for citations, evidence highlighting, bounding-box overlays, and the Evidence Inspector. No button, nav item, chart, or generic UI accent may use this hue family. This is what makes "this is evidence" legible at a glance, independent of icons or copy (DS-02).

### 5.4 Semantic colors

| Token | OKLCH | Approx. hex | Role |
|-------|-------|-------------|------|
| `--dd-success-500` | `oklch(58% 0.13 150)` | `#3F8F5C` | Ingest ready, connection succeeded |
| `--dd-warning-500` | `oklch(68% 0.16 55)` | `#C97A2E` | Low OCR confidence, degraded fidelity — visually distinct hue from brand amber (55° vs 70°) so "warning" is never mistaken for "brand emphasis" |
| `--dd-danger-500` | `oklch(55% 0.19 25)` | `#B3402E` | Ingest failed, provider unreachable, destructive actions |
| `--dd-info-500` | `oklch(58% 0.10 235)` | `#4A76A8` | Neutral informational callouts (used minimally; never the dominant color of a screen) |

### 5.5 Theme composition (semantic surface/text tokens)

These are the tokens components actually consume — never the raw scale values directly.

```css
:root,
[data-theme="dark"] {
  /* Surfaces */
  --dd-bg-app: var(--dd-ink-800);
  --dd-bg-sunken: var(--dd-ink-900);
  --dd-bg-elevated: var(--dd-ink-700);
  --dd-bg-overlay-scrim: color-mix(in oklch, var(--dd-ink-950) 70%, transparent);
  --dd-border-default: color-mix(in oklch, var(--dd-ink-500) 35%, transparent);
  --dd-border-strong: color-mix(in oklch, var(--dd-ink-300) 45%, transparent);

  /* Text */
  --dd-text-primary: var(--dd-ink-25);
  --dd-text-secondary: var(--dd-ink-300);
  --dd-text-muted: var(--dd-ink-500);
  --dd-text-on-amber: var(--dd-ink-900);
  --dd-text-on-evidence: var(--dd-ink-900);

  /* Brand + evidence + semantic (theme-invariant hue, adjusted lightness handled by scale) */
  --dd-accent: var(--dd-amber-500);
  --dd-accent-hover: var(--dd-amber-300);
  --dd-accent-active: var(--dd-amber-600);
  --dd-evidence: var(--dd-evidence-500);
  --dd-evidence-bg: color-mix(in oklch, var(--dd-evidence-500) 16%, transparent);
  --dd-success: var(--dd-success-500);
  --dd-warning: var(--dd-warning-500);
  --dd-danger: var(--dd-danger-500);
  --dd-info: var(--dd-info-500);

  --dd-focus-ring: var(--dd-evidence-300);
}

[data-theme="light"] {
  --dd-bg-app: var(--dd-ink-25);
  --dd-bg-sunken: var(--dd-ink-50);
  --dd-bg-elevated: oklch(100% 0 0);
  --dd-bg-overlay-scrim: color-mix(in oklch, var(--dd-ink-900) 45%, transparent);
  --dd-border-default: var(--dd-ink-100);
  --dd-border-strong: var(--dd-ink-200);

  --dd-text-primary: var(--dd-ink-900);
  --dd-text-secondary: var(--dd-ink-500);
  --dd-text-muted: var(--dd-ink-400);
  --dd-text-on-amber: var(--dd-ink-900);
  --dd-text-on-evidence: oklch(100% 0 0);

  --dd-accent: var(--dd-amber-600);
  --dd-accent-hover: var(--dd-amber-500);
  --dd-accent-active: var(--dd-amber-800);
  --dd-evidence: var(--dd-evidence-700);
  --dd-evidence-bg: color-mix(in oklch, var(--dd-evidence-500) 12%, transparent);
  --dd-success: oklch(46% 0.12 150);
  --dd-warning: oklch(54% 0.15 55);
  --dd-danger: oklch(48% 0.18 25);
  --dd-info: oklch(48% 0.10 235);

  --dd-focus-ring: var(--dd-evidence-500);
}
```

**DS-AD02:** the focus ring uses the evidence-teal hue rather than the brand amber. This keeps keyboard-focus indication visually distinct from "this is brand/CTA emphasis" while still feeling intentional (evidence-teal reads as "precision/interaction," which fits focus states conceptually).

### 5.6 Contrast compliance

All `--dd-text-*` / `--dd-bg-*` pairings meet WCAG AA (≥4.5:1 for body text, ≥3:1 for large text/icons) in both themes; `--dd-accent`/`--dd-evidence` are verified against both their "on-fill" text token and against `--dd-bg-app` for non-fill usage (e.g. amber text on the dark app background). Contrast tokens are re-verified whenever a scale value changes (§9 acceptance criteria).

---

## 6. Typography

| Token | Family | Fallback stack | Usage |
|-------|--------|------------------|-------|
| `--dd-font-sans` | General Sans (self-hosted) | `'General Sans', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif` | All UI text, headings, body — no serif anywhere in the system (DS explicitly rejects the broadsheet/serif direction) |
| `--dd-font-mono` | JetBrains Mono (self-hosted) | `'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace` | Citation ordinals, evidence metadata (page/line/char anchors), document/version/chunk IDs, code file previews, raw confidence scores in the Evidence Inspector |

Both fonts are self-hosted (`public/fonts`, loaded via `next/font/local`) — no Google Fonts or other CDN dependency, consistent with the local-first constraint in doc 17 §13.

### 6.1 Type scale

| Token | Size / line-height | Weight range | Usage |
|-------|----------------------|----------------|-------|
| `--dd-text-2xs` | 11px / 16px | 500 | Metadata captions, evidence anchor labels |
| `--dd-text-xs` | 12px / 16px | 400–500 | Badges, status pills, timestamps |
| `--dd-text-sm` | 13px / 20px | 400–500 | Dense table/list body text (default density) |
| `--dd-text-base` | 14px / 22px | 400 | Default UI body text |
| `--dd-text-md` | 16px / 24px | 400–500 | Document preview reading text, comment body |
| `--dd-text-lg` | 18px / 26px | 500–600 | Section headings within panels |
| `--dd-text-xl` | 20px / 28px | 600 | Panel/page titles |
| `--dd-text-2xl` | 24px / 32px | 600–700 | Surface-level titles (rare; Library/Intelligence/Review/Settings headers) |
| `--dd-text-3xl` | 28px / 36px | 700 | Reserved for empty-state/onboarding hero text only |

**DS-AD03:** DuckDocs' base UI size is **14px**, not the more common 16px default — a deliberate density decision (DS-05) so tables, evidence lists, and comment threads show more information per screen without feeling like tiny print (line-heights stay generous relative to size to preserve legibility).

### 6.2 Weight usage rules

| Weight | Usage |
|--------|-------|
| 400 (Regular) | Body text, prose, comments |
| 500 (Medium) | Labels, badges, table headers, secondary emphasis |
| 600 (Semibold) | Titles, active nav items, primary buttons |
| 700 (Bold) | Reserved for onboarding hero and empty-state headlines only — bold is scarce by design |

Monospace text (`--dd-font-mono`) is always set at `--dd-text-2xs` or `--dd-text-xs` with slightly increased letter-spacing (`0.01em`) to stay legible at small sizes without dominating the visual hierarchy — it should read as "precise metadata," not as a second body-text voice.

---

## 7. Spacing, Layout, and Density

### 7.1 Spacing scale (4px base unit)

| Token | Value |
|-------|-------|
| `--dd-space-0` | 0px |
| `--dd-space-1` | 4px |
| `--dd-space-2` | 8px |
| `--dd-space-3` | 12px |
| `--dd-space-4` | 16px |
| `--dd-space-5` | 20px |
| `--dd-space-6` | 24px |
| `--dd-space-8` | 32px |
| `--dd-space-10` | 40px |
| `--dd-space-12` | 48px |
| `--dd-space-16` | 64px |
| `--dd-space-20` | 80px |

### 7.2 Density modes

| Mode | Row height (list/table) | Panel padding | Default context |
|------|---------------------------|-----------------|-------------------|
| `dense` (default) | 32px | `--dd-space-3` | Library list, Evidence Inspector, comment threads, Settings — the product default everywhere, per DS-05 |
| `comfortable` | 40px | `--dd-space-4` | Onboarding, first-run empty states, and a user-toggleable Settings preference for accessibility/preference |

### 7.3 Layout grid

- Primary breakpoint target ≥1280px uses a 3-column structural grid: `NavRail` (fixed 64px collapsed / 220px expanded) + main content (fluid) + Preview/Inspector pane (fixed 420px, resizable via `SplitPane` between 320–560px).
- Content max-width within the main column is intentionally **not** capped at a narrow reading width (e.g. not 720px) — this is a dense workspace, not an article layout, so tables/grids use available width.

---

## 8. Radius and Elevation

### 8.1 Radius scale

| Token | Value | Usage |
|-------|-------|-------|
| `--dd-radius-xs` | 4px | Badges, small chips, `ConfidenceBadge` |
| `--dd-radius-sm` | 6px | Inputs, buttons |
| `--dd-radius-md` | 8px | Cards, panels, dialogs |
| `--dd-radius-lg` | 12px | Large surfaces (upload dropzone, onboarding panel) |
| `--dd-radius-full` | 999px | Avatars, status dots only |

Radii stay small and consistent (4–12px) rather than the heavily-rounded 16–24px look common in generic AI product UI — another deliberate anti-slop signal (§4.1).

### 8.2 Elevation

DuckDocs favors **borders over heavy shadows** for a flat, precise, document-tool feel; shadows are reserved for true overlays (menus, dialogs, tooltips) floating above content.

| Token | Value | Usage |
|-------|-------|-------|
| `--dd-elevation-0` | `none` (border only: `1px solid var(--dd-border-default)`) | Cards, panels at rest |
| `--dd-elevation-1` | `0 1px 2px color-mix(in oklch, var(--dd-ink-950) 24%, transparent)` | Sticky headers, TopBar |
| `--dd-elevation-2` | `0 4px 12px color-mix(in oklch, var(--dd-ink-950) 32%, transparent)` | Dropdowns, popovers, tooltips |
| `--dd-elevation-3` | `0 12px 32px color-mix(in oklch, var(--dd-ink-950) 40%, transparent)` | Dialogs, sheets |

### 8.3 Cards — used sparingly

Per the product direction, **cards are reserved for genuine interaction containers** (a `DocumentCard`, a dialog, a dropdown surface) — not used as a default wrapper for every section of a page. Dense list/table rows (`DocumentRow`, `EvidenceInspectorList` items, comment thread entries) use border-separated rows with `--dd-elevation-0`/no elevation at all, avoiding the "everything is a floating card on a gray background" dashboard-template look.

---

## 9. Iconography

| Rule | Detail |
|------|--------|
| Icon set | Lucide exclusively — no mixing icon libraries |
| Stroke width | `1.5px` at all sizes for consistency with the grotesk type's stroke contrast |
| Sizes | `16px` (inline/dense), `20px` (default UI), `24px` (empty states/onboarding) — mapped to `--dd-icon-sm/md/lg` |
| Color | Icons inherit `currentColor`; only status/semantic icons (success/warning/danger/evidence) use their semantic token color directly |
| Evidence-specific icons | A small reserved set (citation marker, bounding-box, confidence tiers) always renders in `--dd-evidence` or the semantic confidence color — never in brand amber, to preserve DS-02 |

---

## 10. Motion Tokens

Backs the three patterns defined in [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md) §10. No additional motion tokens exist outside this set (DS-06).

```css
:root {
  --dd-motion-reveal-duration: 180ms;
  --dd-motion-reveal-easing: cubic-bezier(0.22, 1, 0.36, 1); /* ease-out-quart */

  --dd-motion-pulse-duration: 400ms;
  --dd-motion-pulse-easing: cubic-bezier(0.16, 1, 0.3, 1); /* ease-out */

  --dd-motion-settle-duration: 240ms;
  --dd-motion-settle-easing: cubic-bezier(0.16, 1, 0.3, 1);

  --dd-motion-instant: 0ms; /* used when prefers-reduced-motion is set */
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --dd-motion-reveal-duration: var(--dd-motion-instant);
    --dd-motion-pulse-duration: var(--dd-motion-instant);
    --dd-motion-settle-duration: var(--dd-motion-instant);
  }
}
```

| Pattern | Token pair | Framer Motion usage |
|---------|------------|------------------------|
| Reveal | `--dd-motion-reveal-*` | `transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}` on Sheet/Dialog/Panel enter |
| Grounding pulse | `--dd-motion-pulse-*` | One-shot `opacity`/`background-color` keyframe on evidence highlight mount or citation-click navigation target |
| Stream settle | `--dd-motion-settle-*` | `layout` animation on list/height changes during streaming token arrival or new-item insertion |

---

## 11. Z-Index Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--dd-z-base` | 0 | Default content |
| `--dd-z-sticky` | 10 | TopBar, sticky table headers |
| `--dd-z-overlay` | 20 | Preview pane overlay (laptop breakpoint) |
| `--dd-z-dropdown` | 30 | DropdownMenu, Popover, Combobox |
| `--dd-z-modal` | 40 | Dialog, Sheet |
| `--dd-z-toast` | 50 | Toast notifications |
| `--dd-z-tooltip` | 60 | Tooltip (always above everything else it annotates) |

---

## 12. Full CSS Variable Reference (`globals.css` sketch)

```css
@font-face {
  font-family: 'General Sans';
  src: url('/fonts/GeneralSans-Variable.woff2') format('woff2');
  font-weight: 400 700;
  font-display: swap;
}
@font-face {
  font-family: 'JetBrains Mono';
  src: url('/fonts/JetBrainsMono-Variable.woff2') format('woff2');
  font-weight: 400 600;
  font-display: swap;
}

:root {
  --dd-font-sans: 'General Sans', 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --dd-font-mono: 'JetBrains Mono', 'IBM Plex Mono', ui-monospace, monospace;

  --dd-text-2xs: 0.6875rem; --dd-text-xs: 0.75rem; --dd-text-sm: 0.8125rem;
  --dd-text-base: 0.875rem; --dd-text-md: 1rem; --dd-text-lg: 1.125rem;
  --dd-text-xl: 1.25rem; --dd-text-2xl: 1.5rem; --dd-text-3xl: 1.75rem;

  --dd-space-0: 0px; --dd-space-1: 4px; --dd-space-2: 8px; --dd-space-3: 12px;
  --dd-space-4: 16px; --dd-space-5: 20px; --dd-space-6: 24px; --dd-space-8: 32px;
  --dd-space-10: 40px; --dd-space-12: 48px; --dd-space-16: 64px; --dd-space-20: 80px;

  --dd-radius-xs: 4px; --dd-radius-sm: 6px; --dd-radius-md: 8px;
  --dd-radius-lg: 12px; --dd-radius-full: 999px;

  --dd-icon-sm: 16px; --dd-icon-md: 20px; --dd-icon-lg: 24px;

  --dd-z-base: 0; --dd-z-sticky: 10; --dd-z-overlay: 20; --dd-z-dropdown: 30;
  --dd-z-modal: 40; --dd-z-toast: 50; --dd-z-tooltip: 60;

  /* color scale + theme + motion tokens: see §5, §10 */
}

body {
  font-family: var(--dd-font-sans);
  font-size: var(--dd-text-base);
  background: var(--dd-bg-app);
  color: var(--dd-text-primary);
}

[data-density="dense"] { --dd-row-height: 32px; --dd-panel-padding: var(--dd-space-3); }
[data-density="comfortable"] { --dd-row-height: 40px; --dd-panel-padding: var(--dd-space-4); }
```

---

## 13. Tailwind Token Mapping (sketch)

```ts
// tailwind.config.ts (excerpt)
export default {
  darkMode: ['selector', '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        app: 'var(--dd-bg-app)',
        sunken: 'var(--dd-bg-sunken)',
        elevated: 'var(--dd-bg-elevated)',
        border: { DEFAULT: 'var(--dd-border-default)', strong: 'var(--dd-border-strong)' },
        text: { primary: 'var(--dd-text-primary)', secondary: 'var(--dd-text-secondary)', muted: 'var(--dd-text-muted)' },
        accent: { DEFAULT: 'var(--dd-accent)', hover: 'var(--dd-accent-hover)', active: 'var(--dd-accent-active)' },
        evidence: { DEFAULT: 'var(--dd-evidence)', bg: 'var(--dd-evidence-bg)' },
        success: 'var(--dd-success)', warning: 'var(--dd-warning)', danger: 'var(--dd-danger)', info: 'var(--dd-info)',
      },
      fontFamily: { sans: ['var(--dd-font-sans)'], mono: ['var(--dd-font-mono)'] },
      borderRadius: { xs: 'var(--dd-radius-xs)', sm: 'var(--dd-radius-sm)', md: 'var(--dd-radius-md)', lg: 'var(--dd-radius-lg)' },
      spacing: { /* mirrors --dd-space-* */ },
      zIndex: { sticky: 'var(--dd-z-sticky)', overlay: 'var(--dd-z-overlay)', dropdown: 'var(--dd-z-dropdown)', modal: 'var(--dd-z-modal)', toast: 'var(--dd-z-toast)', tooltip: 'var(--dd-z-tooltip)' },
    },
  },
};
```

Components never write `bg-[#181613]` or `text-[14px]` — always `bg-app`, `text-text-primary`, `text-base`, etc., so a token change propagates everywhere (DS-04).

---

## 14. Accessibility

| Requirement | Implementation |
|--------------|------------------|
| Contrast | All semantic text/background pairs meet WCAG AA in both themes (§5.6) |
| Color independence | Confidence tiers, diff additions/removals, and status pills always pair color with an icon or label |
| Focus visibility | `--dd-focus-ring` (evidence-teal) renders a 2px visible ring on every interactive element, never `outline: none` without a replacement |
| Reduced motion | All three motion tokens collapse to `0ms` under `prefers-reduced-motion` (§10) |
| Density preference | `comfortable` density mode is available for users who need larger touch/click targets |

---

## 15. Architecture Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| DS-AD01 | Evidence-teal is a hard-reserved semantic color, enforced by convention + component review | Makes "this is evidence" recognizable independent of copy/icons (DS-02) |
| DS-AD02 | Focus ring uses evidence-teal, not brand amber | Keeps "you are here / interacting precisely" visually distinct from "this is brand emphasis" |
| DS-AD03 | Default base font size is 14px with a dense-first density model | Matches the dense document-work UI requirement, differentiates from generic 16px SaaS defaults |
| DS-AD04 | Dark theme is default; light theme is fully designed, not degraded | Reduces eye strain for long review sessions; still fully serves users who prefer light |
| DS-AD05 | Cards reserved for genuine interaction containers only | Avoids the generic "everything floats on cards over gray" dashboard-template look |
| DS-AD06 | No serif typeface anywhere in the system | Explicit rejection of the broadsheet/editorial visual cliché |
| DS-AD07 | Self-hosted fonts only | Consistent with local-first, no-CDN frontend constraint (doc 17 §13) |

### Alternatives rejected

| Alternative | Why rejected |
|-------------|--------------|
| Purple/violet as brand accent | Explicitly the "AI slop" cliché the brand must avoid |
| Cream background + serif headings | Reads as editorial/lifestyle brand, wrong metaphor for a document intelligence tool |
| Using the same accent color for brand emphasis and evidence | Destroys the "evidence is unmistakable" property that is core to trust (vision G-02) |
| Light-theme-only or light-as-default | Dense, long-session document review benefits from a dark flagship; light must still be complete, not secondary-class |
| Heavy card-and-shadow dashboard aesthetic | Reads as a generic admin template, undermines "polished commercial product" positioning |

---

## 16. Tradeoffs

| Tradeoff | Choice | Consequence |
|----------|--------|-------------|
| Distinctive brand vs. familiar SaaS conventions | Warm ink + reserved evidence-teal + disciplined amber | Slightly steeper initial design-system build vs. reaching for a stock template, but a defensible, recognizable identity |
| Dense default vs. broad accessibility comfort | Dense-first, comfortable as opt-in | Users needing larger targets must toggle a preference rather than get it by default |
| Strict color reservation (evidence-teal) vs. designer flexibility | Hard rule enforced in review | Removes a shade of creative freedom in exchange for a stronger trust signal |

---

## 17. Interfaces

| Interface | Detail |
|-----------|--------|
| Component library | Every token here is the only legitimate source of visual values for components in [19_COMPONENT_LIBRARY.md](./19_COMPONENT_LIBRARY.md) |
| Frontend build | Tailwind config + `globals.css` (§12–13) are the implementation seam into [17_FRONTEND_ARCHITECTURE.md](./17_FRONTEND_ARCHITECTURE.md) |
| UI/UX spec | Motion tokens implement the three patterns defined in [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md) §10 |

---

## 18. Constraints

| ID | Constraint |
|----|------------|
| DS-C01 | No component may use a raw color/spacing/radius value outside these tokens |
| DS-C02 | `--dd-evidence-*` tokens are used only for citation/evidence/confidence surfaces |
| DS-C03 | No serif font family may be introduced without revising this document |
| DS-C04 | No motion pattern outside the three defined in §10 may ship without a documented addition here |
| DS-C05 | All fonts are self-hosted; no external font CDN |

---

## 19. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Evidence-teal reservation erodes over time via ad hoc component styling | Loses the "unmistakable evidence" trust signal | Enforced via component review checklist and linting for hardcoded colors (DS-C01) |
| Dark-first default feels unfamiliar to some enterprise users | Adoption friction | Light theme is fully first-class, one-click switch, remembered per user |
| OKLCH browser support edge cases | Rendering fallback needed on very old browsers | Provide hex fallback values (already documented per token) via PostCSS color-function fallback plugin |
| Dense default feels cramped to some users | Comfort/accessibility complaints | `comfortable` density mode ships in P0, not deferred |

---

## 20. Future Extensibility

- Additional confidence-tier color steps if extraction confidence needs finer granularity than 3 tiers
- A future citation-graph view may need a small additional "relationship" color family — must be proposed as an amendment here, not invented ad hoc in feature code
- Multi-brand/white-label theming (if ever pursued) can layer on top of the existing CSS-variable architecture without restructuring components, since components already consume semantic tokens rather than raw values

---

## 21. Open Questions

| ID | Question | Owner | Needed by |
|----|----------|-------|-----------|
| DS-OQ01 | Final licensing check for General Sans + JetBrains Mono self-hosted distribution | Design + Legal | Before font asset finalization |
| DS-OQ02 | Should `comfortable` density be a per-user persisted setting or a per-session toggle? | Design + Frontend Eng | Before Settings UI build |
| DS-OQ03 | Does the duck wordmark/favicon need a dedicated micro-brand-guidelines addendum? | Brand/Design | Before public release assets |

---

## 22. Acceptance Criteria

- [ ] Palette reviewed and confirmed to contain no purple/violet brand accent and no serif typography
- [ ] Evidence-teal reservation rule (DS-AD01/DS-C02) accepted by design + frontend engineering
- [ ] Contrast compliance verified for every semantic text/background pair in both themes
- [ ] Motion tokens map 1:1 to the three patterns in [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md) §10, with no extras
- [ ] Tailwind token mapping reviewed by frontend engineering as implementable without raw-value escape hatches
- [ ] Dark theme confirmed as default; light theme confirmed as complete, not partial

---

## 23. Cross-References

| Topic | Document |
|-------|----------|
| Component library | [19_COMPONENT_LIBRARY.md](./19_COMPONENT_LIBRARY.md) |
| UI/UX specification | [18_UI_UX_SPECIFICATION.md](./18_UI_UX_SPECIFICATION.md) |
| Frontend architecture | [17_FRONTEND_ARCHITECTURE.md](./17_FRONTEND_ARCHITECTURE.md) |
| File processing / fidelity tiers | [21_FILE_PROCESSING.md](./21_FILE_PROCESSING.md) |

---

## Document Control

| Field | Value |
|-------|-------|
| Version | 0.1.0 |
| Last updated | 2026-07-18 |
| Authors | DuckDocs Architecture Team |
| Review state | Pending team review |
| Previous | [19_COMPONENT_LIBRARY.md](./19_COMPONENT_LIBRARY.md) |
| Next | [21_FILE_PROCESSING.md](./21_FILE_PROCESSING.md) |
