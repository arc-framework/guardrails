# §2.2 Component Breakdown

This rewrite is grounded in shipped source code under `packages/core`, `packages/pip`, and `packages/api` as of 2026-05-11. It excludes docs, specs, tests, and `*_planned.py` files.

## Detection Components

### Guard Pipeline

- **Class:** `GuardPipeline` (`arc_guard.pipeline`), `GuardPipeline` (`arc_guard_core.pipeline`)
- **File:** `packages/pip/src/arc_guard/pipeline.py`; `packages/core/src/arc_guard_core/pipeline.py`
- **Category:** Core
- **Purpose:** Runs the end-to-end guard flow, from inspection through routing, refusal, scoring, rehydration, reporting, and lifecycle emission.
- **Behavior:** The full orchestrator is `arc_guard.pipeline.GuardPipeline`, which composes inspectors, a separate jailbreak detector, a separate conversation-turn inspector, strategy execution, policy routing, fidelity and deception ladders, rehydration checks, reporter flushing, and lifecycle events. Its default chain is regex injection plus Presidio PII inspection, while richer detectors are injected explicitly or via API pipeline factories. The `arc_guard_core.pipeline.GuardPipeline` class also ships, but it is a contract-layer skeleton that only preserves the basic `Guard` shape and disabled/pass-through behavior.
- **Variants:** `arc_guard.pipeline.GuardPipeline` is the real orchestrator; `arc_guard_core.pipeline.GuardPipeline` is the zero-dependency contract-layer variant.
- **Configuration:** Constructor knobs include `config`, `flags`, `inspectors`, `middlewares`, `reporter`, `strategies`, `policy_ruleset`, `policy_router`, `intent_encoder`, `fidelity_scorer`, `rehydration_verifier`, `jailbreak_detector`, `conversation_turn_inspector`, `lifecycle_hook`, `logger_hook`, `metrics_hook`, and `tracer_hook`. Environment-driven defaults come from `EnvFlagProvider` and `GuardConfig.from_env()`, including `GUARD_ENABLED`, `GUARD_INJECTION_ENABLED`, `GUARD_ACTION_STRATEGY`, `GUARD_PII_ENTITIES`, `GUARD_LANGUAGE`, `GUARD_MODEL_PATH`, and `GUARD_MODEL_CACHE_DIR`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Injection Inspector

- **Class:** `InjectionInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/injection.py`
- **Category:** Detection
- **Purpose:** Detects prompt-injection-shaped text with a curated regex set.
- **Behavior:** The inspector scans `GuardResult.text` against built-in and optional extra regex patterns and appends `INJECTION` findings for each match. It is intentionally pre-process only: if the phase is `post_process`, it returns the prior result unchanged. It also supports `explain_matches(...)`, which maps new findings back to the pattern ids that fired.
- **Variants:** None
- **Configuration:** Constructor knob `extra_patterns`. This detector is enabled in the default chain unless `GUARD_INJECTION_ENABLED=false` through the flag provider.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### PII Inspector

- **Class:** `PresidioInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/presidio.py`
- **Category:** Detection
- **Purpose:** Detects PII and PCI entities with `presidio-analyzer`.
- **Behavior:** The inspector builds or accepts a Presidio `AnalyzerEngine`, runs `analyze(...)` over the current text, and converts each Presidio match into a `Finding` with a risk level derived from the score. Unlike `InjectionInspector`, it runs in both pre- and post-process phases and stamps metadata indicating whether the source was input or output. Failures are swallowed and logged so the pipeline stays fail-open at this stage.
- **Variants:** None
- **Configuration:** Constructor knobs `config`, `engine`, and `extra_recognizers`. Tunable operator inputs come through `GuardConfig` and `GuardConfig.from_env()`, especially `pii_entities` and `language` via `GUARD_PII_ENTITIES` and `GUARD_LANGUAGE`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Semantic Inspector

- **Class:** `SemanticIntentInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/semantic_intent.py`
- **Category:** Detection
- **Purpose:** Detects semantically phrased harmful intent that lexical inspectors can miss.
- **Behavior:** At construction time it embeds category prototype phrases, then at runtime embeds the incoming text and compares it against those prototype vectors. When similarity clears the threshold, it emits a critical finding and constructs a refusal envelope directly instead of waiting for downstream strategy mapping. By default it only runs on `pre_process`, and it short-circuits if the run is already blocked or already has a refusal.
- **Variants:** None
- **Configuration:** Constructor knobs `model_name`, `threshold`, `phases`, and `categories`.
- **Optional extra:** `[semantic]`
- **Latency:** Not measured
- **Concern addressed:** semantic extensibility

### Custom Inspector

- **Class:** `CustomInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/custom.py`
- **Category:** Detection
- **Purpose:** Detects operator-defined entity patterns from an injected provider.
- **Behavior:** On every `inspect()` call it asks its `EntityProvider` for the current entity list instead of caching definitions at construction time. Each entity with a regex pattern is matched against the text and converted into a `Finding`, with risk chosen from the entity category. This makes the component effectively hot-reloadable when backed by a mutable provider such as `EntityRegistry`.
- **Variants:** None
- **Configuration:** Constructor knob `provider`; the provider can be any object satisfying the `EntityProvider` protocol.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** semantic extensibility

### SQL Injection Inspector

- **Class:** `SqlInjectionInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/code_injection/sql.py`
- **Category:** Detection
- **Purpose:** Detects SQL-injection-shaped output before it reaches downstream tools.
- **Behavior:** The inspector parses text with `sqlparse`, then combines grammar-aware checks with targeted regexes for stacked statements, comment terminators, union injection, tautologies, and quoted comment endings. It is opt-in and defaults to `post_process` only, which matches the "model emits executable artifact" threat model. When `sqlparse` is unavailable it raises a config error rather than silently faking coverage.
- **Variants:** None
- **Configuration:** Constructor knobs `capture_raw_matches`, `max_input_chars`, `phases`, and `logger`.
- **Optional extra:** `[code-injection]`
- **Latency:** Not measured
- **Concern addressed:** code injection coverage

### Shell Injection Inspector

- **Class:** `ShellInjectionInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/code_injection/shell.py`
- **Category:** Detection
- **Purpose:** Detects shell-command injection patterns in inspected text.
- **Behavior:** The inspector performs a quote-aware scan that distinguishes shell metacharacters in executable positions from characters inside quoted strings. It emits findings for command substitution, destructive piping, and command chaining, and defaults to `post_process` only. Input that exceeds configured size or fails quoting sanity checks is treated as unparseable rather than forced through unsafe heuristics.
- **Variants:** None
- **Configuration:** Constructor knobs `capture_raw_matches`, `max_input_chars`, `phases`, and `logger`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** code injection coverage

### Template Injection Inspector

- **Class:** `TemplateInjectionInspector`
- **File:** `packages/pip/src/arc_guard/inspectors/code_injection/template.py`
- **Category:** Detection
- **Purpose:** Detects SSTI and active HTML payloads in generated text.
- **Behavior:** The inspector looks for template-engine sandbox escapes, executable expression delimiters, and active HTML such as script tags, event attributes, and dangerous URLs. Like the other code-injection inspectors, it is opt-in and defaults to `post_process` only. This component does ship in `src`, so it is a real runtime surface rather than a planned module.
- **Variants:** None
- **Configuration:** Constructor knobs `capture_raw_matches`, `max_input_chars`, `phases`, and `logger`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** code injection coverage

### Conversation Turn Inspector

- **Class:** `StatefulConversationInspector`
- **File:** `packages/pip/src/arc_guard/deception/inspector.py`
- **Category:** Detection
- **Purpose:** Scores multi-turn deception risk from accumulated conversation state.
- **Behavior:** This is a separate code path from the regular inspector chain: the pipeline calls `inspect_turn(...)` after classify and before sanitize, passing any prior `ConversationState` from the guard context. The component returns a `DeceptionScore` plus updated state, and the pipeline then applies a separate deception threshold ladder. It does not implement `inspect(...)`, so it should be modeled as a distinct turn-level detector rather than another standard inspector.
- **Variants:** None
- **Configuration:** Constructor knob `default_conversation_id`; operator thresholds are tuned via `ObservabilityConfig.deception_thresholds`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** jailbreak sensing

### Jailbreak Detector

- **Class:** `RuleBasedJailbreakDetector`, `ClassifierJailbreakDetector`
- **File:** `packages/pip/src/arc_guard/jailbreak/detector.py`; `packages/pip/src/arc_guard/middleware/jailbreak_ml/detector.py`
- **Category:** Detection
- **Purpose:** Produces category-labeled jailbreak signals on a detector path that runs alongside, not inside, the normal inspector chain.
- **Behavior:** The default `RuleBasedJailbreakDetector` emits one `JailbreakSignal` per matched category from a five-family regex/keyword set, and the pipeline converts those signals into synthetic findings so existing routing rules and threshold ladders can consume them. The optional `ClassifierJailbreakDetector` wraps a HuggingFace classifier, maps the score back into the documented jailbreak categories, and is exposed through the `JailbreakMlBundle` factory. This is a distinct pipeline path: `InjectionInspector` still has overlapping jailbreak-like patterns, but the primary jailbreak subsystem is the detector interface.
- **Variants:** `RuleBasedJailbreakDetector` is the default; `ClassifierJailbreakDetector` is the optional ML-backed variant exposed by `JailbreakMlBundle`.
- **Configuration:** `RuleBasedJailbreakDetector` has no constructor knobs. `ClassifierJailbreakDetector` accepts `model_name` and `device`, and operator thresholds are tuned through `ObservabilityConfig.jailbreak_thresholds`.
- **Optional extra:** `[jailbreak-ml]`
- **Latency:** Not measured
- **Concern addressed:** jailbreak sensing

## Remediation Components

### Redact Strategy

- **Class:** `RedactStrategy`
- **File:** `packages/pip/src/arc_guard/strategies/redact.py`
- **Category:** Remediation
- **Purpose:** Replaces matched spans with typed placeholders.
- **Behavior:** The strategy counts occurrences per entity type, then rewrites spans right-to-left so offsets remain stable while producing placeholders such as `[EMAIL_ADDRESS]` or suffixed numbered variants. It also emits `PolicyDecision` records and `TransformSummary` data so the routed outcome can be audited. It is pure string transformation logic with no I/O.
- **Variants:** None
- **Configuration:** No constructor knobs.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

### Hash Strategy

- **Class:** `HashStrategy`
- **File:** `packages/pip/src/arc_guard/strategies/hash.py`
- **Category:** Remediation
- **Purpose:** Replaces matched spans with stable HMAC-based pseudonyms.
- **Behavior:** The strategy loads or creates a secret key, then rewrites each span to a short `[HASH:...]` token using HMAC-SHA256 over the original substring. It walks findings right-to-left to keep offsets valid and emits one `PolicyDecision` per transformed finding. This strategy is the shipped pseudonymization path for stable identifiers.
- **Variants:** None
- **Configuration:** Environment variables `GUARD_HASH_KEY` and `GUARD_HASH_KEY_FILE`; no constructor knobs.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

### Block Strategy

- **Class:** `BlockStrategy`
- **File:** `packages/pip/src/arc_guard/strategies/block.py`
- **Category:** Remediation
- **Purpose:** Produces an empty transformed text and marks the run as blocked.
- **Behavior:** The strategy itself only clears the text and emits block decisions; it does not build the refusal envelope. Refusal construction happens elsewhere, primarily in the policy router and refusal builder path. In other words, blocking behavior is split between the text-transform step and the higher-level refusal assembly step.
- **Variants:** None
- **Configuration:** No constructor knobs.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** graceful refusal

### Warn Strategy

- **Class:** `WarnStrategy`
- **File:** `packages/pip/src/arc_guard/strategies/warn.py`
- **Category:** Remediation
- **Purpose:** Leaves text unchanged while attaching warning-class policy decisions.
- **Behavior:** The strategy iterates the finding set and emits `PolicyDecision` records with `strategy="warn"` and `warn:`-prefixed rationale strings. It does not transform text and is not implemented as a branch inside `RedactStrategy` or `BlockStrategy`. In practice it is selected by policy rules or the default selector for low-sensitivity entity types.
- **Variants:** None
- **Configuration:** No constructor knobs.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

### Tokenize Strategy

- **Class:** `TokenizeStrategy`
- **File:** `packages/pip/src/arc_guard/strategies/tokenize.py`
- **Category:** Remediation
- **Purpose:** Replaces matched spans with per-input deterministic token placeholders.
- **Behavior:** The strategy assigns sequential counters per entity type, then rewrites spans to tokens such as `[CUSTOMER_ID_TOK_1]`. Like `WarnStrategy`, it is a standalone shipped class, not a special branch embedded in another strategy. It is intended for internal identifiers where stable placeholdering is more useful than blunt redaction.
- **Variants:** None
- **Configuration:** No constructor knobs.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

### Strategy Selector

- **Class:** `DefaultStrategySelector`
- **File:** `packages/pip/src/arc_guard/selectors/default.py`
- **Category:** Remediation
- **Purpose:** Maps entity types to registered strategy names.
- **Behavior:** The selector is resolved by the policy router when a `PolicyRule` specifies `selector=` instead of a fixed `strategy=`. The shipped implementation uses a read-only mapping that sends free-text PII to redact, stable ids to hash, internal ids to tokenize, and low-sensitivity context to warn, while unknown entity types fall back to redact and emit a warning event. It is auto-registered under the name `default`.
- **Variants:** `DefaultStrategySelector`
- **Configuration:** Constructor knobs `mapping` and `logger`; operator use is via selector registration and `PolicyRule.selector` values.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

### Content Policy

- **Class:** `SemanticContentPolicy`
- **File:** `packages/pip/src/arc_guard/content_policies/semantic.py`
- **Category:** Remediation
- **Purpose:** Evaluates predicate-style policy matches and can produce aggregate refusals outside the normal entity-inspector path.
- **Behavior:** The only shipped concrete `ContentPolicy` implementation is embedding-based: it lazily loads an encoder, compares the input embedding to a configured exemplar set, and returns a `ContentPolicyDecision`. The aggregate helper evaluates every registered content policy without short-circuiting, records each match separately, and can build one refusal envelope covering all firings. When the semantic extra is missing, `SemanticContentPolicy` stays alive as a no-op rather than crashing the pipeline.
- **Variants:** `SemanticContentPolicy`; custom operator policies can be registered through `content_policies.registry`, but no other concrete built-ins ship in `src`.
- **Configuration:** Constructor knobs `name`, `exemplars`, `similarity_threshold`, `refusal_code`, `encoder`, and `logger`; runtime use depends on content-policy registry entries and policy wiring.
- **Optional extra:** `[semantic]`
- **Latency:** Not measured
- **Concern addressed:** graceful refusal

### Intent Preservation Chain

- **Class:** `NullIntentEncoder`, `SentenceTransformerIntentEncoder`, `IntentLock`, `NullFidelityScorer`, `CosineFidelityScorer`, `NullRehydrationVerifier`, `SemanticRehydrationVerifier`
- **File:** `packages/pip/src/arc_guard/intent/capture.py`; `packages/pip/src/arc_guard/middleware/semantic/encoder.py`; `packages/core/src/arc_guard_core/intent_lock.py`; `packages/pip/src/arc_guard/fidelity/scorer.py`; `packages/pip/src/arc_guard/middleware/semantic/scorer.py`; `packages/pip/src/arc_guard/rehydration/verifier.py`; `packages/pip/src/arc_guard/middleware/semantic/verifier.py`
- **Category:** Remediation
- **Purpose:** Captures intent, scores answer fidelity, verifies safe rehydration, and binds the run with an audit-safe lock.
- **Behavior:** The chain is assembled from four roles, each with concrete shipped classes. `IntentEncoder` is either the null sentinel encoder or the sentence-transformers encoder; `FidelityScorer` is either the null scorer or cosine scorer; `RehydrationVerifier` is either the structural null verifier or the semantic verifier that adds a safety-regression check; `IntentLock` is the immutable digest record tying the artifacts together. The pipeline wires these roles separately, then runs fidelity and rehydration after the main remediation path so low-fidelity or unsafe rehydration can trigger clarification, refusal, or placeholder retention.
- **Variants:** Intent encoders: `NullIntentEncoder`, `SentenceTransformerIntentEncoder`. Fidelity scorers: `NullFidelityScorer`, `CosineFidelityScorer`. Rehydration verifiers: `NullRehydrationVerifier`, `SemanticRehydrationVerifier`. Intent lock: `IntentLock`.
- **Configuration:** Pipeline constructor knobs `intent_encoder`, `fidelity_scorer`, and `rehydration_verifier`; semantic implementations add `model_name`, `injection_inspector`, and threshold tuning via `ObservabilityConfig.fidelity_thresholds`.
- **Optional extra:** `[semantic]`
- **Latency:** Not measured
- **Concern addressed:** intent consistency after rehydration

### Refusal Envelope

- **Class:** `RefusalEnvelope`, `RefusalBuilder`
- **File:** `packages/core/src/arc_guard_core/types.py`; `packages/pip/src/arc_guard/refusal/builder.py`
- **Category:** Remediation
- **Purpose:** Carries the machine-readable and user-visible refusal payload returned when the system blocks or restricts a run.
- **Behavior:** `RefusalEnvelope` itself is a dataclass-like return type in `arc_guard_core.types`, not an orchestrating subsystem. The operational logic sits in `RefusalBuilder`, which resolves refusal templates and rule overrides into a fully-populated envelope used by the policy router and failure paths. In practice the envelope is important to the API contract, but the code treats it as a type plus a helper builder rather than as a standalone module family.
- **Variants:** `RefusalEnvelope` type; `RefusalBuilder` helper.
- **Configuration:** Template and rule configuration flow through `RefusalCode`, registered refusal templates, and `PolicyRule` fields such as `refusal_human_message` and `refusal_next_steps`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** graceful refusal

## Audit, Lifecycle, and Integration Components

### Reporter Subsystem

- **Class:** `LogReporter`, `NullReporter`
- **File:** `packages/pip/src/arc_guard/reporters/log_reporter.py`; `packages/pip/src/arc_guard/reporters/null_reporter.py`
- **Category:** Audit & Lifecycle
- **Purpose:** Receives the final `GuardResult` for audit-side effects after pipeline processing completes.
- **Behavior:** The shipped reporter surface is intentionally small: `NullReporter` discards output, while `LogReporter` writes one warning log line for non-clean results. The pipeline defaults to `NullReporter`, so reporting is opt-in at construction time. No `WebhookReporter` or other outbound reporter implementation ships in `src`; a unit-test comment explicitly notes that the old webhook reporter is gone.
- **Variants:** `NullReporter`, `LogReporter`
- **Configuration:** Pipeline constructor knob `reporter`; no per-class constructor settings on the shipped implementations.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Flag Provider Subsystem

- **Class:** `EnvFlagProvider`, `StaticFlagProvider`
- **File:** `packages/pip/src/arc_guard/flags/env_provider.py`; `packages/pip/src/arc_guard/flags/static_provider.py`
- **Category:** Core
- **Purpose:** Supplies runtime behavior flags such as enablement and legacy action selection.
- **Behavior:** `EnvFlagProvider` reads boolean, string, and list flags from environment variables with a configurable prefix, while `StaticFlagProvider` serves the same interface from an in-memory dict. The pipeline uses these flags for run enablement, default injection-inspector enablement, and the legacy single-strategy path. No third provider integrating with an external feature flag service ships in `src`.
- **Variants:** `EnvFlagProvider`, `StaticFlagProvider`
- **Configuration:** `EnvFlagProvider(prefix=...)`, `StaticFlagProvider(flags=...)`, and env vars such as `GUARD_ENABLED`, `GUARD_INJECTION_ENABLED`, and `GUARD_ACTION_STRATEGY`.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Lifecycle Audit Subsystem

- **Class:** `NullLifecycleSink`, `RingBufferLifecycleSink`, `SqliteLifecycleSink`, `CompositeLifecycleSink`, `RequestSummaryProjector`, `DecisionRecordRecorder`, `BroadcastingLifecycleSink`
- **File:** `packages/core/src/arc_guard_core/lifecycle/sink.py`; `packages/pip/src/arc_guard/observability/ring_buffer_lifecycle_sink.py`; `packages/pip/src/arc_guard/observability/sqlite_lifecycle_sink.py`; `packages/pip/src/arc_guard/observability/composite_lifecycle_sink.py`; `packages/pip/src/arc_guard/observability/request_summary_projector.py`; `packages/pip/src/arc_guard/observability/decision_record_recorder.py`; `packages/api/src/arc_guard_service/transport/events.py`
- **Category:** Audit & Lifecycle
- **Purpose:** Captures typed lifecycle events for replay, storage, projection, and live streaming.
- **Behavior:** The pipeline and API transport emit typed events through a per-request `LifecycleEmitter`, and the concrete sinks decide whether those events are dropped, buffered, persisted, projected into dashboard tables, or broadcast over SSE. `CompositeLifecycleSink` lets deployments fan out to multiple stores, while the projector and decision recorder are lifecycle consumers that maintain derived dashboard tables rather than raw event logs. This subsystem is a real runtime component family, not just a passive datamodel.
- **Variants:** Default `NullLifecycleSink`; replay/storage sinks `RingBufferLifecycleSink`, `SqliteLifecycleSink`, `CompositeLifecycleSink`; projection sinks `RequestSummaryProjector`, `DecisionRecordRecorder`; broadcast sink `BroadcastingLifecycleSink`.
- **Configuration:** Pipeline constructor knob `lifecycle_hook`; service settings `ARC_GUARD_SERVICE_LIFECYCLE_ENABLED`, `ARC_GUARD_SERVICE_LIFECYCLE_BUFFER_CAPACITY`, `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH`, `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_MAX_ROWS`, `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_MAX_AGE_DAYS`, `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_CLEANUP_INTERVAL_SECONDS`, `ARC_GUARD_SERVICE_LIFECYCLE_SSE_SUBSCRIBER_QUEUE_CAPACITY`, and related dashboard queue settings.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Observability Middleware

- **Class:** `OtelObservability`, `OtelTracer`, `OtelLogger`, `OtelMetricSink`, `StdlibBridgeLogger`
- **File:** `packages/pip/src/arc_guard/middleware/otel/__init__.py`; `packages/api/src/arc_guard_service/observability.py`; `packages/core/src/arc_guard_core/observability.py`
- **Category:** Audit & Lifecycle
- **Purpose:** Provides the pluggable logging, tracing, and metrics adapters used by the pipeline and service.
- **Behavior:** In shipped code this is mostly a wiring pattern, not a single middleware stage in the pipeline. The true extension surfaces are the `Logger`, `Tracer`, `MetricSink`, and `LifecycleSink` protocols; `OtelObservability` is just a convenience bundle that packages OTEL-backed implementations of three of them, while `StdlibBridgeLogger` is the API-side bridge for standard logs. Because the pipeline accepts these hooks separately, there is no monolithic runtime component called "observability middleware" inside the orchestrator.
- **Variants:** OTEL adapter bundle `OtelObservability` plus `OtelTracer`, `OtelLogger`, and `OtelMetricSink`; API bridge `StdlibBridgeLogger`.
- **Configuration:** OTEL environment variables, `from_otel_sdk(instrumentation_name=...)`, exporter wiring in `middleware/otel/exporter.py`, and `StdlibBridgeLogger(log, fields)`.
- **Optional extra:** `[otel]`
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Configuration

- **Class:** `GuardConfig` (`arc_guard_core.config`), `GuardConfig` (`arc_guard.config_env`), `ServiceSettings`, `ObservabilityConfig`
- **File:** `packages/core/src/arc_guard_core/config.py`; `packages/pip/src/arc_guard/config_env.py`; `packages/api/src/arc_guard_service/settings.py`; `packages/core/src/arc_guard_core/observability_config.py`
- **Category:** Core
- **Purpose:** Holds structural, service, and observability settings, but not as one single global configuration component.
- **Behavior:** Shipped code splits configuration across multiple Pydantic models. `arc_guard_core.config.GuardConfig` handles structural pipeline settings, `arc_guard.config_env.GuardConfig` handles the batteries-included package defaults and environment loading, `ServiceSettings` governs the API transport and dashboard plane, and `ObservabilityConfig` contains the threshold and sampling knobs. The codebase therefore has a configuration layer, but not one canonical top-level configuration module that owns everything.
- **Variants:** `arc_guard_core.config.GuardConfig`; `arc_guard.config_env.GuardConfig`; `arc_guard_service.settings.ServiceSettings`; `ObservabilityConfig` and its nested threshold models.
- **Configuration:** `GUARD_*` environment variables for SDK/package config and `ARC_GUARD_SERVICE_*` variables for API/service config.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

### Entity Registry

- **Class:** `EntityRegistry`
- **File:** `packages/core/src/arc_guard_core/registry.py`
- **Category:** Core
- **Purpose:** Stores custom `EntityDefinition` entries for provider-driven inspection.
- **Behavior:** The registry is a concrete provider of entity definitions with thread-safe mutation during the construction window and snapshot-style reads on the hot path. It exposes both `entities()` and `get_entities()` and can be frozen to stop later mutation. In practice it is the obvious concrete backing store for `CustomInspector`.
- **Variants:** None
- **Configuration:** Constructor plus runtime methods `register(...)` and `freeze()`; module-level helper `register_entity(...)` for the default registry.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** Core architecture

## Other Top-Level Runtime Components Not Listed in the Prompt

### Policy Router

- **Class:** `RuleBasedPolicyRouter`
- **File:** `packages/pip/src/arc_guard/policy/router.py`
- **Category:** Remediation
- **Purpose:** Resolves findings and policy rules into a concrete routed outcome.
- **Behavior:** The router is the layer that actually turns findings into an aggregate action, transformed text, refusal, clarification, fired-rule list, and transform summaries. It resolves each applicable `PolicyRule`, optionally asks a `StrategySelector` for the final strategy name, validates registry lookups, applies the selected strategies, computes the aggregate risk band, and builds the `RoutedOutcome` consumed by the pipeline. This is a distinct runtime component and, for a senior engineer, the main missing top-level piece from the original list.
- **Variants:** `RuleBasedPolicyRouter`
- **Configuration:** Constructor knobs `classifier` and `refusal_builder`; operator-facing routing logic is configured through `PolicyRuleSet`, strategy registry entries, selector registry entries, and the pipeline's optional `policy_router` injection point.
- **Optional extra:** None
- **Latency:** Not measured
- **Concern addressed:** automatic masking strategy

## Reality-Check Answers

### a) Distinct component or not?

- **Observability Middleware:** No, it is a wiring pattern over `Logger`, `Tracer`, `MetricSink`, and `LifecycleSink`, with `OtelObservability` as a convenience adapter bundle rather than a single pipeline component.
- **Configuration:** No, it is a per-module settings layer composed of multiple Pydantic models rather than one top-level runtime component.
- **Refusal Envelope:** No, it is primarily a return-type dataclass (`RefusalEnvelope`) plus a helper builder (`RefusalBuilder`), not a standalone subsystem.

### b) Other top-level runtime components in shipped code not listed above

Yes. The main additional top-level runtime component is the **Policy Router**, documented above.

### c) Total

Total distinct top-level runtime components in shipped code: 23

This count excludes the three items that are not distinct runtime components in shipped code: `Observability Middleware`, `Configuration`, and `Refusal Envelope`.
