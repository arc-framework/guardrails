# arc-guard-core

Zero-dep contract layer for arc-guardrails.

`arc-guard-core` is the contract package: typed models, Protocol interfaces, the typed exception hierarchy, the configuration schema, the registry, the pipeline shape, and the observability hook surface. Its only runtime dependency is `pydantic`. Installing it pulls **no** provider SDK, transport runtime, or model backend.

## Install

```bash
pip install arc-guard-core
```

## Quick example

```python
from arc_guard_core.config import GuardConfig
from arc_guard_core.pipeline import GuardPipeline
from arc_guard_core.types import GuardInput

pipeline = GuardPipeline(config=GuardConfig())
result = pipeline.pre_process_sync(GuardInput(text="hello"))
print(result.action)  # "pass"
```

## What lives where

| Module | Purpose |
|---|---|
| `arc_guard_core.types` | Typed models — `GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, etc. |
| `arc_guard_core.protocols` | Seven Protocol interfaces (`Guard`, `Inspector`, …) |
| `arc_guard_core.config` | `GuardConfig` (pydantic v2, frozen, `extra='forbid'`) |
| `arc_guard_core.exceptions` | Typed exception hierarchy with declared fail-open/closed markers |
| `arc_guard_core.observability` | `Tracer`, `Logger`, `MetricSink` Protocols + null implementations |
| `arc_guard_core.pipeline` | `GuardPipeline` shape (no provider SDK imports) |
| `arc_guard_core.registry` | Thread-safe `EntityRegistry` |
| `arc_guard_core.refusal.codes` | `RefusalCode` enum |

## References

- [CHANGELOG](./CHANGELOG.md)
- The active spec set lives under `../../specs/`; the migration walkthroughs live under `../../docs/walkthrough/`.
