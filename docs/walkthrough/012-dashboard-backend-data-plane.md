# Walkthrough — Spec 012: Dashboard Backend Data Plane

This page is the operator-facing summary of [Spec 012](../../specs/012-dashboard-backend-data-plane/spec.md). It documents the Python-service data plane that feeds the Vite dashboard: paginated request history, request-scoped DecisionRecord detail, debug/log replay, and filtered live SSE for one request.

## What changed

Four additive deliverables are planned:

| Deliverable                                                                                                                                             | Where                                                                                |
| ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Request-summary read model and `GET /requests` explorer endpoint                                                                                        | planned under `packages/api/src/arc_guard_service/transport/`                        |
| Request-scoped summary / DecisionRecord / debug resources (`GET /requests/{rid}`, `GET /requests/{rid}/decision`, `GET /requests/{rid}/debug`)          | planned under `packages/api/src/arc_guard_service/transport/`                        |
| Additive lifecycle-field enrichments needed for dashboard tooltips and detail panes (`evidence_reference`, deception counts, model config, token usage) | planned across `packages/core/src/arc_guard_core/` and `packages/pip/src/arc_guard/` |
| Dashboard-origin / CORS settings so a separate Vite app can call the Python service directly                                                            | planned under `packages/api/src/arc_guard_service/settings.py`                       |

The existing replay/live surfaces from Spec 010 stay in place. This spec adds a higher-level data plane on top of them.

## Why

Spec 010 made request replay and live event streaming possible, but it still left the frontend doing too much derivation work. A dashboard should not have to reconstruct a request table by scanning raw lifecycle events, nor should it need a separate Node backend just to fetch DecisionRecord and debug detail.

Spec 012 keeps the Python service as the source of truth. The Vite app stays a pure client: it reads a paginated request list, opens stable request-scoped resources, and follows active requests over filtered SSE.

## Public surface

Planned user-visible / integration surfaces:

| Surface                                      | Notes                                                                    |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| `GET /requests`                              | Paginated explorer dataset for request history                           |
| `GET /requests/{rid}`                        | Canonical summary row and workspace resource availability                |
| `GET /requests/{rid}/decision`               | Recorded `DecisionRecord` detail for one request                         |
| `GET /requests/{rid}/debug`                  | Request-scoped debug/log replay resource                                 |
| `GET /events?rid=...`                        | Additive request-scoped SSE filtering on the existing live stream        |
| Additive fields on existing lifecycle events | Enables richer graph tooltips and detail panes without breaking Spec 010 |

## Operator knobs

Planned knobs are additive to the service settings:

| Knob                                | Purpose                                                        |
| ----------------------------------- | -------------------------------------------------------------- |
| dashboard allowed origins           | Permit a separate Vite app to call the backend directly        |
| request-summary retention alignment | Keep explorer data aligned with lifecycle persistence          |
| DecisionRecord capture toggle       | Enable or disable request-addressable DecisionRecord retrieval |
| debug capture / retention controls  | Bound the log/debug replay surface                             |

All payload-safety rules remain inherited from Spec 010: raw text stays off by default.

## References

- [Spec 012 — full specification](../../specs/012-dashboard-backend-data-plane/spec.md)
- [Spec 010 — lifecycle substrate](../../specs/010-lifecycle-sink/spec.md)
- [Scratch source](../superpowers/specs/2026-05-08-dashboard-data-coverage-scratch.md)
