# Contract — Deprecation Policy

FR-007 through FR-009 require that every Spec 001 public symbol stays importable for one minor version after the rewrite ships, then is removable through a documented flow. This contract pins the policy and the Spec 001 → Spec 002 mapping.

## Policy

1. **Add new home first**. The new symbol lands in its `arc_guard_core` or `arc_guard` location, fully tested.
2. **Keep the old name**. The Spec 001 import path remains usable through a PEP 562 `__getattr__` shim in `packages/pip/src/arc_guard/__init__.py` (and any sub-packages).
3. **Warn**. Every access of the old name emits a `DeprecationWarning` naming the replacement and the removal version.
4. **Wait one minor version**. The next minor release ships with the warning still firing. Integrators have time to migrate.
5. **Remove**. The minor release after that removes the old name. Importing it raises `ImportError` with a link to the migration note.
6. **CHANGELOG every step**. Add (with replacement), remove.

## Symbol mapping (Spec 001 → Spec 002)

The mapping covers every public symbol previously exported from `arc_guard.*`. The table is the single source of truth; the contract test asserts every entry is importable through the shim until the listed removal version.

| Spec 001 path | Spec 002 home | Removal version | Notes |
|---|---|---|---|
| `arc_guard.types.RiskLevel` | `arc_guard_core.types.RiskLevel` | `arc-guard 0.3.0` | Shape unchanged |
| `arc_guard.types.GuardContext` | `arc_guard_core.types.GuardContext` | `arc-guard 0.3.0` | Adds `correlation_id` field |
| `arc_guard.types.GuardInput` | `arc_guard_core.types.GuardInput` | `arc-guard 0.3.0` | Adds `policy_hints` field |
| `arc_guard.types.Finding` | `arc_guard_core.types.Finding` | `arc-guard 0.3.0` | Shape unchanged |
| `arc_guard.types.GuardResult` | `arc_guard_core.types.GuardResult` | `arc-guard 0.3.0` | Adds `decisions`, `refusal`, `tokenize` action |
| `arc_guard.types.EntityDefinition` | `arc_guard_core.types.EntityDefinition` | `arc-guard 0.3.0` | Shape unchanged |
| `arc_guard.config.GuardConfig` | `arc_guard.config_env.GuardConfig` | `arc-guard 0.3.0` | Spec 001 presidio/model-path shape preserved unchanged at the new path. The new generic contract `arc_guard_core.config.GuardConfig` is a *separate* class with a different shape — opt in explicitly. |
| `arc_guard.registry.EntityRegistry` | `arc_guard_core.registry.EntityRegistry` | `arc-guard 0.3.0` | Shape unchanged |
| `arc_guard.protocols.Guard` | `arc_guard_core.protocols.guard.Guard` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.Inspector` | `arc_guard_core.protocols.inspector.Inspector` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.ActionStrategy` | `arc_guard_core.protocols.strategy.ActionStrategy` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.Reporter` | `arc_guard_core.protocols.reporter.Reporter` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.FlagProvider` | `arc_guard_core.protocols.flag_provider.FlagProvider` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.Middleware` | `arc_guard_core.protocols.middleware.Middleware` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.protocols.EntityProvider` | `arc_guard_core.protocols.entity_provider.EntityProvider` | `arc-guard 0.3.0` | Docstring extended |
| `arc_guard.pipeline.GuardPipeline` | `arc_guard.pipeline.GuardPipeline` | _(stays in pip)_ | Implementation lives in `pip`; no rename |
| `arc_guard.inspectors.*` | `arc_guard.inspectors.*` | _(stays in pip)_ | No move |
| `arc_guard.strategies.*` | `arc_guard.strategies.*` | _(stays in pip)_ | No move |
| `arc_guard.reporters.*` | `arc_guard.reporters.*` | _(stays in pip)_ | No move |
| `arc_guard.flags.*` | `arc_guard.flags.*` | _(stays in pip)_ | No move |
| `arc_guard.adapters.*` | _removed in `arc-guard 0.2.0`_ | already removed | NATS / Unleash trimmed per roadmap §4.1–§4.2; Spec 007 reintroduction backlog. |
| `arc_guard.middleware.*` | _OTEL removed in `arc-guard 0.2.0`_ | already removed | OTEL middleware owned by Spec 004; namespace preserved for future middleware. |
| `arc_guard.inspectors.semantic` | _removed in `arc-guard 0.2.0`_ | already removed | Semantic inspector owned by Spec 005 (intent fidelity). |
| `arc_guard.reporters.webhook_reporter` | _removed in `arc-guard 0.2.0`_ | already removed | Webhook reporter trimmed per roadmap §4.1; Spec 007 transport backlog. |

Implementation modules that **stayed** in `pip` (inspectors injection / presidio / custom, strategies, reporters null / log, flags) keep their `arc_guard.*` paths because they belong to `pip`; only the contract layer migrated to `core`. Modules that were **trimmed** in Spec 002 (NATS, Unleash, OTEL, semantic, webhook) raise `ModuleNotFoundError` on import — see `packages/pip/CHANGELOG.md` §"Removed" for the rationale and reintroduction plan.

## Warning text

The shim emits a single-line message:

```
DeprecationWarning: arc_guard.types.GuardResult moved to arc_guard_core.types.GuardResult.
The old import path is removed in arc-guard 0.3.0. See https://.../docs/walkthrough/002-rewrite-foundation.md#migration
```

The URL points to the walkthrough's migration section. The contract test verifies the message format.

## Removal procedure

When the removal version ships:

1. Delete the entry from the `_legacy.py` table.
2. The PEP 562 `__getattr__` falls through to `AttributeError`; integrators see `ImportError`.
3. The `_legacy.py` table also records a `removed_in` field; the test that previously asserted "importable with warning" flips to "importable raises ImportError with the migration link".

## Version policy

- `arc-guard` (the `pip` package) versions independently of `arc-guard-core`.
- Spec 002 ships:
  - `arc-guard-core` 0.1.0 (new package, first release).
  - `arc-guard` 0.2.0 (deprecation window opens).
- Spec 003 ships:
  - `arc-guard` 0.3.0 (deprecation window closes; old paths removed).

The version numbers are policy, not promises — the contract is the *flow*, not the *exact numbers*.

## Updating this file

A change to the symbol mapping triggers:

1. The contract test running its "every entry is importable" check on the new table.
2. A CHANGELOG entry under `packages/pip/CHANGELOG.md`.
3. A walkthrough doc update under `docs/walkthrough/002-rewrite-foundation.md`.
