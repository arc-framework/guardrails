# Changelog — arc-guard-core

All notable changes to the `arc-guard-core` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

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
