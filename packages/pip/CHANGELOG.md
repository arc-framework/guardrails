# Changelog — arc-guard

All notable changes to the `arc-guard` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.2.0] — 2026-05-01

### Added
- Spec 001 import surface preserved through PEP 562 `__getattr__` shims; see `_legacy.py` for the deprecation table.
- Batteries-included library now depends on `arc-guard-core` for contracts.

### Changed
- Contract types (`RiskLevel`, `GuardContext`, `GuardInput`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `GuardResult`, `EntityDefinition`, `GuardConfig`) and Protocol interfaces moved to `arc_guard_core`. Old import paths (`arc_guard.types.*`, `arc_guard.config.GuardConfig`, etc.) emit `DeprecationWarning` and are scheduled for removal in `arc-guard 0.3.0`.

### Deprecated
- All Spec 001 type and protocol import paths under `arc_guard.*`. Migration note: see `docs/walkthrough/002-rewrite-foundation.md`.
