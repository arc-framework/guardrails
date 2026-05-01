---

description: "Task list for Spec 003 — Sanitization and Policy Core"
---

# Tasks: Sanitization and Policy Core

**Input**: Design documents from `/specs/003-sanitization-policy-core/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Test tasks ARE included. Justification inherited from Spec 002 — the constitution (Principle IV) mandates `pytest`, FR-013 / FR-024 / FR-034 require automated contract test coverage of all new public types, and FR-023 requires an automated no-raw-payload audit. Tests are not optional.

**Organization**: Tasks are grouped by user story (from spec.md) so each story can be implemented and validated independently. Spec 002's contract test suite is extended (not replaced) — additive snapshot updates land alongside the new public types.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: parallelizable (different files, no dependency on incomplete tasks)
- **[Story]**: maps to user stories — `[US1]` through `[US7]` from spec.md
- All paths are relative to repository root `/Users/dgtalbug/Workspace/arc/sdk/`

## Path conventions

The `packages/{core,pip,api}` workspace established by Spec 002 is unchanged. Spec 003 adds modules:

- `packages/core/src/arc_guard_core/` — new contract types (additive)
- `packages/core/tests/{unit,contract}/` — new tests for the additive surface
- `packages/pip/src/arc_guard/` — new implementation modules (`policy/`, `refusal/`, `decision/`) and updates to `strategies/` and `pipeline.py`
- `packages/pip/tests/{unit,integration}/` — new tests for routing, strategies, decision emission, walkthrough validation

---

## Phase 1: Setup

**Purpose**: version bumps, new directory skeletons, CHANGELOG headers. Spec 002 already established the workspace; nothing structural is created.

- [ ] T001 Bump `packages/core/pyproject.toml` version `0.1.0` → `0.2.0` (additive contract change for Spec 003)
- [ ] T002 Bump `packages/pip/pyproject.toml` version `0.2.0` → `0.3.0` (Spec 001 deprecation removal release coordinated with Spec 003 router landing)
- [ ] T003 [P] Add Spec 003 changelog stub block to `packages/core/CHANGELOG.md` under a new `## [0.2.0] — 2026-05-01` section with empty `### Added` / `### Changed` lists; subsequent tasks fill them in
- [ ] T004 [P] Add Spec 003 changelog stub block to `packages/pip/CHANGELOG.md` under a new `## [0.3.0] — 2026-05-01` section
- [ ] T005 [P] Create new directories: `packages/core/src/arc_guard_core/refusal/` (already exists from Spec 002 — verify), `packages/pip/src/arc_guard/policy/`, `packages/pip/src/arc_guard/refusal/`, `packages/pip/src/arc_guard/decision/`. Create empty `__init__.py` in each new directory.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: cross-cutting infrastructure every user story depends on — new typed models in `core`, the new Protocol, the strategy registry, and the contract snapshot baseline updates. Without these, no user story can land cleanly.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### Core typed models — additive contract surface (data-model §1–§7, §9–§12)

- [ ] T006 Add `ClarificationRequest` frozen dataclass to `packages/core/src/arc_guard_core/types.py` with fields `suggested_rephrase: str`, `next_steps: tuple[str, ...]`, `triggering_rule_id: str | None`, `metadata: dict[str, Any]` per data-model §2. Update `__all__`.
- [ ] T007 Add `GuardResult.clarification: ClarificationRequest | None` field with default `None` to `packages/core/src/arc_guard_core/types.py`. Add a contract invariant in the dataclass: `clarification` may be set only when `action != "block"`.
- [ ] T008 [P] Create `packages/core/src/arc_guard_core/policy.py` containing `RiskBand` (StrEnum), `RiskThresholds` (pydantic, frozen, extra='forbid'), `PolicyRule` (pydantic, frozen, extra='forbid'), `PolicyRuleSet` (pydantic, frozen, extra='forbid'), and `RoutedOutcome` (frozen dataclass) per data-model §3–§6, §8. Module-level `__all__` exports all five.
- [ ] T009 [P] Create `packages/core/src/arc_guard_core/decision.py` containing `DecisionRecord`, `FindingSummary`, `TransformSummary` (frozen dataclasses) per data-model §9–§11. Module-level `__all__` exports all three.
- [ ] T010 [P] Create `packages/core/src/arc_guard_core/placeholders.py` with `DEFAULT_PLACEHOLDERS: dict[str, str]` populated per data-model §7, plus public functions `register_placeholder`, `get_placeholder`, `format_placeholder`, `list_registered`. Validation: label must match `^\[[A-Z][A-Z0-9_]*\]$`. Thread-safe (RLock).
- [ ] T011 [P] Create `packages/core/src/arc_guard_core/refusal/templates.py` with `RefusalTemplate` frozen dataclass and `DEFAULT_REFUSAL_TEMPLATES: dict[RefusalCode, RefusalTemplate]` covering all five `RefusalCode` values per research §5. Public function `register_refusal_template(code, template)`.

### New Protocol (data-model §8, contracts/policy-router.md)

- [ ] T012 Create `packages/core/src/arc_guard_core/protocols/policy_router.py` defining `PolicyRouter` Protocol with the documented `Concurrency:` / `Failure mode:` / `Thread-safety:` docstring lines. Method: `route(self, result: GuardResult, ruleset: PolicyRuleSet) -> RoutedOutcome`. Mark `@runtime_checkable`.
- [ ] T013 Update `packages/core/src/arc_guard_core/protocols/__init__.py` to re-export `PolicyRouter`.

### GuardConfig integration (FR-031)

- [ ] T014 Add `policy: PolicyRuleSet | None` field with default `None` to `packages/core/src/arc_guard_core/config.py` `GuardConfig`. Cross-field validator: when `policy is not None`, every `match` in the ruleset must be a known entity type and every `strategy` must be registered (deferred to runtime registry — see T020).

### Public surface re-exports

- [ ] T015 Update `packages/core/src/arc_guard_core/__init__.py` `__all__` to export the new symbols: `ClarificationRequest`, `RiskBand`, `RiskThresholds`, `PolicyRule`, `PolicyRuleSet`, `RoutedOutcome`, `DecisionRecord`, `FindingSummary`, `TransformSummary`, `RefusalTemplate`, `PolicyRouter`. Verify the import order doesn't introduce a circular dep.

### Spec 002 contract snapshot baseline update

- [ ] T016 Run `cd packages && uv run --package arc-guard-core pytest tests/contract/ -k snapshot --update-snapshot` to refresh `tests/contract/snapshots/{public_types,protocols,exceptions}.json` with the new symbols. Verify the diff is purely additive (every change is "new entry"; nothing removed; nothing narrowed).
- [ ] T017 [P] Add CHANGELOG entries under `packages/core/CHANGELOG.md` `### Added` enumerating the new public symbols (one bullet per symbol).

### Strategy registry (pip)

- [ ] T018 Create `packages/pip/src/arc_guard/strategies/registry.py` with `register_strategy(name, strategy)`, `get_strategy(name)`, `is_registered(name)`, `list_registered()`, and the `@strategy(name)` decorator per contracts/strategy-registry.md. Thread-safe RLock. Raises `StrategyError` for unknown name; raises `ValueError` for empty name; raises `StrategyError` for duplicate registration with a different instance.
- [ ] T019 [P] Update `packages/pip/src/arc_guard/strategies/__init__.py` to import the existing built-ins (`redact`, `hash`, `block`) and register them via `register_strategy` at module load. Add registration calls for the new `warn` and `tokenize` strategies (modules created in subsequent tasks).
- [ ] T020 Add a `validate_strategies_registered(ruleset: PolicyRuleSet) -> None` helper in `packages/pip/src/arc_guard/policy/__init__.py` that iterates `ruleset.rules` and asserts each `rule.strategy` is registered, raising `ConfigCrossFieldError` with code `"config.unknown_strategy"` and `details={"rule_id": ..., "strategy": ...}` if not. This is the runtime hook the `GuardConfig.policy` validator from T014 invokes when a pipeline is constructed.

### Foundational tests

- [ ] T021 [P] Add unit tests in `packages/core/tests/unit/test_policy_models.py` covering `RiskBand` ordering, `RiskThresholds` defaults and validation (non-negative, `low_max ≤ medium_max`), `PolicyRule` required fields, `PolicyRuleSet` empty-rules + default-action edge case, `RoutedOutcome` field defaults.
- [ ] T022 [P] Add unit tests in `packages/core/tests/unit/test_decision_models.py` covering `DecisionRecord`, `FindingSummary`, `TransformSummary` construction, default values, and `dataclasses.asdict` round-trip (no factory references in the dump).
- [ ] T023 [P] Add unit tests in `packages/core/tests/unit/test_placeholders.py` covering `DEFAULT_PLACEHOLDERS` registration, `format_placeholder` for `total=1` (unsuffixed), `total=2` (suffixed `_1`/`_2`), `total=N>2`. Validation errors for malformed labels (lowercase, missing brackets).
- [ ] T024 [P] Add unit tests in `packages/core/tests/unit/test_refusal_templates.py` asserting every `RefusalCode` value has a registered template, every template has non-empty `human_message`, `register_refusal_template` overrides cleanly.
- [ ] T025 [P] Add unit tests in `packages/core/tests/unit/test_clarification_request.py` covering `ClarificationRequest` field defaults and serialization. Cross-validation: `GuardResult(clarification=ClarificationRequest(...), action="block")` must raise (per T007 invariant).
- [ ] T026 [P] Add unit tests in `packages/pip/tests/unit/test_strategy_registry.py` covering register / get / list / is_registered, thread-safe concurrent registration (≥4 workers), duplicate-with-same-instance is no-op, duplicate-with-different-instance raises, decorator form works.

**Checkpoint**: All foundational types live in `core`, the strategy registry is in `pip`, the contract snapshot is updated, and all 6 foundational test files pass. User stories can now begin in parallel.

---

## Phase 3: User Story 1 — Integrator gets typed placeholders out of the box (Priority: P1) 🎯 MVP

**Goal**: An integrator running a benign multi-entity input through the pipeline (with a basic policy) sees typed placeholders (`[EMPLOYEE_NAME]`, `[CREDIT_CARD]`, `[INTERNAL_PROJECT]`) preserving the meaning of each entity. Per-input multi-occurrence suffixing follows D2.

**Independent Test**: Walkthrough A.4 / quickstart §A and the typed-placeholder format suite — input with 1 / 2 / 3 / mixed entities → output respects the registry and D2 format; raw entity content never leaks.

### Redact strategy update (D2)

- [ ] T027 [US1] Update `packages/pip/src/arc_guard/strategies/redact.py` to use the typed-placeholder registry (`arc_guard_core.placeholders.format_placeholder`) and emit `[<TYPE>]` for single occurrences and `[<TYPE>_<N>]` for multiple per D2. Two-pass scan: first count occurrences per entity type, second pass emit replacements in span order. Returns `tuple[str, Sequence[PolicyDecision]]` per Spec 002 `ActionStrategy` Protocol.
- [ ] T028 [US1] Ensure `arc_guard.strategies.redact.RedactStrategy` registers itself under name `"redact"` via the registry decorator at module load. Update `packages/pip/src/arc_guard/strategies/__init__.py` if not already importing it.

### US1 tests

- [ ] T029 [P] [US1] Add unit tests in `packages/pip/tests/unit/test_typed_placeholder_format.py` parametrized over the fixture matrix from contracts/placeholder-registry.md §"Tests": single occurrence unsuffixed, two occurrences suffixed, three occurrences, mixed types in one input, custom-registered type with 1 / 2 occurrences.
- [ ] T030 [P] [US1] Add an integration test in `packages/pip/tests/integration/test_us1_typed_placeholders.py` that runs the pipeline against User Story 1 acceptance scenarios (1-3) with **at least five distinct entity types per SC-001**: an input combining `EMPLOYEE_NAME` + `EMAIL_ADDRESS` + `INTERNAL_PROJECT` + `CREDIT_CARD` + `US_SSN` yields exactly five typed placeholders; two distinct credit-cards yield distinguishable suffixed placeholders (`[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`) per D2; benign input returns unchanged text. Assert zero raw entity bytes appear in the sanitized output (per SC-001 — substring scan with length ≥ 4).

**Checkpoint**: User Story 1 is fully functional. Typed placeholders are correctly emitted; multi-occurrence suffixing works per D2; `Finding` shape is unchanged.

---

## Phase 4: User Story 2 — Composable policy routing (Priority: P1)

**Goal**: An operator authors a `PolicyRuleSet` with multiple rules; one input fires multiple rules; the pipeline produces one combined `GuardResult` with one `PolicyDecision` per fired rule and the conflict-resolution table applied for overlapping rules.

**Independent Test**: Walkthrough A.4 (4 rules fire on one input) and the conflict-resolution suite — assert decision order matches finding span order and the most-restrictive strategy wins on conflicts.

### RuleBasedPolicyRouter implementation

- [ ] T031 [US2] Create `packages/pip/src/arc_guard/policy/router.py` defining `RuleBasedPolicyRouter` satisfying the `PolicyRouter` Protocol from `arc_guard_core.protocols.policy_router`. Constructor accepts `strategy_registry` (defaults to module-level singleton) and the active `RuleSet` is passed per-call to `route`. Raises `PolicyRouterError` (not unwrapped exceptions).
- [ ] T032 [US2] Create `packages/pip/src/arc_guard/policy/conflict.py` with `STRATEGY_PRECEDENCE: tuple[str, ...]` listing names highest-to-lowest restrictive (`block`, `redact`, `tokenize`, `hash`, `warn`, `pass`). Function `resolve_conflict(candidate_rules: Sequence[PolicyRule]) -> PolicyRule` returns the most restrictive; if equal precedence, the first declared rule wins. Records the resolution in the returned `PolicyDecision.rationale`.
- [ ] T033 [US2] Inside `RuleBasedPolicyRouter.route`: for each `Finding`, find all rules whose `match == finding.entity_type` AND `severity_floor <= finding.risk_level`. Resolve conflicts via T032. Apply the resolved strategy through the registry. Build a `PolicyDecision` per fired rule including the conflict-resolution rationale when applicable.
- [ ] T034 [US2] Apply transforms in span order so multi-strategy outputs compose correctly. The router applies replacements in reverse span order to keep earlier spans stable; the resulting `transformed_text` is exposed on `RoutedOutcome.transformed_text`.

### Strategy implementations needed for US2

- [ ] T035 [P] [US2] Update `packages/pip/src/arc_guard/strategies/hash.py` to register itself as `"hash"` and conform to the `apply(text, findings) -> tuple[str, Sequence[PolicyDecision]]` signature returning `[HASH:<8 hex>]` placeholders.
- [ ] T036 [P] [US2] Update `packages/pip/src/arc_guard/strategies/block.py` to register itself as `"block"` and return `("", [PolicyDecision(strategy="block", rationale="blocked by policy", ...)])` — the router builds the `RefusalEnvelope` from the firing rule's overrides.
- [ ] T037 [P] [US2] Create `packages/pip/src/arc_guard/strategies/warn.py` defining `WarnStrategy` registered as `"warn"`. Pass-through transform; emits `PolicyDecision` with `rationale` prefixed `"warn:"` so downstream observers can filter.

### Pipeline integration (the policy-on path)

- [ ] T038 [US2] Update `packages/pip/src/arc_guard/pipeline.py` `_run` to branch on `self.config.policy is None`: if `None`, preserve Spec 001 behavior (current code path); if not, resolve the active router via `self._policy_router or RuleBasedPolicyRouter()` (lazily cached) and call `route(result, self.config.policy)` — the optional `policy_router=` constructor kwarg per plan research §6 lets callers (and tests) inject a custom `PolicyRouter` implementation. Apply the resulting `RoutedOutcome.transformed_text`, populate `result.decisions`, set `result.action` from the aggregate. Wire validation: at pipeline construction, if `policy is not None`, call `validate_strategies_registered(policy)` from T020.
- [ ] T039 [US2] Add `_apply_outcome` helper to `pipeline.py` that builds the new immutable `GuardResult` from the original `findings`, `outcome.transformed_text`, `outcome.decisions`, `outcome.refusal`, `outcome.clarification`, `outcome.aggregate_action`, and the original phase. The pipeline never mutates the original `result`.

### US2 tests

- [ ] T040 [P] [US2] Add unit tests in `packages/pip/tests/unit/test_policy_router.py` covering: single-rule single-finding flow; multiple rules each matching one finding; rule that doesn't match (severity_floor too high) is skipped; rule with unknown entity-type is rejected at validation (caught by T020).
- [ ] T041 [P] [US2] Add unit tests in `packages/pip/tests/unit/test_strategy_conflict_resolution.py` parametrized over the full precedence table: every pair of strategies, both directions, asserting the more-restrictive one wins; equal-precedence picks the first-declared rule. Verify the rationale records the override.
- [ ] T042 [US2] Add an integration test in `packages/pip/tests/integration/test_us2_composable_routing.py` running quickstart §A.3 (4 rules: redact emails / hash cards / block injection / warn names) with a multi-entity input and asserting `len(result.decisions) == 4`, decisions in finding span order, action `"block"` (injection wins), and per-decision strategy attribution.
- [ ] T042b [P] [US2] Add a parametrized fixture suite in `packages/pip/tests/integration/test_us2_policy_combinations.py` covering **at least eight (rules × input) combinations per SC-002**: (1) 4 rules / all 4 fire, (2) 4 rules / 2 fire, (3) 4 rules / 0 fire, (4) overlapping rules same finding (conflict resolution), (5) rule with `severity_floor=HIGH` skipped on a LOW finding, (6) two findings of the same entity type with one matching rule, (7) empty `PolicyRuleSet.rules` with `default_action_when_no_rules_fire="pass"`, (8) all rules at the same precedence resolved by declaration order. Assert decision count, decision order, and `aggregate_action` for each.
- [ ] T043 [P] [US2] Add unit tests in `packages/pip/tests/unit/test_policy_validation.py` covering: unknown entity_type in a rule → `ConfigCrossFieldError` with code `"config.unknown_entity_type"`; unknown strategy name → `ConfigCrossFieldError` with code `"config.unknown_strategy"`; empty rules + `default_action_when_no_rules_fire="block"` → rejected.

**Checkpoint**: Multi-rule policy routing works end-to-end. Pipeline correctly branches on `policy is None`; Spec 001/002 callers see no behavior change.

---

## Phase 5: User Story 3 — Risk-adaptive behavior (Priority: P1)

**Goal**: Aggregate finding severity drives the aggregate action through four bands (LOW / MEDIUM / HIGH / CRITICAL). HIGH triggers partial refusal (D3 — fully sanitized text + refusal envelope, action != "block"). CRITICAL triggers a hard block.

**Independent Test**: Walkthrough B (4 risk-level inputs) — each produces the expected band, action, and refusal-envelope presence.

### RiskClassifier and aggregation

- [ ] T044 [US3] Create `packages/pip/src/arc_guard/policy/classifier.py` with `RiskClassifier` class. Method `classify(findings: Sequence[Finding], thresholds: RiskThresholds) -> RiskBand`. Pure function. Aggregation: max of (per-finding ceiling, count-based escalation per `low_max_count` / `medium_max_count` / `high_escalates_at` / `critical_escalates_at` / `soft_pii_aggregation`).
- [ ] T045 [US3] Create `packages/pip/src/arc_guard/policy/aggregation.py` with `aggregate_action_for_band(band: RiskBand, decisions: Sequence[PolicyDecision]) -> Literal["pass","redact","hash","block","tokenize"]`. LOW/MEDIUM → most restrictive among non-block decisions; HIGH → most restrictive non-block (FR-011 D3); CRITICAL → `"block"`.
- [ ] T046 [US3] Integrate the classifier into `RuleBasedPolicyRouter.route`: after building per-finding decisions, classify the band, derive the aggregate action via T045, and stamp both onto `RoutedOutcome`. When band is HIGH, leave `transformed_text` fully sanitized (D3) and set the refusal builder up (US4); when CRITICAL, set `transformed_text=""` and ensure block strategy applied.

### US3 tests

- [ ] T047 [P] [US3] Add unit tests in `packages/pip/tests/unit/test_risk_classifier.py` parametrized over a 16-row matrix (4 bands × 4 representative entity mixes) asserting the classifier returns the expected `RiskBand`. Cover the soft-PII aggregation (3+ LOW → MEDIUM) and the per-finding ceiling rules (any HIGH → HIGH; any CRITICAL → CRITICAL). Add one explicit case for FR-013: when the soft-PII aggregation rule changes the band (e.g. 3 LOW findings escalate to MEDIUM), the resulting `PolicyDecision.rationale` MUST contain a documented aggregation marker substring (e.g. `"aggregation:soft_pii→MEDIUM"`).
- [ ] T048 [P] [US3] Add unit tests in `packages/pip/tests/unit/test_aggregate_action.py` asserting `aggregate_action_for_band` returns the correct action for every combination of band × {single decision, multiple decisions, conflicting decisions}.
- [ ] T049 [US3] Add an integration test in `packages/pip/tests/integration/test_us3_risk_adaptive.py` running User Story 3 acceptance scenarios (1-4): LOW input → `action="redact"`, no refusal; MEDIUM input → `action="redact"`, rationale flags warn; HIGH input (US_SSN) → fully sanitized text per D3, `refusal is not None`, `action != "block"`; CRITICAL input (jailbreak) → `action="block"`, `text==""`, refusal populated.

**Checkpoint**: All four risk bands route correctly. D3 partial-refusal behavior validated end-to-end.

---

## Phase 6: User Story 4 — Graceful refusal envelope (Priority: P2)

**Goal**: Every block or partial refusal produces a `RefusalEnvelope` with all fields populated from the firing rule's overrides or the registered template defaults. Serializable to JSON without leaking raw payloads.

**Independent Test**: Walkthrough A.4 (block path) — assert envelope has non-empty `code`, `trigger`, `policy`, `human_message`, `next_steps`; serialized JSON contains all public field names.

### Refusal builder

- [ ] T050 [US4] Create `packages/pip/src/arc_guard/refusal/builder.py` with `RefusalBuilder` class. Method `build(firing_rule: PolicyRule, decisions: Sequence[PolicyDecision], code: RefusalCode, trigger: str, policy_id: str) -> RefusalEnvelope`. Resolves `human_message` and `next_steps` from `firing_rule.refusal_human_message` / `firing_rule.refusal_next_steps` if set; otherwise from the registered `RefusalTemplate`.
- [ ] T051 [US4] Integrate the builder into `RuleBasedPolicyRouter.route`: when band is HIGH or CRITICAL, build a `RefusalEnvelope` from the highest-severity firing rule. Wire `RefusalCode` selection: `JAILBREAK` for INJECTION-class findings, `PII_CRITICAL` for high-severity PII, `POLICY_BLOCK` as the default fallback when the firing rule doesn't dictate.
- [ ] T052 [P] [US4] Update `packages/pip/src/arc_guard/strategies/block.py` if needed to surface enough metadata for the builder (e.g. include the `firing_rule.id` in `PolicyDecision.metadata` so the builder can locate it).

### US4 tests

- [ ] T053 [P] [US4] Add unit tests in `packages/pip/tests/unit/test_refusal_builder.py` covering: rule with full overrides → envelope uses overrides verbatim; rule with no overrides → envelope uses registered default for the code; empty `next_steps` from rule → falls back to template default; unknown `RefusalCode` → raises `RefusalEnvelopeError`.
- [ ] T054 [P] [US4] Add a contract test in `packages/core/tests/contract/test_refusal_envelope_completeness.py` (extends the contract suite) parametrized over the default-policy fixtures, asserting every emitted envelope has non-empty `code`, `trigger`, `policy`, `human_message`, and `next_steps`. Failures in this test are blocking — every envelope must be self-contained.
- [ ] T055 [US4] Add an integration test in `packages/pip/tests/integration/test_us4_refusal_envelope.py` running quickstart §A.4 (block path) and §B.3 (HIGH partial refusal) and §B.4 (CRITICAL block), asserting envelope fields and JSON-serializability via `dataclasses.asdict` + `json.dumps` containing all documented field names.

**Checkpoint**: Refusal envelopes are fully populated, registered templates work, and rule-level overrides take precedence.

---

## Phase 7: User Story 5 — Clarification-first control flow (Priority: P2)

**Goal**: When the policy classifies a run as ambiguous and `clarification_enabled=True`, the pipeline returns a `ClarificationRequest` instead of a hard block. Opt-in: `clarification_enabled=False` falls back to the policy default.

**Independent Test**: Walkthrough B.5 — borderline input with `clarification_enabled=True` returns `clarification is not None`, `action="pass"`, `refusal is None`. Same input with `clarification_enabled=False` falls back to the configured default.

### Ambiguous classification + clarification builder

- [ ] T056 [US5] Add `is_ambiguous(band: RiskBand, ruleset: PolicyRuleSet) -> bool` to `packages/pip/src/arc_guard/policy/classifier.py`. Returns `True` when `ruleset.clarification_enabled` is `True` AND `band == ruleset.ambiguous_threshold`. CRITICAL is never ambiguous.
- [ ] T057 [US5] Create `packages/pip/src/arc_guard/policy/clarification.py` with `build_clarification(firing_rule: PolicyRule | None, findings: Sequence[Finding]) -> ClarificationRequest`. The suggested rephrase is drawn from the firing rule's `rationale_template` if present, else from a registered default per finding kind. The `triggering_rule_id` is set when known.
- [ ] T058 [US5] Integrate into `RuleBasedPolicyRouter.route`: after classification, if `is_ambiguous(...)` AND CRITICAL is not present, set `RoutedOutcome.clarification`, leave `transformed_text` set to the sanitized text, set `aggregate_action="pass"`, and skip refusal-envelope construction. The pipeline's `_apply_outcome` populates `GuardResult.clarification` accordingly.

### US5 tests

- [ ] T059 [P] [US5] Add unit tests in `packages/pip/tests/unit/test_clarification.py` covering: enabled + ambiguous band → clarification populated, refusal not set; enabled but band is CRITICAL → no clarification, hard block; disabled → falls back to policy default; T007 invariant — `clarification` populated implies `action != "block"`.
- [ ] T060 [US5] Add an integration test in `packages/pip/tests/integration/test_us5_clarification.py` running Walkthrough B.5 end-to-end and a fixture suite of **at least 10 borderline inputs per SC-006** (partial card numbers, ambiguous personal references, near-policy-edge phrasing, etc.). Each input runs through the pipeline with `clarification_enabled=True`. Assert (a) the single Walkthrough B.5 input produces a populated `ClarificationRequest` with non-empty `suggested_rephrase`, non-empty `next_steps`, and a `triggering_rule_id` that resolves; (b) **at least 80% of the 10-input suite returns `result.clarification is not None` rather than a hard block** — the SC-006 recovery threshold.

**Checkpoint**: Clarification mode works, opt-in semantics preserved, and CRITICAL never asks for clarification.

---

## Phase 8: User Story 6 — Decision record explains every run end-to-end (Priority: P2)

**Goal**: Every pipeline run produces a typed `DecisionRecord` listing detected findings, applied transforms, fired rule ids, aggregate action, aggregate band, latency, and a stable correlation id. No raw payloads leak (FR-023). Emitted via the Spec 002 observability hooks.

**Independent Test**: A fixture suite of inputs produces serialized `DecisionRecord` instances; an automated scan asserts no raw input substring (≥8 chars) appears in the serialized output.

### Decision emitter

- [ ] T061 [US6] Create `packages/pip/src/arc_guard/decision/emitter.py` with `DecisionEmitter` class. Method `build(result: GuardResult, outcome: RoutedOutcome, latency_ms: float, phase: str) -> DecisionRecord`. Builds `FindingSummary` per finding (no raw text — span only); builds `TransformSummary` per applied strategy; populates `fired_rules`, `refusal_code`, `clarification_present`, `correlation_id` (from `GuardContext.correlation_id`).
- [ ] T062 [US6] Method `emit(record: DecisionRecord, *, logger: Logger, metrics: MetricSink) -> None` invokes `logger.event("guard.decision", level="info", **dataclasses.asdict(record))`, `metrics.counter("guard.decisions", attributes={"action": ..., "risk_band": ...})`, and `metrics.histogram("guard.findings_count", float(len(record.findings)))`.
- [ ] T063 [US6] Update `packages/pip/src/arc_guard/pipeline.py` `_run` to instantiate the emitter (cached on the pipeline), measure run latency, build the record after `_apply_outcome`, store on `pipeline._last_decision` for tests, and call `emit(...)` with the configured logger/metrics from `self.config`.

### US6 tests

- [ ] T064 [P] [US6] Add unit tests in `packages/pip/tests/unit/test_decision_emitter.py` covering: build with empty findings → empty `findings` and `transforms`; build with one finding + one transform → exactly one entry each, indices align; latency populated; correlation_id propagated.
- [ ] T065 [US6] Add a contract test in `packages/core/tests/contract/test_no_raw_payload_in_decision_record.py` (the FR-023 scanner). Inputs: a fixture set of three sentences containing distinct PII / PCI / enterprise entities. For each, run the pipeline with the default policy, serialize the decision record via `dataclasses.asdict` + `json.dumps`, and scan for ALL substrings of the original input of length ≥ 8 — every match fails the test. Also scan for the raw entity content (the masked span's original characters).
- [ ] T066 [P] [US6] Add an integration test in `packages/pip/tests/integration/test_us6_decision_record.py` running Walkthrough B.6 — assert `_last_decision` is populated, `findings` lists every detected entity (length, span, entity_type — no raw text), `transforms` lists every applied strategy with `replacement_kind`, `fired_rules` contains the firing rule ids, and the `latency_ms` is finite and positive.
- [ ] T067 [P] [US6] Add unit tests in `packages/pip/tests/unit/test_decision_emission_hooks.py` using fake `Logger` and `MetricSink` implementations that record every call; assert the emitter calls `logger.event("guard.decision", ...)` exactly once per run, calls `metrics.counter` exactly once with the right attributes, and calls `metrics.histogram` exactly once.
- [ ] T067b [P] [US6] Add a non-blocking emission test in `packages/pip/tests/unit/test_decision_emission_nonblocking.py` per FR-022. Wire a deliberately slow fake `Reporter` whose `report()` sleeps for 200ms. Run `pipeline._run` inside `asyncio.wait_for(..., timeout=0.05)` (50ms) on a benign input; assert the run completes inside the budget regardless of reporter latency — the constitution Principle V "non-blocking reporter" requirement made executable.

**Checkpoint**: Decision records are correctly built and emitted; no raw payloads leak.

---

## Phase 9: User Story 7 — Custom strategy without modifying core (Priority: P3)

**Goal**: A contributor implements a custom strategy satisfying the `ActionStrategy` Protocol, registers it via the strategy registry, references it in a `PolicyRuleSet`, and runs the pipeline — all without touching `arc_guard_core`.

**Independent Test**: Walkthrough §C — a fixture custom strategy `tokenize_tenant` registered via decorator, used in a policy, produces tokens in the output and a matching `PolicyDecision`.

### Tokenize strategy (built-in reference implementation)

- [ ] T068 [US7] Create `packages/pip/src/arc_guard/strategies/tokenize.py` with `TokenizeStrategy` registered as `"tokenize"` via the `@strategy("tokenize")` decorator. Per-input deterministic format `[<TYPE>_TOK_<N>]` (1-indexed per type). Cross-run determinism is NOT promised by Spec 003 (research §10).

### US7 tests

- [ ] T069 [P] [US7] Add unit tests in `packages/pip/tests/unit/test_tokenize_strategy.py` covering: single occurrence → `[CREDIT_CARD_TOK_1]`; multiple occurrences → sequential `_TOK_1`, `_TOK_2`; per-input determinism but no cross-input determinism.
- [ ] T070 [US7] Add an integration test in `packages/pip/tests/integration/test_us7_custom_strategy.py` implementing the Walkthrough §C `TokenizeWithTenantSalt` fixture in the test file itself (per quickstart). Register via decorator, build a policy referencing `"tokenize_tenant"`, run the pipeline, assert tokens appear in `result.text` and `result.decisions[0].strategy == "tokenize_tenant"`.
- [ ] T071 [P] [US7] Add a boundary check test in `packages/pip/tests/integration/test_us7_boundary_preserved.py` that runs `tools/check_import_graph.py` after the custom strategy is registered, asserting the workspace's 4 import-linter contracts still pass.

**Checkpoint**: Custom strategies plug in cleanly; the boundary contracts remain intact.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: walkthrough finalization, README cross-links, contract suite verification, full quality gate run.

- [ ] T072 [P] Finalize `packages/core/CHANGELOG.md` `## [0.2.0]` section: enumerate every additive entry (10 new public types + 1 new field on `GuardResult` + 1 new field on `GuardConfig`).
- [ ] T073 [P] Finalize `packages/pip/CHANGELOG.md` `## [0.3.0]` section: enumerate the new built-in strategies (`warn`, `tokenize`), the policy router, the strategy registry, the decision emitter, and the explicit removal of the Spec 001 deprecation shims (per the Spec 002 timeline).
- [ ] T074 [P] Update `packages/pip/README.md` to reference Spec 003: `PolicyRuleSet`, `PolicyRouter`, decision-record emission, link to `quickstart.md`.
- [ ] T075 [P] Create `docs/walkthrough/003-sanitization-policy-core.md` as the operator-facing one-page walkthrough — covers policy authoring, the four risk bands, the typed-placeholder reference, the clarification flow, and the worked decision-record example. Cross-links to all five contract documents.
- [ ] T076 [P] Update `docs/walkthrough/002-rewrite-foundation.md` "What's next" section pointing readers to Spec 003.
- [ ] T077 [P] Update `specs/index.md` Spec 003 row to status `Implemented` once all preceding tasks are green.
- [ ] T078 Update `.specify/memory/patterns.md` Rewrite-sequencing entry for Spec 003 → IMPLEMENTED, with a one-line reference to `specs/003-sanitization-policy-core/contracts/`.
- [ ] T079 Run `cd packages && uv run --package arc-guard-core ruff check src tests`, `uv run --package arc-guard-core mypy src --strict`, `uv run --package arc-guard-core pytest` — all green. Also explicitly verify FR-029 (no modification to existing Spec 002 protocols): assert that `arc_guard_core/protocols/{guard,inspector,strategy,reporter,flag_provider,middleware,entity_provider}.py` files are unchanged from the Spec 002 baseline (compare hashes against the recorded values, e.g. via `git diff main...HEAD packages/core/src/arc_guard_core/protocols/` — the diff MUST be empty for those seven files).
- [ ] T080 [P] Run `cd packages && uv run --package arc-guard ruff check src tests`, `uv run --package arc-guard mypy src --strict`, `uv run --package arc-guard pytest` — all green. Verify the transitional `disable_error_code` block from Spec 002 is shrunk (or unchanged — never grown).
- [ ] T081 [P] Run `cd packages && uv run --package arc-guard-service ruff check src tests`, `uv run --package arc-guard-service mypy src --strict`, `uv run --package arc-guard-service pytest` — all green.
- [ ] T082 Run all four boundary tools — `tools/check_import_graph.py`, `tools/check_dependency_tree.py`, `tools/check_async_blocking.py`, `tools/check_adopt_vs_build.py` — all green. Verify `arc-guard-core` runtime closure is unchanged (still `pydantic` + stdlib).
- [ ] T083 Build wheels for all three packages — `uv build --wheel` — and verify each wheel contains its `py.typed` marker via `unzip -l dist/*.whl | grep py.typed`.
- [ ] T084 Execute `quickstart.md` Walkthrough A end-to-end in a clean venv against the `arc-guard` 0.3.0 wheel; confirm every step's expected output.
- [ ] T085 Execute `quickstart.md` Walkthrough B end-to-end against the workspace; confirm every step's expected output.
- [ ] T086 Execute `quickstart.md` Walkthrough C end-to-end against the workspace; confirm boundary check passes after custom-strategy registration.
- [ ] T087 Run `.specify/scripts/bash/update-agent-context.sh claude` so `CLAUDE.md` reflects Spec 003 tech context.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: no dependencies; can start immediately
- **Phase 2 (Foundational)**: depends on Phase 1; **blocks** all user-story phases
- **Phase 3 (US1)**: depends on Phase 2 (placeholders module + redact strategy infrastructure)
- **Phase 4 (US2)**: depends on Phase 2 (Protocol + registry + policy models) and benefits from Phase 3 redact updates landing first to avoid two-step touches on the same file
- **Phase 5 (US3)**: depends on Phase 4 (the router is the integration point for risk classification)
- **Phase 6 (US4)**: depends on Phase 5 (refusal builder runs after risk classification produces the band)
- **Phase 7 (US5)**: depends on Phase 5 (ambiguous classification fits inside the classifier; clarification populates a `RoutedOutcome` field added in T046)
- **Phase 8 (US6)**: depends on Phase 4 (decision emitter consumes `RoutedOutcome`); can run in parallel with Phases 6 / 7 once Phase 4 closes
- **Phase 9 (US7)**: depends on Phase 4 (registry exists); can run in parallel with Phases 5-8
- **Phase 10 (Polish)**: depends on all earlier phases

### User Story Dependencies (informational — phases enforce ordering)

- **US1 (P1)**: independent of US2-US7; produces typed-placeholder text used by US2's `redact` strategy invocations
- **US2 (P1)**: depends on US1's redact for the placeholder format; otherwise independent
- **US3 (P1)**: depends on US2's router as integration point
- **US4 (P2)**: depends on US3's risk band
- **US5 (P2)**: depends on US3's classifier
- **US6 (P2)**: depends on US2's `RoutedOutcome`; can land in parallel with US4 / US5
- **US7 (P3)**: depends on US2's registry; otherwise independent

### Within Each User Story

- Models and helpers before the router integration that uses them
- Router integration before the integration tests that exercise it end-to-end
- Tests for new modules in the same commit as the modules

### Parallel Opportunities

- **Phase 1 setup**: T003 / T004 / T005 fully parallel
- **Phase 2 foundational**:
  - Track A (core models): T006 → T007 (sequential, same file); T008, T009, T010, T011 parallel after T006/T007
  - Track B (snapshot + tests): T015 → T016 → T017 → T021–T025 (all parallel after T015)
  - Track C (registry): T018 → T019 → T020 → T026 (sequential, but track-parallel with A/B)
- **Phase 3 (US1)**: T027 → T028 (same file); T029, T030 parallel after
- **Phase 4 (US2)**: T031 → T032 → T033 → T034 (sequential router build); T035, T036, T037 parallel after T031; T040–T043 parallel after T034
- **Phase 5 (US3)**: T044 → T045 → T046 (sequential); T047, T048 parallel; T049 after T046
- **Phase 6 (US4)**: T050 → T051 (sequential, T052 can land in parallel); T053, T054 parallel after T050; T055 after T051
- **Phase 7 (US5)**: T056 → T057 → T058 sequential; T059, T060 parallel after
- **Phase 8 (US6)**: T061 → T062 → T063 sequential; T064, T065, T066, T067 parallel after T063
- **Phase 9 (US7)**: T068 first; T069, T070, T071 parallel after T068
- **Phase 10 (Polish)**: T072–T078 mostly parallel; T079, T080, T081 parallel; T082 sequential after package gates; T083–T087 mostly parallel

---

## Parallel Example: Phase 2 Foundational

```bash
# After T006 + T007 land:

# Track A — additional core types (independent files)
Task: "Create policy.py — RiskBand, RiskThresholds, PolicyRule, PolicyRuleSet, RoutedOutcome"  # T008
Task: "Create decision.py — DecisionRecord, FindingSummary, TransformSummary"                  # T009
Task: "Create placeholders.py — DEFAULT_PLACEHOLDERS + register/get/format helpers"            # T010
Task: "Create refusal/templates.py — RefusalTemplate + DEFAULT_REFUSAL_TEMPLATES"              # T011

# Track B — Protocol + GuardConfig (dependent on Track A's types)
# Run after Track A:
Task: "Create protocols/policy_router.py — PolicyRouter Protocol"      # T012
Task: "Update protocols/__init__.py — re-export PolicyRouter"          # T013
Task: "Add GuardConfig.policy field"                                   # T014

# Track C — public surface re-exports + snapshot update
# Run after Tracks A+B:
Task: "Update arc_guard_core/__init__.py __all__"                      # T015
Task: "Run pytest --update-snapshot"                                   # T016
Task: "Add CHANGELOG entries"                                          # T017

# Track D — strategy registry (independent of all of A/B/C until validation)
Task: "Create strategies/registry.py"                                  # T018
Task: "Update strategies/__init__.py — register built-ins"             # T019
Task: "Add validate_strategies_registered helper"                      # T020

# Tests (parallel after each implementation track lands)
Task: "test_policy_models.py"            # T021
Task: "test_decision_models.py"          # T022
Task: "test_placeholders.py"             # T023
Task: "test_refusal_templates.py"        # T024
Task: "test_clarification_request.py"    # T025
Task: "test_strategy_registry.py"        # T026
```

---

## Implementation Strategy

### MVP First (User Story 1 + just enough Phase 2)

1. Complete Phase 1 (Setup)
2. Complete Phase 2 (Foundational) — all 21 tasks
3. Complete Phase 3 (US1 — typed placeholders)
4. **STOP and VALIDATE**: run Walkthrough A.5 from `quickstart.md`. Confirm benign input passes through; multi-entity input gets typed placeholders.
5. Tag `arc-guard-core 0.2.0-rc1` if shipping incrementally.

### Incremental Delivery

1. **Setup + Foundational** → core types and registry in place.
2. **Add US1** → typed placeholders → run Walkthrough A.5.
3. **Add US2** → composable routing → run Walkthrough A.4 (4-rule input).
4. **Add US3** → risk-adaptive bands → run Walkthrough B.2–B.4.
5. **Add US4** → refusal envelopes verified → ship `arc-guard-core 0.2.0` and `arc-guard 0.3.0-beta`.
6. **Add US5** → clarification mode → run Walkthrough B.5.
7. **Add US6** → decision records → no-raw-payload contract test green.
8. **Add US7** → custom strategy walkthrough → run Walkthrough C.
9. **Polish** → docs, full quality gate, ship `arc-guard-core 0.2.0` + `arc-guard 0.3.0`.

### Parallel Team Strategy

After Phase 2 closes:
- **Developer A**: Phase 3 (US1) → Phase 4 (US2) — the routing critical path.
- **Developer B**: Phase 5 (US3) once Phase 4 closes → Phase 6 (US4) → Phase 7 (US5).
- **Developer C**: Phase 8 (US6) — decision emitter — once Phase 4 closes; parallel to US3/4/5.
- **Developer D**: Phase 9 (US7) — custom strategy walkthrough — once Phase 4 closes.

Phase 10 needs all developers to converge for the integration walkthroughs and the final gate.

---

## Notes

- `[P]` tasks touch different files and have no dependency on other incomplete `[P]` tasks within the same phase. Verify before launching.
- `[Story]` label maps each task to its user story for traceability against `spec.md`.
- Tests are mandatory because the constitution mandates them (Principle IV) and FR-013 / FR-024 / FR-034 require automated contract test coverage of every additive type.
- Verify each test fails before its target module is implemented (TDD discipline) where the test has a clear failure-to-success transition (US2 router, US3 classifier, US4 builder, US5 clarification, US6 emitter, US7 custom strategy).
- Commit at every checkpoint. Each phase ends in a coherent, testable state.
- After T020 (strategy registry validator) and T038 (pipeline integration), every subsequent change can break the pipeline — re-run `tools/check_import_graph.py` after adding any new strategy or router-internal module.
- If a task discovers a contradiction with the spec or plan, stop and update the spec/plan first, per roadmap §10 ("if a task appears during planning and is not clearly mapped to a current spec, add it back into the roadmap before starting work").
- The Spec 002 transitional `disable_error_code` block on `pip` SHOULD shrink as the legacy strategies migrate to the new registry-driven shape. Track per task: shrinking is a feature; growing is a regression.
