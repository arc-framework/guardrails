# Contracts — Rewrite Foundation

These five documents are the externally observable surface of Spec 002. The contract test suite at `packages/core/tests/contract/` snapshots and asserts against them.

| File | Purpose | Spec FRs |
|---|---|---|
| [public-types.md](./public-types.md) | Every public typed model in `arc_guard_core`. The "what crosses every boundary" contract. | FR-010, FR-011, FR-012, FR-013 |
| [protocols.md](./protocols.md) | Every Protocol interface, its sync/async contract, its declared exceptions, and its thread-safety expectations. | FR-014, FR-015 |
| [exceptions.md](./exceptions.md) | The typed exception hierarchy plus the fail-open vs fail-closed table per public stage. | FR-021, FR-022, FR-023 |
| [package-boundaries.md](./package-boundaries.md) | The allowed import edges between `core`, `pip`, and `api`, and the enforcement rules in `tools/check_import_graph.py`. | FR-001 — FR-006 |
| [deprecation-policy.md](./deprecation-policy.md) | The mapping from Spec 001 public symbols to Spec 002 homes, plus the deprecation-window rules and removal procedure. | FR-007, FR-008, FR-009 |

## How these contracts are enforced

1. **`tests/contract/test_public_surface_snapshot.py`** introspects `arc_guard_core` at runtime, builds a JSON snapshot of every public type's fields and every protocol's signatures, and diffs it against the stored baseline under `tests/contract/snapshots/`. Additive changes pass with a CHANGELOG check; renames, removals, and type narrowings fail.
2. **`tools/check_import_graph.py`** runs `import-linter` against the rules in [package-boundaries.md](./package-boundaries.md) on every commit.
3. **`tests/contract/test_failure_modes.py`** asserts that every public stage's documented exceptions are listed in [exceptions.md](./exceptions.md) and carry the matching `__failure_mode__` marker.
4. **`packages/pip/tests/deprecation/test_legacy_imports.py`** verifies that every Spec 001 public name listed in [deprecation-policy.md](./deprecation-policy.md) is reachable through the PEP 562 shim with the documented warning, and that the current public names do not warn.
5. **`tools/check_adopt_vs_build.py`** verifies any new runtime dependency added to `core` references a recorded adopt-vs-build entry.

## Stability and versioning

- Every entry in these contracts has a stability marker (`@stable`, `@experimental`, `@deprecated`).
- Additive changes (new optional field, new optional protocol method with default, new exception subclass) are permitted within a minor version; the changelog of the affected package MUST list them.
- Breaking changes (rename, removal, type narrowing, fail-mode change) require a major-version bump for the affected package, an entry in [deprecation-policy.md](./deprecation-policy.md), and a migration note.
