# Phase 0 — Research: Sanitization and Policy Core

**Feature**: 003-sanitization-policy-core
**Date**: 2026-05-01
**Purpose**: Resolve every "NEEDS CLARIFICATION" before Phase 1 design starts. Each item below has a Decision, a Rationale, and Alternatives Considered. The three contract-level Q1/Q2/Q3 questions were already resolved as decisions D1, D2, D3 in spec.md before this command ran — they are not repeated here.

---

## 1. Placement of new public types

**Question**: Where do `PolicyRule`, `PolicyRuleSet`, `PolicyRouter`, `DecisionRecord`, `ClarificationRequest`, and the `TypedPlaceholder` registry helpers live?

**Decision**:
- **Contracts** (no provider deps, snapshot-tracked): `arc_guard_core.types` (frozen dataclasses for `ClarificationRequest`, `DecisionRecord`, `FindingSummary`, `TransformSummary`), `arc_guard_core.policy` (pydantic models for `PolicyRule`, `PolicyRuleSet`, `RiskBand` enum, `RiskThresholds`), `arc_guard_core.placeholders` (registry helpers + default labels), `arc_guard_core.refusal.templates` (`RefusalTemplate` registry), `arc_guard_core.protocols.policy_router` (`PolicyRouter` Protocol).
- **Implementations** (in `pip`): `arc_guard.policy.router` (`RuleBasedPolicyRouter`), `arc_guard.policy.classifier`, `arc_guard.policy.conflict`, `arc_guard.policy.aggregation`, `arc_guard.strategies.registry` (`StrategyRegistry`), `arc_guard.strategies.{warn,tokenize}.py`, `arc_guard.refusal.builder`, `arc_guard.decision.emitter`.

**Rationale**:
- Contracts in `core` keep the snapshot test suite as the single change-detection point for Spec 003's additive surface.
- Implementations in `pip` keep `core` zero-dep — even hashlib / secrets imports stay in pip.
- The split mirrors Spec 002's `core` vs `pip` philosophy exactly: `core` is shape, `pip` is behavior.

**Alternatives considered**:
- *All implementations in core*: rejected — pollutes the contract layer with policy logic that may evolve independently of the Protocol.
- *Inline policy rules into `GuardConfig`*: rejected — `PolicyRuleSet` is a complex enough domain to warrant its own model.

---

## 2. Strategy registry mechanism

**Question**: How are strategies discovered and resolved by name?

**Decision**: A **module-level singleton** `StrategyRegistry` in `arc_guard.strategies.registry`. Built-ins (`redact`, `hash`, `block`, `warn`, `tokenize`) register on import. User strategies register via `registry.register(name, strategy)` or via a decorator `@register_strategy("name")`. The registry is thread-safe (RLock) and validated at policy-load time — `PolicyRuleSet` validation rejects unknown strategy names with `ConfigCrossFieldError`.

**Rationale**:
- Module-level singleton mirrors how `EntityRegistry` already works in Spec 002 (`packages/core/src/arc_guard_core/registry.py`). Consistency over novelty.
- Tests can install a custom registry by patching the module attribute (Python's standard pattern).
- Validation at policy-load time catches the "unknown strategy name" case eagerly, not at first use.

**Alternatives considered**:
- *DI through `GuardConfig`*: rejected — adds boilerplate for the 99% case where built-ins are sufficient. DI is still possible by passing a custom registry into `RuleBasedPolicyRouter`.
- *Entry-point–based plugin discovery (importlib.metadata)*: rejected — adds packaging complexity for a marginal benefit; user strategies are typically per-application, not redistributable plugins.

---

## 3. Typed-placeholder index suffixing implementation

**Question**: How does the redact strategy emit `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]` per D2?

**Decision**: The redact strategy iterates findings in **span order** (ascending `start`). For each entity type, it maintains a per-type counter scoped to the current input. The first occurrence renders as `[<TYPE>]`; subsequent occurrences render as `[<TYPE>_<N>]` starting at `N=2`, OR — if the strategy detects more than one match for a given type *before* emitting the first replacement — it renders the first as `[<TYPE>_1]` and subsequent as `[<TYPE>_2]`, etc.

**Rationale**:
- D2 says "single occurrence remains unsuffixed; multiple occurrences are suffixed". Pre-counting per type gives the correct format on first emission.
- Span-order iteration is deterministic and matches how a reader scans the text. `Finding` objects already carry `start` so sorting is trivial.
- The placeholder format is part of the public contract; the index belongs to the input, not to global state — no cross-run leakage.

**Alternatives considered**:
- *Always suffix (`[CREDIT_CARD_1]` even for one card)*: rejected — D2 explicitly chose unsuffixed for the single case to keep simple inputs readable.
- *Suffix from `0`*: rejected — humans count from 1 in this context.

**Implementation note**: the per-type counter is computed in two passes: first pass counts occurrences per type; second pass emits with the right format. This is O(n) and simple.

---

## 4. RiskClassifier aggregation defaults

**Question**: What are the default risk thresholds and aggregation rules?

**Decision**:

```python
DEFAULT_RISK_THRESHOLDS = RiskThresholds(
    low_max_count=2,        # ≤ 2 LOW findings → LOW band
    medium_max_count=4,     # ≤ 4 MEDIUM findings → MEDIUM band
    high_escalates_at=1,    # any HIGH finding → HIGH band
    critical_escalates_at=1,# any CRITICAL finding → CRITICAL band
    soft_pii_aggregation=3, # 3+ LOW findings escalate to MEDIUM
)
```

The aggregate band is the **maximum** of:
- the per-finding ceiling (any CRITICAL → CRITICAL; any HIGH → HIGH; etc.), and
- the count-based escalation (3+ LOW → MEDIUM; 5+ MEDIUM → HIGH).

**Rationale**:
- Rules are configurable per `PolicyRuleSet`; the defaults match the roadmap §2.3 narrative.
- The "soft PII aggregation" rule operationalizes the principle that several low-risk leaks combine into something worse — a known issue with naive guardrails.
- Pure function over findings — no external state.

**Alternatives considered**:
- *Severity-weighted scoring (sum of severity values)*: rejected for the default — harder to explain, harder to tune. Could be added as a custom classifier later.
- *Configurable function plug-in*: deferred — users who need custom aggregation can subclass `RuleBasedPolicyRouter` or pass a custom `PolicyRouter` impl.

---

## 5. RefusalTemplate registry vs inline strings

**Question**: How does the refusal builder produce the `human_message` and `next_steps` for a `RefusalEnvelope`?

**Decision**: A `RefusalTemplate` registry in `arc_guard_core.refusal.templates` maps each `RefusalCode` to a default template:

```python
DEFAULT_REFUSAL_TEMPLATES = {
    RefusalCode.JAILBREAK: RefusalTemplate(
        human_message="This request was blocked because it appeared to attempt jailbreaking the system.",
        next_steps=("Rephrase without language that asks the assistant to ignore its rules.",),
    ),
    RefusalCode.PII_CRITICAL: RefusalTemplate(
        human_message="This request contained sensitive personal information that cannot be processed.",
        next_steps=(
            "Remove personally identifying details before re-submitting.",
            "Use a placeholder description instead of real names or numbers.",
        ),
    ),
    RefusalCode.STRATEGY_FAILED: RefusalTemplate(
        human_message="An internal processing step failed; the request was blocked as a safety measure.",
        next_steps=("Retry the request.", "Contact support if the issue persists."),
    ),
    RefusalCode.POLICY_BLOCK: RefusalTemplate(
        human_message="This request was blocked by policy.",
        next_steps=("Adjust the request and try again.",),
    ),
    RefusalCode.FIDELITY_DROP_PLACEHOLDER: RefusalTemplate(
        human_message="(reserved for Spec 005)",
        next_steps=(),
    ),
}
```

`PolicyRule` may override either field per rule. The builder uses the rule-level override if present; otherwise the registered default.

**Rationale**:
- A registry keeps the messages auditable and translatable without scattering string literals across the codebase.
- Per-rule overrides give operators full control without forcing them to override the default.
- Templates are typed; the contract test verifies all `RefusalCode` values have a registered template.

**Alternatives considered**:
- *Inline strings in the policy*: rejected — duplication, drift risk, harder to localize.
- *Format-string templates with placeholders*: deferred — adds complexity; can be retrofitted in Spec 005 if needed.

---

## 6. Pipeline integration point

**Question**: How does the existing `arc_guard.pipeline.GuardPipeline._run` get the new policy-routing behavior without breaking Spec 001 callers?

**Decision**: Inside `_run`, replace the existing direct-action selection (which currently picks one strategy from a flag) with this flow:

1. Run the inspector chain (unchanged).
2. If `self.config.policy is None` → preserve Spec 001 behavior: pick one strategy from `flags.get_string("action_strategy", "redact")`, apply it to the full text, return.
3. If `self.config.policy is not None` → invoke `PolicyRouter.route(result, self.config.policy)`, get back the per-finding decisions and aggregate band, apply each decision's strategy in span order, build the `RefusalEnvelope` if HIGH or CRITICAL, build the `ClarificationRequest` if ambiguous, populate `GuardResult.decisions`, `refusal`, `clarification`, set `action` per FR-011, build and emit the `DecisionRecord`, return.

**Rationale**:
- Branch-by-`policy is None` keeps Spec 001 callers behavior-stable. The new path is fully opt-in.
- The integration point is the smallest possible change to the pipeline's public flow.
- The router never runs when `policy is None`, which means zero overhead for callers that haven't migrated.

**Alternatives considered**:
- *Always run the router with an empty `PolicyRuleSet` as the default*: rejected — would force every caller to populate `policy=` to avoid an empty-policy block, which is a behavior change.
- *Make the router a Middleware*: rejected — middleware are pre/post hooks, not transform stages. Routing IS the transform stage.

---

## 7. DecisionRecord emission cadence

**Question**: When and how often is a `DecisionRecord` emitted?

**Decision**: Once per `_run`, after strategies apply and the `GuardResult` is finalized, before the reporter is invoked. Emission goes through three Spec 002 hooks:

- `Logger.event("guard.decision", level="info", **record_dump)` — structured log line.
- `MetricSink.counter("guard.decisions", attributes={"action": result.action, "risk_band": band})` — count metric.
- `MetricSink.histogram("guard.findings_count", len(result.findings))` — distribution.
- The `Reporter.report(result)` call (existing) sees the `DecisionRecord` via `result` (the record is included in the `GuardResult` only via the `decisions` field — the full `DecisionRecord` is available through a side channel: the emitter's last-built record is held on `pipeline._last_decision` for tests, but the canonical pathway is the logger event).

**Rationale**:
- One record per run keeps the audit trail clean.
- The three hooks correspond to three different consumer needs: humans (logger), dashboards (metrics), forwarders (reporter).
- Including the full record on `GuardResult` would bloat the public type; the `DecisionRecord` lives in logs / events / a side accessor for tests.

**Alternatives considered**:
- *Embed the full DecisionRecord in `GuardResult`*: rejected — too much surface area for the typical caller; the existing `decisions` tuple is the right level for the result type.
- *Emit per-finding records*: rejected — too noisy. One record per run is the audit unit.

---

## 8. JSON serialization mechanism

**Question**: How are `DecisionRecord`, `ClarificationRequest`, `PolicyRuleSet` serialized to JSON for events and config dumps?

**Decision**:
- **Pydantic-backed types** (`PolicyRule`, `PolicyRuleSet`, `RiskThresholds`): use `model.model_dump_json()` and `model.model_validate_json()`.
- **Frozen dataclass types** (`DecisionRecord`, `ClarificationRequest`, `FindingSummary`, `TransformSummary`): use `dataclasses.asdict()` + `json.dumps()`. Default values are stable; tests assert serialized output matches the contract snapshot.

**Rationale**:
- Mirrors the Spec 002 split: pydantic at boundaries (validation), dataclasses for internal value types.
- JSON output for both kinds is simple and stable.
- The contract test suite already snapshots both kinds via the runtime introspection in `_snapshot.py`.

**Alternatives considered**:
- *All-pydantic*: rejected — extra overhead for the high-frequency `DecisionRecord` build path.
- *Custom encoder*: deferred — only needed if a field type is not natively JSON-serializable. None expected.

---

## 9. Backward compatibility with Spec 001 pipeline

**Question**: What does a Spec 001 caller see if they upgrade to the Spec 003 release of `arc-guard` without setting `GuardConfig.policy`?

**Decision**: Identical behavior to Spec 002. The pipeline detects `policy is None` and falls back to the existing one-strategy-from-flag chain. No visible difference in `GuardResult`. The `GuardResult.decisions` and `clarification` fields default to `()` and `None` respectively. No DecisionRecord is emitted (since the policy router never ran).

**Rationale**:
- Strict opt-in for the new behavior — zero breakage for existing callers.
- Anyone wanting the new behavior sets `policy=PolicyRuleSet(...)`.

**Alternatives considered**:
- *Auto-derive a default `PolicyRuleSet` from `flags.get_string("action_strategy")`*: rejected — silently changes behavior for callers who didn't ask for it.

---

## 10. Tokenize strategy details

**Question**: What does the `tokenize` strategy emit, and is it deterministic across runs?

**Decision**: For Spec 003, `tokenize` emits **deterministic per-input** tokens with the format `[<TYPE>_TOK_<N>]`, where `<N>` is the per-type sequence number for the input (1-indexed). Cross-run determinism is NOT promised — the same credit-card number in two different inputs gets the same token only by coincidence.

**Rationale**:
- Per-input determinism is sufficient for in-conversation referentiality (the LLM can refer to "the first card" by its token).
- Cross-run determinism requires a per-tenant secret and is out of scope for Spec 003. Spec 007 may add it through dependency injection of a secret-bound tokenizer.
- The contract test verifies the per-input deterministic format only.

**Alternatives considered**:
- *Cross-run-deterministic HMAC tokens*: deferred — needs secret management, which is Spec 007 territory.
- *UUID-based tokens*: rejected — non-deterministic even within a single input, breaks LLM referentiality.

---

## 11. Strategy conflict resolution

**Question**: When two policy rules apply to the same finding with different strategies, which wins?

**Decision**: Fixed precedence (highest to lowest restrictiveness):

```
block > redact > tokenize > hash > warn > pass
```

The router selects the **most restrictive** strategy when there's a tie on match. The decision rationale records the conflict resolution: `"rule_id_X (strategy=block) overrode rule_id_Y (strategy=hash)"`.

**Rationale**:
- Deterministic, easy to reason about, easy to test.
- "Restrictive" is the safer default — operators can always loosen by removing the more-restrictive rule.
- Documenting the resolution in the rationale gives auditors the trail.

**Alternatives considered**:
- *Rule-order precedence (first match wins)*: rejected — depends on declaration order which is fragile.
- *Configurable precedence per `PolicyRuleSet`*: deferred — single fixed table is simpler and matches the constitution's "fail-safe" preference.

---

## 12. Walkthrough recipe for adding a custom strategy

**Question**: What does the contributor walkthrough look like (FR-025, User Story 7)?

**Decision**: A single-page recipe (in `quickstart.md` §C) covering:

1. Implement a class satisfying the `arc_guard_core.protocols.strategy.ActionStrategy` Protocol — specifically the `apply(text, findings) -> tuple[str, Sequence[PolicyDecision]]` method and the `name: str` attribute.
2. Register at startup: `from arc_guard.strategies.registry import register_strategy` then either decorator or imperative call.
3. Author a `PolicyRule` referencing the strategy by name in a `PolicyRuleSet`.
4. Write one fixture test that runs an input through the pipeline with the custom strategy in the policy and asserts the output contains tokens (or whatever the strategy emits) and that `decisions[0].strategy == "your_name"`.
5. Confirm `tools/check_import_graph.py` still passes (no `core` import from the user strategy).

**Rationale**:
- A linear recipe matches how integrators read docs.
- One fixture test is enough to lock the contract; users add more for their own logic.
- The import-graph step is the safety net that catches accidental coupling.

**Alternatives considered**:
- *Multi-page tutorial*: rejected — wrong audience for the rewrite-foundation era. Operators want recipes, not curricula.

---

## Summary table

| Topic | Decision |
|---|---|
| 1 — Type placement | Contracts in `core`; implementations in `pip` |
| 2 — Strategy registry | Module-level singleton + decorator + thread-safe RLock |
| 3 — Placeholder suffixing | Two-pass span-order iteration; first occurrence unsuffixed; subsequent `_1`, `_2`, … in declaration order |
| 4 — Risk aggregation defaults | `low ≤ 2`, `medium ≤ 4`, `high → HIGH`, `critical → CRITICAL`, `3+ soft PII → MEDIUM`; configurable |
| 5 — Refusal templates | Registry mapping `RefusalCode` → `RefusalTemplate`; per-rule overrides allowed |
| 6 — Pipeline integration | Branch on `config.policy is None`: keep Spec 001 behavior or invoke `PolicyRouter` |
| 7 — DecisionRecord cadence | One per `_run`, after strategies, before reporter; via `Logger` / `MetricSink` |
| 8 — JSON serialization | Pydantic for boundary models, dataclasses + `asdict` for internal records |
| 9 — Spec 001 backward compat | `policy is None` → identical Spec 002 behavior |
| 10 — Tokenize details | Per-input deterministic `[<TYPE>_TOK_<N>]`; cross-run determinism is Spec 007 |
| 11 — Strategy conflict | Fixed precedence `block > redact > tokenize > hash > warn > pass`; recorded in rationale |
| 12 — Custom strategy walkthrough | Linear 5-step recipe in `quickstart.md` §C |

All NEEDS CLARIFICATION items resolved. Phase 1 design proceeds.
