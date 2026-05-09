# Changelog — arc-guard

All notable changes to the `arc-guard` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.10.0] — 2026-05-09

### Added
- Four new `arc_guard.observability` modules supporting the dashboard data plane:
  - `request_summary_projector.RequestSummaryProjector` — incremental writer-side projection from the `LifecycleEvent` stream into the `request_summaries` SQLite table. Implements the `LifecycleSink` Protocol; non-blocking on write failure with a dropped-write counter.
  - `decision_record_recorder.DecisionRecordRecorder` — non-blocking writer for `decision_records` rows. Bounded `asyncio.Queue` + single background drain task. Subscribes to `DecisionEmitted` events; ignores other event types.
  - `debug_log_handler.RidLogHandler` + `rid_context_var` — stdlib `logging.Handler` that captures records emitted while `rid_context_var` is set and forwards them to `DebugEntryWriter`.
  - `debug_entry_writer.DebugEntryWriter` — non-blocking writer for the `debug_entries` SQLite table. Bounded queue + per-rid monotonic `seq` counter held in memory.

### Changed
- `arc_guard.observability.sqlite_lifecycle_sink.SqliteLifecycleSink` now applies a forward-only schema-v2 migration on construction. Pre-existing v1 databases are upgraded in place — three new tables (`request_summaries`, `decision_records`, `debug_entries`) plus six indexes are created without data loss; the `lifecycle_meta.schema_version` row is upserted from `'1'` to `'2'`. The retention task evicts the new tables in lockstep with `lifecycle_events` inside one transaction.
- The four lifecycle event emit sites in `pipeline.py` (and `transport/openai.py` for the backend events) populate the new optional fields when data is available: `JailbreakDetected.evidence_reference`, `BackendCalled.model_config_snapshot`, `BackendResponded.token_usage`. Existing constructors continue to work; the new fields default to `None`.

### Migration notes
- Additive only. No breaking changes; no migration required for non-dashboard deployments.
- The lifecycle JSON wire format gains four optional fields on existing event types — they appear as `null` when unset; consumers that strictly type-check the JSON envelope MUST treat unknown fields as forward-compatible (already the convention).

## [0.9.0] — 2026-05-08

### Added
- `arc_guard.selectors` subpackage — runtime support for the new `StrategySelector` Protocol from `arc_guard_core` 0.8.0.
  - `DefaultStrategySelector` — bundled selector with documented entity-type → strategy-name mapping covering Presidio + project-recognized PII / credentials / internal identifiers / location data, plus a documented `redact` fallback for unmapped types (with a structured `guard.selector.unmapped_entity_type` observability event).
  - `register_selector` / `get_selector` / `is_registered` / `list_registered` / `freeze_selectors` / `selector` decorator — registry surface mirroring `arc_guard.strategies.registry`.
  - The `"default"` selector auto-registers on import of `arc_guard.selectors`.
- `arc_guard.content_policies` subpackage — runtime support for the new `ContentPolicy` Protocol.
  - `SemanticContentPolicy` — bundled policy backed by the spec-005 intent encoder under the existing `[semantic]` extra; emits a structured `guard.content_policy.semantic_extra_missing` warning + registers as a no-op when the extra is missing (FR-010 fail-open) and raises `ConfigSchemaError` distinguishing the missing-model case from the missing-extra case.
  - `register_content_policy` / `get_content_policy` / etc. — registry surface mirroring the strategy registry.
  - `arc_guard.content_policies.aggregate` — helper module with `evaluate_content_policies(text, policies)`, `build_finding_metadata(firing)`, and `build_aggregate_refusal_envelope(firings)` implementing the no-short-circuit aggregate evaluation contract.
- `arc_guard.inspectors.code_injection` subpackage — three new `Inspector` Protocol implementations targeting the data-flowing-into-tools threat model.
  - `SqlInjectionInspector` — sqlparse-backed grammar-aware tokenization, lazy-imported behind the new `[code-injection]` extra. Detects stacked statements, comment-terminator attacks, and union-injection.
  - `ShellInjectionInspector` — stdlib `shlex` tokenization. Detects command substitution, pipe-into-destructive-command, and command-chaining at non-quoted positions.
  - `TemplateInjectionInspector` — stdlib `re` + curated pattern list. Detects Jinja-style sandbox-escape sigils and active HTML.
  - Each inspector accepts a `phases: Iterable[str]` constructor arg (default `frozenset({"post_process"})`); operators with template-rendered prompts opt into pre-process scanning by passing both phases.
  - Each inspector accepts a `capture_raw_matches: bool = False` constructor arg. By default, lifecycle event payloads carry only a structured fingerprint (sha256 hash + length in chars/bytes + char-class summary); operators with appropriate downstream sink discipline opt into raw-match capture per inspector.
  - Closed-posture exception handling via a shared decorator that re-raises unhandled inspector failures as `StrategyError` (mapping to `RefusalCode.STRATEGY_FAILED` via the `FAIL_RULE` table).
  - Unparseable input (oversize content, sqlparse error) returns no finding and emits a structured `guard.code_injection.unparseable_input` observability event without raising.
- New optional install extra: `[code-injection] = ["sqlparse>=0.4"]`. Required only for `SqlInjectionInspector`; the shell and template inspectors ship with stdlib only.
- Two new pytest markers in `pyproject.toml`: `requires_semantic` and `requires_code_injection` for tests gated by optional extras.

### Changed
- `arc_guard.policy.RuleBasedPolicyRouter._resolve_strategy_name(rule, finding, guard_result)` — new helper. When `rule.strategy is not None` returns it; when `rule.selector is not None` resolves the selector via `arc_guard.selectors.registry.get_selector`, invokes `selector.select(finding, guard_result)`, validates the returned name against the strategy registry, and returns it. Closed-posture failure modes:
  - Unknown selector name → `ConfigCrossFieldError` (`config.cross_field_violation`).
  - Selector raises an exception → `StrategyError` with the original exception attached as `__cause__`; the `FAIL_RULE` table maps `StrategyError` → `RefusalCode.STRATEGY_FAILED` with closed posture.
  - Selector returns a non-string or unregistered strategy name → `StrategyError`.
- `RuleBasedPolicyRouter.route()` now passes through `StrategyError` and `ConfigCrossFieldError` instead of re-wrapping them into `PolicyRouterError`. The previous re-wrap obscured the `STRATEGY_FAILED` and config-violation refusal-code mappings at the pipeline boundary.
- `arc_guard.policy.validate_strategies_registered` — extended to validate `selector` references against the selector registry when `rule.selector is set`.
- `PolicyDecision.metadata` gains a `"selector"` key when a rule used `selector:` instead of `strategy:`, so downstream `StrategyExecuted` lifecycle events can identify which selector fired.

### Migration notes
- Existing operators with policy files using `strategy:` see zero behavior change. The legacy resolution path is preserved verbatim.
- Operators opt into selector-driven masking by replacing `strategy:` with `selector:` on a rule; the framework validates at policy-load time that the selector name is registered.
- The `[code-injection]` extra is opt-in. Operators who don't install it can still import `arc_guard` and use `ShellInjectionInspector` and `TemplateInjectionInspector` (stdlib-only); only `SqlInjectionInspector` lazy-fails with a clear install hint when `sqlparse` is missing.
- Code-injection lifecycle events are fingerprint-only by default. To capture the raw matched text (for in-house attack-pattern catalogs with appropriate access control), pass `capture_raw_matches=True` per inspector.
- The `freeze_selectors()` and `freeze_content_policies()` registry-seal helpers are exposed but are not currently called from `GuardPipeline.__init__` (matching the existing `freeze_strategies()` pattern, which is also defined-but-not-called). A later spec may wire all three together.

## [0.8.0] — 2026-05-04

### Added
- `GuardPipeline(lifecycle_hook=…)` constructor argument — defaults to `NullLifecycleSink`, so existing callers see identical behavior. When wired, the pipeline emits typed `LifecycleEvent`s through the sink at every pointcut (stage boundaries, inspector runs, finding production, sanitization, policy resolution, strategy execution, decision emission, refusal construction, fidelity scoring, rehydration, report flush).
- Three concrete `LifecycleSink` implementations under `arc_guard.observability`:
  - `RingBufferLifecycleSink` — per-rid OrderedDict-backed drop-oldest buffer (default capacity 5,000 rids); rid-level eviction so partial requests never appear in the lookup; exposes a `drop_counter` attribute.
  - `SqliteLifecycleSink` — stdlib `sqlite3` + JSON1, retention-driven cleanup (configurable max-rows AND max-age, whichever is stricter); per-rid query path uses an indexed lookup.
  - `CompositeLifecycleSink` — sequential fan-out across N child sinks with per-child failure isolation and per-child failure counters; query() falls through tier-by-tier and reports which tier served the response.
- `BroadcastingLifecycleSink` — wraps a child sink + a subscriber registry so the api SSE feed can publish each event to live subscribers without coupling the sink contract to transport details. Marked Provisional.
- `ExplainableInspector` capability implementation on `InjectionInspector` — re-tests built-in / extra patterns at each finding's span and returns `InspectorMatchExplanation` records, which the pipeline emits as `InspectorMatchExplain` lifecycle events.
- Pipeline-internal lifecycle emission via `GuardContext.metadata["_lifecycle_emitter"]` — when the api transport stashes a `LifecycleEmitter` there, pipeline-internal events share the same `rid` + monotonic `seq` counter as transport-layer events, producing one connected event graph per request.

### Migration notes
- Default behavior unchanged: `lifecycle_hook` defaults to `NullLifecycleSink`. Callers do not need to update construction sites.
- Existing `Logger.event(...)` / `Reporter.report(...)` / `MetricSink.counter(...)` / `Tracer.start_span(...)` calls are preserved unchanged. Lifecycle emission is purely additive — verified by `tests/contract/test_lifecycle_does_not_change_existing_events.py` (byte-identical Logger snapshot with vs. without the hook wired).

## [0.7.1] — 2026-05-03

### Removed
- The pre-rewrite `python/arc-guardrails/` directory (deprecation README, orphaned `pyproject.toml`, `uv.lock`, and the duplicate `tests/`) and the stale `python/arc-common/` duplicate (the canonical `arc-common` distribution is unaffected — it lives in the arc-platform repo and was never imported from this SDK repo's copy). The functional source migration to `packages/pip/` happened in `arc-guard 0.2.x` → `0.3.0`; this entry only records the cleanup of the empty distribution shells. Pre-rewrite research notes are archived at `docs/archive/pre-rewrite-analysis/`.

### Migration notes
- No code changes. No public-surface change. Operators pinned to `arc-guard` 0.7.x see no behavior difference.

## [0.7.0] — 2026-05-03

### Added
- Re-exports follow `arc-guard-core` 0.6.0 surface — `TransportError`, `RefusalCode.API_TRANSPORT_TIMEOUT`, `FAILURE_API_TRANSPORT` are visible to downstream consumers via the established `arc_guard_core` re-export path. No new pip-package symbols.

### Changed
- Dependency floor bumped to `arc-guard-core>=0.6.0` to pick up the new transport-layer leaf exception and refusal code.

### Migration notes
- Additive only on the public surface. No breaking changes; no migration required.

## [0.6.0] — 2026-05-02

### Added
- New `arc_guard.jailbreak/` sub-package: `RuleBasedJailbreakDetector` default with curated patterns across the 5 documented jailbreak categories; `apply_jailbreak_ladder` helper.
- New `arc_guard.deception/` sub-package: `StatefulConversationInspector` default (counter-based heuristic; no ML); `update_state` / `fresh_state` reducers; `apply_deception_ladder` helper.
- New `arc_guard.evaluation/` sub-package: `HarnessImpl` driving 4 pipeline configurations; `load_adversarial_corpus` validator; per-configuration metric computations; JSON Lines + Markdown report writers.
- New `arc-guard[jailbreak-ml]` install extra: `transformers>=4.30`, `torch>=2.0`. Ships `JailbreakMlBundle.from_huggingface_jailbreak()` factory with `ClassifierJailbreakDetector` wrapping a transformer-based jailbreak classifier.
- Bundled adversarial corpus under `tests/fixtures/adversarial_corpus.py` (≥ 50 entries × 5 categories) — also importable at runtime for the evaluation harness.
- New CLI entrypoint `tools/run_evaluation.py` driving the harness against operator-provided or bundled corpus.
- `GuardPipeline` accepts new optional kwargs `jailbreak_detector` and `conversation_turn_inspector` (Protocol implementations following the bare-name convention).
- Pipeline emits `STAGE_DECEPTION_INSPECT` (post-classify, pre-sanitize) span + `guard.deception.scored` event + `arc_guardrails.deception.score` counter + `arc_guardrails.deception.duration` histogram. The jailbreak detector runs inside `STAGE_CLASSIFY` and emits `arc_guardrails.jailbreak.detected` counter + `arc_guardrails.jailbreak.duration` histogram.
- `DecisionRecord` emitted by the pipeline carries the new `jailbreak_signals` and `deception_score` fields when the new stages ran.

### Changed
- Depends on `arc-guard-core>=0.5.0` for the new Protocols, exception leaves, threshold types, refusal codes, stage constant, and additive field changes to `GuardResult` / `GuardContext` / `DecisionRecord`.

### Migration notes
- Additive only on the public pipeline surface; default behavior with no `jailbreak_detector` / `conversation_turn_inspector` configured uses the rule-based / stateful defaults; operators see no behavior change unless they opt in to the new stage's emissions.
- Operators wanting multi-turn deception detection thread a `ConversationState` through `GuardContext.conversation_state` and read the updated state back from `GuardResult.conversation_state` (top-level field, NOT under `result.context`).

## [0.5.0] — 2026-05-02

### Added
- New `arc_guard.intent/` sub-package: `NullIntentEncoder` default, `capture_intent` stage helper, `build_intent_lock` content-addressed audit-binding builder, and a `canonicalize` helper (NFC → strip → collapse whitespace → lowercase → UTF-8) used by the lock hashing.
- New `arc_guard.fidelity/` sub-package: `NullFidelityScorer` default returning the `not_measured` sentinel, `apply_fidelity_ladder(result, score, thresholds)` helper that respects FR-013 risk-precedence (no-op when `result.action == "block"` or `result.refusal is not None`).
- New `arc_guard.rehydration/` sub-package: `NullRehydrationVerifier` running the two structural checks (placeholder provenance + 16-char structural-shift window), `apply_rehydration(text, verdict, entity_map)` implementing accept / reject / partial paths with the documented `guard.rehydration.applied` and `guard.rehydration.rejected` events.
- New `arc_guard[semantic]` install extra: `sentence-transformers>=2.2`, `numpy>=1.24`. Ships `SemanticBundle.from_sentence_transformers()` factory with `SentenceTransformerIntentEncoder`, `CosineFidelityScorer`, and `SemanticRehydrationVerifier` (extends the structural verifier with a Check 3 safety-regression pass via the foundation `InjectionInspector`).
- `GuardPipeline` accepts new optional kwargs `intent_encoder`, `fidelity_scorer`, `rehydration_verifier` (Protocol implementations following the `policy_router` bare-name convention; not observability sinks). Construction-time `scorer.compatible_with(encoder)` validation raises `ConfigCrossFieldError` on mismatch.
- Pipeline emits `STAGE_DEFEND` (pre-sanitize), `STAGE_VERIFY` (post-execute, pre-decision-emit), `STAGE_REHYDRATE` (post-verify when sanitization fired) spans + the documented event/counter trio (`guard.intent.captured`, `guard.fidelity.scored`, `guard.rehydration.applied`/`rejected`, `arc_guardrails.fidelity.score`, `arc_guardrails.rehydration.verdict`, `arc_guardrails.fidelity.duration`). Encoder calls go through `concurrency.offload.run_off_loop` so the asyncio event loop is not blocked.
- `DecisionRecord` emitted by the pipeline carries the new `intent_lock` and `fidelity_score` fields when the defend stage ran.
- Performance benchmark `tests/perf/test_fidelity_overhead.py` (marked `@pytest.mark.slow`) measures null-default and canned-backend fidelity overhead.

### Changed
- Depends on `arc-guard-core>=0.4.0` for the new Protocols, exception leaves, `FidelityScore`, `IntentLock`, `FidelityThresholds`, `STAGE_DEFEND`/`STAGE_VERIFY`/`STAGE_REHYDRATE` constants, and the `RefusalCode.FIDELITY_DROP` rename.

### Migration notes
- Additive only on the public pipeline surface; default behavior with no `intent_encoder` / `fidelity_scorer` / `rehydration_verifier` configured produces the documented `not_measured` sentinel score and a structural-only rehydration verdict — existing callers see no behavior change.
- Operators on `arc-guard[otel]` see the new stages in their OTEL spans and the new events/counters/histogram in their metric pipeline; no contract changes to the OTEL adapter.

## [0.4.0] — 2026-05-02

### Added
- New observability glue sub-package `arc_guard.observability/`:
  - `stage_runner` — context-manager factory wrapping each pipeline stage with span / log / metric emissions and posture-aware failure-mode application.
  - `recording` — `RecordingTracer` / `RecordingLogger` / `RecordingMetricSink` with `CapturedSpan` / `CapturedEvent` / `CapturedMetric` dataclasses; thread-safe via internal lock; intentionally importable from production code so dependent specs can use them.
  - `attributes` — `BoundedRedactor` default `AttributeRedactor` implementation: rejects values containing input substrings, values exceeding the configured byte cap, and metric attributes outside the allow-list.
  - `leak_scanner` — pure-function `scan_for_leaks(captured, originals)` returning a list of `LeakReport` entries; substring search only, no regex / entropy.
  - `sampling` — `BufferedTracer`, `BufferedLogger`, `LogLevelFloorLogger`, and `RunSampler` implementing post-decision sampling. Buffered emissions flush at run end if sampled-in or if the run produced a refusal and `refusal_always_emits=True`. Failure events bypass sampling entirely.
  - `validation` — `validate_request_with_observability(validator, payload, ...)` wraps an API-boundary validator and emits `guard.request.rejected` + `arc_guardrails.request.rejected` on `ApiBoundaryValidationError`. Standalone `emit_request_rejected` helper for callers who do their own validation.
- New concurrency sub-package `arc_guard.concurrency/`:
  - `offload` — `run_off_loop(callable_, ..., stage, metric_sink)` wrapping `asyncio.to_thread` with an `arc_guardrails.observability.offload` counter.
- New OTEL adapter sub-package `arc_guard.middleware.otel/` (gated by the `arc-guard[otel]` extra):
  - `OtelTracer` / `OtelLogger` / `OtelMetricSink` adapters satisfying the foundation `Tracer` / `Logger` / `MetricSink` Protocols structurally.
  - `OtelObservability.from_otel_sdk()` bundles the three with the SDK's auto-configured providers.
  - `exporter.configure_otlp_exporter()` and `safe_shutdown()` for explicit control over OTLP wiring.
  - Top-level `arc_guard.middleware.from_otel_sdk()` lazy factory: bare `import arc_guard.middleware` works without the extra; calling the factory without it raises a friendly `ImportError`.
- `RegistryFrozenError(ConfigCrossFieldError)` declared in `arc_guard_core.exceptions`; raised by both `EntityRegistry` and `StrategyRegistry` after `freeze()`. Inherits `config` rule via MRO.
- Pipeline stages emit spans, structured events, and metrics via `stage_runner`. Default sinks remain null — opt-in by passing a configured `tracer_hook` / `logger_hook` / `metrics_hook` to `GuardPipeline`.
- Pipeline emits `guard.refusal.constructed` event + `arc_guardrails.refusal.emitted` counter (with `refusal_code` label) when the policy router builds a refusal envelope.
- Pipeline emits run-level `guard.run.started` / `guard.run.completed` events plus `arc_guardrails.run.duration` histogram and `arc_guardrails.run.action` counter.
- Recursive `pre_process` invocation propagates `parent_run_correlation_id` on the inner run's `guard.run.started` event via a `contextvars.ContextVar`. Sequential top-level runs do not see each other as parent.
- `arc-guard[otel]` install extra. Dependencies: `opentelemetry-api>=1.20`, `opentelemetry-sdk>=1.20`, `opentelemetry-exporter-otlp>=1.20`.
- Performance benchmark suite under `tests/perf/` (marked `@pytest.mark.slow`; excluded from default CI via `addopts = -m 'not slow'`). Measures observability overhead delta — current median is ~0.013ms vs null sinks.

### Changed
- `StrategyRegistry` and `EntityRegistry` adopt frozen-after-construction discipline via the shared core helper `arc_guard_core._registry_lock.FrozenAfterConstructionRegistry`. Construction-time registration is unchanged; post-snapshot registration raises `RegistryFrozenError`.
- The async pipeline path routes synchronous strategy dispatch through `concurrency.offload.run_off_loop` so the event loop is not blocked by strategies that do heavy regex or model work.
- `GuardPipeline` accepts a new optional `tracer_hook` parameter alongside the existing `logger_hook` / `metrics_hook`.

### Migration notes
- Additive only on the public observability surface; `GuardConfig.observability` defaults preserve prior behavior.
- Custom registry consumers that mutated registries at runtime will hit `RegistryFrozenError` and need to register before pipeline construction.
- Strategies that depended on synchronous (non-`to_thread`) execution within the async pipeline now run on the asyncio default thread-pool executor; pure-CPU strategies see ~50µs of additional context-switch overhead per run. Tune via the standard asyncio executor knobs if needed.

## [0.3.0] — 2026-05-01

### Added
- New built-in strategies `warn` and `tokenize` registered in the strategy registry by default.
- `RuleBasedPolicyRouter` — default `PolicyRouter` implementation: resolves per-finding routing decisions, applies precedence (`block > redact > tokenize > hash > warn > pass`), aggregates risk via `RiskClassifier`, builds refusal envelopes for HIGH / CRITICAL bands, and emits a `DecisionRecord` per pipeline run.
- `StrategyRegistry` thread-safe in-memory mapping with `register_strategy`, `get_strategy`, `is_registered`, `list_registered`, and a `@strategy("name")` decorator.
- `RefusalBuilder` consumes `RefusalTemplate` defaults and per-rule overrides; never returns an envelope with empty required fields.
- `DecisionEmitter` builds and emits a `DecisionRecord` per run via `Logger.event` and `MetricSink.counter` / `histogram`. Emission is non-blocking; emitter failures are suppressed.
- Clarification flow: when `PolicyRuleSet.clarification_enabled=True` and the run lands on `ambiguous_threshold`, the pipeline returns a populated `GuardResult.clarification` instead of a hard block.
- Pipeline accepts new optional kwargs: `policy_ruleset`, `policy_router`, `logger_hook`, `metrics_hook`. When `policy_ruleset is None`, Spec 001/002 behavior is preserved.

### Changed
- `redact` strategy emits typed placeholders per the registry (`[<TYPE>]` for single occurrences, `[<TYPE>_1]` / `[<TYPE>_2]` / … for multiple, in span order).
- `hash` strategy emits `[HASH:<8 hex>]` instead of bare 16-hex digests.
- All built-in strategies return `Sequence[PolicyDecision]` to satisfy the `ActionStrategy` Protocol.

## [0.2.0] — 2026-05-01

### Added
- Spec 001 import surface preserved through PEP 562 `__getattr__` shims; see `_legacy.py` for the deprecation table.
- Batteries-included library now depends on `arc-guard-core` for contracts.

### Changed
- Contract types (`RiskLevel`, `GuardContext`, `GuardInput`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `GuardResult`, `EntityDefinition`, `GuardConfig`) and Protocol interfaces moved to `arc_guard_core`. Old import paths (`arc_guard.types.*`, `arc_guard.config.GuardConfig`, etc.) emit `DeprecationWarning` and are scheduled for removal in `arc-guard 0.3.0`.

### Deprecated
- All Spec 001 type and protocol import paths under `arc_guard.*`. Migration note: see `docs/walkthrough/002-rewrite-foundation.md`.

### Removed
- `arc_guard.adapters.nats_reporter` (and the `[nats]` extra) — A.R.C.-Platform-specific transport. Roadmap §4.1 future-expansion. Reintroduction tracked under Spec 007.
- `arc_guard.adapters.unleash_provider` (and the `[unleash]` extra) — single-vendor flag provider. Roadmap §4.2 future-expansion. Spec 003+ will design a generic flag/policy system.
- `arc_guard.middleware.otel` (and the `[otel]` extra) — owned by Spec 004 (Observability and Runtime Hardening). The hook surface in `arc_guard_core.observability` (`Tracer`, `Logger`, `MetricSink`) remains; Spec 004 ships the OTEL-backed implementation.
- `arc_guard.inspectors.semantic` (and the `[semantic]` extra) — owned by Spec 005 (Safe Rehydration and Intent Fidelity). The next iteration will reintroduce semantic inspection under the intent-lock contract.
- `arc_guard.reporters.webhook_reporter` (and the `[webhook]` extra) — generic HTTP transport. Roadmap §4.1 future-expansion.
- `[arc]` aggregate extra — was the bundle of `[nats]`/`[unleash]`/`[otel]`, all removed.

The trimmed code lives in git history at the `python/arc-guardrails/` snapshot and can be resurrected per spec by re-implementing under the Spec 002 contracts.
