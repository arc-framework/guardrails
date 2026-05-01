# Contract — Public Types

This contract enumerates every public typed model added or modified by Spec 003. The full field-level descriptions and validation rules live in [`../data-model.md`](../data-model.md). This file is the index used by the contract test snapshot.

## Public surface added or modified by Spec 003

| Symbol | Kind | Module | Stability | Status |
|---|---|---|---|---|
| `ClarificationRequest` | frozen dataclass | `arc_guard_core.types` | `@stable` | NEW (D1) |
| `RiskBand` | `StrEnum` | `arc_guard_core.policy` | `@stable` | NEW |
| `RiskThresholds` | pydantic model | `arc_guard_core.policy` | `@stable` | NEW |
| `PolicyRule` | pydantic model | `arc_guard_core.policy` | `@stable` | NEW |
| `PolicyRuleSet` | pydantic model | `arc_guard_core.policy` | `@stable` | NEW |
| `RoutedOutcome` | frozen dataclass | `arc_guard_core.policy` | `@stable` | NEW |
| `DecisionRecord` | frozen dataclass | `arc_guard_core.decision` | `@stable` | NEW |
| `FindingSummary` | frozen dataclass | `arc_guard_core.decision` | `@stable` | NEW |
| `TransformSummary` | frozen dataclass | `arc_guard_core.decision` | `@stable` | NEW |
| `RefusalTemplate` | frozen dataclass | `arc_guard_core.refusal.templates` | `@stable` | NEW |
| `GuardResult.clarification` | optional field | `arc_guard_core.types.GuardResult` | `@stable` | NEW (D1) |
| `GuardConfig.policy` | optional field | `arc_guard_core.config.GuardConfig` | `@stable` | NEW |

## Re-exports from `arc_guard_core.__init__`

Spec 003 adds these names to `arc_guard_core.__all__`:

```python
__all__ += [
    "ClarificationRequest",
    "RiskBand",
    "RiskThresholds",
    "PolicyRule",
    "PolicyRuleSet",
    "RoutedOutcome",
    "DecisionRecord",
    "FindingSummary",
    "TransformSummary",
    "RefusalTemplate",
    "PolicyRouter",
]
```

The Spec 002 snapshot test picks up the new entries automatically and requires a CHANGELOG entry (additive — passes; not a break).

## Diff rules (inherited from Spec 002 contract)

| Diff kind | Outcome |
|---|---|
| New entry in `__all__` | Pass with required CHANGELOG entry |
| New optional field on existing type (`GuardResult.clarification`, `GuardConfig.policy`) | Pass with required CHANGELOG entry |
| Rename / removal of any Spec 002 OR Spec 003 entry | Fail; requires deprecation flow |
| Type narrowing | Fail |
| `default` change | Fail |
| `stability` lowering (e.g. `stable` → `experimental`) | Fail |

## Pydantic-specific rules

`RiskThresholds`, `PolicyRule`, `PolicyRuleSet` all declare `model_config = ConfigDict(frozen=True, extra='forbid')`. The contract test asserts both flags are set on every Spec 003 pydantic model.

## Adding a new typed model in Spec 003+

1. Define it in the appropriate module (`arc_guard_core.policy` for routing types, `arc_guard_core.decision` for audit types, `arc_guard_core.types` for cross-cutting).
2. Add it to `arc_guard_core.__all__`.
3. Run `pytest packages/core/tests/contract -k snapshot --update-snapshot` and review the diff.
4. Add a CHANGELOG entry.
5. Update [`../data-model.md`](../data-model.md) with the field-level description.

## Adding a field to an existing Spec 002 / 003 model

Same flow. Optional fields with defaults are additive; required fields are breaking.
