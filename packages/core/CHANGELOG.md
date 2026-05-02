# Changelog — arc-guard-core

All notable changes to the `arc-guard-core` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

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
