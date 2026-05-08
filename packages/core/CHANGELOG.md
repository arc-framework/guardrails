# Changelog — arc-guard-core

All notable changes to the `arc-guard-core` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.8.0] — 2026-05-08

### Added
- `arc_guard_core.protocols.StrategySelector` runtime-checkable Protocol — extension point that maps a detected `Finding` plus surrounding `GuardResult` context to a registered strategy name. Stateless contract; selectors choose among strategy names already registered, they do not own strategy implementations.
- `arc_guard_core.protocols.ContentPolicy` runtime-checkable Protocol + `ContentPolicyDecision` frozen dataclass — predicate-shaped policy evaluation distinct from `Inspector`'s entity-level findings. `ContentPolicyDecision` carries `matched: bool`, `confidence: float | None`, `policy_name: str`, `refusal_code: RefusalCode | None`.
- `PolicyRule.selector: str | None` field — name of a registered `StrategySelector`. Mutually exclusive with `strategy`; a `model_validator` enforces "exactly one of" at construction time with messages naming the rule id and conflicting fields.
- Three new `RefusalCode` enum members: `SQL_INJECTION`, `SHELL_INJECTION`, `TEMPLATE_INJECTION`. Default `RefusalTemplate` entries pre-registered for each, with operator-customizable `human_message` and `next_steps`.
- Package-root re-exports for the three new public symbols (`StrategySelector`, `ContentPolicy`, `ContentPolicyDecision`) so they resolve via `from arc_guard_core import StrategySelector` per the public-surface manifest convention.

### Changed
- `PolicyRule.strategy`: type relaxed from required `str` to optional `str | None = None`. Existing policy files using `strategy:` parse identically. Operators opt into selector-driven masking by replacing `strategy:` with `selector:` on a rule.

### Migration notes
- Additive only on the public surface. No breaking changes; no migration required for operators staying on the legacy `strategy:` form.
- Code reading `rule.strategy` and assuming non-None must now check `if rule.strategy is not None:`. The strategy-resolution helper in `arc_guard.policy.router` (pip package) handles the new selector path; consumers of `PolicyRule.strategy` outside `arc_guard.*` are unaffected when they continue to author rules with `strategy:` set.

## [0.7.0] — 2026-05-04

### Added
- New `arc_guard_core.lifecycle` subpackage:
  - `LifecycleSink` runtime-checkable Protocol — the 4th observability hook (sibling to `Logger` / `Tracer` / `MetricSink`).
  - `LifecycleEventBase` frozen dataclass (`id`, `parent_id`, `seq`, `ts`, `rid`, `event_type`) and 28 typed event dataclasses forming the `LifecycleEvent` tagged union (23 base events: `RequestStarted`, `PreProcessStarted`, `PostProcessStarted`, `PreProcessCompleted`, `PostProcessCompleted`, `StageRan`, `IntentCaptured`, `InspectorRan`, `FindingProduced`, `JailbreakDetected`, `DeceptionScored`, `FidelityScored`, `SanitizationApplied`, `PolicyResolved`, `StrategyExecuted`, `DecisionEmitted`, `RefusalProduced`, `BackendCalled`, `BackendResponded`, `PayloadRewritten`, `ResponseAssembled`, `RequestCompleted`, `ReportFlushed`; 5 conditional events: `PolicyRuleEvaluated`, `InspectorFailed`, `PlaceholderMapBuilt`, `RehydrationVerified`, `InspectorMatchExplain`).
  - `NullLifecycleSink` default implementation — no-op; absorbs all sink errors per Protocol contract.
  - `LifecycleEmitter` — per-rid emitter with monotonic `seq` counter shared between transport and pipeline emission sites.
  - `PayloadCapturePolicy` Protocol with `should_capture_sanitized()` / `should_capture_raw_input()` methods, plus `NullPayloadCapturePolicy` default (captures nothing). Policies gate optional richer event content; defaults are constitutionally aligned with Principle V (events MUST avoid raw sensitive payloads by default).
  - `new_event_id()` ULID-based event id generator.
- New optional Protocol `arc_guard_core.protocols.ExplainableInspector` — opt-in capability for inspectors to surface match metadata via `explain_matches(text, new_findings) -> list[InspectorMatchExplanation]`. Used by regex-based inspectors to populate `InspectorMatchExplain` events.

### Migration notes
- Additive only on the public surface. No breaking changes; no migration required.
- Existing inspectors that do not implement `ExplainableInspector` continue to work unchanged; pipelines silently skip the optional `InspectorMatchExplain` emission for them.

## [0.6.0] — 2026-05-03

### Added
- `RefusalCode.API_TRANSPORT_TIMEOUT` enum member — sibling of `API_INVALID_REQUEST`; emitted by transport-layer timeouts. Default `RefusalTemplate` registered with operator-facing human message + next-steps guidance.
- `TransportError(PipelineError)` leaf exception — `__failure_mode__='closed'`, `__valid_codes__={transport.timeout, transport.payload_too_large, transport.invalid_state}`. Used by the `arc-guard-service` HTTP transport for transport-layer failures distinct from pipeline-decision territory.
- `FAIL_RULE` entry for `TransportError` mapping to severity `error` and refusal code `API_TRANSPORT_TIMEOUT`. Posture is read from the new leaf's `__failure_mode__` ClassVar at lookup time per the foundation discipline.
- `FAILURE_API_TRANSPORT` string constant in `arc_guard_core.failure_modes`.

### Migration notes
- Additive only on the public surface. No breaking changes; no migration required.
- Callers handling specific refusal codes should add a branch for `API_TRANSPORT_TIMEOUT` if they want to distinguish transport-layer timeouts from other transport-layer rejections.

## [0.5.0] — 2026-05-02

### Added
- New pipeline stage constant `STAGE_DECEPTION_INSPECT` in `arc_guard_core.stages`. Appended additively to `STAGE_DESCRIPTORS`; runs after `STAGE_CLASSIFY` and before `STAGE_SANITIZE`.
- New Protocol modules: `protocols/jailbreak_detector.py` (`JailbreakDetector` runtime-checkable Protocol), `protocols/conversation_turn_inspector.py` (`ConversationTurnInspector`), `protocols/evaluation_harness.py` (`EvaluationHarness`).
- `arc_guard_core.jailbreak`: `JailbreakSignal` frozen dataclass with runtime regex validation on `evidence_reference` (`[A-Z][A-Z0-9_]*`) and `JailbreakCategory` Literal alias (5 categories).
- `arc_guard_core.deception`: `DeceptionScore` frozen dataclass (INVERSE direction relative to `FidelityScore` — higher = more deception) with `measured(value)` / `not_measured()` factories and module-level `NOT_MEASURED` singleton; `ConversationState` per-conversation accumulator with `conversation_id`, `turn_count`, `role_play_markers`, `escalation_signals`, `state_version` fields.
- `arc_guard_core.evaluation`: `Configuration` Literal (4 documented pipeline configurations), `ExpectedOutcome` Literal, `CorpusCategory` Literal, `CorpusEntry` frozen dataclass, `ConfigurationMetrics` with 12 metric columns (including `intelligibility_score`), `EvaluationReport` frozen dataclass.
- `JailbreakThresholds` and `DeceptionThresholds` nested pydantic models on `ObservabilityConfig`. **INVERSE direction** relative to `FidelityThresholds`: ordered `refuse > clarify > warn` since higher = more risk.
- Four new exception leaves with `__failure_mode__` discipline: `JailbreakDetectorError(AdapterError)` closed-conservative; `ConversationTurnInspectorError(AdapterError)` closed-conservative; `EvaluationHarnessError(PipelineError)` closed; `CorpusValidationError(ValidationError)` closed.
- Four new `FAIL_RULE` entries + matching `FAILURE_*` string constants.
- Two new `RefusalCode` members: `JAILBREAK_STRONG` (sibling of `JAILBREAK`, distinguishes strong-detector refusals from regex refusals in audit records) and `DECEPTION_DRIFT` (multi-turn deception refusals). Default refusal templates registered for both.
- `GuardResult` gains additive fields: `deception_score: DeceptionScore | None = None` and `conversation_state: ConversationState | None = None` (the **updated** state returned by the inspector; operators thread it forward to the next turn).
- `GuardContext` gains additive field `conversation_state: ConversationState | None = None` (the **prior** state the operator threads in).
- `DecisionRecord` gains additive fields `jailbreak_signals: tuple[JailbreakSignal, ...] = ()` and `deception_score: DeceptionScore | None = None`.

## [0.4.0] — 2026-05-02

### Added
- Three new pipeline stage constants in `arc_guard_core.stages`: `STAGE_DEFEND` (intent capture pre-sanitization), `STAGE_VERIFY` (fidelity-score computation post-generation), `STAGE_REHYDRATE` (safety-checked reinsertion). Appended additively to `STAGE_DESCRIPTORS`; existing call sites unchanged.
- New Protocol modules under `arc_guard_core.protocols/`: `intent_encoder.py` (`IntentEncoder` runtime-checkable Protocol + `IntentRepresentation` opaque type alias), `fidelity_scorer.py` (`FidelityScorer` Protocol with `compatible_with(encoder)` pairing check), `rehydration_verifier.py` (`RehydrationVerifier` Protocol + `RehydrationVerdict` frozen dataclass with three-way `accept` / `reject` / `partial` decision discriminator).
- `arc_guard_core.fidelity` module: `FidelityScore` frozen dataclass with `value: float | None` + `sentinel: Literal["measured", "not_measured"]` discriminator, `measured(value)` / `not_measured()` classmethod constructors, module-level `NOT_MEASURED` singleton.
- `arc_guard_core.intent_lock.IntentLock` frozen dataclass: SHA-256 hex digests of canonicalized original intent, sanitized prompt, rehydrated answer, plus `encoder_id`. Content-addressed audit binding for `DecisionRecord`; the lock contains zero raw text.
- `arc_guard_core.observability_config.FidelityThresholds` nested pydantic model: frozen, `extra="forbid"`, three fields (`warn`/`clarify`/`refuse`) each `Field(ge=0.0, le=1.0)` with a `model_validator(mode="after")` enforcing `warn > clarify > refuse`. Hung off `ObservabilityConfig.fidelity_thresholds` with default `(0.7, 0.5, 0.3)`.
- Three new exception leaves in `arc_guard_core.exceptions`: `IntentEncoderError(AdapterError)` with `__failure_mode__='closed-conservative'`, `FidelityScorerError(AdapterError)` with `__failure_mode__='open'`, `RehydrationVerifierError(PipelineError)` with `__failure_mode__='closed'`. Each declares its own `__valid_codes__` set.
- Three new `FAIL_RULE` entries in `arc_guard_core.failure_modes`: `IntentEncoderError → (intent_encoder, warn, None)`, `FidelityScorerError → (fidelity_scorer, warn, None)`, `RehydrationVerifierError → (rehydration_verifier, error, RefusalCode.FIDELITY_DROP)`. Posture is read from `__failure_mode__` ClassVar at lookup time per the foundation discipline.
- `GuardResult` gains two additive optional fields: `fidelity_score: FidelityScore | None = None` and `fidelity_warning: bool = False` (typed boolean indicator set by the fidelity threshold ladder).
- `DecisionRecord` gains two additive optional fields: `intent_lock: IntentLock | None = None` and `fidelity_score: FidelityScore | None = None`.

### Changed
- Renamed `RefusalCode.FIDELITY_DROP_PLACEHOLDER` → `RefusalCode.FIDELITY_DROP` (placeholder reservation upgraded to live code). The placeholder member was a reservation, never a stable consumer-facing surface; the rename keeps the contract-snapshot delta minimal. The default `RefusalTemplate` for `FIDELITY_DROP` now contains real human-message + next-steps text instead of the previous "(reserved)" stub.
- `ObservabilityConfig` gains `fidelity_thresholds: FidelityThresholds = Field(default_factory=FidelityThresholds)` (additive — existing constructors continue to work).

### Migration notes
- Callers that referenced `RefusalCode.FIDELITY_DROP_PLACEHOLDER` (none expected per the 0.3.0 CHANGELOG which described it as a reservation) update to `RefusalCode.FIDELITY_DROP`.
- All other surface changes are additive; no other public types break.

## [0.3.0] — 2026-05-02

### Added
- `arc_guard_core.stages` module: `STAGE_VALIDATE`, `STAGE_CLASSIFY`, `STAGE_SANITIZE`, `STAGE_ROUTE`, `STAGE_EXECUTE`, `STAGE_REFUSAL`, `STAGE_DECISION_EMIT`, `STAGE_REPORT`, plus `STAGE_DESCRIPTORS` allow-list.
- `arc_guard_core.failure_modes` module: `FailureRule` NamedTuple, `FAIL_RULE` table covering all 12 leaf exceptions, `lookup_rule(exc_type)` helper that walks MRO and reads posture from foundation `__failure_mode__` ClassVar.
- `arc_guard_core.observability_config.ObservabilityConfig` frozen pydantic model: `sampling_rate`, `refusal_always_emits`, `log_level_floor`, `metric_attribute_allow_list`, `max_attribute_bytes`. Validates fully at construction time.
- `arc_guard_core.protocols.attribute_redactor.AttributeRedactor` Protocol with `RedactionResult` frozen dataclass.
- `arc_guard_core._registry_lock.FrozenAfterConstructionRegistry` shared internal helper. Generic over the value type; both `EntityRegistry` (core) and `StrategyRegistry` (pip) compose with it. Underscore-prefixed: not part of the public surface.
- `RegistryFrozenError(ConfigCrossFieldError)` leaf exception. Inherits the `config` rule via MRO walking in `failure_modes.lookup_rule`; declares `__failure_mode__ = "closed"` and `__valid_codes__ = {"registry.frozen"}` per the foundation invariant.
- `RefusalCode` enum extended with six new members: `API_INVALID_REQUEST`, `INTERNAL_PIPELINE_ERROR`, `INTERNAL_ADAPTER_ERROR`, `INTERNAL_REFUSAL_BUILD_ERROR`, `INTERNAL_ENTITY_PROVIDER_ERROR`, `INTERNAL_UNKNOWN_ERROR`. Default refusal templates registered for each.
- `EntityRegistry` adopts the frozen-after-construction discipline: `register()` raises `RegistryFrozenError` after `freeze()`; `entities()` returns a snapshot copy that does not require locking on the hot path.

### Changed
- `GuardConfig` gains `observability: ObservabilityConfig` field with safe defaults (full sampling, full verbosity, conservative attribute allow-list). Additive — existing constructors continue to work.
- Contract-snapshot machinery (`tests/contract/_snapshot.py`) canonicalizes `frozenset` / `set` / `dict` defaults via a stable repr so post-Python-3.7 hash randomization no longer produces flaky snapshot diffs.

### Migration notes
- Additive only on the public surface. No breaking changes; no migration required.
- Callers that mutated `EntityRegistry` after pipeline construction will now see `RegistryFrozenError`. Move registrations earlier (before pipeline construction) to keep working.

## [0.2.0] — 2026-05-01

### Added
- (Spec 003) `ClarificationRequest` frozen dataclass in `arc_guard_core.types`.
- (Spec 003) `RiskBand` (StrEnum), `RiskThresholds`, `PolicyRule`, `PolicyRuleSet`, `RoutedOutcome`, `TransformSummary` in `arc_guard_core.policy`.
- (Spec 003) `DecisionRecord`, `FindingSummary` in `arc_guard_core.decision`.
- (Spec 003) `RefusalTemplate`, `DEFAULT_REFUSAL_TEMPLATES`, `register_refusal_template`, `get_refusal_template` in `arc_guard_core.refusal.templates`.
- (Spec 003) `DEFAULT_PLACEHOLDERS` registry, `register_placeholder`, `get_placeholder`, `format_placeholder` (D2 sequential per-type suffix) in `arc_guard_core.placeholders`.
- (Spec 003) `PolicyRouter` Protocol in `arc_guard_core.protocols.policy_router` (sync, thread-safe, fail-closed).

### Changed
- (Spec 003) `GuardResult` gains optional `clarification: ClarificationRequest | None` field per D1. Mutually exclusive with `action="block"`.
- (Spec 003) `GuardConfig` gains optional `policy: PolicyRuleSet | None` field; `None` preserves Spec 001/002 behavior.

## [0.1.0] — 2026-05-01

### Added
- Initial release. Zero-dep contract layer for arc-guardrails.
- Typed models: `RiskLevel`, `GuardContext`, `GuardInput`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `GuardResult`, `EntityDefinition`.
- Configuration schema: `GuardConfig` (pydantic v2, `frozen=True`, `extra='forbid'`).
- Seven Protocol interfaces: `Guard`, `Inspector`, `ActionStrategy`, `Reporter`, `FlagProvider`, `Middleware`, `EntityProvider`.
- Observability hook surface (experimental): `Tracer`, `Logger`, `MetricSink` Protocols with null-object defaults.
- Typed exception hierarchy with declared fail-open / fail-closed failure modes per stage.
- `GuardPipeline` shape (no provider SDK imports).
- `EntityRegistry` (thread-safe, in-memory).
- `RefusalCode` enum.
