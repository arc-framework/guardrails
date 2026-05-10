# Walkthrough — Spec 010: Per-Request Lifecycle Sink

This page is the operator-facing summary of [Spec 010](../../specs/010-lifecycle-sink/spec.md). It documents the new per-request lifecycle event substrate, the live SSE feed and replay endpoint that consume it, and the SQLite-backed persistence + browser that make replay survive a service restart.

## What changed

Five deliverables, all additive:

| Deliverable                                                                                                                                                                                                                                                                                                                                                                        | Where                                                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `arc_guard_core.lifecycle` subpackage: `LifecycleSink` Protocol, `LifecycleEmitter`, 28 typed event dataclasses (23 base + 5 conditional) forming the `LifecycleEvent` tagged union, `NullLifecycleSink`, `PayloadCapturePolicy`                                                                                                                                                   | [`packages/core/src/arc_guard_core/lifecycle/`](../../packages/core/src/arc_guard_core/lifecycle/)                   |
| `GuardPipeline(lifecycle_hook=…)` constructor argument plus three concrete sinks: `RingBufferLifecycleSink` (drop-oldest, OrderedDict-backed), `SqliteLifecycleSink` (stdlib `sqlite3` + JSON1, retention-driven cleanup), `CompositeLifecycleSink` (sequential fan-out with per-child failure isolation)                                                                          | [`packages/pip/src/arc_guard/observability/`](../../packages/pip/src/arc_guard/observability/)                       |
| `GET /events` SSE feed and `GET /lifecycle/{rid}` replay endpoint in the api, with the default Composite sink (Ring + Sqlite + Broadcast) wired through `ServiceSettings`; tier fall-through (`X-Lifecycle-Tier` response header) lets callers see which sink served the response                                                                                                  | [`packages/api/src/arc_guard_service/transport/http.py`](../../packages/api/src/arc_guard_service/transport/http.py) |
| Compose stack adds a read-only `sqlite-ui` service (port 8081) under the `dev` profile so operators can browse the lifecycle DB directly; `prod` profile suppresses it; `make docker-nuke` now wipes both `api_lifecycle-data` and `api_ollama-models`                                                                                                                             | [`packages/api/docker-compose.yml`](../../packages/api/docker-compose.yml), [`Makefile`](../../Makefile)             |
| Two payload-capture flags on `ServiceSettings`: `lifecycle_capture_payloads` (POST-sanitization text on `SanitizationApplied.text_after` / `BackendResponded.response_text`) defaults `True`, while `lifecycle_capture_raw_input` (raw inbound text on `RequestStarted.raw_input`) stays opt-in and security-sensitive; the raw-leak invariant is enforced by a security soak test | [`packages/api/src/arc_guard_service/settings.py`](../../packages/api/src/arc_guard_service/settings.py)             |

The decision contract from Specs 002–006 is unchanged. Spec 010 ships purely additive surfaces. No deprecations. No renames.

## Why

Without this spec, an operator debugging a single request had to correlate three independent observability streams (`Logger.event(...)`, `Reporter.report(...)`, `MetricSink.histogram(...)`) using a `correlation_id` and best-effort timestamp ordering. Refusal investigations in particular ("why was request `abc123` blocked?") required parsing log lines and matching policy rule ids by hand.

The lifecycle sink is the fourth observability surface — typed, parent-id-linked events that form a directed graph per request. The same data feeds (1) a live SSE console for in-flight inspection and (2) a replay lookup for forensic investigation, and survives a service restart through the SQLite tier. This closes the most-requested observability gap on the rewrite roadmap and provides the data substrate that future enterprise gaps (backtesting, alerting) will build on without additional pipeline changes.

The `Sibling-Protocol` architectural choice (lifecycle as a 4th hook alongside Logger / Tracer / MetricSink, never replacing them) is verified by [test_lifecycle_does_not_change_existing_events.py](../../packages/pip/tests/contract/test_lifecycle_does_not_change_existing_events.py) — the Logger event stream is byte-identical with and without the lifecycle hook wired.

## Public surface

The new symbols are all listed in [`docs/public-surface.md`](../public-surface.md). Highlights:

| Symbol                                                                                                                                                                                                          | Package                    | Kind                    | Band        | Notes                                                                     |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ----------------------- | ----------- | ------------------------------------------------------------------------- |
| `LifecycleSink`                                                                                                                                                                                                 | `arc_guard_core.lifecycle` | protocol                | Stable      | The 4th observability hook                                                |
| `LifecycleEvent`                                                                                                                                                                                                | `arc_guard_core.lifecycle` | constant (tagged union) | Stable      | `Union[…]` of all 28 event types                                          |
| `LifecycleEventBase`                                                                                                                                                                                            | `arc_guard_core.lifecycle` | dataclass               | Stable      | Universal envelope (`id`, `parent_id`, `seq`, `ts`, `rid`, `event_type`)  |
| `NullLifecycleSink`                                                                                                                                                                                             | `arc_guard_core.lifecycle` | class                   | Stable      | Default — no-op                                                           |
| `LifecycleEmitter`                                                                                                                                                                                              | `arc_guard_core.lifecycle` | class                   | Stable      | Per-rid emitter shared between transport + pipeline                       |
| `PayloadCapturePolicy`                                                                                                                                                                                          | `arc_guard_core.lifecycle` | protocol                | Stable      | Two-flag policy gating sanitized vs raw text                              |
| 28 event dataclasses (`RequestStarted`, `StageRan`, `InspectorRan`, `FindingProduced`, `SanitizationApplied`, `DecisionEmitted`, `RefusalProduced`, `BackendCalled`, `BackendResponded`, `RequestCompleted`, …) | `arc_guard_core.lifecycle` | dataclass               | Stable      | All `frozen=True`; conditional events fire only under their preconditions |
| `RingBufferLifecycleSink`                                                                                                                                                                                       | `arc_guard.observability`  | class                   | Stable      | Per-rid drop-oldest, default capacity 5,000 rids                          |
| `SqliteLifecycleSink`                                                                                                                                                                                           | `arc_guard.observability`  | class                   | Stable      | Stdlib `sqlite3` + JSON1; retention 500k rows / 7d (whichever stricter)   |
| `CompositeLifecycleSink`                                                                                                                                                                                        | `arc_guard.observability`  | class                   | Stable      | Sequential fan-out, per-child failure counters                            |
| `BroadcastingLifecycleSink`                                                                                                                                                                                     | `arc_guard.observability`  | class                   | Provisional | Wraps a sink + the SSE subscriber registry                                |
| `ExplainableInspector`                                                                                                                                                                                          | `arc_guard_core.protocols` | protocol                | Provisional | Optional inspector capability to surface `InspectorMatchExplain` events   |

## Operator knobs

All knobs live on `ServiceSettings` (or as `ARC_GUARD_SERVICE_*` env vars):

| Field                           | Default                 | Env var                                           |
| ------------------------------- | ----------------------- | ------------------------------------------------- |
| `lifecycle_buffer_capacity`     | `5000`                  | `ARC_GUARD_SERVICE_LIFECYCLE_BUFFER_CAPACITY`     |
| `lifecycle_sqlite_path`         | `None` (in-memory only) | `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH`         |
| `lifecycle_sqlite_max_rows`     | `500_000`               | `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_MAX_ROWS`     |
| `lifecycle_sqlite_max_age_days` | `7`                     | `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_MAX_AGE_DAYS` |
| `lifecycle_capture_payloads`    | `True`                  | `ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_PAYLOADS`    |
| `lifecycle_capture_raw_input`   | `False`                 | `ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_RAW_INPUT`   |

The two payload-capture flags are independent. `lifecycle_capture_payloads=True` now makes sanitized diffs and backend responses available by default. `lifecycle_capture_raw_input=True` remains security-sensitive and is enforced by [test_no_raw_payload_in_sink_default.py](../../packages/api/tests/security/test_no_raw_payload_in_sink_default.py) — under default settings, zero raw PII strings appear in any captured event field.

## References

- [Spec 010 — full specification](../../specs/010-lifecycle-sink/spec.md)
- [Spec 010 — implementation plan](../../specs/010-lifecycle-sink/plan.md)
- [Spec 010 — task list](../../specs/010-lifecycle-sink/tasks.md)
- [Public-surface manifest](../public-surface.md)
- [Brainstorm source](../superpowers/specs/2026-05-03-lifecycle-sink-brainstorm.md)
- Pipeline emission: [`packages/pip/src/arc_guard/pipeline.py`](../../packages/pip/src/arc_guard/pipeline.py)
- Transport emission: [`packages/api/src/arc_guard_service/transport/openai.py`](../../packages/api/src/arc_guard_service/transport/openai.py)
