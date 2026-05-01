# Implementation Plan: Rewrite Foundation — Package Split, Contracts, and Engineering Baseline

**Branch**: `002-rewrite-foundation` | **Date**: 2026-05-01 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-rewrite-foundation/spec.md`

## Summary

Spec 002 splits the existing `python/arc-guardrails/` monolith into three packages — `packages/core` (zero-dep contracts and pipeline shape), `packages/pip` (batteries-included guardrail library), and `packages/api` (thin deployment surface) — and pins the contracts, validation rules, exception hierarchy, and concurrency policy that every later rewrite spec inherits. Existing code is *moved* into the new layout in stages, not rewritten; Spec 001 tests come along as behavioral guardrails; the Spec 001 import surface stays alive behind a deprecation shim for one minor version.

The technical approach: (1) introduce the `packages/` workspace alongside the live `python/arc-guardrails/` so migration is staged and reversible; (2) extract zero-dep contract modules to `packages/core`; (3) move provider-coupled implementation to `packages/pip`; (4) leave `packages/api` as a thin scaffold seeded for Spec 007; (5) wire enforcement gates (import-graph audit, contract test suite, concurrency lint, deprecation warnings, adopt-vs-build pre-merge check) so the boundary rules are *automatic*, not aspirational.

## Technical Context

| Aspect | Value |
|---|---|
| **Language / Version** | Python 3.11+ (constitution-mandated baseline; matches existing `python/arc-guardrails/pyproject.toml`) |
| **Project Type** | Multi-package Python library workspace (`uv` workspace under `packages/`) plus a thin service surface |
| **Primary Dependencies (`packages/core`)** | `pydantic` only. No presidio, torch, transformers, nats, unleash, opentelemetry at install time. `typing_extensions` allowed for back-compat typing helpers if needed |
| **Primary Dependencies (`packages/pip`)** | `arc-guard-core` (workspace dep), `presidio-analyzer`, `presidio-anonymizer`, plus optional extras `[semantic]`, `[nats]`, `[unleash]`, `[webhook]`, `[otel]` (preserved from Spec 001) |
| **Primary Dependencies (`packages/api`)** | `arc-guard` (workspace dep), `pydantic-settings`, `fastapi` *(api package is scaffolded only in Spec 002; full wiring is Spec 007)* |
| **Storage** | N/A — library is in-process; configuration loads from environment / files; no persistent state in `core` |
| **Testing** | `pytest` + `pytest-asyncio` + `pytest-cov`. New: contract test suite under `packages/core/tests/contract/` snapshotting public types and protocol signatures |
| **Target Platform** | Linux / macOS / Windows Python 3.11+ runtimes; offline / air-gapped install supported (constitution Product Constraint) |
| **Performance Goals** | No regression vs. Spec 001 baseline. Spec 002 adds no hot-path logic; the only runtime cost is one extra import indirection across package boundaries |
| **Constraints** | Zero provider SDKs in `core` install closure (enforced by import-graph + dependency-tree audits); `mypy --strict` clean across all three packages; no blocking calls on the asyncio event loop in async pipeline paths |
| **Scale / Scope** | One library, three packages, ~30-40 source modules total after migration. ~5-10 new infra modules for boundary enforcement (import-graph check, contract snapshot, deprecation shim, concurrency lint, adopt-vs-build check) |
| **Workflow** | `uv` workspace; per-package `pyproject.toml`, version, and `CHANGELOG.md`; per-package quality gate runs `ruff check`, `pytest`, `mypy --strict` |
| **Resolved unknowns** | See [research.md](./research.md). Key resolution: roadmap's `common`/`core`/`api` is reconciled with the package restructure design's `core`/`pip`/`api` — this plan adopts `core`/`pip`/`api` |

No `NEEDS CLARIFICATION` markers remain after Phase 0 research.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution at `.specify/memory/constitution.md` v1.0.0.

| Principle | Status | Evidence |
|---|---|---|
| **I. Generic-First Core** | PASS | `packages/core` declares zero provider runtime deps (FR-003); import-graph check enforces (FR-006). No NATS, Unleash, OTEL, presidio, torch reachable from `core`'s install closure (SC-002). |
| **II. One Contract, Many Modes** | PASS | Contract types (`GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, `RefusalEnvelope`) live in `packages/core` and are versioned. `packages/pip` (SDK / library mode) and `packages/api` (deployment-mode scaffold) both consume the same contract surface. |
| **III. Adapter Isolation** | PASS | Adapters stay in `packages/pip/.../adapters/` behind optional extras (FR-005). No adapter symbol is reachable from `core` (FR-006, SC-003). |
| **IV. Enterprise Python Baseline** | PASS | Each package uses `pyproject.toml`, `src/` layout, `uv`, `ruff`, `mypy --strict`, `pytest` (FR-027 - FR-030, SC-010). Contract test suite + per-package CHANGELOG enforce versioning discipline (FR-013, FR-030). |
| **V. Security, Observability, Resilience** | PASS | Typed exception hierarchy with declared fail-open vs fail-closed behavior per stage (FR-021 - FR-023). OTEL/logging hook surface stubbed in `core` so Spec 004 can wire it without re-shaping contracts (Assumption #5). Reporter paths preserved as non-blocking from Spec 001. |

| Product Constraint | Status | Evidence |
|---|---|---|
| Versioned event names and payload schemas | PASS | Contract types are versioned, with stability markers and additive-vs-breaking change rules in the contract test suite (FR-012, FR-013). |
| Configurable, product-neutral defaults | PASS | FR-020 forbids hard-coded provider names, NATS subjects, paths, or logger names in defaults. |
| Heavy deps stay optional | PASS | Presidio, torch, transformers, nats, unleash, otel all remain optional extras in `packages/pip` (no change from Spec 001) and are absent from `packages/core`. |
| Feature declares affected modes and contract impact | PASS | Spec 002 declares SDK as primary, sidecar/worker/gateway/batch/CLI as inheritors. Contract impact stated: introduces `GuardInput`/`GuardResult`/etc. in their stable home. |
| Offline / air-gapped operation possible | PASS | `packages/core` has zero network-dependent runtime deps. Default install path requires no provider SDK. |

| Workflow Gate | Status | Evidence |
|---|---|---|
| Feature classified | PASS | `core-contract` + `enterprise-baseline` (combined classification per `.specify/memory/patterns.md` heuristics — package split is `core-contract`, baseline gates are `enterprise-baseline`). |
| Compatibility / migration / enterprise impact stated | PASS | Spec §"Compatibility, Migration, and Enterprise Impact" + FR-007 - FR-009. |
| Local quality gate | PASS | Each package gates on `ruff` + `pytest` + `mypy --strict` (FR-028, SC-010). |
| Public behavior changes documented in `docs/` | PASS | FR-033 (walkthrough page), FR-035 (READMEs link to migration note and contract reference). |
| Staged migration, no implicit rename | PASS | FR-008 (Spec 001 surface importable for one minor with deprecation warnings) + FR-009 (migration note with worked example). No silent string-replace. |

**Gate result**: PASS. No violations. **Complexity Tracking** section below remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/002-rewrite-foundation/
├── plan.md                 # This file (/speckit.plan output)
├── spec.md                 # Feature specification
├── research.md             # Phase 0 output — design decisions, naming, library reuse
├── data-model.md           # Phase 1 output — entity / contract definitions
├── quickstart.md           # Phase 1 output — integrator and contributor walkthroughs
├── contracts/              # Phase 1 output
│   ├── README.md
│   ├── public-types.md     # GuardInput, GuardResult, Finding, PolicyDecision, RefusalEnvelope
│   ├── protocols.md        # Guard, Inspector, Reporter, FlagProvider, ActionStrategy + new VIVA-deferred slots
│   ├── exceptions.md       # Typed exception hierarchy, fail-open vs fail-closed table
│   ├── package-boundaries.md  # Allowed import edges, enforcement rules
│   └── deprecation-policy.md  # Spec 001 → Spec 002 surface mapping, removal policy
├── checklists/
│   └── requirements.md     # Spec quality checklist (already present)
└── tasks.md                # Phase 2 output (NOT created by /speckit.plan — see /speckit.tasks)
```

### Source Code (repository root)

The repo currently has a single Python package under `python/arc-guardrails/`. Spec 002 introduces the `packages/` workspace alongside it; migration is staged so the old path stays buildable until each piece is moved.

```text
sdk/
├── packages/                                # NEW — uv workspace root for the rewrite
│   ├── pyproject.toml                       # uv workspace declaration
│   ├── README.md                            # Workspace orientation, links to walkthrough
│   ├── core/                                # arc-guard-core — zero-dep contracts + pipeline shape
│   │   ├── pyproject.toml                   # name: arc-guard-core; runtime dep: pydantic only
│   │   ├── README.md
│   │   ├── CHANGELOG.md
│   │   ├── src/arc_guard_core/
│   │   │   ├── __init__.py                  # Curated public surface
│   │   │   ├── types.py                     # GuardInput, GuardContext, GuardResult, Finding, RiskLevel, PolicyDecision, RefusalEnvelope
│   │   │   ├── exceptions.py                # Typed exception hierarchy + fail-open/closed markers
│   │   │   ├── pipeline.py                  # GuardPipeline shape (no third-party imports)
│   │   │   ├── config.py                    # GuardConfig schema (structural only; no env IO)
│   │   │   ├── registry.py                  # EntityRegistry (thread-safe, in-memory)
│   │   │   ├── observability.py             # OTEL/logging hook surface (no-op default; Spec 004 wires)
│   │   │   ├── concurrency.py               # Concurrency markers (sync/async/thread-safety)
│   │   │   └── protocols/
│   │   │       ├── __init__.py
│   │   │       ├── guard.py                 # Guard
│   │   │       ├── inspector.py             # Inspector
│   │   │       ├── strategy.py              # ActionStrategy
│   │   │       ├── reporter.py              # Reporter
│   │   │       ├── flag_provider.py         # FlagProvider
│   │   │       ├── middleware.py            # Middleware
│   │   │       └── entity_provider.py       # EntityProvider
│   │   └── tests/
│   │       ├── unit/
│   │       │   ├── test_types.py
│   │       │   ├── test_exceptions.py
│   │       │   ├── test_pipeline_shape.py
│   │       │   └── test_registry.py
│   │       └── contract/
│   │           ├── test_public_surface_snapshot.py     # FR-013
│   │           ├── test_protocol_signatures.py
│   │           └── snapshots/                          # Frozen public types and protocol signatures
│   │
│   ├── pip/                                 # arc-guard — batteries-included library
│   │   ├── pyproject.toml                   # name: arc-guard; runtime dep: arc-guard-core, presidio-*; extras preserved
│   │   ├── README.md
│   │   ├── CHANGELOG.md
│   │   ├── src/arc_guard/
│   │   │   ├── __init__.py                  # Re-exports curated public surface (Spec 001 compat shim lives here)
│   │   │   ├── _legacy.py                   # Spec 001 deprecation shims (FR-008)
│   │   │   ├── inspectors/                  # Migrated from python/arc-guardrails/src/arc_guard/inspectors/
│   │   │   ├── strategies/                  # Migrated
│   │   │   ├── reporters/                   # Migrated
│   │   │   ├── flags/                       # Migrated
│   │   │   ├── adapters/                    # Migrated (NATS, Unleash, OTEL exporters)
│   │   │   ├── middleware/                  # Migrated (OTEL middleware stays here, behind extra)
│   │   │   └── config_env.py                # Env-var hydration (env IO lives here, not in core)
│   │   └── tests/
│   │       ├── unit/                        # Migrated test files
│   │       ├── integration/                 # Migrated
│   │       └── deprecation/
│   │           └── test_legacy_imports.py   # FR-008 verifies Spec 001 paths still importable with warnings
│   │
│   └── api/                                 # arc-guard-service — thin deployment surface (scaffold only in Spec 002)
│       ├── pyproject.toml                   # name: arc-guard-service; runtime dep: arc-guard, pydantic-settings; api framework optional
│       ├── README.md                        # Marks scope as "Spec 007 owns full wiring"
│       ├── CHANGELOG.md
│       ├── src/arc_guard_service/
│       │   ├── __init__.py
│       │   ├── settings.py                  # Pydantic settings skeleton
│       │   └── _placeholder.py              # Documents handoff to Spec 007
│       └── tests/
│           └── test_package_imports.py      # Smoke test that the package installs and imports
│
├── tools/                                   # NEW — repo-level enforcement scripts
│   ├── check_import_graph.py                # FR-006, SC-003 — fails build if core imports adapters/transports
│   ├── check_async_blocking.py              # FR-025, SC-007 — flags blocking calls on async pipeline path
│   ├── check_dependency_tree.py             # FR-005, SC-002 — audits core install closure for forbidden packages
│   ├── check_adopt_vs_build.py              # FR-031, FR-032, SC-009 — pre-merge check for new core runtime deps
│   └── README.md
│
├── python/                                  # EXISTING — preserved during migration
│   ├── arc-guardrails/                      # Stays buildable until each module is moved to packages/
│   └── arc-common/                          # Decision recorded in research.md (fold into packages/core or retire)
│
├── docs/
│   ├── walkthrough/
│   │   ├── 002-rewrite-foundation.md        # NEW — package layout walkthrough (FR-033)
│   │   └── 001-arc-guard-rails.md           # Existing
│   └── md/                                   # Existing
│
└── specs/
    ├── 002-rewrite-foundation/              # This spec
    └── 001-arc-guard-rails/                 # Baseline
```

**Structure Decision**: three-package `uv` workspace under `packages/` with names `core` / `pip` / `api`, adopted from the package restructure design at `docs/superpowers/specs/2026-04-20-packages-restructure-design.md`. The roadmap's `common`/`core`/`api` is mapped to `core`/`pip`/`api` in [research.md §1](./research.md). Existing `python/arc-guardrails/` stays buildable through the migration window; `python/arc-common/` is decided in research.md §3.

The boundary-enforcement scripts live at the repo root under `tools/` so they can audit the workspace as a whole and remain runnable in CI without per-package wiring.

## Complexity Tracking

> Constitution Check passed without violations. This section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                              |

## Phase 0 — Research output

[research.md](./research.md) resolves the following decisions before Phase 1 design:

1. Naming reconciliation — `common`/`core`/`api` (roadmap) vs `core`/`pip`/`api` (design). Decision: adopt design names.
2. Workspace tooling — `uv` workspace vs separate repos vs monorepo helpers. Decision: `uv` workspace.
3. Fate of existing `python/arc-common/` — fold into `packages/core` or retire. Decision: retire after Spec 002 lands; nothing in it is reused by `core`.
4. Validation library — pydantic v2 vs dataclasses+manual vs attrs+cattrs. Decision: pydantic v2 for boundary models, frozen dataclasses for internal value types.
5. Contract snapshot mechanism — handwritten `.pyi` snapshot vs `inspect.signature` runtime snapshot vs `mypy --strict` only. Decision: runtime introspection snapshot stored as JSON under `tests/contract/snapshots/`, diffed in test.
6. Import-graph enforcement — `pydeps`, `import-linter`, custom AST walker. Decision: `import-linter` (purpose-built, declarative `.ini` rules).
7. Async-blocking enforcement — `flake8-async`, `ruff` rule `ASYNC*`, custom AST walker. Decision: ruff `ASYNC` lint family + a small custom walker for the async pipeline boundary.
8. Deprecation shim mechanism — `__getattr__` module hook + `warnings.warn` vs `DeprecationWarning` decorator vs lazy import. Decision: PEP 562 `__getattr__` with `DeprecationWarning`.
9. OTEL hook stub shape — null-object protocol, async generator, callback list. Decision: null-object protocol; Spec 004 substitutes the real implementation.

Every NEEDS CLARIFICATION item from Technical Context is closed above.

## Phase 1 — Design output

Phase 1 produces four artifacts:

- [data-model.md](./data-model.md) — every public typed model from FR-010, with field-level descriptions, validation rules, and stability markers.
- [contracts/](./contracts/) — five contract documents (public types, protocols, exceptions, package boundaries, deprecation policy). One per cross-cutting concern. These are the "external interface" of the foundation per the plan template's Phase 1 step 2.
- [quickstart.md](./quickstart.md) — integrator and contributor walkthroughs, validating User Stories 1, 2, and 3 from the spec end-to-end.
- Agent context refresh — `.specify/scripts/bash/update-agent-context.sh claude` is run to add the rewrite's tech context to `CLAUDE.md` between the managed markers.

## Phase 2 — Tasks (NOT generated by /speckit.plan)

Per the SpecKit convention, `tasks.md` is produced by `/speckit.tasks` from this plan. The plan establishes:

- migration is staged (move modules in three batches: contracts → implementation → adapters), each batch running its own quality gate before the next starts;
- the boundary-enforcement scripts under `tools/` are wired *before* any module is moved so a regression cannot land silently;
- the Spec 001 deprecation shim is wired *first* under `packages/pip/_legacy.py` so the old import paths keep working from day one of the new layout.

## Re-evaluation: Constitution Check (post-design)

Phase 1 introduces no new principle conflicts. The contract documents under `contracts/` reinforce Principles I–V rather than relax them. Re-check status: **PASS** with no entries added to Complexity Tracking.

## Notes for downstream specs

- Spec 003 inherits the contract types from this spec without modification; new sanitization fields are added as optional, additive entries verified by the contract test suite.
- Spec 004 wires the no-op OTEL/logging hook surface in `core` to real exporters in `pip`'s `middleware/` directory.
- Spec 005 extends `GuardResult` and `RefusalEnvelope` (additively) with fidelity-related fields; the contract test suite catches the addition and requires a CHANGELOG entry.
- Spec 006 adds adversarial corpora and the evaluation harness under a new top-level directory; no `core`/`pip` contract changes are expected.
- Spec 007 fully wires `packages/api` with route handlers, request/response models, and integration documentation. Spec 002 leaves it as a scaffold with the install path tested.
