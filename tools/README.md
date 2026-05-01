# tools/

Repo-level boundary-enforcement scripts for the arc-guardrails rewrite (Spec 002).

| Script | Purpose | Spec FRs |
|---|---|---|
| `check_import_graph.py` | Runs `import-linter` against `packages/.importlinter` and asserts loading `arc_guard_core` does not pull any forbidden provider module | FR-006, SC-003 |
| `check_dependency_tree.py` | Audits the `arc-guard-core` runtime dependency closure for forbidden provider SDKs | FR-005, SC-002 |
| `check_async_blocking.py` | Flags blocking calls (`time.sleep`, `subprocess.run`, model inference) reachable from async pipeline entry points | FR-025, SC-007 |
| `check_adopt_vs_build.py` | Diffs `packages/core/pyproject.toml` runtime deps against `main`; requires every new entry to be referenced from `.specify/memory/libraries.md` or `specs/002-rewrite-foundation/decisions/` | FR-031, FR-032, SC-009 |

## How to run

```bash
# From the repo root:
python tools/check_import_graph.py
python tools/check_dependency_tree.py
python tools/check_async_blocking.py
python tools/check_adopt_vs_build.py    # uses git diff vs main by default

# Or via the workspace venv:
cd packages && uv run python ../tools/check_import_graph.py
```

## Updating the snapshot baselines

The contract test suite under `packages/core/tests/contract/` stores baseline
snapshots in JSON. Legitimate additive changes (new optional field, new
optional protocol method, new exception subclass) require running:

```bash
cd packages && uv run --package arc-guard-core pytest tests/contract/ -k snapshot --update-snapshot
```

Then verify the diff and add a CHANGELOG entry under `packages/core/CHANGELOG.md`.

## Adopt-vs-build dev-deps exemption

`check_adopt_vs_build.py` only enforces the rule on **runtime** dependencies
in `arc-guard-core`. Dev tooling (linters, test runners, etc.) added under
`[dependency-groups.dev]` is exempt by policy (FR-031 acceptance scenario 2).

## CI integration

These scripts are intended to run as pre-merge checks. Each returns non-zero
on violation. The expected wiring is one CI job per script.
