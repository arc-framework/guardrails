# Walkthrough — Spec 004: Observability and Runtime Hardening

This page is the operator-facing summary of [Spec 004](../../specs/004-obs-runtime-hardening/spec.md). It documents the stage instrumentation contract, the failure-mode table, the concurrency guarantees, the OTEL adapter, and the operator-tunable knobs.

## What changed

Spec 004 makes every pipeline run **observable** and **production-safe**:

- Every implemented stage emits a span, a structured event pair, and a metric sample. Default sinks remain null — opt in by configuring `tracer` / `logger` / `metrics` hooks.
- A documented **failure-mode contract** for every leaf exception class: `__failure_mode__` ClassVar declares posture (open / closed / closed-conservative); the `FAIL_RULE` table contributes the per-class label, severity, and refusal code on top.
- **Frozen-after-construction registries** (strategy, entity) reject post-construction mutation so concurrent reads on the hot path are lock-free.
- A canned **OTEL adapter** under the `arc-guard[otel]` extra wires spans / events / metrics to any OTLP-compatible collector with zero application-code changes.
- Five **operator knobs** on `ObservabilityConfig` — sampling rate, refusal-always-emit, log-level floor, metric attribute allow-list, byte cap.

## Why

Specs 002 and 003 produced rich decision records but had no first-class export path — an integrator could read `pipeline._last_decision` for tests, but production traffic produced no spans, no metrics, no structured logs. Spec 004 wires the foundation observability hooks to a real OTEL adapter, formalizes the failure-mode contract so transient inspector errors don't cascade into hard refusals, and adds the bounded-redactor + leak-scanner discipline that lets us prove (not just claim) that no raw user text escapes via observability. Frozen-after-construction registries close a concurrency hazard that became visible under load.

## Public surface

| Symbol | Kind | Band | Notes |
|---|---|---|---|
| `ObservabilityConfig` / `LogLevelFloor` | class / enum | provisional | Operator-tunable observability config. |
| `STAGE_DESCRIPTORS` | constant | provisional | Closed allow-list of stage names; later specs append additively. |
| `STAGE_VALIDATE` / `STAGE_CLASSIFY` / `STAGE_SANITIZE` / `STAGE_ROUTE` / `STAGE_EXECUTE` / `STAGE_REFUSAL` / `STAGE_DECISION_EMIT` / `STAGE_REPORT` | constant | provisional | Stage-name string constants. |
| `FailureRule` / `FAIL_RULE` / `lookup_rule` / `Severity` | class / dict / function | provisional | Per-exception observability metadata table. |
| `FAILURE_*` (12 string constants) | constant | provisional | Stable failure-class labels for observability attributes. |
| `RegistryFrozenError` | class | provisional | Raised when registry mutation happens after pipeline construction. |
| `AttributeRedactor` / `RedactionResult` | protocol / dataclass | provisional | Bounded-redactor protocol for observability values. |
| `from_otel_sdk()` (under `[otel]` extra) | function | provisional | Factory returning an OTEL bundle. |

## Quick example

```python
from arc_guard_core.config import GuardConfig
from arc_guard_core.observability_config import ObservabilityConfig
from arc_guard_core.types import GuardInput
from arc_guard.middleware import from_otel_sdk
from arc_guard.pipeline import GuardPipeline

# Operator wires up the OTEL adapter (requires `arc-guard[otel]` extra
# and OTEL_* env vars set per the OTEL SDK's auto-config).
otel = from_otel_sdk(instrumentation_name="my-service")

# Tune the knobs for a higher-volume deployment.
config = GuardConfig(
    observability=ObservabilityConfig(
        sampling_rate=0.10,            # export 10% of normal runs
        refusal_always_emits=True,     # always export refusals
        log_level_floor="warn",        # suppress info-level transitions
        max_attribute_bytes=512,
    ),
)

pipeline = GuardPipeline(
    config=config,
    tracer_hook=otel.tracer,
    logger_hook=otel.logger,
    metrics_hook=otel.metric_sink,
)

# Run as usual; every stage emits to OTEL. No application changes.
result = await pipeline.pre_process(GuardInput(text="hello"))
```

## Stage instrumentation contract

Every implemented stage emits, per run:

| Emission | Name | Notes |
|---|---|---|
| Span | `guard.stage.<stage>` | One per executed stage; nested under a run-level span. |
| Event (start) | `guard.stage.started` (info) | Fires when the stage span opens. |
| Event (end) | `guard.stage.completed` (info) | Fires on successful exit; carries `duration_ms`. |
| Metric (latency) | `arc_guardrails.stage.duration` | Histogram, milliseconds. |

Run-level emissions:

| Emission | Name | Notes |
|---|---|---|
| Event | `guard.run.started` (info) | Pipeline entry. |
| Event | `guard.run.completed` (info) | Pipeline exit; carries `action` + `risk_band`. |
| Metric | `arc_guardrails.run.duration` | Total run latency. |
| Metric | `arc_guardrails.run.action` | Counter keyed by final action + risk band. |

Stage names (closed initial set):

```
validate · classify · sanitize · route · execute · refusal · decision_emit · report
```

The set is module-level constants exported as `STAGE_DESCRIPTORS`. Downstream extensions append; existing call sites do not change.

## Failure-mode contract

Every leaf exception class in `arc_guard_core.exceptions` resolves to a `FailureRule` via MRO walking. The full canonical table lives in [`contracts/failure-mode.md`](../../specs/004-obs-runtime-hardening/contracts/failure-mode.md). Common entries:

| Exception | Posture | Severity | Refusal code |
|---|---|---|---|
| `ApiBoundaryValidationError` | closed | warn | `API_INVALID_REQUEST` |
| `StrategyError` | closed | error | `STRATEGY_FAILED` |
| `PolicyRouterError` | closed | error | `POLICY_BLOCK` |
| `RefusalEnvelopeError` | closed | critical | `INTERNAL_REFUSAL_BUILD_ERROR` |
| `EntityProviderError` | closed | error | `INTERNAL_ENTITY_PROVIDER_ERROR` |
| `InspectorError` | open | warn | (fail-open) |
| `ReporterError` | open | warn | (fail-open) |
| `FlagProviderError` | closed-conservative | warn | (degrades to default) |
| `ConfigSchemaError` / `ConfigCrossFieldError` | closed | critical | (construction-time) |
| Uncategorized | closed | critical | `INTERNAL_UNKNOWN_ERROR` |

When a stage raises, the pipeline:

1. Looks up the rule via `lookup_rule(type(exc))`.
2. Emits `guard.stage.failed` at the rule's severity with `{stage, failure_class, posture, exception_type}`.
3. Increments `arc_guardrails.stage.failed`.
4. Branches by posture:
   - **closed** → builds a refusal envelope using the rule's `refusal_code` and short-circuits the run.
   - **open** → continues with the failed contribution absent.
   - **closed-conservative** → returns the documented conservative default (e.g. flag treated as disabled).

## Concurrency hardening

- **Frozen-after-construction registries**. Pipeline construction freezes the strategy and entity registries; subsequent `register(...)` calls raise `RegistryFrozenError` (a `ConfigCrossFieldError` subclass that inherits the `config` rule via MRO).
- **Immutable contract types**. `GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `DecisionRecord`, `ClarificationRequest`, and `ObservabilityConfig` are all frozen — safe to share across concurrent runs without locking.
- **Async offload**. `arc_guard.concurrency.run_off_loop(callable_, ..., stage, metric_sink)` wraps `asyncio.to_thread` and increments `arc_guardrails.observability.offload` per call. Use it inside async strategies / inspectors that have to call blocking code (regex, model inference) so the event loop stays responsive.
- **Stress-test verified**. The suite includes a 100-thread sync stress test and a 100-coroutine asyncio stress test with a 1ms canary tick; both verify zero cross-talk and event-loop p99 jitter under 10ms.

## OTEL adapter

Install the extra:

```bash
pip install 'arc-guard[otel]'
```

Set the standard OTEL SDK environment variables (`OTEL_EXPORTER_OTLP_ENDPOINT`, etc.) and call the factory:

```python
from arc_guard.middleware import from_otel_sdk
otel = from_otel_sdk(instrumentation_name="my-service")
```

The bundle exposes `.tracer`, `.logger`, and `.metric_sink` — pass them as the pipeline's hooks. Behavior:

- Every span / event / metric the pipeline emits is delivered to the configured collector.
- Transport failures (collector unreachable) fire an `arc_guardrails.observability.export_failed` counter on a fallback sink rather than raising. Observable but non-blocking.
- The bare `import arc_guard.middleware` works with or without the extra. Calling `from_otel_sdk()` without the extra installed raises a friendly `ImportError` with the install hint.

## Operator knobs

`ObservabilityConfig` ships with safety-first defaults:

| Field | Default | Effect |
|---|---|---|
| `sampling_rate` | 1.0 | Probability that a non-refusal-class run exports its span tree. |
| `refusal_always_emits` | True | Refusal-class runs always export, regardless of sampling. |
| `log_level_floor` | `"info"` | Minimum level for stage-transition events. Failure events bypass entirely. |
| `metric_attribute_allow_list` | `{correlation_id, decision_id, stage, action, risk_band, failure_class}` | Allowed metric attribute keys; out-of-list attributes drop. |
| `max_attribute_bytes` | 1024 | Per-attribute byte cap. |

For a higher-volume deployment:

```python
ObservabilityConfig(
    sampling_rate=0.10,
    refusal_always_emits=True,
    log_level_floor="warn",
    metric_attribute_allow_list=frozenset({
        "correlation_id", "stage", "action", "risk_band", "failure_class",
        "user_segment",  # operator's custom dimension
    }),
)
```

Validation runs at construction time; an invalid config fails the pipeline construction call rather than the first request.

## Payload safety

Every span attribute, log field, and metric label is sanitized before reaching the backend:

- Values larger than `max_attribute_bytes` are dropped with `reason="exceeds_byte_cap"`.
- Metric labels with keys outside the allow-list are dropped with `reason="not_in_allow_list"`.
- Values containing a 4+ character substring of the run's input text are dropped with `reason="contains_input_substring"`.

Each drop fires:

- A `guard.observability.attribute_dropped` event at WARN level.
- An `arc_guardrails.observability.attribute_dropped` counter with the reason as a label.

The CI-time payload-leak scanner (`arc_guard.observability.scan_for_leaks`) sweeps captured artifacts against an originals list and is wired into the test suite as the SC-002 enforcement.

## Verification

The spec ships a comprehensive test surface: stage-emission contract, payload-leak scanner over a 50-input sensitive corpus, parametrized fault injection over the full FAIL_RULE table, 100-concurrent stress (sync + async), OTEL conformance + round-trip + transport-failure, sampling statistical match, and an end-to-end integration smoke. The performance benchmarks under `tests/perf/` measure observability overhead — under 1ms median per run on representative CI hardware.

## References

- [Spec 004 — Observability and Runtime Hardening](../../specs/004-obs-runtime-hardening/spec.md)
- [`contracts/`](../../specs/004-obs-runtime-hardening/contracts/) — log schema, metric schema, failure-mode table, OTEL adapter conformance, concurrency model
- [`packages/pip/CHANGELOG.md`](../../packages/pip/CHANGELOG.md) — version-level traceability
- [`packages/core/CHANGELOG.md`](../../packages/core/CHANGELOG.md)
