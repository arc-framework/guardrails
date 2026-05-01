# Phase 0 — Research: Rewrite Foundation

**Feature**: 002-rewrite-foundation
**Date**: 2026-05-01
**Purpose**: Resolve every "NEEDS CLARIFICATION" before Phase 1 design starts. Each item below has a Decision, a Rationale, and Alternatives Considered.

---

## 1. Package naming — `common`/`core`/`api` vs `core`/`pip`/`api`

**Tension**: The rewrite roadmap §1.2 says `packages/common`, `packages/core`, `packages/api`. The package restructure design at `docs/superpowers/specs/2026-04-20-packages-restructure-design.md` §4 says `packages/core`, `packages/pip`, `packages/api` with different semantics:

| Name in roadmap | Description in roadmap | Closest design name | Description in design |
|---|---|---|---|
| `common` | "tiny and dependency-light" | `core` | "zero-dep" — only stdlib + pydantic |
| `core` | "all actual guardrail logic" | `pip` | "batteries-included library" — inspectors, strategies, adapters |
| `api` | "thin deployment surface" | `api` | "microservice (FastAPI)" |

The semantic mapping is clean (roadmap-`common` ≡ design-`core`; roadmap-`core` ≡ design-`pip`); the names are not.

**Decision**: Adopt the design's names — `core`, `pip`, `api`.

**Rationale**:
- The design is the more concrete, more recent reference (2026-04-20 vs the roadmap's 2026-05-01 high-level pass) and was authored as the binding restructure plan.
- `pip` (the batteries-included library that users `pip install arc-guard`) communicates intent more clearly than reusing `core` for that role.
- The spec's Assumption #1 already permits this: "If [the design] lands a renaming before this spec is implemented, the names propagate; the boundary rules in this spec do not."
- The boundary rules in the spec (FR-002 through FR-006) are name-agnostic; they describe shape, not identifiers.

**Alternatives considered**:
- *Use roadmap names verbatim*: rejected — would require renaming both packages later when Spec 003+ pulls from the design's directory layout, defeating roadmap §1.2's "do not let strings move twice".
- *Introduce a fourth `common` package for true cross-cutting utilities*: rejected — premature abstraction. There is no module that is logically shared between `core` and `api` but does not belong to `core`. If one emerges in Spec 003-005, it can be added then without touching this plan.
- *Rename the roadmap*: rejected — out of scope for Spec 002. The roadmap remains an aspirational planning doc; the design is the executable layout.

**Action**: Map roadmap items mentioning `common` to `core` and roadmap items mentioning `core` to `pip` throughout this plan and downstream artifacts. Record this mapping once, here. Spec 002's spec.md `FR-001`–`FR-005` remain valid because they describe boundary semantics, not names.

---

## 2. Workspace tooling

**Question**: How are the three packages wired so they share a single development environment, share lockfiles, run a single test command, but publish independently?

**Decision**: `uv` workspace — a single root `pyproject.toml` under `packages/` declaring `tool.uv.workspace.members = ["core", "pip", "api"]`, with each member keeping its own `pyproject.toml`, version, and `CHANGELOG.md`.

**Rationale**:
- The constitution mandates `uv` (Principle IV); using `uv` workspaces inherits that mandate without adding a second tool.
- `uv` workspaces handle path-based intra-workspace dependencies (e.g. `arc-guard` declares `arc-guard-core = { workspace = true }`) without requiring publish-then-install cycles during development.
- A single `uv lock` produces a unified lockfile across packages, making the dependency-tree audit (FR-005, SC-002) deterministic.
- `uv run --package arc-guard-core pytest` lets the quality gate target a single package per FR-028.

**Alternatives considered**:
- *Three separate repos with `path =` editable installs*: rejected — adds repo coordination overhead, fragments PR review, and breaks the constitutional "one shared decision contract" by giving each package its own release cadence by default.
- *Poetry workspaces*: rejected — constitution mandates `uv`. No reason to add a parallel tool.
- *`pip install -e` editable installs without a workspace declaration*: rejected — works locally but breaks the dependency-tree audit because the install closures of the three packages diverge.

---

## 3. Fate of existing `python/arc-common/`

**Question**: The roadmap explicitly warns "do not let existing arc-common become the new guardrail common by accident". What happens to the existing `python/arc-common/` package?

**Inputs**:
- `python/arc-common/` exists with `pyproject.toml` and `src/arc_common/`.
- The constitution and patterns memory do not require it to remain.
- `arc-guard` does not currently import from `arc_common` (verified by inspection: existing `python/arc-guardrails/src/arc_guard/` has no `arc_common` imports).

**Decision**: Retire `python/arc-common/` after the rewrite foundation lands. It is not folded into `packages/core` and it is not used as the rewrite's `common`. The package is left untouched during Spec 002's migration window; its retirement is documented as a follow-up captured in `tasks.md` and revisited in Spec 007's "future backlog capture" step.

**Rationale**:
- Folding `arc-common` into `packages/core` would violate Principle I (Generic-First Core) if any of its current code carries hidden product-specific assumptions, and would violate the "do not silently absorb later specs" rule (roadmap §10) if its purpose is unclear.
- Leaving it alone during Spec 002 satisfies the constitution's "no implicit string-replace renames" rule and keeps the migration strictly additive.
- A retirement decision in Spec 007 (or a dedicated cleanup spec) gets the proper treatment: changelog entry, explicit deprecation, removal release.

**Alternatives considered**:
- *Move `arc-common` content into `packages/core` now*: rejected — risks importing product-coupled helpers into the zero-dep contract layer.
- *Delete `arc-common` in this spec*: rejected — destructive change without a migration note for any external caller; cleaner to deprecate-then-remove.
- *Rename `arc-common` to `arc-guard-common` and keep it*: rejected — adds a fourth package without any code that needs it.

---

## 4. Validation library

**Question**: How are typed boundary models defined? Pydantic v2, frozen dataclasses + manual validators, or attrs + cattrs?

**Decision**:
- **Boundary models** (cross-package, cross-API, configuration): `pydantic` v2.
- **Internal value types and findings**: `dataclasses(frozen=True)`.

**Rationale**:
- `pydantic` is already required by the constitution's libraries memory (`PRIMARY` status). Using it at boundaries inherits validated parsing, JSON schema export, and constitution alignment for free.
- Frozen dataclasses for internal value types avoid pydantic overhead in inner loops (e.g. constructing many `Finding` instances per pipeline run) and match the existing Spec 001 code shape under `python/arc-guardrails/src/arc_guard/types.py`.
- The contract test suite (FR-013) snapshots both kinds of types uniformly via `inspect`; the choice does not leak into the snapshot format.
- Mixing them is safe because pydantic v2 happily round-trips dataclasses through `TypeAdapter`.

**Alternatives considered**:
- *Pydantic everywhere*: rejected — measurable per-call overhead at the inspector level, and the existing dataclass-based types in Spec 001 are already shipped; the migration would cost more than it pays back.
- *Dataclasses everywhere*: rejected — boundary validation (FR-016 through FR-019) requires a real validation library at config and API edges; rolling our own would violate the reuse-before-build rule.
- *attrs + cattrs*: rejected — would add a third typing tool when pydantic and stdlib dataclasses already cover both ends. No constitutional listing.

---

## 5. Contract snapshot mechanism

**Question**: How does the contract test suite (FR-013) detect renames, removals, and type narrowings of public types and protocol signatures?

**Decision**: A runtime introspection snapshot stored as JSON under `packages/core/tests/contract/snapshots/`. The snapshot generator walks the curated public surface (the names re-exported from `arc_guard_core.__init__`), records each name's kind (class / dataclass / pydantic model / Protocol / function / enum), its public field set with type strings, and its method signatures with parameter and return annotations. The contract test diffs the live snapshot against the stored one; additive changes pass with a CHANGELOG check, breaking changes fail.

**Rationale**:
- The snapshot is human-reviewable JSON, which makes pull-request diffs explainable to reviewers — a `mypy --strict` failure on an internal test is opaque by comparison.
- Runtime introspection survives refactors that move classes between modules within a package, which `.pyi` snapshots do not.
- It interoperates with both pydantic models and frozen dataclasses without needing a stub generator.
- The diff logic is small enough (under 200 lines) that it does not justify importing a third-party tool, and it would be a bespoke contract anyway.

**Alternatives considered**:
- *Handwritten `.pyi` snapshot*: rejected — needs manual updates on every additive change and does not capture pydantic-specific behavior.
- *`mypy --strict` only*: rejected — catches type narrowings but does not surface renames or removals as a single auditable diff. Useful as a complementary gate (FR-028), not as the contract suite.
- *`griffe` or `pdoc` introspection libraries*: deferred — they would work, but the snapshot is small enough and stable enough that adopting one adds a dep without removing code. Revisitable in Spec 007 if doc generation joins the build.

---

## 6. Import-graph enforcement

**Question**: How does FR-006 / SC-003 (the import-graph check that fails the build if `core` imports an adapter, transport, or provider SDK) get enforced?

**Decision**: `import-linter` with declarative `.ini` rules, plus a small wrapper script under `tools/check_import_graph.py` that runs it as part of the per-package quality gate.

**Rationale**:
- `import-linter` is purpose-built for this exact problem: declaring forbidden import edges between packages or modules. Rules are static text, version-controlled, and reviewable.
- The constitution's libraries memory does not list it, but the adopt-vs-build rule (FR-031) is satisfied by the alternatives analysis below: a custom AST walker would replicate `import-linter`'s logic. The adopt-vs-build note will be recorded under `.specify/memory/libraries.md` when the dependency lands.
- Runs in a few hundred milliseconds even on CI, so it can sit on every PR.

**Rules to declare** (initial set):

```ini
[importlinter]
root_packages = arc_guard_core arc_guard arc_guard_service

[importlinter:contract:core_zero_dep]
name = core may not depend on pip or api or any provider SDK
type = forbidden
source_modules = arc_guard_core
forbidden_modules =
    arc_guard
    arc_guard_service
    presidio_analyzer
    presidio_anonymizer
    nats
    UnleashClient
    httpx
    opentelemetry
    torch
    transformers

[importlinter:contract:pip_no_api]
name = pip may not depend on api
type = forbidden
source_modules = arc_guard
forbidden_modules = arc_guard_service

[importlinter:contract:layered]
name = api → pip → core, never reversed
type = layers
layers =
    arc_guard_service
    arc_guard
    arc_guard_core
```

**Alternatives considered**:
- *Custom AST walker*: rejected on adopt-vs-build grounds — `import-linter` exists and is mature.
- *`pydeps`*: rejected — produces graphs but does not enforce rules out of the box.
- *Manual review only*: rejected — Principle III demands enforcement.

---

## 7. Async-blocking enforcement

**Question**: How does FR-025 / SC-007 (no blocking calls on the asyncio event loop in async pipeline paths) get caught before merge?

**Decision**: `ruff` with the `ASYNC` rule family enabled (currently `ASYNC100`–`ASYNC230` cover `time.sleep`, `subprocess.run`, blocking IO, and unawaited coroutines), plus a small custom AST walker under `tools/check_async_blocking.py` that flags calls into known-blocking modules (`time`, `subprocess`, `socket`, third-party model inference) from any function reachable from the async pipeline entry point.

**Rationale**:
- `ruff` is already a constitutional gate; turning on its `ASYNC` rule family is free.
- The custom walker covers the cases ruff misses — specifically, calls into `presidio_analyzer.AnalyzerEngine.analyze` and `transformers.pipeline()` from an async context. These are domain-specific and unlikely to land in a generic linter.
- The walker is ~150 lines, so the adopt-vs-build calculus favors building it. The note will be recorded under `.specify/memory/libraries.md` if the walker grows beyond a single file.

**Alternatives considered**:
- *`flake8-async`*: rejected — ruff's `ASYNC` rules supersede it for our use cases.
- *Trio's pytest plugin to detect blocking at runtime*: rejected — we use asyncio, not trio, and runtime detection misses the "before merge" requirement of SC-007.
- *Manual review only*: rejected — this is exactly the kind of regression that landed in Spec 001's NATS reporter and motivated the "non-blocking" constitutional clause.

---

## 8. Deprecation shim mechanism

**Question**: How do FR-008 / SC-008 ensure every Spec 001 public symbol stays importable for one minor version with a deprecation warning that names its replacement, then becomes an `ImportError` with a migration link in the next minor version?

**Decision**: PEP 562 module-level `__getattr__` in `packages/pip/src/arc_guard/__init__.py` (and any sub-packages where Spec 001 re-exported names), backed by a single `_legacy.py` table that maps old names to new locations and tracks the removal version. Each access raises a `DeprecationWarning` (via `warnings.warn(..., DeprecationWarning, stacklevel=2)`) with the replacement and removal version. The contract test suite verifies (a) every Spec 001 public name is reachable through the shim and (b) every shim entry has a stored removal version. A separate test runs with `warnings.simplefilter("error")` and asserts that imports of *current* public names produce no warnings.

**Rationale**:
- PEP 562 `__getattr__` is the idiomatic way to deprecate at module level without having to keep the old objects alive.
- Centralizing the table in `_legacy.py` makes the migration auditable: a single grep shows which symbols are scheduled for removal.
- The two-step warning model (warning during the deprecation window, `ImportError` after) matches the spec's Acceptance Scenarios for User Story 4.

**Alternatives considered**:
- *`@deprecated` decorator on each old function*: rejected — does not work for renamed classes or modules, and would require keeping the old definitions around.
- *Lazy importer that re-imports from the new location*: rejected — adds startup cost and hides the warning behind import-time side effects.
- *Stub module with hand-written re-exports*: rejected — duplicates the table, drift-prone.

---

## 9. OTEL / logging hook surface in `core`

**Question**: Spec 002 must seed `core` with hooks that Spec 004 will wire to real OTEL spans, structured logs, and metrics — without committing `core` to any provider SDK.

**Decision**: A null-object protocol surface in `arc_guard_core/observability.py`. Three protocols — `Tracer`, `Logger`, `MetricSink` — each with the minimum methods Spec 004 will need (`Tracer.start_span`, `Logger.bind`, `Logger.event`, `MetricSink.counter`, `MetricSink.histogram`). Default implementations are no-ops. The pipeline accepts these via `GuardConfig` and falls back to the null instances when nothing is supplied. Spec 004 will provide concrete implementations in `packages/pip/src/arc_guard/middleware/` that wrap real exporters.

**Rationale**:
- Keeps `core` honest to Principle I (no OTEL SDK reachable from `core`).
- Gives Spec 004 a stable target without requiring a contract change at that point.
- Null-object pattern means the default install does *something correct* (silent), not a `None` check at every call site.

**Alternatives considered**:
- *Async generator–based event stream*: rejected — adds asyncio coupling to a hook that needs to work in sync contexts too.
- *Callback list*: rejected — fan-out semantics do not match span/log/metric APIs cleanly. Spec 004 would have to invent the protocol anyway.
- *Defer entirely to Spec 004*: rejected — leaves `core` without a hook surface, forcing Spec 004 to either reach into `core` modules or duplicate the pipeline shape. Either move violates contract stability.

---

## 10. Adopt-vs-build pre-merge check

**Question**: How is FR-031 / FR-032 / SC-009 (every new runtime dependency in `core` must reference a recorded adopt-vs-build note) enforced?

**Decision**: A pre-commit / CI hook (`tools/check_adopt_vs_build.py`) that:
1. Runs `uv tree --package arc-guard-core --depth 1` (or equivalent inspection of `packages/core/pyproject.toml`).
2. Diffs the runtime dependency set against `main`.
3. For every newly added runtime dependency, requires a matching entry under `.specify/memory/libraries.md` *or* a referenced ADR file under `specs/002-rewrite-foundation/decisions/` whose front matter names the dependency.
4. Fails the check if either (a) a dependency was added without a note, or (b) the note exists but does not include the comparison-with-build paragraph required by §V.

**Rationale**:
- Mechanizes the constitution's reuse-before-build rule. The check is what turns it from a "we should remember" into a gate.
- The ADR-or-libraries-memory dual location respects existing repo conventions: small, repeated dependencies (e.g. `import-linter`) get a one-line entry in `libraries.md`; large dependencies get an ADR.
- Exempts dev-only dependencies per FR-031's Acceptance Scenario 2.

**Alternatives considered**:
- *No automated check, rely on PR review*: rejected — explicitly forbidden by the rewrite roadmap §1.9.
- *Block all new dependencies*: rejected — the rewrite legitimately needs `import-linter` and possibly a couple more tools; the rule is "documented decision", not "no new deps".
- *Use `uv`'s `--locked` mode*: rejected — that catches lockfile drift, not the policy question of whether a new dep should exist.

---

## 11. Migration sequencing

**Question**: In what order do existing modules move from `python/arc-guardrails/src/arc_guard/` into `packages/`?

**Decision**: Three batches, each gated by green CI before the next starts.

- **Batch A — Contracts**: `types.py`, `protocols/`, `config.py` skeleton, `registry.py`, the new `exceptions.py`, the new `observability.py`, the new `concurrency.py`. Move into `packages/core/src/arc_guard_core/`. Wire the contract test suite, the import-graph linter, and the dependency-tree audit. Ship a deprecation shim in the old location that re-exports from the new module.
- **Batch B — Implementations**: `inspectors/`, `strategies/`, `flags/`, `reporters/`, `middleware/`, `pipeline.py`. Move into `packages/pip/src/arc_guard/`. Spec 001 tests come along. Wire the async-blocking lint and the deprecation shim's PEP 562 `__getattr__` for the old `arc_guard.*` import paths.
- **Batch C — Adapters**: `adapters/` (NATS, Unleash, OTEL exporters). Move into `packages/pip/src/arc_guard/adapters/` behind their existing extras. Confirm the import-graph rules forbid these from being reachable from `arc_guard_core`.

**Rationale**:
- Ordering by dependency direction (contracts → implementations → adapters) means each batch's destination is already populated with its imports' targets.
- Each batch ships with the deprecation shim so `python/arc-guardrails` callers never break in-flight.
- Three batches keeps PR sizes reviewable; one mega-PR would defeat the constitution's "merge-ready work must pass local quality checks" gate.

**Alternatives considered**:
- *Single big-bang move*: rejected — too risky given the constitution's no-implicit-rename rule.
- *Per-module micro-batches*: rejected — too much churn in `__init__.py` shims; deprecation table would oscillate.

---

## 12. `packages/api` scope in Spec 002

**Question**: How much of the API surface lands in Spec 002 vs Spec 007?

**Decision**: Scaffold-only in Spec 002. `packages/api/` exists with `pyproject.toml`, a `settings.py` skeleton, a placeholder module documenting the handoff, and a single smoke test that verifies the package installs and imports. No routes, no FastAPI app factory, no dependencies beyond `arc-guard` and `pydantic-settings`.

**Rationale**:
- The spec explicitly fences "API package wiring beyond a thin surface" out of scope and assigns it to Spec 007.
- Without the scaffold present, the workspace declaration in `packages/pyproject.toml` would be inconsistent.
- The smoke test ensures the layered import-graph rule actually exercises a real `arc_guard_service` consumer of `arc_guard`.

**Alternatives considered**:
- *Skip `packages/api/` until Spec 007*: rejected — the package boundary is part of FR-001 / FR-004 and must exist to be tested.
- *Land a full FastAPI app now*: rejected — silently absorbs Spec 007 and violates roadmap §10.

---

## Summary table

| Topic | Decision |
|---|---|
| 1 — Package names | `core` / `pip` / `api` (design names; roadmap mapping recorded) |
| 2 — Workspace tooling | `uv` workspace under `packages/` |
| 3 — `python/arc-common/` | Retire after Spec 002; do not fold into `core` |
| 4 — Validation library | `pydantic` v2 at boundaries, `dataclasses(frozen=True)` internally |
| 5 — Contract snapshot | Runtime JSON snapshot under `tests/contract/snapshots/` |
| 6 — Import-graph | `import-linter` + `tools/check_import_graph.py` |
| 7 — Async-blocking | `ruff` `ASYNC` rules + `tools/check_async_blocking.py` |
| 8 — Deprecation shim | PEP 562 `__getattr__` + central `_legacy.py` table |
| 9 — OTEL/logging hooks | Null-object protocol surface in `core/observability.py` |
| 10 — Adopt-vs-build check | `tools/check_adopt_vs_build.py` against `libraries.md` and ADRs |
| 11 — Migration sequencing | Three batches: contracts → implementations → adapters |
| 12 — `packages/api` scope | Scaffold only; Spec 007 owns full wiring |

All NEEDS CLARIFICATION items resolved. Phase 1 design proceeds.
