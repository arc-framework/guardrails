# Walkthrough — Spec 014: Pipeline Instrumentation Completion

This page is the operator-facing summary of [Spec 014](../../specs/014-pipeline-instrumentation-completion/spec.md). It closes the instrumentation gaps that prevented the GuardRailFlow dashboard's later tabs from showing real data: silent canonical stages, missing payload-text capture sites, an empty `DecisionRecord` on the production path, the `debug_entries` rid binding, and orphaned `live=1` rows. The retired `POST /v1/guard` endpoint becomes a 410 Gone tombstone in the same release. Visual chrome (curtain theme toggle, dotted backdrop, animated gradient border on the active stage, branded logo, multi-level Spread, FunnelChart, bidirectional filter sync, animated dotted-surface) lands alongside.

## What changed

Twelve operator-visible deliverables, all additive on the contract surface (no breaking schema changes):

| Deliverable | Where |
| --- | --- |
| All 12 canonical pipeline stages now emit `StageRan` events on every path (pass-through, redact, block, refuse) | [`packages/pip/src/arc_guard/pipeline.py`](../../packages/pip/src/arc_guard/pipeline.py) |
| `PolicyResolved` + `PolicyRuleEvaluated` + `DecisionEmitted` + `RefusalProduced` + `RehydrationVerified` start firing on the production policy-ruleset path | same |
| New optional `text_before` / `text_after` fields on `SanitizationApplied`, `StrategyExecuted`, `PayloadRewritten`, `RehydrationVerified` and `response_text` on `BackendResponded` / `ResponseAssembled`. Gated on `lifecycle_capture_payloads=True` | [`packages/core/src/arc_guard_core/lifecycle/events.py`](../../packages/core/src/arc_guard_core/lifecycle/events.py) |
| New `RequestErrored` terminal event class — sister to `RequestCompleted` | same |
| New `StaleLiveSweeper` periodic task — promotes hung `live=1` rows to `status='errored'` by emitting `RequestErrored` events through the composite sink | [`packages/pip/src/arc_guard/observability/stale_live_sweeper.py`](../../packages/pip/src/arc_guard/observability/stale_live_sweeper.py) |
| `rid_context_var` is now bound to the pipeline's emitter rid for the duration of a run, so structured-log entries flowing through `RidLogHandler` carry the same rid the lifecycle events do | [`packages/pip/src/arc_guard/pipeline.py`](../../packages/pip/src/arc_guard/pipeline.py) |
| `POST /v1/guard` retired — replaced by an HTTP 410 Gone tombstone returning a JSON envelope pointing at `POST /v1/chat/completions` | [`packages/api/src/arc_guard_service/transport/http.py`](../../packages/api/src/arc_guard_service/transport/http.py) |
| `POST /events/close-all` operator escape hatch for stuck SSE subscribers | [`packages/api/src/arc_guard_service/transport/events.py`](../../packages/api/src/arc_guard_service/transport/events.py) |
| Privacy toggle (👁 / 🙈), multi-level Spread control, FunnelChart, bidirectional filter sync, typed per-event StageTab renderers, ⚠ stale defense-in-depth tag, Diff/Replay token-diff viewer | [`apps/guardrail-flow/src/`](../../apps/guardrail-flow/src/) |
| Vendored visual primitives — curtain theme toggle, animated dotted surface (canvas-based wave field), animated gradient border on the active stage, three branded logo variants (PipelineBrand / WordmarkBrand / GuardrailBrand) | [`apps/guardrail-flow/src/components/visuals/`](../../apps/guardrail-flow/src/components/visuals/) |
| Two new `ServiceSettings` knobs: `request_summary_stale_threshold_seconds` (default 600) and `request_summary_sweep_interval_seconds` (default 60; `<= 0` disables the sweeper) | [`packages/api/src/arc_guard_service/settings.py`](../../packages/api/src/arc_guard_service/settings.py) |
| Closed taxonomy grows from 28 to 29 events (`RequestErrored` is the new terminal); the lifecycle event tagged-union shape stays identical otherwise | [`packages/core/src/arc_guard_core/lifecycle/`](../../packages/core/src/arc_guard_core/lifecycle/) |

## Why

After Spec 013 shipped, the dashboard's tabs were structurally correct but partly empty. Three classes of gap drove the lost data:

1. **Silent stages.** Half the canonical 12-stage list (`validate`, `sanitize`, `route`, `execute` on the policy-ruleset path, `decision_emit`, plus conditional `refusal` / `rehydrate`) never emitted `StageRan`. The workspace canvas drew the nodes but they stayed inactive even on completed requests.
2. **Empty `DecisionRecord`.** The policy router emitted `DecisionEmitted` only on its own branch; legacy and pass-through paths went without. The Decision tab in the Inspector was usually empty.
3. **Capture-flag-gated text fields didn't exist.** Operators turning capture flags ON saw size counts but no actual `text_before / text_after` — the events didn't carry them. The Diff/Replay tab had nothing to render.

Plus three smaller defects the dashboard exposed:

4. **Orphan `live=1` rows.** When a backend hung past a usable threshold, the row stayed `live=1` forever. The explorer's live count drifted upward.
5. **Wrong-rid debug entries.** `rid_context_var` reflected whatever HTTP middleware had set it (often the dashboard's own lookup-API rid), so pipeline-emitted log lines were tagged with the dashboard's rid instead of the guard request's rid.
6. **`POST /v1/guard` was dead code.** No production callers, no full-pipeline behavior (skipped `post_process`), and a confusing parallel surface to `/v1/chat/completions`. Removed in this spec.

Spec 014 closes all six gaps in one release. The supporting visual chrome was bundled in to consolidate the dashboard's "GA polish" pass into one ship.

## Public surface

| Symbol | Package | Kind | Band | Notes |
| --- | --- | --- | --- | --- |
| `RequestErrored` | `arc_guard_core` | dataclass | Stable | New terminal lifecycle event. |
| `StaleLiveSweeper` | `arc_guard` (`observability/`) | class | Provisional | Background sweeper sink. Constructed by the api transport when `request_summary_sweep_interval_seconds > 0`. |
| `text_before` / `text_after` (5 events) | `arc_guard_core` | optional fields | Stable | Default `None`; populated when `lifecycle_capture_payloads=True`. |
| `response_text` (`BackendResponded` / `ResponseAssembled`) | `arc_guard_core` | optional field | Stable | Same gate as above. |
| `request_summary_stale_threshold_seconds` | `arc_guard_service` (`ServiceSettings`) | int field | Provisional | Default 600 (10 min). |
| `request_summary_sweep_interval_seconds` | `arc_guard_service` (`ServiceSettings`) | int field | Provisional | Default 60. `<= 0` disables. |
| `POST /v1/guard` | `arc_guard_service` | endpoint | Removed | Returns HTTP 410 Gone with `endpoint_removed` envelope pointing at `/v1/chat/completions`. |
| `POST /events/close-all` | `arc_guard_service` | endpoint | Provisional | Operator escape hatch. Returns `{closed, remaining_after_signal}`. |

## Operator knobs

```bash
# Capture flags (default OFF in code, ON in docker-compose dev profile)
ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_PAYLOADS=true
ARC_GUARD_SERVICE_LIFECYCLE_CAPTURE_RAW_INPUT=true

# Sweeper
ARC_GUARD_SERVICE_REQUEST_SUMMARY_STALE_THRESHOLD_SECONDS=600
ARC_GUARD_SERVICE_REQUEST_SUMMARY_SWEEP_INTERVAL_SECONDS=60   # 0 to disable
```

The dashboard's privacy toggle (👁 / 🙈) lives in the App-shell header. Defaults to **masked** — payload-bearing fields render as placeholder dots until the operator clicks to reveal. The setting persists per browser via `localStorage`.

The multi-level Spread control on the workspace canvas cycles through three layout densities (factors `1.05` → `1.5` → `2.2`); current level is stored in the volatile UI store and resets per workspace open.

`POST /events/close-all` signals every open SSE subscriber to terminate. Useful when long-lived dashboards have left zombie streams open after a backend restart.

## References

- [Spec 014](../../specs/014-pipeline-instrumentation-completion/spec.md) — full requirements + scope.
- [`quickstart.md`](../../specs/014-pipeline-instrumentation-completion/quickstart.md) — 10-step end-to-end validation walkthrough.
- [`preview-canvas-flow.md`](../../specs/014-pipeline-instrumentation-completion/preview-canvas-flow.md) — Mermaid diagrams of what the canvas + inspector tabs render after this spec.
- [`contracts/event-additions.md`](../../specs/014-pipeline-instrumentation-completion/contracts/event-additions.md) — capture-gate matrix.
- [`contracts/stale-live-sweeper.md`](../../specs/014-pipeline-instrumentation-completion/contracts/stale-live-sweeper.md) — sweeper algorithm.
- [`contracts/v1-guard-removal.md`](../../specs/014-pipeline-instrumentation-completion/contracts/v1-guard-removal.md) — 410 Gone envelope.
- [`contracts/visual-primitives.md`](../../specs/014-pipeline-instrumentation-completion/contracts/visual-primitives.md) — vendored 21st.dev component contract.
- [Spec 013 walkthrough](./013-guardrailflow-dashboard.md) — the dashboard surface this spec lights up.
- [Spec 010 walkthrough](./010-lifecycle-sink.md) — the lifecycle sink + emission contract this spec extends.
- [Spec 005 walkthrough](./005-intent-fidelity-rehydration.md) — the `RehydrationVerified` event semantics + `[semantic]` extra.
