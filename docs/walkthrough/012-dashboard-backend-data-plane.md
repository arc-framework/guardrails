# Walkthrough — Spec 012: Dashboard Backend Data Plane

This page is the operator-facing summary of [Spec 012](../../specs/012-dashboard-backend-data-plane/spec.md). It documents the operator-dashboard backend resources built atop the lifecycle-sink substrate: paginated request history, request workspace assembly, DecisionRecord and debug-entry retrieval, filtered live SSE for one rid, and the strict-CORS configuration that lets a separately-hosted Vite app consume the data plane from the browser.

## What changed

Six deliverables, all additive on top of the lifecycle-sink baseline:

| Deliverable | Where |
|---|---|
| `arc_guard_core.schemas` subpackage: nine pydantic v2 read models (`RequestSummary`, `RequestPage`, `RequestPageFilters`, `RequestWorkspaceManifest`, `WorkspaceResourcesAvailability`, `WorkspaceResourceLinks`, `RequestDecisionEnvelope`, `RequestDebugEntry`, `RequestDebugPage`) plus opaque cursor encode/decode helpers. All `frozen=True, extra="forbid"`. The `stage` field is a `Literal` bound to `STAGE_DESCRIPTORS`, drift-checked by a contract test. | [`packages/core/src/arc_guard_core/schemas/`](../../packages/core/src/arc_guard_core/schemas/) |
| Schema v2 migration on the existing `arc_guardrail.db` SQLite store: three new tables (`request_summaries` writer-side projection, `decision_records` keyed by `(rid, decision_id)`, `debug_entries` keyed by `(rid, seq)`) plus six indexes. Forward-only, idempotent. Retention task extended to evict the new tables in lockstep with `lifecycle_events` inside one transaction. | [`packages/pip/src/arc_guard/observability/sqlite_lifecycle_sink.py`](../../packages/pip/src/arc_guard/observability/sqlite_lifecycle_sink.py) |
| Four new `arc_guard.observability` modules wired into the composite sink chain: `request_summary_projector` (incremental writer-side projection), `decision_record_recorder` (non-blocking writer for DecisionRecord rows), `debug_log_handler` (`RidContextVar` + `logging.Handler` tap), `debug_entry_writer` (non-blocking writer for the debug-entries table). All writers carry a dropped-write counter and never block the request path. | [`packages/pip/src/arc_guard/observability/`](../../packages/pip/src/arc_guard/observability/) |
| Four new HTTP routes plus an additive `?rid=` filter on the existing SSE endpoint: `GET /requests` (paginated explorer), `GET /requests/{rid}` (workspace manifest), `GET /requests/{rid}/decision` (DecisionRecord retrieval), `GET /requests/{rid}/debug` (cursor-paginated debug entries), `GET /events?rid=<rid>` (filtered live tail with terminal sentinel). Built in [`transport/requests.py`](../../packages/api/src/arc_guard_service/transport/requests.py) and the extended [`transport/events.py`](../../packages/api/src/arc_guard_service/transport/events.py). | [`packages/api/src/arc_guard_service/transport/`](../../packages/api/src/arc_guard_service/transport/) |
| Request-scope rid middleware in [`transport/http.py`](../../packages/api/src/arc_guard_service/transport/http.py) sets `rid_context_var` on entry and echoes the rid in the `X-Request-Id` response header. Resolved via the new shared helper [`transport/_rid.py`](../../packages/api/src/arc_guard_service/transport/_rid.py) — the same precedence used by the chat-completions transport, factored out so the two paths cannot drift. | [`packages/api/src/arc_guard_service/transport/_rid.py`](../../packages/api/src/arc_guard_service/transport/_rid.py) |
| Strict-shape CORS middleware: explicit allow-list (no wildcards), `GET`/`OPTIONS` methods only, no credentials, named header allow-list (`Content-Type`, `Cache-Control`, `Last-Event-ID`), `Access-Control-Max-Age: 600`. Default-deny — empty `dashboard_origins` list installs no middleware. Rejects wildcards, non-http(s) schemes, trailing slashes, paths, and queries at startup via the `ServiceSettings.dashboard_origins` field validator. | [`packages/api/src/arc_guard_service/settings.py`](../../packages/api/src/arc_guard_service/settings.py) |

The decision contract from prior specs is unchanged. Spec 012 ships purely additive surfaces. The closed lifecycle-event taxonomy stays at 28 types — four event classes gain optional fields (`evidence_reference` on `JailbreakDetected`, `marker_counts` on `DeceptionScored`, `model_config_snapshot` on `BackendCalled`, `token_usage` on `BackendResponded`); existing constructors and wire format are preserved.

## Why

Without this spec, an operator wanting a dashboard had to either (a) write a Node BFF that consumed the lifecycle-sink SSE feed and built its own request explorer, or (b) walk the raw SQLite events table by hand. Both paths re-implement core concerns (filtering, pagination, payload safety, restart-survivable storage) on the wrong side of the contract boundary.

The dashboard backend data plane provides those concerns in the Python service where they belong:

- **Explorer view**: a stable paginated read model (`request_summaries`) maintained by writer-side projection, so the dashboard fetches O(log n) per page instead of folding 20+ events per row at query time.
- **Workspace view**: a single `GET /requests/{rid}` returns the canonical summary plus a manifest of which subordinate resources (lifecycle, decision, debug, live-stream) are available. Missing resources fail independently with a clean 404/503 split.
- **Live follow**: an additive `?rid=` filter on the existing SSE feed. Terminated rids return a sentinel and close cleanly — no replay, no zombie streams.
- **Cross-origin**: a strict CORS allow-list keeps the door narrow. Default-deny prevents accidental exposure during development-to-production transitions.

The reporter-path discipline from the lifecycle sink carries forward: every dashboard writer is non-blocking and exposes a dropped-write counter. A SQLite write failure under load drops a row from the dashboard tier; the request path is unaffected and the live SSE feed continues.

## Public surface

All new symbols appear in [`docs/public-surface.md`](../public-surface.md) under the Provisional band. Highlights:

| Symbol | Package | Kind | Band | Notes |
|---|---|---|---|---|
| `RequestSummary` | `arc_guard_core` | class | Provisional | Explorer-table row; `stage` Literal drift-checked against `STAGE_DESCRIPTORS` |
| `RequestPage`, `RequestPageFilters` | `arc_guard_core` | class | Provisional | Paginated `GET /requests` envelope + effective-filter echo |
| `RequestWorkspaceManifest`, `WorkspaceResourcesAvailability`, `WorkspaceResourceLinks` | `arc_guard_core` | class | Provisional | Workspace-detail manifest returned by `GET /requests/{rid}` |
| `RequestDecisionEnvelope` | `arc_guard_core` | class | Provisional | DecisionRecord retrieval envelope |
| `RequestDebugEntry`, `RequestDebugPage` | `arc_guard_core` | class | Provisional | Per-rid debug envelope + cursor-paginated page |
| `encode_debug_cursor`, `decode_debug_cursor` | `arc_guard_core` | function | Provisional | Opaque base64-urlsafe-JSON cursor format `{"seq": int, "rid": str}`; decode raises on any malformed token |

The four lifecycle event types that gained fields keep their Stable status; the new fields are documented as Provisional optional extensions.

## Operator knobs

All knobs live on `ServiceSettings` (or as `ARC_GUARD_SERVICE_*` env vars):

| Field | Default | Env var |
|---|---|---|
| `dashboard_origins` | `[]` (cross-origin requests rejected) | `ARC_GUARD_SERVICE_DASHBOARD_ORIGINS` (comma-separated list) |
| `dashboard_max_request_page_size` | `200` | `ARC_GUARD_SERVICE_DASHBOARD_MAX_REQUEST_PAGE_SIZE` |
| `dashboard_max_debug_page_size` | `200` | `ARC_GUARD_SERVICE_DASHBOARD_MAX_DEBUG_PAGE_SIZE` |
| `dashboard_decision_record_queue_capacity` | `1000` | `ARC_GUARD_SERVICE_DASHBOARD_DECISION_RECORD_QUEUE_CAPACITY` |
| `dashboard_debug_entry_queue_capacity` | `5000` | `ARC_GUARD_SERVICE_DASHBOARD_DEBUG_ENTRY_QUEUE_CAPACITY` |

The CORS allow-list validator runs at startup. Wildcards (`*`), non-`http`/`https` schemes, trailing slashes, and any path/query/fragment component are rejected with a clear error before the server binds the port. The dashboard data plane is intentionally read-only and unauthenticated — operators fronting production deployments are expected to layer their own auth proxy in front of the service.

## References

- [Spec 012 — full specification](../../specs/012-dashboard-backend-data-plane/spec.md)
- [Spec 012 — implementation plan](../../specs/012-dashboard-backend-data-plane/plan.md)
- [Spec 012 — task list](../../specs/012-dashboard-backend-data-plane/tasks.md)
- [Public-surface manifest](../public-surface.md)
- [Walkthrough — Spec 010 (lifecycle-sink substrate)](010-lifecycle-sink.md)
- HTTP routes: [`packages/api/src/arc_guard_service/transport/requests.py`](../../packages/api/src/arc_guard_service/transport/requests.py)
- Filtered SSE: [`packages/api/src/arc_guard_service/transport/events.py`](../../packages/api/src/arc_guard_service/transport/events.py)
- Schema migration + retention: [`packages/pip/src/arc_guard/observability/sqlite_lifecycle_sink.py`](../../packages/pip/src/arc_guard/observability/sqlite_lifecycle_sink.py)
