# Contracts — Sanitization and Policy Core

These five documents are the externally observable surface of Spec 003. The Spec 002 contract test suite at `packages/core/tests/contract/` extends to snapshot every public type listed here.

| File | Purpose | Spec FRs |
|---|---|---|
| [public-types.md](./public-types.md) | Every new typed model: `ClarificationRequest`, `DecisionRecord`, `FindingSummary`, `TransformSummary`, `PolicyRule`, `PolicyRuleSet`, `RiskBand`, `RiskThresholds`, `RoutedOutcome`, plus the additive fields on `GuardResult` and `GuardConfig`. | FR-001, FR-005, FR-021, FR-031, D1 |
| [policy-router.md](./policy-router.md) | The `PolicyRouter` Protocol — sync / fail-closed / thread-safe. Method shape and exception contract. | FR-005, FR-008 |
| [strategy-registry.md](./strategy-registry.md) | `StrategyRegistry` public API; built-in registered names; conflict-resolution table. | FR-007, FR-025, FR-026, FR-027 |
| [decision-record.md](./decision-record.md) | `DecisionRecord` schema; the "no raw payload" rule; JSON serialization rules; emission cadence. | FR-021, FR-022, FR-023, FR-024 |
| [placeholder-registry.md](./placeholder-registry.md) | `TypedPlaceholder` registry; default labels; D2 suffix format; override mechanism. | FR-001, FR-002, FR-003, FR-004 |

## How these contracts are enforced

1. **`tests/contract/test_public_surface_snapshot.py`** (extended) — picks up the new public types added to `arc_guard_core.__all__`. Additive entries pass with a CHANGELOG check; rename/removal/narrowing fails.
2. **`tests/contract/test_protocol_signatures.py`** (extended) — picks up `PolicyRouter` and asserts it carries the documented `Concurrency:` and `Failure mode:` lines.
3. **`tests/contract/test_no_raw_payload_in_decision_record.py`** (NEW) — emits `DecisionRecord` from a fixture suite of inputs, serializes each, scans for raw substrings (the original input text, the original entity content). Any hit fails the test.
4. **`tests/contract/test_strategy_conflict_resolution.py`** (NEW) — exhaustive parametrized test over the `block > redact > tokenize > hash > warn > pass` precedence table.
5. **`tests/contract/test_typed_placeholder_format.py`** (NEW) — fixture inputs with 1, 2, 3 occurrences of the same type; assert the output respects the D2 format.
6. **`tools/check_import_graph.py`** — unchanged. The new modules in `pip` MUST NOT introduce any reverse import edge.
7. **`tools/check_dependency_tree.py`** — unchanged. Spec 003 adds zero runtime deps.

## Stability and versioning

- Every entry in these contracts is `@stable` from the moment it lands (with `RefusalCode.FIDELITY_DROP_PLACEHOLDER` reserved for Spec 005).
- Additive changes (new optional field on a Spec 003 model, new built-in strategy name, new default placeholder label) are permitted within a minor version with a CHANGELOG entry.
- Breaking changes to any Spec 003 contract require a major-version bump and the deprecation flow established by Spec 002.

## Versioning impact

- `arc-guard-core` 0.1.0 → **0.2.0** (additive: new types and one new optional field)
- `arc-guard` 0.2.0 → **0.3.0** (existing planned removal release for Spec 001 import paths AND the Spec 003 router landing — coordinated)
- `arc-guard-service` 0.1.0 → unchanged in Spec 003
