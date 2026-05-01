---

description: "Task list for Spec 002 — Rewrite Foundation"
---

# Tasks: Rewrite Foundation — Package Split, Contracts, and Engineering Baseline

**Input**: Design documents from `/specs/002-rewrite-foundation/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included. Justification: the constitution (Principle IV) mandates `pytest` as a quality gate, and FR-013 / SC-005 require an automated contract test suite. The contract test suite is the load-bearing artifact of this spec — it is not optional.

**Organization**: Tasks are grouped by user story (from spec.md) so each story can be implemented and validated independently. Migration of implementation modules (inspectors, strategies, adapters) is split into a dedicated post-story phase because it does not gate any user story's independent test.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: maps to user stories — `[US1]` through `[US5]` from spec.md
- All paths absolute relative to repository root `/Users/dgtalbug/Workspace/arc/sdk/`

## Path Conventions

This is a multi-package Python `uv` workspace. New layout (per [plan.md](./plan.md) §"Project Structure"):

- `packages/core/src/arc_guard_core/` — zero-dep contracts
- `packages/pip/src/arc_guard/` — batteries-included library (Spec 001 import name preserved)
- `packages/api/src/arc_guard_service/` — thin deployment scaffold
- `packages/{core,pip,api}/tests/{unit,contract,integration,deprecation}/` — per-package tests
- `tools/` — repo-level boundary-enforcement scripts
- `docs/walkthrough/` — one-page walkthrough docs
- `python/arc-guardrails/` and `python/arc-common/` — legacy locations preserved during migration window

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Stand up the `packages/` `uv` workspace and per-package skeletons.

- [x] T001 Create directory `packages/` with workspace root `packages/pyproject.toml` declaring `[tool.uv.workspace]` members `["core", "pip", "api"]`
- [x] T002 [P] Create `packages/core/pyproject.toml` with name `arc-guard-core`, version `0.1.0`, runtime deps `["pydantic>=2.0"]`, Python `>=3.11`
- [x] T003 [P] Create `packages/pip/pyproject.toml` with name `arc-guard`, version `0.2.0`, runtime deps `["arc-guard-core", "presidio-analyzer>=2.2", "presidio-anonymizer>=2.2"]`, plus extras `[semantic]`, `[nats]`, `[unleash]`, `[webhook]`, `[otel]`, `[arc]` preserved from existing `python/arc-guardrails/pyproject.toml`
- [x] T004 [P] Create `packages/api/pyproject.toml` with name `arc-guard-service`, version `0.1.0`, runtime deps `["arc-guard", "pydantic-settings>=2.0"]`, optional extra `[fastapi]`
- [x] T005 [P] Add `[tool.ruff]`, `[tool.mypy]` (with `strict = true`), and `[tool.pytest.ini_options]` sections to all three package `pyproject.toml` files (FR-028)
- [x] T006 [P] Create empty `packages/core/src/arc_guard_core/__init__.py`, `packages/pip/src/arc_guard/__init__.py`, `packages/api/src/arc_guard_service/__init__.py`
- [x] T007 [P] Create `packages/core/CHANGELOG.md`, `packages/pip/CHANGELOG.md`, `packages/api/CHANGELOG.md` with the 0.1.0 / 0.2.0 / 0.1.0 initial entries
- [x] T008 [P] Create `packages/core/README.md`, `packages/pip/README.md`, `packages/api/README.md` linking to the spec, the migration note, and the contract reference (FR-035)
- [x] T009 [P] Create `packages/README.md` describing workspace layout and how to run `uv sync`, `uv run --package <name>`, and the boundary-enforcement scripts
- [x] T010 [P] Create empty test directories: `packages/core/tests/{unit,contract,integration}/`, `packages/pip/tests/{unit,integration,deprecation}/`, `packages/api/tests/`, each with `__init__.py`
- [x] T011 Run `uv sync` from `packages/` and verify the workspace resolves cleanly

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Cross-cutting infrastructure that every user story depends on — typed exception hierarchy, observability hook surface, and the registry of refusal codes. Without these, the contract types in US1 cannot land.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Exception hierarchy (FR-021, FR-022, FR-023)

- [x] T012 Create `packages/core/src/arc_guard_core/exceptions.py` with the base `ArcGuardError` and the second-level classes (`ConfigError`, `ValidationError`, `PipelineError`, `AdapterError`, `RefusalEnvelopeError`) per [contracts/exceptions.md](./contracts/exceptions.md)
- [x] T013 Add leaf exception classes to `packages/core/src/arc_guard_core/exceptions.py`: `ConfigSchemaError`, `ConfigCrossFieldError`, `ApiBoundaryValidationError`, `PipelineContractValidationError`, `AdapterBoundaryValidationError`, `InspectorError`, `StrategyError`, `PolicyRouterError`, `ReporterError`, `FlagProviderError`, `EntityProviderError` — each with `__failure_mode__` and `__valid_codes__` class-level attributes
- [x] T014 [P] Add unit tests in `packages/core/tests/unit/test_exceptions.py` asserting every leaf class has `__failure_mode__` set, `__valid_codes__` populated, and `__init__` validates `code in __valid_codes__`

### Observability hook surface (research §9, data-model §10)

- [x] T015 [P] Create `packages/core/src/arc_guard_core/observability.py` with `Tracer`, `Logger`, `MetricSink` Protocols and `NullTracer`, `NullLogger`, `NullMetricSink` no-op implementations
- [x] T016 [P] Add unit tests in `packages/core/tests/unit/test_observability.py` asserting null implementations satisfy each Protocol and `start_span` returns a usable context manager

### Refusal code registry

- [x] T017 [P] Create `packages/core/src/arc_guard_core/refusal/__init__.py` and `packages/core/src/arc_guard_core/refusal/codes.py` with `RefusalCode` `StrEnum` containing the initial code set (e.g. `JAILBREAK`, `PII_CRITICAL`, `STRATEGY_FAILED`, `FIDELITY_DROP_PLACEHOLDER`)
- [x] T018 [P] Add unit tests in `packages/core/tests/unit/test_refusal_codes.py` asserting every code is unique and addressable as `RefusalCode.<name>`

### Concurrency markers

- [x] T019 [P] Create `packages/core/src/arc_guard_core/concurrency.py` with marker dataclasses / typed-dict descriptions (`SyncOnly`, `AsyncOnly`, `SyncOrAsync`, `ThreadSafe`) used in protocol docstrings to annotate concurrency expectations

**Checkpoint**: Foundation modules are in place. User stories can now begin in parallel.

---

## Phase 3: User Story 1 — Integrator installs `core` without provider dependencies (Priority: P1) 🎯 MVP

**Goal**: An integrator can install only `arc-guard-core` from the workspace into a clean environment and run a benign pass-through guard call without pulling NATS, Unleash, OTEL, presidio, torch, or transformers.

**Independent Test**: Walkthrough A (`quickstart.md` §A.1–A.6) — install closure shows only `pydantic` and `arc-guard-core`; `pre_process_sync` returns `GuardResult(action="pass", is_clean=True, bypass_reason=None)`; `sys.modules` has no forbidden module loaded.

### Boundary enforcement tooling for US1

- [x] T020 [P] [US1] Create `tools/check_import_graph.py` — wraps `lint-imports` against `packages/.importlinter`; also asserts `arc_guard_core` runtime import does not load any forbidden module (FR-006)
- [x] T021 [P] [US1] Create `packages/.importlinter` with the rules from [contracts/package-boundaries.md](./contracts/package-boundaries.md)
- [x] T022 [P] [US1] Create `tools/check_dependency_tree.py` — runs `uv tree --package arc-guard-core` and asserts the runtime closure contains only `pydantic` and stdlib (SC-002)
- [x] T023 [P] [US1] Add `import-linter` to dev dependencies via the workspace `[tool.uv]` section
- [x] T024 [P] [US1] Add an adopt-vs-build entry for `import-linter` in `.specify/memory/libraries.md` referencing this spec (FR-031)
- [x] T025 [P] [US1] Create `tools/README.md` documenting all `check_*.py` scripts and how to run them

### Contract types for US1 (move + extend)

- [x] T026 [US1] Create `packages/core/src/arc_guard_core/types.py` by porting `python/arc-guardrails/src/arc_guard/types.py` and extending: add `correlation_id: str | None = None` to `GuardContext`, add `policy_hints: frozenset[str] = frozenset()` to `GuardInput`, add `decisions: tuple[PolicyDecision, ...] = ()`, `refusal: RefusalEnvelope | None = None`, `"tokenize"` literal to `GuardResult` (data-model §2, §3, §7)
- [x] T027 [US1] Add `PolicyDecision` and `RefusalEnvelope` frozen dataclasses to `packages/core/src/arc_guard_core/types.py` per data-model §5, §6
- [x] T028 [US1] Define `arc_guard_core.__all__` in `packages/core/src/arc_guard_core/__init__.py` re-exporting `RiskLevel`, `GuardContext`, `GuardInput`, `Finding`, `PolicyDecision`, `RefusalEnvelope`, `GuardResult`, `EntityDefinition` from `types`, `GuardConfig` from `config`, `RefusalCode` from `refusal.codes`, plus the seven core protocols and the observability hooks
- [x] T029 [P] [US1] Add `packages/core/src/arc_guard_core/protocols/__init__.py` and per-protocol files (`guard.py`, `inspector.py`, `strategy.py`, `reporter.py`, `flag_provider.py`, `middleware.py`, `entity_provider.py`) ported from `python/arc-guardrails/src/arc_guard/protocols/`, with docstrings extended to declare sync/async, declared exceptions, thread-safety, and fail-open/closed mode per [contracts/protocols.md](./contracts/protocols.md). Update all internal imports from `arc_guard.types` / `arc_guard.config` etc. to `arc_guard_core.types` / `arc_guard_core.config`.
- [x] T030 [US1] Create `packages/core/src/arc_guard_core/config.py` with `GuardConfig` pydantic v2 `BaseModel` (`frozen=True`, `extra='forbid'`) per data-model §9 — fields: `enabled`, `lite_mode`, `inspector_order`, `policy_hints_default`, `tracer`, `logger`, `metrics`
- [x] T031 [P] [US1] Create `packages/core/src/arc_guard_core/registry.py` by porting `python/arc-guardrails/src/arc_guard/registry.py` (`EntityRegistry`, thread-safe in-memory)
- [x] T032 [US1] Create `packages/core/src/arc_guard_core/pipeline.py` with `GuardPipeline` shape (no provider SDK imports — only `arc_guard_core.*` modules and `pydantic` are permitted) — accepts `GuardConfig`, exposes `pre_process`, `post_process`, `pre_process_sync`, `post_process_sync`; with no inspectors registered, all four entry points return a `GuardResult(action="pass", text=input.text)` (data-model §11)

### Tests for US1

- [x] T033 [P] [US1] Add unit tests in `packages/core/tests/unit/test_types.py` covering `RiskLevel` ordering, `GuardContext` with/without `correlation_id`, `GuardInput` with `policy_hints`, `Finding.span` property, `GuardResult.is_clean` and `max_risk` properties, `PolicyDecision` and `RefusalEnvelope` construction
- [x] T034 [P] [US1] Add unit tests in `packages/core/tests/unit/test_pipeline_shape.py` exercising the empty-inspector pass-through, the `bypass_reason="disabled"` path when `enabled=False`, and immutability of returned `GuardResult`
- [x] T035 [P] [US1] Add unit tests in `packages/core/tests/unit/test_registry.py` covering registration and retrieval of `EntityDefinition`, plus a *concurrent-execution* test using `concurrent.futures.ThreadPoolExecutor` (≥4 workers) that registers and reads entries concurrently and asserts no lost updates (FR-026)
- [x] T036 [P] [US1] Add an install-closure test in `packages/core/tests/integration/test_install_closure.py` that imports `arc_guard_core` and asserts `set(sys.modules) & {"presidio_analyzer", "nats", "UnleashClient", "httpx", "opentelemetry", "torch", "transformers"} == set()` (US1 acceptance scenario 1)
- [x] T037 [US1] Run `tools/check_import_graph.py` and `tools/check_dependency_tree.py` against the workspace; both must pass before this phase closes (US1 acceptance scenarios 2 and 3)

**Checkpoint**: User Story 1 is fully functional. `arc-guard-core` installs cleanly with only `pydantic`; the empty pipeline runs; the import-graph and dependency-tree audits pass.

---

## Phase 4: User Story 2 — Contributor refactors a stage without breaking the public contract (Priority: P1)

**Goal**: A contract test suite snapshots the public typed models and protocol signatures and detects every rename, removal, type narrowing, and additive change, requiring CHANGELOG entries for additive changes and blocking breaking changes.

**Independent Test**: Walkthrough B §B.2–B.5 — internal renames pass; additive optional fields fail with a CHANGELOG-required message; breaking renames fail with a deprecation-required message.

### Snapshot generator and diff

- [x] T038 [P] [US2] Create `packages/core/tests/contract/_snapshot.py` with a `build_snapshot()` function that walks `arc_guard_core.__all__`, introspects each entry, and produces the JSON shape documented in [contracts/public-types.md](./contracts/public-types.md) §"Snapshot schema"
- [x] T039 [P] [US2] Extend `_snapshot.py` to introspect Protocol classes per [contracts/protocols.md](./contracts/protocols.md) §"Snapshot format" — capture each method's signature, async flag, declared exceptions, and the protocol's thread-safety and failure-mode markers
- [x] T040 [P] [US2] Extend `_snapshot.py` to introspect the exception hierarchy per [contracts/exceptions.md](./contracts/exceptions.md) §"Snapshot format" — capture parent class, `__failure_mode__`, and `__valid_codes__`
- [x] T041 [US2] Add `_snapshot.diff(old, new)` returning a structured list of (kind, name, detail) tuples that the test asserts against
- [x] T042 [US2] Generate the baseline snapshots and store them as `packages/core/tests/contract/snapshots/public_types.json`, `protocols.json`, `exceptions.json`

### Contract tests

- [x] T043 [US2] Add `packages/core/tests/contract/test_public_surface_snapshot.py` that runs `build_snapshot()` and asserts no diff against the baseline; on additive changes (new optional field, new exception subclass, etc.), assert that `packages/core/CHANGELOG.md` has been touched in the same commit (use `git diff --name-only HEAD~1` or the `pytest --update-snapshot` flag)
- [x] T044 [US2] Add `packages/core/tests/contract/test_protocol_signatures.py` covering rename, removal, async-flip, signature-change, and thread-safety-weakening cases. Also assert every Protocol's docstring contains a `Concurrency:` line declaring sync/async/both, mirroring the failure-mode assertion in T062 (FR-024, SC-007)
- [x] T045 [US2] Add `packages/core/tests/contract/test_failure_modes.py` covering exception-class-level changes per the diff rules in `contracts/exceptions.md`
- [x] T046 [US2] Add a deliberate-mutation test fixture in `packages/core/tests/contract/test_diff_examples.py` that mutates copies of the snapshot and asserts each diff kind is detected (SC-005)
- [x] T047 [P] [US2] Add a `--update-snapshot` flag to the snapshot test invocation (e.g. via `pytest --update-snapshot`) for legitimate additive changes; document it in `tools/README.md`

**Checkpoint**: User Story 2 is fully functional. The contract test suite blocks every breaking change, requires CHANGELOG entries for additive changes, and lets internal refactors through.

---

## Phase 5: User Story 3 — Contributor relies on validated boundaries (Priority: P2)

**Goal**: Configuration, API requests, pipeline contracts, and adapter inputs/outputs all reject malformed data with a typed validation error that names the offending field. Async pipeline paths fail the lint when blocking calls are introduced.

**Independent Test**: Walkthrough B §B.6–B.8 — malformed config raises `ConfigSchemaError` with field name; malformed API payload raises `ApiBoundaryValidationError`; out-of-range `Finding` raises `PipelineContractValidationError`. `tools/check_async_blocking.py` flags a deliberately blocking call.

### Configuration validation

- [x] T048 [US3] Extend `packages/core/src/arc_guard_core/config.py` `GuardConfig` with cross-field validators (e.g. `inspector_order` names must be registered) raising `ConfigCrossFieldError` (FR-016)
- [x] T049 [P] [US3] Add unit tests in `packages/core/tests/unit/test_config_validation.py` for: unknown-field rejection (`extra='forbid'`), wrong-type rejection, cross-field violations, and the error messages naming the offending fields

### Pipeline contract validators

- [x] T050 [US3] Add `_validate_finding(f: Finding) -> None` and `_validate_decision(d: PolicyDecision) -> None` helpers to `packages/core/src/arc_guard_core/pipeline.py`, raising `PipelineContractValidationError` with the offending field in `details` (FR-018)
- [x] T051 [P] [US3] Add unit tests in `packages/core/tests/unit/test_pipeline_validation.py` covering invalid spans (`end <= start`), out-of-range scores, missing inspector name, and out-of-range `RiskLevel`

### API boundary validation (scaffold)

- [x] T052 [P] [US3] Create `packages/api/src/arc_guard_service/settings.py` with a minimal pydantic-settings model (placeholder) that loads from env
- [x] T053 [P] [US3] Create `packages/api/src/arc_guard_service/_placeholder.py` documenting the Spec 007 handoff per research §12
- [x] T054 [US3] Create `packages/api/src/arc_guard_service/validators.py` with `validate_request_payload(payload: Mapping[str, Any]) -> GuardInput` raising `ApiBoundaryValidationError` on shape mismatch (FR-017)
- [x] T055 [P] [US3] Add unit tests in `packages/api/tests/test_request_validation.py` for malformed payloads — wrong types, missing required keys, extra unknown keys
- [x] T056 [P] [US3] Add a smoke test in `packages/api/tests/test_package_imports.py` that imports `arc_guard_service` and asserts the package loads without provider deps reachable beyond what `arc-guard` already pulls (research §12)

### Adapter boundary validation

- [x] T057 [P] [US3] Add `validate_adapter_input` / `validate_adapter_output` helpers in `packages/core/src/arc_guard_core/_adapter_contract.py` raising `AdapterBoundaryValidationError` (FR-019)
- [x] T058 [P] [US3] Add unit tests in `packages/core/tests/unit/test_adapter_contract.py` covering both directions

### Concurrency policy enforcement

- [x] T059 [P] [US3] Create `tools/check_async_blocking.py` per research §7 — combines ruff `ASYNC` rule output with a small AST walker that flags blocking calls into `time`, `subprocess`, `socket`, `presidio_analyzer.AnalyzerEngine.analyze`, and `transformers.pipeline.__call__` from any function reachable from `Guard.pre_process` / `Guard.post_process` (FR-025, SC-007)
- [x] T060 [P] [US3] Enable ruff `ASYNC` rule family in each package's `[tool.ruff.lint]` config
- [x] T061 [P] [US3] Add a regression test fixture in `packages/core/tests/contract/test_async_blocking.py` that runs `tools/check_async_blocking.py` against a deliberately-blocking sample async function and asserts it is flagged

### Public-stage failure-mode declarations

- [x] T062 [US3] Add `packages/core/tests/contract/test_failure_mode_declarations.py` asserting every public stage (`Guard`, `Inspector`, `ActionStrategy`, `Reporter`, `FlagProvider`, `Middleware`, `EntityProvider`) has its declared exceptions present in the hierarchy and matching `__failure_mode__` (FR-022, SC-006)

### Product-neutral defaults (FR-020)

- [x] T101 [P] [US3] Add `packages/core/tests/unit/test_config_defaults_neutrality.py` asserting `GuardConfig()` defaults contain no hard-coded provider names (`nats`, `unleash`, `presidio`, `arc`, etc.), no NATS subjects (`arc.ai.*`), no platform-specific filesystem paths (`/var/`, `~/Library`, `C:\\`), and no logger names that imply a specific platform (FR-020). Walk every default field value via `model_dump()` and run a substring/regex blocklist.

### No internal exception leaks at the public boundary (FR-023)

- [x] T102 [US3] Add `packages/core/tests/contract/test_no_unwrapped_leaks.py` that, for every leaf exception class in the hierarchy, injects a raise into each documented `Guard` call site (via monkeypatched stages and adapters) and asserts the public method returns a `GuardResult` (with `bypass_reason` for fail-open or `refusal` populated for fail-closed) — no exception escapes unwrapped (FR-023, complements [contracts/exceptions.md](./contracts/exceptions.md) §"No leak rule")

**Checkpoint**: User Story 3 is fully functional. Every documented boundary rejects malformed data with a typed error; the async-blocking lint catches regressions; failure-mode declarations are enforced; defaults are product-neutral; no internal exceptions leak across the public API.

---

## Phase 6: User Story 4 — Library maintainer ships a deprecation cleanly (Priority: P2)

**Goal**: Every Spec 001 public symbol stays importable through `packages/pip/src/arc_guard/` for one minor version with a `DeprecationWarning` naming the replacement and removal version. Current public names produce no warning. The migration note documents the mapping.

**Independent Test**: Walkthrough A §A.7 — importing `arc_guard.types.GuardResult` emits a `DeprecationWarning` whose message contains `"moved to arc_guard_core.types.GuardResult"` and `"removed in arc-guard 0.3.0"`. Current paths (`arc_guard_core.types.GuardResult`) produce no warning.

### Legacy table and shim

- [x] T063 [US4] Create `packages/pip/src/arc_guard/_legacy.py` with `LEGACY_SYMBOLS: dict[str, LegacyEntry]` populated from [contracts/deprecation-policy.md](./contracts/deprecation-policy.md) §"Symbol mapping" — each entry holds `new_module`, `new_name`, `removed_in`, optional `note_url`
- [x] T064 [US4] Implement PEP 562 `__getattr__` in `packages/pip/src/arc_guard/__init__.py` that consults `_legacy.LEGACY_SYMBOLS`, emits `warnings.warn(..., DeprecationWarning, stacklevel=2)` with the documented message format, and returns the resolved attribute from `arc_guard_core`
- [x] T065 [P] [US4] Add identical PEP 562 `__getattr__` shims in `packages/pip/src/arc_guard/types.py`, `packages/pip/src/arc_guard/protocols/__init__.py`, `packages/pip/src/arc_guard/config.py`, `packages/pip/src/arc_guard/registry.py` — these submodules forward to `arc_guard_core` while preserving the Spec 001 import paths

### Migration note

- [x] T066 [P] [US4] Create `docs/walkthrough/002-rewrite-foundation.md` with a "Migration" section listing every Spec 001 symbol → new home, the deprecation timeline, and a worked example for the most common usage (FR-009, FR-033)
- [x] T067 [P] [US4] Update `packages/pip/README.md` and `packages/core/README.md` to link to the migration section (FR-035)

### Tests for US4

- [x] T068 [P] [US4] Add `packages/pip/tests/deprecation/test_legacy_imports.py` that for every entry in `LEGACY_SYMBOLS` imports the old path under `warnings.catch_warnings(record=True)`, asserts a `DeprecationWarning` is raised, and asserts the message contains the new module name and removal version
- [x] T069 [P] [US4] Add `packages/pip/tests/deprecation/test_no_warning_on_current_paths.py` that runs with `warnings.simplefilter("error")` and imports the canonical `arc_guard_core.*` paths, asserting no warning fires
- [x] T070 [P] [US4] Add `packages/pip/tests/deprecation/test_post_removal.py` (parametrized) that simulates the removal release by bumping `LEGACY_SYMBOLS` `removed_in` to the current version and asserts `ImportError` with the migration link is raised
- [x] T071 [P] [US4] Add `packages/pip/tests/deprecation/test_changelog_records_removal.py` asserting any deprecation entry has a corresponding line in `packages/pip/CHANGELOG.md` (US4 acceptance scenario 3)

**Checkpoint**: User Story 4 is fully functional. Spec 001 imports continue to work with deprecation warnings; current paths are warning-free; the migration note is published.

---

## Phase 7: User Story 5 — Contributor adds a new dependency only after a recorded review (Priority: P3)

**Goal**: A pre-merge check requires every newly added runtime dependency in `arc-guard-core` to be referenced from an adopt-vs-build entry under `.specify/memory/libraries.md` or `specs/002-rewrite-foundation/decisions/`. Dev-only deps are exempt.

**Independent Test**: Walkthrough B §B.9 — adding `httpx` to `packages/core/pyproject.toml` without an entry fails the check; reverting passes; adding the entry also passes.

### Decisions directory and check script

- [x] T072 [P] [US5] Create `specs/002-rewrite-foundation/decisions/` with a `README.md` documenting the ADR template (front-matter must name the dependency)
- [x] T073 [US5] Create `tools/check_adopt_vs_build.py` per research §10 — diffs `packages/core/pyproject.toml` runtime deps against the merge-base, requires every new entry to be referenced from `.specify/memory/libraries.md` or `specs/002-rewrite-foundation/decisions/*.md` (FR-031, FR-032)
- [x] T074 [P] [US5] Update `tools/README.md` documenting the check, including the dev-deps-exempt rule (FR-031 acceptance scenario 2)

### Tests for US5

- [x] T075 [P] [US5] Add `tools/tests/test_check_adopt_vs_build.py` with fixtures: (a) PR adds a new runtime dep without a referenced entry → fails, (b) PR adds a new runtime dep with a `libraries.md` entry → passes, (c) PR adds a new runtime dep with a referenced ADR → passes, (d) PR adds only a dev dep → passes (US5 acceptance scenarios 1 and 2)

**Checkpoint**: User Story 5 is fully functional. New `core` runtime deps cannot land without a recorded review.

---

## Phase 8: Implementation Migration (Batch B + C)

**Purpose**: Move the existing implementation modules (inspectors, strategies, reporters, flags, adapters, middleware, pipeline) from `python/arc-guardrails/src/arc_guard/` into `packages/pip/src/arc_guard/`, preserving Spec 001 import paths and tests. This closes the FR-007 work that no single user story strictly requires for its independent test, but which the rewrite foundation must complete before Spec 003 starts.

**Note**: this phase has no `[Story]` label because it is cross-cutting cleanup of the existing codebase. It depends on Phases 3, 4, and 6 being complete.

### Batch B — implementations

- [x] T076 Move `python/arc-guardrails/src/arc_guard/inspectors/` to `packages/pip/src/arc_guard/inspectors/` via `git mv`; update internal imports from `arc_guard.types` etc. to import from `arc_guard_core.types` (the public re-export still resolves)
- [x] T077 [P] Move `python/arc-guardrails/src/arc_guard/strategies/` to `packages/pip/src/arc_guard/strategies/`
- [x] T078 [P] Move `python/arc-guardrails/src/arc_guard/reporters/` to `packages/pip/src/arc_guard/reporters/`
- [x] T079 [P] Move `python/arc-guardrails/src/arc_guard/flags/` to `packages/pip/src/arc_guard/flags/`
- [x] T080 [P] Move `python/arc-guardrails/src/arc_guard/middleware/` to `packages/pip/src/arc_guard/middleware/`
- [x] T081 Move `python/arc-guardrails/src/arc_guard/pipeline.py` (the implementation, with inspector chain) to `packages/pip/src/arc_guard/pipeline.py`, importing `GuardPipeline` shape from `arc_guard_core.pipeline` and extending it with the runtime inspector chain
- [x] T082 [P] Move `python/arc-guardrails/src/arc_guard/config.py` (env hydration) to `packages/pip/src/arc_guard/config_env.py`; update `arc_guard.config` to be a deprecation shim per Phase 6

### Batch C — adapters

- [x] T083 [P] Move `python/arc-guardrails/src/arc_guard/adapters/` to `packages/pip/src/arc_guard/adapters/`; verify `tools/check_import_graph.py` still passes (adapters reachable only from `arc_guard.adapters`, never from `arc_guard_core`)
- [x] T103 [P] Add `packages/pip/tests/integration/test_extras_gating.py` that, in a clean venv with `arc-guard` installed without extras, verifies importing each adapter (`arc_guard.adapters.nats_reporter`, `arc_guard.adapters.unleash_provider`, etc.) raises `ModuleNotFoundError` with a hint message naming the matching extra to install (FR-005)

### Test migration

- [x] T084 Move `python/arc-guardrails/tests/` to the appropriate `packages/pip/tests/{unit,integration}/` subdirectories, preserving the existing test names; update test imports
- [x] T085 Verify `cd packages/pip && uv run pytest` passes against the migrated tests

### Decommission the old location

- [x] T086 Remove the now-empty `python/arc-guardrails/src/arc_guard/` modules (the deprecation shims live in `packages/pip/src/arc_guard/` instead). Keep `python/arc-guardrails/pyproject.toml` and a top-level deprecation README pointing to `packages/pip/`
- [x] T087 Add a CHANGELOG entry to `packages/pip/CHANGELOG.md` recording the migration of each module group

**Checkpoint**: All Spec 001 implementation modules now live in `packages/pip/`. The legacy `python/arc-guardrails/` is decommissioned to a stub README. All tests still pass.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Walkthrough doc finalization, README cross-links, retirement decision for `arc-common`, and a final dry-run of the quickstart.

- [x] T088 [P] Finalize `docs/walkthrough/002-rewrite-foundation.md` — add the architecture diagram, the package-boundary table, and the "what's next" pointer to Spec 003 (FR-033)
- [x] T089 [P] Update repo-root `README.md` (and `python/README.md` if present) to link to `packages/README.md` and the walkthrough
- [x] T090 [P] Verify the `import-linter` adopt-vs-build entry added by T024 is present and complete in `.specify/memory/libraries.md` (audit-only; no second add)
- [x] T091 [P] Add a one-line entry to `.specify/memory/patterns.md` cross-referencing this spec as the reference for "package split" patterns
- [x] T092 Update `specs/index.md` Spec 002 row to status `In Progress` while tasks run, then `Done` when this phase closes
- [x] T093 Decide and record the `python/arc-common/` retirement plan per research §3 — if retiring in Spec 002, add a deprecation README; if deferring to Spec 007, add a backlog entry under `specs/002-rewrite-foundation/decisions/arc-common-retirement.md`
- [x] T094 [P] Run `cd packages/core && uv run ruff check src tests`, `uv run mypy src --strict`, `uv run pytest` — all green
- [x] T095 [P] Run `cd packages/pip && uv run ruff check src tests`, `uv run mypy src --strict`, `uv run pytest` — all green
- [x] T096 [P] Run `cd packages/api && uv run ruff check src tests`, `uv run mypy src --strict`, `uv run pytest` — all green
- [x] T097 Run all `tools/check_*.py` scripts end-to-end against the workspace and confirm zero regressions
- [ ] T098 Execute `quickstart.md` Walkthrough A end-to-end in a clean venv; confirm every step's expected output
- [ ] T099 Execute `quickstart.md` Walkthrough B end-to-end against the workspace; confirm every step's expected output
- [x] T100 Run `.specify/scripts/bash/update-agent-context.sh claude` once more so `CLAUDE.md` reflects the final package layout (research §1 mapping)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; can start immediately
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks** all user-story phases
- **Phase 3 (US1)**: depends on Phase 2
- **Phase 4 (US2)**: depends on Phase 3 (snapshot needs the public surface to exist)
- **Phase 5 (US3)**: depends on Phase 2 (and Phase 3 for `GuardConfig` and pipeline-helper hook points; in practice run after US1)
- **Phase 6 (US4)**: depends on Phase 3 (the canonical types must exist in `core` before the legacy table can point to them)
- **Phase 7 (US5)**: depends on Phase 2 only (the check script is independent of the core types)
- **Phase 8 (Migration)**: depends on Phase 3, 4, and 6 (types in `core`, contract suite green, deprecation shim live)
- **Phase 9 (Polish)**: depends on all earlier phases

### User Story Dependencies

- **US1 (P1)**: independent of US2-5; gates Phase 8 indirectly via the package layout
- **US2 (P1)**: depends on US1's public surface existing; otherwise independent
- **US3 (P2)**: independent of US2/US4; can run in parallel with them after US1
- **US4 (P2)**: depends on US1 (canonical types in `core`)
- **US5 (P3)**: independent of US1-4; can run in parallel with any of them after Phase 2

### Within Each User Story

- For US1, US3: tests for new modules are added in the same phase as the modules; running pytest on each commit catches regressions immediately
- For US2: the snapshot generator + diff are built before the contract tests are wired
- For US4: `_legacy.py` table is populated before the PEP 562 shim is wired
- For US5: the decisions/ scaffolding lands before the check script

### Parallel Opportunities

- **All Phase 1 setup tasks** (T002–T010) can run in parallel after T001 lands
- **All Phase 2 foundational tasks** (T012, T015, T017, T019) can run in parallel
- **Within US1**: T020-T025 (tooling) and T026-T032 (contract types) are two independent tracks. Within the second track, T029 (protocols), T031 (registry) can run in parallel with T026-T028; T030 depends on T026/T027 only via type imports
- **Within US3**: T048-T051 (config + pipeline validators), T052-T056 (api scaffold + boundary validators), T057-T058 (adapter validators), T059-T061 (async-blocking lint) are four independent tracks
- **Within US4**: T063-T065 (shim) and T068-T071 (tests) become parallel once the legacy table exists; T066-T067 (docs) can run in parallel with both
- **Phase 8 Batch B**: T077-T080 are independent module moves; T076 sets the pattern, then T077-T080 run in parallel; T082 is independent of all
- **Phase 9**: T088-T097 are mostly parallel after T088 completes

---

## Parallel Example: User Story 1

```bash
# After Phase 2 closes, kick these tasks off in parallel:

# Track A — boundary tooling
Task: "Create tools/check_import_graph.py"           # T020
Task: "Create packages/.importlinter"                # T021
Task: "Create tools/check_dependency_tree.py"        # T022

# Track B — contract types and protocols
Task: "Port types.py to packages/core/src/arc_guard_core/types.py with new fields"  # T026
Task: "Port protocols/ to packages/core/src/arc_guard_core/protocols/"               # T029
Task: "Port registry.py to packages/core/src/arc_guard_core/registry.py"             # T031

# Track C — tests (after Track B lands)
Task: "Unit tests for types"                         # T033
Task: "Unit tests for pipeline shape"                # T034
Task: "Unit tests for registry"                      # T035
Task: "Install-closure integration test"             # T036
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run Walkthrough A from `quickstart.md`. Confirm `arc-guard-core` installs in a clean venv with only `pydantic`, the empty pipeline runs, and the import-graph and dependency-tree audits pass.
5. Tag `arc-guard-core 0.1.0` if shipping.

### Incremental Delivery

1. **Setup + Foundational** → workspace in place
2. **Add US1** → `core` installable + clean → run Walkthrough A → MVP
3. **Add US2** → contract test suite live → refactor safety → ship `arc-guard-core 0.1.1` if any additive changes happened
4. **Add US3** → boundary validation → test malformed config / payloads / findings
5. **Add US4** → deprecation shim → run Walkthrough A §A.7
6. **Add US5** → adopt-vs-build check
7. **Phase 8** → migrate inspectors/strategies/adapters into `packages/pip/`
8. **Phase 9** → polish, walkthrough, retire `python/arc-common/`

### Parallel Team Strategy

Once Phase 2 closes:

- **Developer A**: US1 (P1) — package layout and core extraction
- **Developer B**: US2 (P1) — contract snapshot suite (can start once US1 has the public surface stub)
- **Developer C**: US5 (P3) — adopt-vs-build check (independent)
- After US1 closes:
  - **Developer A**: US4 (P2) — deprecation shim
  - **Developer B**: US3 (P2) — boundary validation
- Phase 8 (migration) is a coordinated sequence that needs all three developers to merge their stories first.

---

## Notes

- `[P]` tasks touch different files and have no dependency on other incomplete `[P]` tasks within the same phase. Verify before launching.
- `[Story]` label maps each task to its user story for traceability against `spec.md`.
- Tests are present because the constitution mandates them and FR-013 / SC-005 require the contract suite. The contract suite is *the* verification artifact for this spec; do not skip it.
- Verify each test fails before its target module is implemented (TDD discipline) where the test has a clear failure-to-success transition (US2 contract suite, US3 validators, US4 shim, US5 check).
- Commit at every checkpoint. Each phase ends in a coherent, testable state.
- After every module move in Phase 8, re-run `tools/check_import_graph.py` — silent boundary regressions are the highest-cost defect class for this spec.
- If a task discovers a contradiction with the spec or plan, stop and update the spec/plan first, per roadmap §10 ("if a task appears during planning and is not clearly mapped to a current spec, add it back into the roadmap before starting work").
