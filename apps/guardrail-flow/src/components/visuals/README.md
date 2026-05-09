# Visuals

Vendored visual primitives — repo-owned source, not npm packages. Same posture as `shadcn/ui`: the 21st.dev CLI (or hand-vendoring) writes the source into the project; we then customize it for arc-guard branding before merging.

## Components

| File                                   | Source                                                                             | Used by                                                                 |
| -------------------------------------- | ---------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| `CurtainThemeToggle.tsx`               | https://21st.dev/community/components/fatih-developer/curtain-theme-toggle/default | `App.tsx` — replaces the prior 🌞/🌙 button toggle                      |
| `DottedSurface.tsx`                    | https://21st.dev/community/components/efferd/dotted-surface/default                | `App.tsx` — wraps `<main>` so the backdrop renders behind every route   |
| `AnimatedGradientBorder.tsx`           | https://21st.dev/community/components/easemize/animated-gradient-border/default    | `LifecycleCanvas.tsx` — wraps the active stage during workspace replay  |
| `brand/PipelineBrand.tsx` (+ siblings) | https://21st.dev/community/components/svg-ui/cpu-architecture/default              | `App.tsx` header — replaces the static `GR` chip. See `brand/README.md` |

## House rules

- Each component is a typed React function component.
- No internal Zustand slice — theming via CSS variables, hook locals only.
- Animate via CSS keyframes, SVG `<animate>`, or `@formkit/auto-animate` — no `framer-motion`.
- Each file opens with a one-paragraph header docstring naming the source URL and the customizations applied.
- Theme-aware: every component must render correctly in light AND dark themes.
- Bundle budget: aggregate visual additions ≤ 25 KB gzipped delta vs. the prior baseline.

## Refresh / refactor protocol

If a future change wants to refresh a vendored component (e.g. upstream improvement), re-paste the latest 21st.dev source into the file, then re-apply the customizations documented in the header comment. NEVER ship the default rendering — the rebrand is intentional and load-bearing.
