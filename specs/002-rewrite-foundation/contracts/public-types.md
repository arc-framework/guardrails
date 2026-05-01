# Contract — Public Types

This contract enumerates every public typed model exported from `arc_guard_core`. It is the on-disk reference for the contract test suite.

The full field-level descriptions and validation rules live in [`../data-model.md`](../data-model.md). This file is a stable index that the contract test snapshot resolves against.

## Public surface (re-exported from `arc_guard_core`)

| Symbol | Kind | Module | Stability |
|---|---|---|---|
| `RiskLevel` | `IntEnum` | `arc_guard_core.types` | `@stable` |
| `GuardContext` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `GuardInput` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `Finding` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `PolicyDecision` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `RefusalEnvelope` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `GuardResult` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `EntityDefinition` | frozen dataclass | `arc_guard_core.types` | `@stable` |
| `GuardConfig` | pydantic v2 model | `arc_guard_core.config` | `@stable` |
| `RefusalCode` | `StrEnum` of registered codes | `arc_guard_core.refusal.codes` | `@stable` |

## Snapshot schema

Each entry in `tests/contract/snapshots/public_types.json` looks like:

```json
{
  "name": "GuardResult",
  "kind": "dataclass",
  "module": "arc_guard_core.types",
  "stability": "stable",
  "fields": [
    {"name": "text", "type": "str", "default": null},
    {"name": "action", "type": "Literal['pass', 'redact', 'hash', 'block', 'tokenize']", "default": "'pass'"},
    {"name": "findings", "type": "tuple[Finding, ...]", "default": "()"},
    {"name": "decisions", "type": "tuple[PolicyDecision, ...]", "default": "()"},
    {"name": "refusal", "type": "RefusalEnvelope | None", "default": "None"},
    {"name": "bypass_reason", "type": "Literal['disabled', 'error', None]", "default": "None"},
    {"name": "phase", "type": "Literal['pre_process', 'post_process']", "default": "'pre_process'"}
  ],
  "properties": ["is_clean", "max_risk"],
  "introduced_in": "core@0.1.0"
}
```

The snapshot generator walks every name in `arc_guard_core.__all__` and produces one entry. The diff layer applies these rules:

| Diff kind | Outcome |
|---|---|
| New entry | Pass with required CHANGELOG entry |
| Removed entry | Fail; requires deprecation flow (see `deprecation-policy.md`) |
| Renamed field | Fail; requires deprecation flow |
| New optional field | Pass with required CHANGELOG entry |
| Removed field | Fail |
| Type widened (`int → int \| str`) | Pass with CHANGELOG entry |
| Type narrowed (`int \| str → int`) | Fail |
| `default` changed | Fail (defaults are part of the contract) |
| `stability` lowered (`stable → experimental`) | Fail |
| `stability` raised (`experimental → stable`) | Pass with CHANGELOG entry |

## Pydantic-specific rules

`GuardConfig` declares `model_config = ConfigDict(frozen=True, extra='forbid')`. The contract test asserts:

- `extra='forbid'` is set (FR-016 — unknown configuration fields fail validation).
- `frozen=True` is set (immutability).
- Each field's JSON schema is captured in the snapshot, so additive optional fields appear as a schema diff that the diff layer can rule on.

## Adding a public type

1. Define the type in `arc_guard_core/types.py` (or the appropriate module).
2. Add it to `arc_guard_core.__all__`.
3. Run `pytest packages/core/tests/contract -k snapshot --update`. Inspect the diff.
4. Add a CHANGELOG entry under `packages/core/CHANGELOG.md`.
5. Update [`../data-model.md`](../data-model.md) with the field-level description.

## Removing a public type

1. Mark the type `@deprecated` in source.
2. Add an entry to [`deprecation-policy.md`](./deprecation-policy.md) with the replacement and removal version.
3. Wait one minor version.
4. Remove the type. The snapshot diff will require a CHANGELOG entry referring to the deprecation note.
