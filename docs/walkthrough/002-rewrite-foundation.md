# Walkthrough — Spec 002: Rewrite Foundation

This page is the one-page integrator-facing summary of [Spec 002](../../specs/002-rewrite-foundation/spec.md). It documents the new package layout, the boundary rules, and how to migrate from the Spec 001 import paths.

## What changed

The single `python/arc-guardrails/` package is split into three packages under `packages/`:

| Package | Distribution name | Role |
|---|---|---|
| `packages/core/` | `arc-guard-core` | Zero-dep contract layer — typed models, Protocols, exception hierarchy, configuration schema, pipeline shape, observability hooks |
| `packages/pip/` | `arc-guard` | Batteries-included library — concrete inspectors, strategies, reporters, flag providers, middleware, adapters; depends on `core` plus optional extras |
| `packages/api/` | `arc-guard-service` | Thin deployment surface scaffold; full wiring is owned by Spec 007 |

Allowed import direction: `api → pip → core`, never reversed. Enforced by `tools/check_import_graph.py` against `packages/.importlinter`.

## Why

Spec 001 shipped one package that pulled `presidio`, optional `nats-py`, optional `UnleashClient`, etc., even when callers only needed the contracts. The rewrite splits the public surface so an integrator can `pip install arc-guard-core` and depend on the typed contracts without inheriting any provider SDK. See [Spec 002 §"User Story 1"](../../specs/002-rewrite-foundation/spec.md) for the full motivation.

## Public surface

Spec 002 establishes the foundation surface every later spec builds on. All entries are `stable` per the [public-surface manifest](../public-surface.md):

| Symbol | Kind | Notes |
|---|---|---|
| `GuardInput` / `GuardResult` / `GuardContext` | dataclass | Primary input / output / context contracts. |
| `Finding` / `PolicyDecision` / `RefusalEnvelope` / `EntityDefinition` | dataclass | Detection / decision / refusal record types. |
| `RiskLevel` | enum | `low` / `medium` / `high` / `critical`. |
| `RefusalCode` | enum | Foundation members (`JAILBREAK`, `PII_CRITICAL`, etc.); extended additively in later specs. |
| `Guard` / `Inspector` / `ActionStrategy` / `Reporter` / `FlagProvider` / `Middleware` / `EntityProvider` | protocol | The seven plug-in surfaces. |
| `GuardConfig` / `GuardPipeline` | class | Pipeline shape (concrete implementation in `arc_guard.pipeline`). |
| `EntityRegistry` / `register_entity` | class / function | In-memory entity catalog. |
| `Tracer` / `Logger` / `MetricSink` / `Null*` | protocol / class | Observability hook surface with null defaults. |
| `ArcGuardError` and 12 leaf exceptions | class | Typed exception hierarchy with declared failure modes. |

The full inventory (140+ entries spanning Specs 002–007) lives in [`docs/public-surface.md`](../public-surface.md).

## Operator knobs

Spec 002 ships **zero optional extras**. The pipeline runs offline-only with default inspectors. Knobs:

- `GuardConfig.observability` — null-default observability hook fields (real wiring lands in Spec 004).
- Custom `Inspector` / `ActionStrategy` / `Reporter` instances passed to the `GuardPipeline(...)` constructor.
- `EntityRegistry.register(...)` for custom entity definitions (frozen at pipeline-construction time once Spec 003's `RegistryFrozenError` discipline lands).

## Migration

### Spec 001 import paths still work

If you previously imported types or protocols from `arc_guard.*`, your imports keep working through `arc-guard 0.2.x` with a `DeprecationWarning` naming the new home. The old paths are removed in `arc-guard 0.3.0`.

```python
# Spec 001 (still works in arc-guard 0.2.x; emits DeprecationWarning)
from arc_guard.types import GuardInput, GuardResult
from arc_guard.config import GuardConfig
from arc_guard.protocols import Inspector

# Spec 002 (canonical — no warning)
from arc_guard_core.types import GuardInput, GuardResult
from arc_guard_core.config import GuardConfig
from arc_guard_core.protocols import Inspector
```

### Symbol mapping

The full table lives at [`specs/002-rewrite-foundation/contracts/deprecation-policy.md`](../../specs/002-rewrite-foundation/contracts/deprecation-policy.md). Highlights:

| Spec 001 path | Spec 002 home | Removed in |
|---|---|---|
| `arc_guard.types.RiskLevel` | `arc_guard_core.types.RiskLevel` | `arc-guard 0.3.0` |
| `arc_guard.types.GuardContext` | `arc_guard_core.types.GuardContext` (adds `correlation_id`) | `arc-guard 0.3.0` |
| `arc_guard.types.GuardInput` | `arc_guard_core.types.GuardInput` (adds `policy_hints`) | `arc-guard 0.3.0` |
| `arc_guard.types.GuardResult` | `arc_guard_core.types.GuardResult` (adds `decisions`, `refusal`, `tokenize` action) | `arc-guard 0.3.0` |
| `arc_guard.config.GuardConfig` | `arc_guard_core.config.GuardConfig` (adds observability hook fields) | `arc-guard 0.3.0` |
| `arc_guard.protocols.*` | `arc_guard_core.protocols.*` | `arc-guard 0.3.0` |
| `arc_guard.registry.EntityRegistry` | `arc_guard_core.registry.EntityRegistry` | `arc-guard 0.3.0` |
| Inspectors / strategies / reporters / flags / middleware / adapters | unchanged paths under `arc_guard.*` (just relocated to `packages/pip/`) | _stays in pip_ |

### Worked example

A Spec 001 caller looked like:

```python
from arc_guard.config import GuardConfig
from arc_guard.types import GuardInput
from arc_guard.pipeline import GuardPipeline

config = GuardConfig.from_env()
pipeline = GuardPipeline(config=config)
result = await pipeline.pre_process(GuardInput(text=user_prompt))
```

The same code in Spec 002:

```python
from arc_guard_core.config import GuardConfig
from arc_guard_core.types import GuardInput
from arc_guard.pipeline import GuardPipeline           # implementation stays in pip
from arc_guard.config_env import GuardConfig as _Env   # env hydration moved here

config = _Env.from_env()                               # or use arc_guard_core's structural model directly
pipeline = GuardPipeline(config=config)
result = await pipeline.pre_process(GuardInput(text=user_prompt))
```

The contract types (`GuardConfig`, `GuardInput`, etc.) are imported from `arc_guard_core`. The runtime pipeline implementation continues to live in `arc_guard.pipeline`.

## Boundary rules at a glance

```
arc_guard_service  (api)
        ↓
    arc_guard      (pip)
        ↓
arc_guard_core     (core, zero-dep — pydantic + stdlib only)
```

- `core` MUST NOT import `pip`, `api`, any adapter, or any provider SDK.
- `pip` MUST NOT import `api`.

These rules are enforced on every commit by `tools/check_import_graph.py`. See [Spec 002 contracts](../../specs/002-rewrite-foundation/contracts/) for the full set.

## Trimmed in Spec 002 (no deprecation window)

Spec 002 ships **zero optional extras**. The following modules were removed
outright in `arc-guard 0.2.0` rather than deprecated, because they fall
outside Spec 002's scope and the roadmap explicitly defers them:

| Removed | Owning future spec | Why removed |
|---|---|---|
| `arc_guard.adapters.nats_reporter`, `[nats]` extra | Spec 007 transports backlog | A.R.C.-Platform-specific transport; roadmap §4.1 |
| `arc_guard.adapters.unleash_provider`, `[unleash]` extra | Spec 003+ generic policy/flag system | Single-vendor flag provider; roadmap §4.2 |
| `arc_guard.middleware.otel`, `[otel]` extra | Spec 004 (Observability and Runtime Hardening) | Owned by Spec 004; the hook surface in `arc_guard_core.observability` stays |
| `arc_guard.inspectors.semantic`, `[semantic]` extra | Spec 005 (Safe Rehydration and Intent Fidelity) | Will be redesigned under the intent-lock contract |
| `arc_guard.reporters.webhook_reporter`, `[webhook]` extra | Spec 007 transports backlog | Generic HTTP transport; roadmap §4.1 |
| `[arc]` aggregate extra | n/a | Was a bundle of the above |

Importing any of these now raises `ModuleNotFoundError`. The trimmed code
lives in git history at the `python/arc-guardrails/` Spec 001 snapshot and
can be resurrected per spec by re-implementing under the Spec 002 contracts.

## What's next

[Spec 003 — Sanitization and Policy Core](./003-sanitization-policy-core.md) is implemented. It ships typed-placeholder sanitization, the composable policy router, the four risk bands (D3 partial-refusal), the clarification flow, and decision-record emission — all built additively on the contracts established here.

Spec 004 wires real OTEL spans and structured logs through the observability hook surface this spec stubbed in. Spec 005 reintroduces semantic inspection under the intent-fidelity contract.

## References

- [Spec 002 — Rewrite Foundation](../../specs/002-rewrite-foundation/spec.md)
- [Spec 002 contracts](../../specs/002-rewrite-foundation/contracts/) — public types, deprecation policy, exception hierarchy, import-graph rules
- [`docs/public-surface.md`](../public-surface.md) — authoritative stability bands for every Spec 002 symbol
- [`packages/core/CHANGELOG.md`](../../packages/core/CHANGELOG.md) — version-level traceability
- [`packages/pip/CHANGELOG.md`](../../packages/pip/CHANGELOG.md)
