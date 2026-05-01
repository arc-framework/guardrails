# Changelog — arc-guard

All notable changes to the `arc-guard` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.3.0] — 2026-05-01

### Added
- (Spec 003) New built-in strategies `warn` and `tokenize` registered in the strategy registry by default.
- (Spec 003) `RuleBasedPolicyRouter` — default `PolicyRouter` implementation that resolves per-finding routing decisions, applies the configured precedence (`block > redact > tokenize > hash > warn > pass`), and emits a `DecisionRecord` per pipeline run.
- (Spec 003) `StrategyRegistry` thread-safe in-memory mapping with `register_strategy`, `get_strategy`, `is_registered`, `list_registered`, and a `@strategy("name")` decorator.
- (Spec 003) `RefusalBuilder` and decision `Emitter` modules wiring Spec 002 observability hooks.
- (Spec 003) Pipeline now branches on `GuardConfig.policy is None`: `None` preserves Spec 001/002 behavior; otherwise the policy router runs.

### Changed
- (Spec 003) `redact` strategy emits typed placeholders per the typed-placeholder registry (`[<TYPE>]` for single occurrences, `[<TYPE>_1]`/`[<TYPE>_2]`/… for multiple).

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
