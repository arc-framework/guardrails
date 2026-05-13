# Walkthrough — Spec 013: GuardRailFlow Dashboard

This page is the operator-facing summary of [Spec 013](../../specs/013-guardrailflow-dashboard/spec.md). It documents the Vite-based GuardRailFlow application that sits on top of the [Spec 012 backend data plane](./012-dashboard-backend-data-plane.md) and turns request replay, DecisionRecord detail, and debug data into a usable operator dashboard.

## What changed

Four deliverables shipped in Phase 1:

| Deliverable | Where |
| --- | --- |
| `apps/guardrail-flow/` Vite + React 18 + TypeScript 5 SPA | new app path outside the Python workspace |
| `/requests` explorer with cursor-friendly pagination, URL-state filters, and live-row badges | `apps/guardrail-flow/src/routes/explorer.tsx` |
| `/requests/:rid` workspace: 12-stage lifecycle canvas (React Flow), 4-tab inspector, 4-tab bottom debug dock | `apps/guardrail-flow/src/routes/workspace.tsx` |
| Build-time `VITE_DASHBOARD_MODE=fixture` mode so the app runs and demos without a backend | `apps/guardrail-flow/src/lib/api/{fixtures,client,index}.ts` |

The app is a **pure Vite SPA** — no Next.js, no Node backend-for-frontend, no SSR. An architectural-constraint test (`tests/contract/no-node-runtime-imports.test.ts`) walks `src/` via the TypeScript compiler API and fails the build if any module imports `next/*`, `next-server`, `@vercel/edge`, or `node:*`.

## Why

The user chose Vite as the dashboard base, which means the Python service owns the backend data plane (Spec 012) and the UI stays a pure client. This split keeps shipping fast: the app focuses on table, canvas, decision, and debug UX instead of reinventing backend logic.

The dashboard answers two questions fast for an operator looking at any request:

- **what path did this request take?** — the canvas highlights the executed stages, marks blocked branches, and animates the active stage when a live SSE stream is attached.
- **why did the system choose that path?** — the inspector exposes the captured DecisionRecord (rules + resolved action), and the debug dock shows lifecycle events, structured-logging entries, and backend round-trip detail.

## Public surface

| Surface | Notes |
| --- | --- |
| `GET /requests` (explorer route) | Filters: rid prefix, since, until, multi-select status / action / risk band. URL-state via search params; auto-refetch every 5 s when any row is live. |
| `GET /requests/:rid` (workspace route) | Lifecycle canvas + Inspector (`?tab=stage\|decision\|policy\|json`) + Debug Dock (`?dock=lifecycle\|logs\|backend\|diff_replay`). Tab focus is deep-linkable. |
| Inspector tabs | Stage (events scoped to the selected canvas node), Decision (CodeMirror JSON view of the captured DecisionRecord), Policy (rules + matched/unmatched + resolved action), JSON (full manifest + lifecycle + decision merged). |
| Debug Dock tabs | Lifecycle SSE (chronological event list, expandable to JSON), Logs (cursor-paginated debug entries with severity badges), Backend (BackendCalled + BackendResponded side-by-side), Diff/Replay (Phase-2 placeholder). |
| App shell | Top bar shows a "FIXTURE MODE" banner in fixture mode and an SSE-status pill (connecting / live / throttled / terminated / error) in live mode. Theme toggle persists via the browser's localStorage. |
| Error boundaries | Top-level boundary wraps the entire router; per-route boundaries wrap `/requests` and `/requests/:rid` so a render error in one surface does not blank the whole app. |

## Operator knobs

| Knob | Variable / control | Purpose |
| --- | --- | --- |
| Mode | `VITE_DASHBOARD_MODE` (`live` default; `fixture`) | Build-time toggle between live backend and canned fixtures. No runtime toggle in Phase 1. |
| Backend URL | `VITE_DASHBOARD_API_URL` | Points the Vite app at the target Python service. Required in live mode. |
| CORS allow-list | `ServiceSettings.dashboard_origins` (Spec 012) | Backend declares the dashboard origins; misconfiguration surfaces in the UI as a `<CorsErrorBanner>` with the exact env var to fix. |
| Theme | App-shell button | Persists `light` / `dark` via the Zustand UI store; the `dark` class is toggled on `documentElement`. |
| Layout | inspector collapse, debug-dock height | Persists across reloads via `localStorage` (`guardrail-flow.ui` key). Volatile state (selected node, active tabs, SSE status) resets on workspace unmount. |

The app inherits backend payload-safety rules — it never creates a richer raw-data surface than the Spec 012 service exposes.

## SSE close discipline

Live updates use `@microsoft/fetch-event-source` (so we can attach `Authorization` headers, unlike the native `EventSource`). The connection closes via three triggers from FR-009:

1. Server emits the `terminated` sentinel — the SSE wrapper resolves cleanly.
2. Route unmount — the hook's effect cleanup aborts the controller.
3. Tab hidden continuously past 60 s — the throttle aborts the controller; on tab refocus the hook re-subscribes with the cached `Last-Event-ID` header.

All three are covered by tests in `tests/sse/`.

## Phase-1 measurements

These are operator-run measurements per FR-017's narrow-scope discipline; the Phase-1 walkthrough records the structure, and the operator fills in the actual numbers when running against their hardware. If numbers drift, a Phase-2 spec can promote them to automated `slow`-marked perf tests.

| Success criterion | Procedure | Measured value | Hardware |
| --- | --- | --- | --- |
| **SC-002** — explorer first-page p95 ≤ 1 s | Open `/requests` against a backend with ≥ 1 000 retained requests; record time from route navigation to first row render across at least 10 attempts via DevTools Performance. | _operator-fill_ | _operator-fill_ |
| **SC-003** — SSE → graph p95 ≤ 100 ms | Instrument the SSE hook with `performance.now()` at SSE-arrival and at React commit (via `useEffect` dependent on the lifecycle cache slice); record at least 50 events. | _operator-fill_ | _operator-fill_ |
| **SC-005 / FR-015** — responsive at 1280 px | Open the dashboard at 1280 px viewport width; confirm explorer, graph, inspector, debug dock are all reachable via at least one user action without horizontal scroll. | _operator-fill_ | _operator-fill_ |

## References

- [Spec 013 — full specification](../../specs/013-guardrailflow-dashboard/spec.md)
- [Spec 012 — backend data plane](../../specs/012-dashboard-backend-data-plane/spec.md)
- [Spec 010 — lifecycle substrate](../../specs/010-lifecycle-sink/spec.md)
- [`apps/guardrail-flow/CHANGELOG.md`](../../apps/guardrail-flow/CHANGELOG.md)
