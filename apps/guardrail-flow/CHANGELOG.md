# Changelog — guardrail-flow

All notable changes to the GuardRailFlow dashboard app are documented here. Format follows Keep a Changelog; this app adheres to Semantic Versioning.

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
