# arc-guard — DEPRECATED LOCATION

**This directory is the Spec 001 home of `arc-guard`. Spec 002 moved the
implementation to [`packages/pip/`](../../packages/pip/).**

## Where the code lives now

| Old location | New location |
|---|---|
| `python/arc-guardrails/src/arc_guard/types.py` | `packages/core/src/arc_guard_core/types.py` |
| `python/arc-guardrails/src/arc_guard/protocols/` | `packages/core/src/arc_guard_core/protocols/` |
| `python/arc-guardrails/src/arc_guard/registry.py` | `packages/core/src/arc_guard_core/registry.py` |
| `python/arc-guardrails/src/arc_guard/config.py` (presidio shape) | `packages/pip/src/arc_guard/config_env.py` |
| `python/arc-guardrails/src/arc_guard/inspectors/` | `packages/pip/src/arc_guard/inspectors/` |
| `python/arc-guardrails/src/arc_guard/strategies/` | `packages/pip/src/arc_guard/strategies/` |
| `python/arc-guardrails/src/arc_guard/reporters/` | `packages/pip/src/arc_guard/reporters/` |
| `python/arc-guardrails/src/arc_guard/flags/` | `packages/pip/src/arc_guard/flags/` |
| `python/arc-guardrails/src/arc_guard/middleware/` | `packages/pip/src/arc_guard/middleware/` |
| `python/arc-guardrails/src/arc_guard/adapters/` | `packages/pip/src/arc_guard/adapters/` |
| `python/arc-guardrails/src/arc_guard/pipeline.py` | `packages/pip/src/arc_guard/pipeline.py` |

## Why the migration

Spec 002 splits the contract layer (typed models, Protocols, exception hierarchy,
configuration schema, observability hooks) into a zero-dep `arc-guard-core`
package that an integrator can install without pulling presidio, NATS, Unleash,
OTEL, or any model runtime. The batteries-included library `arc-guard` now
depends on `arc-guard-core` and continues to ship the concrete inspectors,
strategies, reporters, and adapters under the same import paths.

See the migration walkthrough at
[`docs/walkthrough/002-rewrite-foundation.md`](../../docs/walkthrough/002-rewrite-foundation.md)
for the full mapping and a worked example.

## Deprecation timeline

- **`arc-guard 0.2.x`**: Spec 001 import paths (`arc_guard.types.*`,
  `arc_guard.config.GuardConfig`, `arc_guard.protocols.*`,
  `arc_guard.registry.*`) keep working through PEP 562 ``__getattr__`` shims.
  Each access emits a `DeprecationWarning` naming the new home.
- **`arc-guard 0.3.0`**: shims are removed; importing from the old paths
  raises `ImportError` with a link to this migration note.

## What still lives here

This directory keeps:

- `pyproject.toml` — kept to mark the legacy distribution while the deprecation
  window is open. The `[project]` table remains valid but points at no source.
- `analysis/`, `images/` — historical artifacts referenced by Spec 001 docs.
- `tests/` — original Spec 001 test suite, preserved for reference. The live
  suite has been migrated to `packages/pip/tests/` and is the authoritative one.
- `uv.lock` — preserved for archival reproducibility of Spec 001.

## What to do as a caller

If you use `from arc_guard.types import GuardResult`:

```bash
# Spec 002 canonical path:
from arc_guard_core.types import GuardResult
```

If you use `from arc_guard.inspectors.presidio import PresidioInspector`:

```python
# Unchanged — implementation modules keep their import path:
from arc_guard.inspectors.presidio import PresidioInspector
```

See [`packages/pip/CHANGELOG.md`](../../packages/pip/CHANGELOG.md) for the full
list of deprecated symbols and their removal version.
