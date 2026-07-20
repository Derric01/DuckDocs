# DuckDocs Design System

## Direction

Dense ink-and-signal-amber precision workspace. Dark graphite is the flagship theme, light is first-class. Amber identifies DuckDocs actions. Evidence-teal is reserved for citations, highlights, confidence, and the evidence inspector.

## Tokens

- Dark app: `#211e1a`; sunken: `#181613`; elevated: `#2e2a25`; text: `#faf9f7`, secondary `#a9a59a`, muted `#5e5a50`.
- Light app: `#faf9f7`; sunken: `#f3f2ef`; elevated `#ffffff`; text `#181613`, secondary `#5e5a50`, muted `#7d786c`.
- Brand amber: `#d7a746` dark, `#a97418` light.
- Evidence teal: `#3f9c93` dark, `#245e58` light.
- Semantic: success `#3f8f5c`, warning `#c97a2e`, danger `#b3402e`, info `#4a76a8`.

## Typography

General Sans is the intended UI family with a system fallback; JetBrains Mono is reserved for evidence metadata, identifiers, citations, and code. Base UI size is 14px. The type scale is compact and fixed for product surfaces.

## Layout

Desktop target is a Nav Rail, fluid primary workspace, and 420px evidence/preview pane. The rail collapses at laptop sizes; the evidence pane becomes a sheet below 1280px. Mobile uses a single-column flow with a bottom navigation affordance.

## Shape and elevation

Radii are small and consistent: 4px badges, 6px controls, 8px cards/panels, 12px onboarding surfaces. Borders carry most hierarchy. Shadows are reserved for overlays.

## Motion

Only three motion patterns ship: 180ms reveal for panels and dialogs, a single 400ms grounding pulse for evidence, and 240ms stream settle for incoming content. All collapse under `prefers-reduced-motion`.

## Interaction language

Use Lucide icons at 16/20/24px with 1.5px stroke. Every control has hover, focus, active, disabled, loading, and error states. Citation chips are numbered, keyboard reachable, confidence-aware, and open the evidence pane at the exact anchor.
