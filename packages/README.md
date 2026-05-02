# arc-guardrails — packages workspace

The rewrite foundation: three packages, one `uv` workspace, strict dependency direction.

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

- Per-package READMEs: [`core/`](./core/README.md), [`pip/`](./pip/README.md), [`api/`](./api/README.md)
- Per-package CHANGELOGs document version-level traceability.
- The active spec set lives under `../specs/`; the migration walkthroughs live under `../docs/walkthrough/`.
