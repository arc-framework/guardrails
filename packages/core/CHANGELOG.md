# Changelog — arc-guard-core

All notable changes to the `arc-guard-core` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

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
