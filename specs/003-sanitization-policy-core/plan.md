# Implementation Plan: Sanitization and Policy Core

**Branch**: `003-sanitization-policy-core` | **Date**: 2026-05-01 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/003-sanitization-policy-core/spec.md`

## Summary

Spec 003 builds the sanitize stage and the policy-routing skeleton on top of Spec 002's frozen contract layer. The work is **additive only**: 7 new public types in `arc_guard_core`, 2 new fields on existing models (`GuardResult.clarification`, `GuardConfig.policy`), 1 new Protocol (`PolicyRouter`), and a richer implementation chain in `packages/pip/src/arc_guard/`. The Spec 002 contract test suite catches every additive change and requires CHANGELOG entries; no existing Protocol or type shape is modified.

The technical approach: (1) add the typed-placeholder registry, the policy / rule-set models, the decision-record model, and the clarification-request model to `arc_guard_core`; (2) add a `PolicyRouter` Protocol to `arc_guard_core.protocols`; (3) implement the default `RuleBasedPolicyRouter` in `packages/pip/src/arc_guard/policy/`; (4) implement a `StrategyRegistry` and built-in strategies (`redact`, `hash`, `block`, `warn`, `tokenize`) under `packages/pip/src/arc_guard/strategies/`; (5) integrate the router into the existing pipeline so its `_run` returns `GuardResult` populated with `decisions`, `refusal`, and `clarification` per the resolved contract decisions D1–D3; (6) emit a `DecisionRecord` per run through the Spec 002 observability hooks (null-default; Spec 004 wires real backends).

## Technical Context

| Aspect | Value |
|---|---|
| **Language / Version** | Python 3.11+ (constitution-mandated; matches Spec 002 baseline) |
| **Project Type** | Multi-package Python `uv` workspace established by Spec 002 (`packages/{core,pip,api}`) |
| **Primary Dependencies (`packages/core`)** | `pydantic` only — unchanged. Spec 003 adds typed models that fit within this constraint. |
| **Primary Dependencies (`packages/pip`)** | `arc-guard-core`, `presidio-analyzer`, `presidio-anonymizer` — unchanged. Spec 003 adds **no new runtime deps** (router and registry are pure stdlib + `arc_guard_core`). |
| **Primary Dependencies (`packages/api`)** | `arc-guard`, `pydantic-settings` — unchanged |
| **Storage** | N/A — policy rules are loaded from in-memory configuration; decision records are emitted through hooks, never persisted by this layer |
| **Testing** | `pytest` + `pytest-asyncio` + the Spec 002 contract snapshot suite. New: policy-router fixture suite, decision-record contract tests, typed-placeholder format tests. |
| **Target Platform** | Linux / macOS / Windows Python 3.11+ runtimes; offline / air-gapped install supported (no external services in the policy layer) |
| **Performance Goals** | Single-input pipeline run: under 5ms overhead added by the policy router and decision-record build for a 1KB input with 5 findings (excludes the inspector cost which is unchanged). Verified by a fixture benchmark in tests. |
| **Constraints** | Zero new runtime deps in `core` or `pip`; `mypy --strict` clean across all three packages (no new `disable_error_code` blocks); no blocking calls on async pipeline paths; no raw sensitive payloads in any emitted event (constitution Principle V). |
| **Scale / Scope** | ~12 new source modules, ~25 new test files (mostly fixture-driven), 7 new public types in `core`, 1 new Protocol, 5 built-in strategies registered by default. |
| **Workflow** | Same `uv` workspace as Spec 002; per-package quality gate runs `ruff check`, `pytest`, `mypy --strict`. The Spec 002 contract test suite extends to cover the new public surface. |
| **Resolved unknowns** | See [research.md](./research.md). Phase 0 resolves placement of new types, registry mechanism, integration with the existing pipeline, and naming. |

No `NEEDS CLARIFICATION` markers remain after Phase 0. The three open questions from spec.md (Q1/Q2/Q3) were already resolved as decisions D1, D2, D3 before this command ran; they ARE the locked contract this plan implements.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution at `.specify/memory/constitution.md` v1.0.0.

| Principle | Status | Evidence |
|---|---|---|
| **I. Generic-First Core** | PASS | All new core types (`PolicyRule`, `PolicyRuleSet`, `PolicyRouter` Protocol, `DecisionRecord`, `ClarificationRequest`, `TypedPlaceholder` registry helpers) are platform-neutral. No NATS / Unleash / OTEL / vendor coupling. The default placeholder labels (`[EMPLOYEE_NAME]`, `[CREDIT_CARD]`, …) are generic enterprise concepts, not provider-specific. |
| **II. One Contract, Many Modes** | PASS | The new `PolicyRouter` Protocol and `DecisionRecord` model live in `core` so SDK / sidecar / worker / gateway / batch / CLI usage modes inherit them unchanged. |
| **III. Adapter Isolation** | PASS | No adapters added. The `StrategyRegistry` is a thread-safe in-memory mapping; user-defined strategies register through it without modifying core. |
| **IV. Enterprise Python Baseline** | PASS | All new modules use `pyproject.toml` + `src/` + `uv` + `ruff` + `mypy --strict` + `pytest`. No new `disable_error_code` blocks; the Spec 002 transitional override on `pip` shrinks once Spec 003 strategies replace the legacy direct-action chain. |
| **V. Security, Observability, Resilience** | PASS | `DecisionRecord` schema explicitly forbids raw payloads (FR-023). Strategies are fail-closed by Spec 002 contract; `PolicyRouter` failure is fail-closed (`PolicyRouterError` already declared in Spec 002 exceptions). Reporters remain non-blocking. The router is pure sync computation — no event-loop blocking. |

| Product Constraint | Status | Evidence |
|---|---|---|
| Versioned event names and payload schemas | PASS | `DecisionRecord`, `ClarificationRequest`, and the new `GuardResult.clarification` field are versioned through Spec 002's contract snapshot suite; CHANGELOG entries required. |
| Configurable, product-neutral defaults | PASS | Default placeholder labels are generic; default `PolicyRuleSet` is empty (opt-in); default risk thresholds are documented in the contract. |
| Heavy deps stay optional | PASS | Zero new runtime deps. Strategy implementations use only `arc_guard_core` types and stdlib (e.g. `hashlib` for `hash`, `secrets` for `tokenize`). |
| Feature declares affected modes and contract impact | PASS | Spec §"Compatibility, Migration, and Enterprise Impact" documents both. Contract impact is explicitly ADDITIVE. |
| Offline / air-gapped operation possible | PASS | The policy router is a pure function over already-classified findings. No external services. |

| Workflow Gate | Status | Evidence |
|---|---|---|
| Feature classified | PASS | `core-contract` (additive contract types) + `must-have` (roadmap §2). |
| Compatibility / migration / enterprise impact stated | PASS | Spec §"Compatibility, Migration, and Enterprise Impact". |
| Local quality gate | PASS | Each package gates on `ruff` + `pytest` + `mypy --strict`; no new exemptions added. |
| Public behavior changes documented in `docs/` | PASS | FR-035 mandates a walkthrough page describing the policy authoring flow plus a typed-placeholder reference and per-user-story examples. |
| Staged migration, no implicit rename | PASS | No renames. Existing Spec 002 callers see new fields default to `None`; no behavior change without explicit `policy=` opt-in. |

**Gate result**: PASS. No violations. **Complexity Tracking** section below remains empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-sanitization-policy-core/
├── plan.md                  # This file (/speckit.plan output)
├── spec.md                  # Feature specification (with D1/D2/D3 baked in)
├── research.md              # Phase 0 — design decisions, naming, placement
├── data-model.md            # Phase 1 — every new public type with field-level descriptions
├── quickstart.md            # Phase 1 — operator + integrator + contributor walkthroughs
├── contracts/               # Phase 1
│   ├── README.md
│   ├── public-types.md       # ClarificationRequest, DecisionRecord, PolicyRule, PolicyRuleSet, TypedPlaceholder
│   ├── policy-router.md      # PolicyRouter Protocol shape, sync/async, failure mode
│   ├── strategy-registry.md  # StrategyRegistry contract, registered names, conflict resolution
│   ├── decision-record.md    # DecisionRecord schema, no-raw-payload rule, JSON serialization
│   └── placeholder-registry.md # TypedPlaceholder registry, default labels, override mechanism
├── checklists/
│   └── requirements.md      # Spec quality checklist (already closed — all items pass)
└── tasks.md                 # Phase 2 output (NOT created by /speckit.plan — see /speckit.tasks)
```

### Source code (additions to the existing workspace)

The `packages/{core,pip,api}` workspace established by Spec 002 is unchanged. Spec 003 ADDS modules; nothing is removed or renamed.

```text
packages/
├── core/                                  # arc-guard-core 0.1.0 → 0.2.0 (minor bump for additive change)
│   └── src/arc_guard_core/
│       ├── types.py                       # MODIFIED — adds ClarificationRequest dataclass, adds GuardResult.clarification field
│       ├── policy.py                      # NEW — PolicyRule, PolicyRuleSet, RiskBand enum, RiskThresholds
│       ├── decision.py                    # NEW — DecisionRecord, FindingSummary, TransformSummary
│       ├── placeholders.py                # NEW — TypedPlaceholder registry helpers (default labels + extension API)
│       ├── refusal/
│       │   └── templates.py               # NEW — RefusalTemplate registry mapping RefusalCode -> human_message + next_steps
│       ├── protocols/
│       │   └── policy_router.py           # NEW — PolicyRouter Protocol (sync, fail-closed, thread-safe)
│       ├── config.py                      # MODIFIED — adds GuardConfig.policy field (PolicyRuleSet | None, default None)
│       └── __init__.py                    # MODIFIED — re-exports new public surface
│
├── pip/                                   # arc-guard 0.2.0 → 0.3.0 (still in deprecation window for Spec 001 paths)
│   └── src/arc_guard/
│       ├── policy/                        # NEW DIRECTORY
│       │   ├── __init__.py
│       │   ├── router.py                  # RuleBasedPolicyRouter — default PolicyRouter implementation
│       │   ├── classifier.py              # RiskClassifier — pure function from findings to RiskBand
│       │   ├── conflict.py                # Strategy conflict resolver (block > redact > tokenize > hash > warn > pass)
│       │   └── aggregation.py             # Aggregation rules (e.g. three soft-PII findings → MEDIUM band)
│       ├── strategies/                    # MODIFIED
│       │   ├── __init__.py                # MODIFIED — registers built-ins on import
│       │   ├── registry.py                # NEW — StrategyRegistry, default-registered names
│       │   ├── redact.py                  # MODIFIED — emits typed placeholders per D2
│       │   ├── hash.py                    # MODIFIED — returns PolicyDecision per Spec 002 protocol
│       │   ├── block.py                   # MODIFIED — same
│       │   ├── warn.py                    # NEW — pass-through with rationale flag
│       │   └── tokenize.py                # NEW — deterministic per-input tokens
│       ├── pipeline.py                    # MODIFIED — wires PolicyRouter into the run path; emits DecisionRecord
│       ├── refusal/                       # NEW DIRECTORY
│       │   ├── __init__.py
│       │   └── builder.py                 # RefusalEnvelope builder using RefusalTemplate registry
│       └── decision/                      # NEW DIRECTORY
│           ├── __init__.py
│           └── emitter.py                 # Builds DecisionRecord from pipeline state, emits via Logger / Reporter / MetricSink
│
└── api/                                   # arc-guard-service 0.1.0 — unchanged in Spec 003
```

**Structure decision**: Spec 003 adds modules to the existing `core/pip/api` layout — no boundary changes. The new `policy/`, `refusal/`, and `decision/` directories under `packages/pip/src/arc_guard/` keep concerns separated and let Spec 005 (intent fidelity) plug into the same emitter without reshaping anything.

The Spec 002 boundary-enforcement scripts (`tools/check_*.py`) are unchanged; they audit the new modules automatically. The transitional `disable_error_code` block in `pip/pyproject.toml` shrinks as the legacy strategies move to the new registry-driven shape — Spec 003 reduces the override surface; Spec 005+ can finish the job.

## Complexity Tracking

> Constitution Check passed without violations. This section is intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| _(none)_  | _(n/a)_    | _(n/a)_                              |

## Phase 0 — Research output

[research.md](./research.md) resolves the following decisions before Phase 1 design:

1. Placement of new types — `core` for contracts, `pip` for implementations.
2. Strategy registry mechanism — module-level singleton vs DI; chose module-level singleton with explicit override hook.
3. Typed-placeholder index suffixing implementation — span-order iteration; numbering reset per input.
4. RiskClassifier aggregation defaults — counts and severities; configurable per `PolicyRuleSet`.
5. RefusalTemplate registry vs inline strings — registry, with fallback to a generic template per `RefusalCode`.
6. Pipeline integration point — replace the existing direct-action selection in `arc_guard.pipeline.GuardPipeline._run` with a `PolicyRouter` call.
7. DecisionRecord emission cadence — once per `_run`, after strategies apply, before reporter dispatch.
8. JSON serialization mechanism — pydantic-backed `model_dump_json` for the new pydantic models; manual `asdict` for the dataclass-backed records (no raw payloads).
9. Backwards-compatibility for the legacy `arc_guard.pipeline` chain — when `GuardConfig.policy is None`, the chain falls back to the existing one-strategy-from-flag behavior; no behavior change for Spec 001 callers who haven't opted in.
10. Tokenize strategy details — deterministic per-input token format `[CREDIT_CARD_TOK_1]`, `[CREDIT_CARD_TOK_2]`, …; cross-run determinism is not promised by Spec 003 (Spec 007+ may add per-tenant deterministic tokens via an injected secret).
11. Strategy conflict resolution table — fixed precedence `block > redact > tokenize > hash > warn > pass`; documented in contracts.
12. Walkthrough recipe for adding a custom strategy — single-page guide covering Protocol implementation, registry registration, policy authoring, and one fixture test.

Every NEEDS CLARIFICATION item from Technical Context is closed.

## Phase 1 — Design output

Phase 1 produces five artifacts:

- [data-model.md](./data-model.md) — every new public type from FR-001 / FR-005 / FR-021 / D1, with field-level descriptions, validation rules, stability markers, and JSON-serialization rules.
- [contracts/](./contracts/) — five contract documents covering public types, the `PolicyRouter` Protocol, the strategy registry, the decision-record schema (with the no-raw-payload rule), and the placeholder registry. These are the externally observable surface of Spec 003.
- [quickstart.md](./quickstart.md) — three walkthroughs: operator authors a `PolicyRuleSet`, integrator runs a multi-strategy input end-to-end, contributor adds a custom strategy.
- Agent context refresh — `.specify/scripts/bash/update-agent-context.sh claude` runs to add the Spec 003 tech context to `CLAUDE.md` between the managed markers.
- Spec 002 contract test suite extension — the existing snapshots gain entries for the new public types; this happens during Phase 2 implementation but is documented here so the contract tests pass cleanly when the new types land.

## Phase 2 — Tasks (NOT generated by /speckit.plan)

Per the SpecKit convention, `tasks.md` is produced by `/speckit.tasks` from this plan. The plan establishes:

- Implementation is staged in three batches: (A) core additive types and protocol, (B) pip implementation modules (router, registry, strategies, refusal builder, decision emitter), (C) pipeline integration + decision emission + walkthrough doc.
- Spec 002's contract snapshot is updated as part of batch A; the additive-change CHANGELOG entries land with the same commit so the contract test suite passes throughout.
- Tests for each batch land in the same commit as the implementation — TDD where applicable (router conflict resolution, risk aggregation, refusal builder, decision-record schema).

## Re-evaluation: Constitution Check (post-design)

Phase 1 introduces no new principle conflicts. The contract documents reinforce Principles I–V rather than relax them; the no-raw-payload rule for `DecisionRecord` is captured contractually with a contract test that scans serialized records for forbidden substrings. Re-check status: **PASS** with no entries added to Complexity Tracking.

## Notes for downstream specs

- **Spec 004** (Observability and Runtime Hardening) wires real OTEL spans through the same `Tracer` / `Logger` / `MetricSink` hooks Spec 002 stubbed and Spec 003 emits to. The hook surface is stable; only the implementations change.
- **Spec 005** (Safe Rehydration and Intent Fidelity) extends `GuardResult` and `RefusalEnvelope` *additively* with fidelity-related fields. Spec 003's `DecisionRecord` already has a `transforms` slot that Spec 005 fills with intent-aware rehydration data.
- **Spec 006** (Jailbreak, Deception, Evaluation) adds new inspectors that produce findings with `entity_type=INJECTION` / `JAILBREAK`. The policy router routes them through the existing `block` strategy — no router changes needed unless multi-turn state lands as a new finding category.
- **Spec 007** (Integration, API, Documentation) wires `arc_guard_service` request handlers to populate `GuardConfig.policy` from request payloads or environment, then return the resulting `GuardResult` (including `decisions`, `refusal`, `clarification`) as the API response.
