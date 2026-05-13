# GuardRailFlow Production-Grade Refactor Plan

Date: 2026-05-12

## Executive Summary

GuardRailFlow does not need a full frontend rewrite. The current app is already structurally good enough to upgrade through focused refactoring. The right production-grade path is to preserve the working product model, reduce orchestration hotspots, harden delivery, replace the hard-coded shell background with a configurable background system, and expose those preferences through a first-class settings page.

Recommended decision:

- Refactor the current app.
- Do not rewrite the whole frontend.
- If a rewrite ever becomes necessary, limit it to the shell and screen-model seams, not the route structure, API contracts, fixtures, or domain UI flows.

## Current Assessment

Current app quality is roughly 8.4/10. That is already above the usual internal-dashboard baseline because the app has:

- a sensible Vite + React + TypeScript foundation
- clean React Query and Zustand usage
- a real fixture mode for local review without backend coupling
- contract-style tests that reduce frontend-backend drift
- a request workspace that feels like a purpose-built operator tool instead of a generic CRUD shell

It is not yet production-grade because a few implementation choices are still too hard-coded or too concentrated:

- `src/App.tsx` hard-wires a single global `DottedSurface` background
- `src/routes/workspace.tsx` is taking on too much orchestration responsibility
- bundle size is high enough to trigger the Vite chunk-size warning
- lint, router, and test warning noise still dilute signal

## Existing Seams To Build On

| Existing file                                    | What it already gives us                                                                   | Why it matters                                                                                          |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `src/App.tsx`                                    | Global shell mounts one `DottedSurface` around routed content                              | This is the correct seam to replace with a generic background host.                                     |
| `src/main.tsx`                                   | Central route table for all top-level screens                                              | This is the correct seam to add a `/settings` route for visual-system controls.                         |
| `src/components/visuals/DottedSurface.tsx`       | Full-screen Canvas2D background, theme-aware, paused on hidden tabs, honors reduced motion | This should be preserved and generalized, not thrown away.                                              |
| `src/lib/state/ui-store.ts`                      | Persisted UI preferences for theme, layout, and payload visibility                         | This is the right home for background mode and animation preferences.                                   |
| `src/components/visuals/brand/PipelineBrand.tsx` | CPU-architecture-derived trace and pin geometry already exists in the visuals layer        | The new CPU background mode can reuse this visual language instead of inventing a second brand grammar. |
| `src/styles/globals.css`                         | Stable theme tokens for shell surfaces                                                     | Background modes can stay token-driven and safe across light and dark themes.                           |

## Production-Grade Goals

1. Remove hard-coded shell visuals and make background behavior an explicit user preference.
2. Support switchable background modes: `none`, `dotted`, and `cpu`.
3. Let operators enable or disable animation independently of background mode.
4. Add a dedicated settings page that owns all configurable visual-system options.
5. Respect reduced-motion and avoid GPU-heavy dependencies.
6. Decompose route orchestration hotspots, especially the request workspace.
7. Eliminate warning noise and reduce build chunk pressure.
8. Keep fixture mode and contract tests as first-class development surfaces.

## Recommendation: Refactor, Not Rewrite

The app already has the right domain structure, routing model, and product workflow. A rewrite would mostly re-spend time rebuilding working behavior and reintroducing bugs. The better production-grade move is:

- keep the current routes and fixtures
- extract reusable shell primitives
- move route orchestration into screen-model hooks and smaller components
- harden performance, accessibility, and settings management

Rewrite should only be considered if the route surfaces become impossible to decompose cleanly or if the visual system proves too coupled to the existing shell. Based on the current code, neither condition is true.

## Background System Refactor

### Product Behavior

Add two control layers for the visual system:

- a lightweight `Display` popover in the app shell for fast toggles
- a dedicated `/settings` page as the canonical place for all visual-system controls

Do not keep adding loose icon buttons to the header.

Recommended operator-facing controls:

- Background mode: `None`, `Dotted`, `CPU`
- Animate background: `On` or `Off`

Recommended settings-page scope:

- Theme
- Payload visibility default
- Background mode
- Background animation
- future visual-system options like density, glass/transparency level, or accent strategy if the shell grows more configurable later

Recommended defaults:

- `backgroundMode = "dotted"`
- `backgroundAnimationEnabled = false`

Why this is the right default:

- production dashboards should favor legibility over motion by default
- animation should be opt-in, not forced on every operator
- the app already has heavy information density in the canvas and dock surfaces

Runtime rules:

- if the operator enables animation and the OS does not request reduced motion, animate the active background mode
- if `prefers-reduced-motion: reduce` is active, render the chosen background statically even when animation is enabled in settings
- if the operator chooses `None`, render no decorative background at all

### Proposed Store Shape

Add persisted background settings to `src/lib/state/ui-store.ts`.

```ts
export type BackgroundMode = 'none' | 'dotted' | 'cpu';

interface PersistentSlice {
  theme: Theme;
  inspectorCollapsed: boolean;
  dockCollapsed: boolean;
  dockHeightPx: number;
  payloadVisibility: PayloadVisibility;
  backgroundMode: BackgroundMode;
  backgroundAnimationEnabled: boolean;
}
```

Recommended store actions:

- `setBackgroundMode(mode: BackgroundMode)`
- `setBackgroundAnimationEnabled(v: boolean)`
- optional helper: `toggleBackgroundAnimation()`

### Proposed Shell Architecture

Replace the hard-coded `DottedSurface` mount in `src/App.tsx` with a new generic shell primitive.

```tsx
<BackgroundSurface mode={backgroundMode} animate={backgroundAnimationEnabled}>
  <main className='flex flex-1 flex-col'>
    <Outlet />
  </main>
</BackgroundSurface>
```

Recommended file split:

- `src/components/visuals/backgrounds/BackgroundSurface.tsx`
- `src/components/visuals/backgrounds/DottedBackground.tsx`
- `src/components/visuals/backgrounds/CpuBackground.tsx`
- `src/components/shell/DisplaySettingsPopover.tsx`
- `src/routes/settings.tsx`
- `src/components/settings/VisualSettingsPage.tsx`

Responsibilities:

- `BackgroundSurface`: layout, z-index, reduced-motion gating, background selection
- `DottedBackground`: current Canvas2D renderer extracted from `DottedSurface`
- `CpuBackground`: new CPU-trace visual mode
- `DisplaySettingsPopover`: quick-toggle entry point for the most frequently changed display settings plus a link to `/settings`
- `VisualSettingsPage`: full settings surface for all visual-system controls

### Route Addition

Add a dedicated settings route to the top-level route table.

Recommended route:

- `/settings`

Recommended placement in `src/main.tsx`:

- peer route alongside `/chat`, `/requests`, and `/architecture`
- wrapped in the same `RouteBoundary` pattern already used by the rest of the app

## CPU Background Mode

### Design Direction

The CPU background should reuse the existing visual language already present in `src/components/visuals/brand/PipelineBrand.tsx` instead of introducing a new art direction.

That means:

- low-opacity trace lines
- sparse pin endpoints
- subtle pulse movement along a limited set of traces
- chip-like geometry without literal repeated logo wallpaper

It should feel like an abstract hardware trace field, not like a giant decorative sticker behind the product.

### Technical Direction

Recommended implementation choices:

- build CPU mode with lightweight SVG or Canvas2D primitives only
- reuse the trace and pin grammar from `PipelineBrand.tsx`
- keep all color and alpha decisions token-driven through the current theme system
- pause animation on hidden tabs just like the existing dotted renderer
- keep the static CPU background visually valid even when animation is disabled

Avoid:

- adding `three`, `pixi`, or any particle/scene framework
- high-contrast pulses that compete with React Flow nodes and cards
- repeated literal chip icons tiled across the full page

### Performance Budget

The existing dotted surface explicitly avoids a heavy graphics dependency and stays within a small visuals budget. The CPU mode should keep the same philosophy.

Production-grade target:

- background work must add no heavy runtime dependency
- background rendering must stop or freeze when the document is hidden
- background animation must remain optional
- the final build should clear the current Vite chunk-size warning after broader code-splitting work

## App-Shell Cleanup

The current header already carries environment state, SSE state, payload visibility, and theme controls. A production-grade version should consolidate display preferences into a single shell control rather than continuing to add individual buttons.

Recommended shell structure:

- keep the environment badge and SSE badge visible at a glance
- keep a small `Display` popover for fast access to common toggles
- add a clear path from that popover to `/settings` for full configuration
- keep the header focused on navigation and operational status, not preference clutter

This cleanup matters even if the visual system is the only change, because the current shell is the natural place where background switching would otherwise become messy.

## Settings Page

If GuardRailFlow is going to become a configurable visual system, a dedicated settings page is not optional. The header can host shortcuts, but the full system needs a stable, discoverable home.

### Route and Navigation

Recommended route:

- `/settings`

Recommended navigation pattern:

- expose `Settings` from the shell navigation or overflow menu
- expose `Open full settings` from the `Display` popover
- keep the page reachable even when the operator lands deep inside `/requests/:rid`

### Page Structure

Recommended sections:

- `Appearance`
  - theme
  - background mode
  - background intensity if added later
- `Motion`
  - background animation toggle
  - reduced-motion status note explaining OS override behavior
- `Operator Privacy`
  - default payload visibility behavior
- `Layout`
  - room for future shell density or panel-behavior preferences

### Product Rules

- the settings page is the source of truth for persistent visual preferences
- the header `Display` popover is a convenience layer, not the only control surface
- settings changes should preview immediately across the current route without a reload
- settings must persist through the existing UI store persistence model

### Implementation Notes

Recommended page responsibilities:

- render current persisted values from `useUiStore`
- update settings live as operators toggle controls
- explain when `prefers-reduced-motion` forces static rendering
- keep options focused on shell and operator-display concerns, not domain workflow settings

## Broader Production-Grade Refactor

### 1. Settings Route and Preference Model

Add the settings route early, because it clarifies where visual-system concerns belong and prevents more shell clutter.

Recommended split:

- `SettingsRoute` for route-level composition
- `VisualSettingsPage` for the settings UI
- optional small presentational sections like `AppearanceSettingsCard`, `MotionSettingsCard`, and `PrivacySettingsCard`

Target outcome:

- all configurable display behavior has one obvious home
- future visual-system options can be added without bloating the shell header
- the app gains a real production-grade preferences surface instead of an ad hoc control cluster

### 2. Workspace Route Decomposition

`src/routes/workspace.tsx` should be reduced from an orchestration-heavy route into a thin route boundary plus a screen model.

Recommended split:

- `useWorkspaceScreenModel()` for queries, tab sync, selected node logic, and SSE wiring
- `WorkspaceHeader` for title and status chips
- `WorkspaceCanvasPane` for lifecycle canvas loading and error states
- `WorkspaceInspectorPane` for inspector composition
- `WorkspaceDockPane` for debug dock composition

Target outcome:

- route file becomes easy to scan
- state ownership becomes obvious
- focused tests become easier to write

### 3. Chat Route Hardening

The chat workspace is promising, but production-grade behavior should keep its shell contract clear:

- selected request should remain the single source of truth for replay state
- background preferences should apply consistently across chat, requests, and architecture routes
- route-specific warnings and edge states should be tested in fixture mode

### 4. Warning and Tooling Cleanup

Before calling the app production-grade, reduce warning noise:

- address the current lint warnings
- opt into or resolve the current React Router future-flag warnings
- reduce React test `act(...)` warnings
- add a simple build-budget check so chunk regressions are visible in CI

### 5. Bundle and Performance Hardening

Production-grade should mean predictable delivery, not only good visuals.

Recommended focus:

- split heavy route-level dependencies where practical
- lazy-load large visualization surfaces when they are not needed on first paint
- keep visual enhancements out of the critical path
- confirm fixture mode still boots quickly after refactor

## Implementation Phases

| Phase   | Scope                           | Deliverables                                                                                                                      | Exit Criteria                                                                               |
| ------- | ------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Phase 1 | Settings foundation             | `backgroundMode`, `backgroundAnimationEnabled`, `/settings` route, `VisualSettingsPage`, persisted store updates                  | Operators can manage visual-system preferences from a dedicated settings page               |
| Phase 2 | Shell quick controls            | `DisplaySettingsPopover`, `BackgroundSurface` wrapper, settings-page navigation link                                              | Common toggles are fast to reach without turning the header into a button cluster           |
| Phase 3 | Background renderer extraction  | `DottedSurface` split into reusable background component; new `CpuBackground` added                                               | Background switching works without remounting route content; reduced-motion remains correct |
| Phase 4 | Workspace decomposition         | `useWorkspaceScreenModel` and smaller workspace shell components                                                                  | `workspace.tsx` becomes thin and behavior stays unchanged                                   |
| Phase 5 | Delivery hardening and final UX | warning cleanup, chunking improvements, test expansion, docs, fixture walkthrough validation, settings-page polish, visual tuning | team can demo all main routes with production-like settings and no distracting regressions  |

## Acceptance Criteria

The refactor should be considered production-grade only when all of the following are true:

1. Operators can switch background mode between `None`, `Dotted`, and `CPU`.
2. Operators can enable or disable animation independently of mode.
3. Operators can manage these preferences from a dedicated `/settings` page.
4. Reduced-motion users always get a static background.
5. Background preferences persist across reloads.
6. Background changes do not break readability of React Flow canvases, cards, or inspector surfaces.
7. No heavy graphics dependency is introduced for the visual upgrade.
8. The workspace route is materially smaller and easier to reason about.
9. Build, typecheck, lint, and tests are stable enough to serve as a release baseline.

## If A Rewrite Ever Becomes Necessary

If the team still decides to rewrite, the rewrite should be deliberately narrow.

Preserve:

- the current route map
- the API layer and fixture mode
- the lifecycle canvas product model
- existing contract tests and fixtures

Rewrite only:

- the app shell
- the background system
- route-level orchestration into screen-model hooks

A whole-app rewrite would be the wrong cost profile for the current state of this codebase.

## Final Recommendation

Treat GuardRailFlow as a good product surface that needs hardening, not replacement.

The best production-grade move is:

- refactor the shell into a configurable visual system
- add a dedicated settings page as the canonical control surface for that system
- add a switchable `CPU` background mode alongside the current dotted background
- make animation opt-in and persisted
- decompose route orchestration and reduce delivery noise

That path preserves what is already working, adds the background flexibility you want, and moves the app toward a production-grade front-end without wasting time on a full rewrite.
