# Changelog — guardrail-flow

All notable changes to the GuardRailFlow dashboard app are documented here. Format follows Keep a Changelog; this app adheres to Semantic Versioning.

## [0.2.0] — 2026-05-09

### Added

- Privacy toggle 👁/🙈 in the App-shell header. Persisted to the Zustand UI store's PersistentSlice (`payloadVisibility`, default `"masked"`). Masks `raw_input` / `response_text` / `text_before` / `text_after` everywhere they render — PayloadTab, StageTab text deltas, Diff/Replay, and the JSON view (deep-walks objects).
- `⚠ stale` defense-in-depth tag in the explorer table. Renders in place of the live dot when `live=true` AND `last_event_at` is older than 30 minutes — covers the gap before the backend sweeper acts.
- Multi-level Spread control on the workspace canvas. Cycles through factors `1.05` → `1.5` → `2.2` → back. Button label transitions Spread → Wide → Reset. Persisted as `canvasSpreadLevel: 1 | 2 | 3` on the VolatileSlice (default 1).
- reaviz `FunnelChart` card alongside the existing 4 metrics cards: Total → Pass → Redact → Block.
- Bidirectional filter sync — clicking a Pie segment legend (Actions or Risk) sets the explorer table's filter via `useExplorerFilters().setFilter`.
- `Diff/Replay` dock tab now renders side-by-side colored token-level diffs for `SanitizationApplied`, `StrategyExecuted`, `PayloadRewritten`, `RehydrationVerified`. Hand-rolled LCS-backtrack diff in `lib/diff/token-diff.ts` (~75 lines, no library).
- `Text deltas` collapsible panel on the Stage tab — surfaces `text_before` / `text_after` for the selected stage's transformative events.
- PolicyTab enrichment — `risk` badge alongside the resolved action; per-rule `applied` / `matched` / `skipped` status; `bypass_reason` chip when present. Canonical source of truth: `PolicyRuleEvaluated` events (with fallback to `decision.policy.rules`).
- Vendored visual primitives under `src/components/visuals/`:
  - `CurtainThemeToggle.tsx` — replaces the prior 🌞/🌙 button. Curtain animation in `--background` color over a 300ms ease-in-out sweep.
  - `DottedSurface.tsx` — wraps `<main>`. Subtle 24px-grid radial-gradient backdrop using `--muted-foreground`.
  - `AnimatedGradientBorder.tsx` — wraps the active stage on the workspace canvas during replay. 2s linear sweep when active; static gradient when historical.
  - `brand/{PipelineBrand,WordmarkBrand,GuardrailBrand}.tsx` — three arc-branded variants of the 21st.dev cpu-architecture primitive. None reference "CPU" anywhere. `brand/index.ts` re-exports `PipelineBrand` as `BrandLogo` (the operator-on-call switches by editing one line).
- `@formkit/auto-animate@0.8.4` for list-growth transitions (LifecycleSSETab events, LogsTab debug entries, StageTab events). ~1 KB bundle delta.
- Smooth `transition-colors duration-200 ease-out` on every StageNode for natural state transitions during replay.

### Changed

- TypeScript types in `types/api.ts` now mirror the new optional payload-text fields on `RequestStarted`, `BackendResponded`, `SanitizationApplied`, `StrategyExecuted`, `PayloadRewritten`, `ResponseAssembled`, `RehydrationVerified`, plus the new `RequestErrored` terminal event interface.
- Tombstone for retired `POST /v1/guard` is reflected in the canvas registry description and both copies of `request-flow.canvas`.

## [0.1.0] — 2026-05-09

Initial release. Spec 013 Phase 1 scope.

### Added

- Vite 5 + React 18 + TypeScript 5 strict-mode SPA scaffold under `apps/guardrail-flow/`.
- Pinned library stack: TanStack Query 5, TanStack Table 8, React Flow 11, CodeMirror 6, Zustand 4 (with `persist`), `@microsoft/fetch-event-source`, `react-error-boundary`, shadcn/ui (Tailwind CSS 3.4 with class-based dark mode).
- `/requests` Request Explorer route with URL-state filters (`rid_prefix`, `since`, `until`, multi-select `status` / `action` / `risk_band`), pagination, live-row badge, and 5 s auto-refetch when any row is live.
- `/requests/:rid` Request Workspace route composing:
  - 12-stage React Flow canvas with hand-tuned node positions, executed-path highlighting, and active-stage animation; node selection drives the inspector (`?tab=` URL state).
  - Right-side Inspector with four tabs: `Stage` (events scoped to selected node), `Decision` (CodeMirror read-only JSON of the captured DecisionRecord), `Policy` (rules + matched / unmatched + resolved action), `JSON` (full lifecycle + manifest + decision merged).
  - Bottom Debug Dock (collapsible, pointer-resizable) with four tabs: `Lifecycle SSE`, `Logs` (cursor-paginated, IntersectionObserver-driven infinite load), `Backend`, `Diff/Replay` (Phase-2 placeholder).
- Filtered SSE client over `@microsoft/fetch-event-source` with three-trigger close (server `terminated` sentinel / route unmount / tab hidden > 60 s) and `Last-Event-ID` reconnect on visibility return.
- Build-time mode toggle: `VITE_DASHBOARD_MODE=fixture` swaps the live API client for a fixture-mode client backed by static JSON in `apps/guardrail-flow/fixtures/`.
- Fixture corpus: 10 explorer rows (mix of pass / block / redact / clarify / refuse / errored + 1 live row), full lifecycle event stream for the completed and live rids, 5-entry debug log.
- App-shell badges: `FIXTURE MODE` banner in fixture mode, SSE-status pill (connecting / live / throttled / terminated / error) in live mode.
- Theme toggle (light / dark) persisted to `localStorage` via the Zustand UI store.
- CORS error UX: a `<CorsErrorBanner>` names the misconfigured origin and shows the exact env-var fix.
- Top-level + per-route error boundaries (`react-error-boundary`); per-route boundaries reset on pathname change so navigation between rids clears stuck states.
- Quality gate: `pnpm typecheck`, `pnpm lint`, `pnpm format`, `pnpm test` — folded into the repo-root `make all` via the `dashboard-check` Make target.
- Tests (narrow scope per FR-017): `tests/contract/no-node-runtime-imports.test.ts` (FR-003 architectural constraint via the TS compiler API), `tests/contract/shapes-match-backend.test.ts` (fixtures parse through TS narrowers), `tests/contract/fixture-routes-resolve.test.ts` (every fixture route resolves), `tests/sse/close-on-{terminated-sentinel,route-unmount,tab-hidden-throttle}.test.ts` (the three FR-009 close triggers).
