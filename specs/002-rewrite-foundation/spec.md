# Feature Specification: Rewrite Foundation — Package Split, Contracts, and Engineering Baseline

**Feature Branch**: `002-rewrite-foundation`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "USE REWRITE ROADMAP TO START SPEC 002"

## Roadmap Alignment *(mandatory for rewrite specs)*

- **Roadmap reference**: [`docs/superpowers/specs/2026-05-01-rewrite-roadmap.md`](../../docs/superpowers/specs/2026-05-01-rewrite-roadmap.md)
- **Restructure reference**: `docs/superpowers/specs/2026-04-20-packages-restructure-design.md`
- **Category**: foundation
- **Depends on**: Spec 001 (`001-arc-guard-rails`) — preserves its public guard contract and tests as migration source.
- **Naming reconciliation**: the rewrite roadmap §1.2 names the packages `common`/`core`/`api`, but the package restructure design names them `core`/`pip`/`api`. This spec adopts the design names: `core` (zero-dep contract layer), `pip` (batteries-included library), `api` (thin deployment surface). Mapping rationale and the resolved decision live in [`research.md` §1](./research.md).
- **Roadmap items closed by this spec**:
  - §1.1 Lock the rewrite boundary (codify scope as enterprise prompt/response guardrailing for external LLMs).
  - §1.2 Fix package boundaries before feature growth (resolved as `packages/core`, `packages/pip`, `packages/api`; see "Naming reconciliation" above).
  - §1.3 Preserve current code as migration source (move and refactor, do not rewrite from zero).
  - §1.6 Set engineering standards from day zero (Python 3.11+, ruff, pytest, mypy --strict, Protocol interfaces, typed models).
  - §1.7 Validate data at every boundary (configuration, API, pipeline, adapter junctions) — establishes the rule and the configuration/pipeline-contract junction; per-junction expansion lives in later specs.
  - §1.9 Reuse before build (adopt-vs-build review captured before any custom infrastructure is introduced).
- **Roadmap items partially seeded (handed to later specs)**:
  - §1.4 Define baseline pipeline → Spec 003 owns the four-stage flow; this spec only fixes the *contract types* the stages will consume and produce.
  - §1.8 OTEL, logging, exceptions, concurrency → this spec sets the *policy* (fail-open vs fail-closed exception classes, async vs blocking ownership, thread-safety expectations); Spec 004 owns the OTEL schema, span set, and runtime instrumentation.
  - §1.5 Evaluation harness → Spec 006.
  - §1.11 Documentation rewrite → walkthrough notes for foundation only; consolidation lives in Spec 007.
- **Items explicitly left for later specs**:
  - Sanitization, policy routing, risk-adaptive behavior, refusal envelope authoring, clarification path → Spec 003.
  - OTEL spans, metrics, runtime hardening → Spec 004.
  - Semantic intent lock, fidelity scoring, rehydration safety → Spec 005.
  - Jailbreak / deception / adversarial harness → Spec 006.
  - Additional transports, dashboards, packaging polish → Spec 007 / future backlog.

### Compatibility, Migration, and Enterprise Impact

- **Target module type**: foundation rewrite of the `arc-guardrails` Python library. New layout: `packages/core` (contract layer), `packages/pip` (batteries-included library), `packages/api` (thin deployment surface).
- **Usage modes affected**: SDK (primary). Sidecar / worker / gateway / batch / CLI inherit the same contracts but are not implemented in this spec.
- **Contract impact**: introduces stable, versioned contract types (`GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, `RefusalEnvelope`) in `core`. Public symbols re-exported from a single import surface; the Spec 001 surface is preserved as a compatibility shim until Spec 003 lands.
- **Migration impact**: existing callers continue to import from `arc_guard` during a deprecation window; the new namespace becomes the canonical surface. No silent string-replace renames — the migration is staged per the constitution's Governance section.
- **Enterprise impact**: install footprint shrinks (`core` is dependency-light); offline / air-gapped operation is preserved because no provider SDK becomes a runtime dependency of `core`.

## User Scenarios & Testing *(mandatory)*

> Audience note: this is a developer-facing foundation. "Users" here are library *integrators* (engineering teams adopting `arc-guardrails`) and *contributors* (developers extending the library). Each story describes an observable outcome at a package boundary, not an internal refactor.

### User Story 1 - Integrator installs `core` without provider dependencies (Priority: P1)

An enterprise Python team adopting `arc-guardrails` wants to depend on the guardrail decision logic without inheriting NATS, Unleash, OTEL exporters, or any large model runtime. They install the `core` distribution, build a guard pipeline, and run it in-process against synthetic input.

**Why this priority**: this is the foundation of platform-neutrality from the constitution (Generic-First Core, Adapter Isolation). Without it, every later spec will leak provider concerns into `core` and the constitution is violated.

**Independent Test**: install `core` into a fresh virtual environment with no extras; import the library; instantiate a pipeline with the default in-memory configuration; submit a benign input; receive a structured pass result. The test fails if any provider-specific module is imported transitively or if any extra dependency is required for that flow.

**Acceptance Scenarios**:

1. **Given** a clean environment with only `core` installed, **When** the integrator imports the library and runs a pass-through guard call, **Then** the call completes without ImportError and without loading any adapter, transport, or provider SDK.
2. **Given** a clean environment with only `core` installed, **When** the integrator runs the dependency-tree audit, **Then** no NATS, Unleash, presidio, transformer, or webhook dependency is reachable from `core`'s declared runtime requirements.
3. **Given** a clean environment, **When** the integrator opts into an adapter via the documented extra (e.g. `arc-guardrails[nats]`), **Then** the adapter is available behind its `Protocol` and `core` itself remains unchanged.

---

### User Story 2 - Contributor refactors a stage without breaking the public contract (Priority: P1)

A library contributor changes how an inspector is implemented inside `core`. The change must not alter the shape of `GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, or `RefusalEnvelope` consumed by integrators.

**Why this priority**: contracts are the load-bearing artifact of the rewrite. If they are not pinned and validated, every later spec inherits churn risk.

**Independent Test**: a contract test suite snapshots the public typed models and protocol signatures. Running it after any change inside `core` either passes (no public change) or fails with a clear diff and a required version-bump entry. The test fails if a public field is renamed, removed, or has its type narrowed without a changelog entry and a documented migration.

**Acceptance Scenarios**:

1. **Given** the contract test suite, **When** a contributor renames an internal helper, **Then** the suite passes with no change required.
2. **Given** the contract test suite, **When** a contributor adds a new optional field to `GuardResult`, **Then** the suite reports the additive change and requires a changelog entry but does not block (additive changes are allowed in minor versions).
3. **Given** the contract test suite, **When** a contributor renames a public field, **Then** the suite blocks the change and points at the migration policy.

---

### User Story 3 - Contributor relies on validated boundaries to refactor safely (Priority: P2)

A contributor moves a module between packages or replaces an internal implementation. They expect that any malformed configuration, request payload, or finding produced inside the pipeline is rejected at the nearest boundary with a typed error, not propagated as a silent dictionary.

**Why this priority**: validation at boundaries is the constitution's Security/Observability/Resilience principle in operational form. It enables Specs 003-007 to evolve without re-discovering data shape bugs.

**Independent Test**: feed a malformed configuration to the loader; feed a malformed request payload to the API boundary; feed a malformed `Finding` into the pipeline contract. Each must reject with a typed validation exception that names the offending field. The test fails if any malformed input is silently coerced or accepted.

**Acceptance Scenarios**:

1. **Given** a configuration file with a missing required field, **When** the loader runs, **Then** loading fails with a typed configuration-validation error that names the field and points at documentation.
2. **Given** a request crossing the API boundary with the wrong shape, **When** the boundary validates it, **Then** the request is rejected with a typed validation error before any pipeline stage executes.
3. **Given** a `Finding` produced internally with an out-of-range severity, **When** it crosses the pipeline contract, **Then** the contract layer raises a typed pipeline-validation error rather than propagating the value.

---

### User Story 4 - Library maintainer ships a deprecation cleanly (Priority: P2)

A maintainer needs to remove a public symbol that existed in Spec 001. The maintainer marks the symbol deprecated for one minor version, ships the change with a changelog entry, and removes it in the next minor version. Integrators who pinned the older version see no change; integrators who upgrade see a deprecation warning with a migration link before the removal.

**Why this priority**: the constitution forbids implicit string-replace renames. A working deprecation path is what makes the package split safe to ship without breaking Spec 001 callers.

**Independent Test**: deprecate one symbol; in the deprecation window, importing it logs a structured deprecation warning that names the replacement; in the removal release, importing it raises an ImportError with the same migration link. The test fails if either step is silent.

**Acceptance Scenarios**:

1. **Given** a deprecated symbol still exported, **When** an integrator imports it, **Then** they receive a deprecation warning that names the replacement and the removal version.
2. **Given** the removal release, **When** an integrator imports the removed symbol, **Then** they receive an ImportError that links to the migration note.
3. **Given** any deprecation, **When** the changelog is reviewed, **Then** the deprecation, replacement, and removal version are recorded.

---

### User Story 5 - Contributor adds a new dependency only after a recorded review (Priority: P3)

A contributor wants to introduce a new third-party library to solve a subsystem (e.g. validation, retries, logging adapter). Before the dependency is added, the contributor records an adopt-vs-build note that compares at least one strong open-source option against a custom build, and references the constitution's reuse-before-build rule.

**Why this priority**: this is the operational form of roadmap §1.9 and constitution principle V. It prevents the rewrite from accumulating bespoke infrastructure that later specs cannot replace.

**Independent Test**: a pre-merge check requires that any change adding a runtime dependency to `core` references an adopt-vs-build entry under `.specify/memory/libraries.md` or the spec's decisions directory. The test fails if a runtime dependency is added without that record.

**Acceptance Scenarios**:

1. **Given** a pull request that adds a runtime dependency to `core`, **When** the pre-merge check runs, **Then** it requires a referenced adopt-vs-build entry before merge.
2. **Given** a pull request that adds a development-only dependency, **When** the pre-merge check runs, **Then** it allows the change without requiring the same review depth (dev tooling is exempt by policy).

---

### Edge Cases

- A consumer pins a transitive dependency that conflicts with `core`'s declared range — the dependency-tree audit must surface the conflict at install time rather than at first use.
- A contributor moves a module across packages without updating re-exports — the contract test must fail before merge.
- A circular import is introduced between `pip` and `core` (or any other reversed layer dependency) — the import-graph check must fail before merge.
- A configuration value is valid in isolation but invalid given another value (cross-field rule) — validation must fail at load time with both fields named, not at first use.
- An exception is raised inside a pipeline stage during a *fail-open* code path — the policy must be honored: the user receives a typed bypass result that records the failure cause, not a raw stack trace.
- An exception is raised in a *fail-closed* code path — the policy must be honored: the user receives a typed refusal envelope, not a partial result.
- A blocking call is added to the async pipeline path — the concurrency policy check must catch the regression before merge.
- An adapter is imported from `core` by mistake — the import-graph check must fail before merge.
- The Spec 001 import path is used after the deprecation window — the import must raise ImportError with a migration link, not silently fall back.

## Requirements *(mandatory)*

### Functional Requirements

#### Package boundaries

- **FR-001**: The library MUST be split into three top-level packages — `core` (zero-dep contract layer), `pip` (batteries-included library), and `api` (thin deployment surface) — each with its own `pyproject.toml`, src layout, version, and changelog.
- **FR-002**: `core` MUST contain only the contract layer — typed models, `typing.Protocol` interfaces, the typed exception hierarchy, the configuration schema, the registry, the pipeline shape, and the observability hook surface. It MUST stay dependency-light (only `pydantic` and Python stdlib at install time) and MUST NOT import `pip` or `api`.
- **FR-003**: `pip` MUST contain all guardrail decision logic — concrete inspectors, strategies, reporters, flag providers, middleware, and adapters — built on top of `core`'s contract types. Its default install path MUST NOT require any provider SDK; provider integrations MUST live behind optional extras (FR-005).
- **FR-004**: `api` MUST be a thin deployment surface that consumes `core`'s contracts and `pip`'s implementations via their public Protocols. It MUST NOT contain guardrail decision logic.
- **FR-005**: Adapters (NATS, Unleash, OTEL exporters, webhook reporters, model-backed inspectors) MUST live in `pip` behind optional extras and remain importable only when the relevant extra is installed.
- **FR-006**: The library MUST provide an automated import-graph check that fails the build if `core` imports any module from `pip`, `api`, an adapter, a transport, or a provider SDK.

#### Migration from existing code

- **FR-007**: Existing code under `python/arc-guardrails/src/arc_guard/` MUST be moved into the new package layout in stages, with tests preserved as behavioral guardrails throughout.
- **FR-008**: The Spec 001 public import surface MUST continue to work for one minor version after the new namespace ships, with deprecation warnings naming each replacement.
- **FR-009**: A migration note MUST be published describing the mapping from each Spec 001 public symbol to its new home, with a worked example for the most common usage.

#### Contract layer

- **FR-010**: A versioned contract layer MUST define typed models for the inputs, outputs, and intermediate decisions that cross stage and adapter boundaries — at minimum `GuardInput`, `GuardResult`, `Finding`, `PolicyDecision`, and `RefusalEnvelope`.
- **FR-011**: Stage-to-stage and adapter-to-core boundaries MUST consume and produce these typed models; raw dictionaries crossing those boundaries MUST be rejected by the contract test suite.
- **FR-012**: Public-facing contracts MUST be documented with field-level descriptions, version annotations, and stability markers.
- **FR-013**: Public contracts and protocols MUST be covered by an automated contract test suite that detects renames, removals, and type narrowings and that requires a changelog entry for any additive change.

#### Protocol interfaces

- **FR-014**: Cross-package and cross-stage seams MUST be expressed as `typing.Protocol` interfaces, not concrete classes.
- **FR-015**: Each protocol MUST declare its method signatures, expected exceptions, and concurrency expectations (sync/async, thread-safety) explicitly in its docstring or a referenced design note.

#### Configuration and validation

- **FR-016**: Configuration MUST be validated at load time. Missing required fields, type mismatches, and cross-field violations MUST produce a typed configuration-validation error that names the offending field(s).
- **FR-017**: API request and response payloads MUST be validated at the API boundary before any pipeline work runs.
- **FR-018**: Internal pipeline contracts MUST validate `Finding` and `PolicyDecision` shapes before they cross stages.
- **FR-019**: Adapter inputs and outputs MUST be validated before and after any external call.
- **FR-020**: Configuration defaults MUST be product-neutral (no hard-coded provider names, NATS subjects, filesystem paths, or logger names that imply a specific platform).

#### Exception policy

- **FR-021**: A typed exception hierarchy MUST be defined with at minimum: configuration errors, validation errors (per boundary), pipeline errors, adapter errors, and refusal-envelope errors.
- **FR-022**: Each public stage and adapter MUST declare whether each failure mode is fail-open (continue with a recorded bypass) or fail-closed (terminate with a refusal envelope), and that declaration MUST be enforced by tests.
- **FR-023**: No internal exception type MUST leak across the public API boundary unwrapped; outward-facing failures MUST be expressed as typed result objects or documented public exceptions.

#### Concurrency policy

- **FR-024**: The library MUST document, per public stage, whether it is synchronous, asynchronous, or both.
- **FR-025**: Blocking model inference and other CPU-bound work MUST NOT run on the asyncio event loop; the policy MUST be enforced by an automated check on the async pipeline path.
- **FR-026**: Shared registries, caches, and adapter handles MUST declare their thread-safety contract in code (marker, docstring, or types) and MUST be exercised by at least one concurrent test.

#### Engineering baseline (standing rules, asserted here for the rewrite scope)

- **FR-027**: All packages MUST target Python 3.11 or later.
- **FR-028**: `ruff`, `pytest`, and `mypy --strict` MUST be wired into each package's quality gate and run on every change.
- **FR-029**: Each package MUST use `pyproject.toml`, `src/` layout, and `uv` for dependency management, consistent with the constitution's Enterprise Python Baseline.
- **FR-030**: Each package MUST publish a changelog entry for every public change.

#### Reuse before build

- **FR-031**: Any new runtime dependency added to `core` MUST be preceded by a recorded adopt-vs-build note that compares at least one credible open-source option against a custom build.
- **FR-032**: The adopt-vs-build note MUST be referenced from the change that adds the dependency and stored under `.specify/memory/libraries.md` or the spec's decisions directory.

#### Documentation

- **FR-033**: A walkthrough page MUST be published for the new package layout describing what lives where and why.
- **FR-034**: The spec, plan, and tasks artifacts MUST be kept aligned with the constitution and roadmap as the work progresses; the speckit context-update script MUST be run when the active plan introduces new technology or workflow context.
- **FR-035**: The migration note (FR-009) and the public contract reference MUST be discoverable from the package READMEs.

### Key Entities

- **`core` package** (`arc-guard-core`): zero-dep contract layer — typed models, Protocol interfaces, typed exception hierarchy, configuration schema, pipeline shape, and observability hook surface. Dependency-light (`pydantic` + stdlib only). Provider-neutral. Imported by both `pip` and `api`.
- **`pip` package** (`arc-guard`): batteries-included library — concrete inspectors, strategies, reporters, flag providers, middleware, and adapters. Depends on `core` plus optional extras for provider integrations. Holds the guardrail decision logic that follows in Spec 003.
- **`api` package** (`arc-guard-service`): thin deployment surface that consumes `core` Protocols and `pip` implementations. Holds no decision logic. Spec 002 ships only the scaffold; Spec 007 owns full wiring.
- **`GuardInput`**: typed model representing the request crossing into the pipeline. Carries content, mode (pre/post), correlation identifiers, and policy hints.
- **`GuardResult`**: typed model representing the pipeline outcome. Carries action, findings, decision rationale, and a refusal envelope when applicable.
- **`Finding`**: typed model representing a single detected concern (kind, span, severity, source detector). Crosses stage boundaries.
- **`PolicyDecision`**: typed model representing the chosen response for a finding (or set of findings). Carries strategy, severity, and explanation hooks.
- **`RefusalEnvelope`**: typed model returned when the system blocks or restricts. Carries trigger, policy reference, and next-step guidance, both machine- and human-readable.
- **Protocol surface**: `Guard`, `Inspector`, `Reporter`, `FlagProvider`, `ActionStrategy` — interfaces that adapters and stages implement. Concrete shapes evolve in later specs; signatures and exception expectations are fixed here.
- **Exception hierarchy**: typed exception classes covering configuration, boundary validation, pipeline, adapter, and refusal-envelope failures.
- **Adopt-vs-build record**: written note comparing at least one open-source option against a custom build for any new runtime dependency in `core`.

## Out of Scope *(mandatory for rewrite specs)*

The following are intentionally NOT delivered by this spec and MUST NOT be silently absorbed:

- Typed sanitization, composable policy routing, risk-adaptive behavior, graceful refusal authoring, clarification path, explainable decision records — these are Spec 003.
- OTEL span schema, structured logging schema, runtime hardening, full async / thread-safety implementation across stages — these are Spec 004.
- Semantic intent lock, intent fidelity score, rehydration safety checker — these are Spec 005.
- Stateful jailbreak and deception detection, adversarial corpora, comparative evaluation harness — these are Spec 006.
- API package wiring beyond a thin surface, integration notes, doc consolidation, future-transport backlog capture — these are Spec 007.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An integrator can install only `core` and run a benign pass-through guard call in a fresh environment in under five minutes, with zero adapter or provider SDK dependencies installed.
- **SC-002**: The dependency-tree audit for `core` shows zero NATS, Unleash, transport, model-backed, or webhook runtime dependencies.
- **SC-003**: The import-graph check fails any change that lets `core` import an adapter, a transport, or a provider SDK.
- **SC-004**: 100% of cross-stage and cross-adapter boundaries validated by the contract test suite consume and produce typed models; zero raw dictionaries cross those boundaries.
- **SC-005**: The contract test suite catches every public rename, removal, or type-narrowing change and requires a changelog entry for additive changes — verified by a deliberately mutated reference change set.
- **SC-006**: 100% of public stages and adapters declare their fail-open or fail-closed behavior, and an automated check fails any new public stage that omits the declaration.
- **SC-007**: 100% of public stages declare sync / async / both, and any blocking call introduced on the async pipeline path is caught before merge.
- **SC-008**: Every Spec 001 public symbol either remains importable with a deprecation warning naming its replacement, or is removed in a release that publishes a corresponding migration entry — verified by the contract test suite and changelog.
- **SC-009**: Every new runtime dependency added to `core` is traceable to a referenced adopt-vs-build record in `.specify/memory/libraries.md` or the spec's decisions directory.
- **SC-010**: All packages pass `ruff`, `pytest`, and `mypy --strict` as a gate on every change.
- **SC-011**: A walkthrough page describing the new package layout is published and discoverable from each package README before this spec is closed.

## Assumptions

- The package restructure design at `docs/superpowers/specs/2026-04-20-packages-restructure-design.md` defines the resolved package names: `core` (zero-dep contract layer), `pip` (batteries-included library), `api` (thin deployment surface). The mapping from the rewrite roadmap's `common`/`core`/`api` terminology to these names is documented in [`research.md` §1](./research.md). Any further renaming propagates to this spec; the *boundary rules* in this spec do not.
- The existing `arc-common` Python package is being retired (not folded into `core`). Per [`research.md` §3](./research.md), no module in `arc-common` is reused by `core`, and the retirement timing — Spec 002 or deferred to Spec 007 — is captured under `specs/002-rewrite-foundation/decisions/`.
- One minor version is a sufficient deprecation window for Spec 001 symbols. If integrators require longer, the window can be extended without changing the contract test suite.
- "Strict" `mypy` is achievable for the foundation surface. If a third-party dependency forces a localized escape hatch, it is recorded in the adopt-vs-build note for that dependency rather than relaxed library-wide.
- OTEL, structured logging, and metrics *hooks* are stubbed in `core` (no-op by default) so Spec 004 can wire them without re-shaping contracts. The hook surface is part of the contract layer; the schema and exporters are not.
- Offline / air-gapped operation remains a constitution-level constraint and does not require an extra requirement here; it follows from FR-003 and FR-005.

## Dependencies

- Spec 001 (`001-arc-guard-rails`) — its public guard contract and tests are the migration source for `core`.
- The package restructure design — defines the named layout that this spec operationalizes.
- The constitution at `.specify/memory/constitution.md` — every requirement here inherits its principles.
- `.specify/memory/patterns.md` and `.specify/memory/libraries.md` — patterns guide how the boundary rules are applied; libraries records the adopt-vs-build entries.
