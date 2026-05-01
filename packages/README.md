# arc-guardrails — packages workspace

This is the rewrite foundation defined by [Spec 002](../specs/002-rewrite-foundation/spec.md). Three packages, one `uv` workspace, strict dependency direction.

## Layout

```
packages/
├── core/           # arc-guard-core — zero-dep contracts (pydantic + stdlib only)
├── pip/            # arc-guard      — batteries-included library (depends on core)
└── api/            # arc-guard-service — thin deployment scaffold (depends on pip)
```

Allowed import edges: `api → pip → core`, never reversed. Enforced by `tools/check_import_graph.py` against `packages/.importlinter`.

## Common commands

```bash
# Sync all packages into the shared workspace lockfile
uv sync

# Run a quality gate against a single package
uv run --package arc-guard-core ruff check src tests
uv run --package arc-guard-core mypy src
uv run --package arc-guard-core pytest

# Run boundary checks
python ../tools/check_import_graph.py
python ../tools/check_dependency_tree.py
python ../tools/check_async_blocking.py

# Run the contract test suite
uv run --package arc-guard-core pytest tests/contract/
```

## References

- [Spec 002 — Rewrite Foundation](../specs/002-rewrite-foundation/spec.md)
- [Implementation plan](../specs/002-rewrite-foundation/plan.md)
- [Migration walkthrough](../docs/walkthrough/002-rewrite-foundation.md)
- Per-package READMEs: [`core/`](./core/README.md), [`pip/`](./pip/README.md), [`api/`](./api/README.md)
