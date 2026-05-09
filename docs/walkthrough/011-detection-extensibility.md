# Walkthrough — Spec 011: Detection Extensibility

This page is the operator-facing summary of [Spec 011](../../specs/011-detection-extensibility/spec.md). It documents three new detection capabilities — automatic masking strategy selection, semantic content policies, and code-injection inspectors — all shipped as additive surfaces with no api package changes.

## What changed

Five deliverables, all additive:

| Deliverable | Where |
|---|---|
| `StrategySelector` and `ContentPolicy` Protocols (runtime_checkable) + `ContentPolicyDecision` frozen dataclass — operator-extension surface for picking a strategy per detected entity, and for evaluating a policy at the rule level | [`packages/core/src/arc_guard_core/protocols/`](../../packages/core/src/arc_guard_core/protocols/) |
| `PolicyRule.selector` — new optional field (mutually exclusive with `strategy`); existing policy files parse identically | [`packages/core/src/arc_guard_core/policy.py`](../../packages/core/src/arc_guard_core/policy.py) |
| Three new `RefusalCode` values (`SQL_INJECTION`, `SHELL_INJECTION`, `TEMPLATE_INJECTION`) with default operator-customizable `RefusalTemplate` entries | [`packages/core/src/arc_guard_core/refusal/`](../../packages/core/src/arc_guard_core/refusal/) |
| `arc_guard.selectors` and `arc_guard.content_policies` subpackages — `DefaultStrategySelector` (auto-registered under `"default"`) plus `SemanticContentPolicy` (under the existing `[semantic]` extra) plus aggregate-evaluation helper | [`packages/pip/src/arc_guard/selectors/`](../../packages/pip/src/arc_guard/selectors/), [`packages/pip/src/arc_guard/content_policies/`](../../packages/pip/src/arc_guard/content_policies/) |
| `arc_guard.inspectors.code_injection` subpackage — `SqlInjectionInspector` (under new `[code-injection]` extra), `ShellInjectionInspector` (stdlib), `TemplateInjectionInspector` (stdlib); structured fingerprint payload by default, opt-in raw-match capture per inspector | [`packages/pip/src/arc_guard/inspectors/code_injection/`](../../packages/pip/src/arc_guard/inspectors/code_injection/) |

The decision contract from Specs 002–006 and the lifecycle event taxonomy from Spec 010 are unchanged. Spec 011 ships purely additive surfaces — no deprecations, no renames, the api package is untouched.

## Why

Without this spec, every PII-aware deployment had to write twelve hand-bindings of `strategy:` per rule; every "block this topic" policy had to ship a regex over keyword lists that misses paraphrases; and every operator running an LLM in front of a SQL/shell/template-rendering tool had no defense against the data-flowing-into-tools direction (the existing `InjectionInspector` covers prompt-injection, not code-injection).

The three capabilities together make the framework decide what the operator previously had to specify:

- **Automatic masking** — operators say "use the default selector"; the framework picks per-entity strategies (`redact` for free-text PII, `hash` for stable identifiers, `block` for credentials, `tokenize` for internal identifiers, `warn` for low-sensitivity context). Removes the most-touched policy surface from operator hands.
- **Semantic content policies** — operators provide three to ten exemplars and a similarity threshold; the framework rejects requests whose semantic distance from the exemplar set falls below threshold, catching paraphrases keyword logic would miss. Reuses the spec-005 intent encoder under the existing `[semantic]` extra.
- **Code-injection detection** — three new inspectors flag SQL stacked statements, shell command-substitution / chaining, and template-engine sandbox-escape sigils. Each fires independently; each produces a distinct `RefusalCode`. Default phase wiring is post-process only (the threat model is LLM-output-then-executed-by-tools); pre-process scanning is an opt-in for operators with template-rendered prompts.

## Public surface

The following names are tracked in [`docs/public-surface.md`](../public-surface.md) under `arc_guard_core`:

| Symbol | Kind | Band | Notes |
|---|---|---|---|
| `StrategySelector` | class | Stable | Runtime_checkable Protocol; pick a strategy name per finding |
| `ContentPolicy` | class | Stable | Runtime_checkable Protocol; evaluate input as a policy predicate |
| `ContentPolicyDecision` | class | Stable | Frozen dataclass; carries match, confidence, name, code |

The package root arc_guard is kept mainly for migration compatibility per the manifest convention; bundled implementations live under arc_guard.selectors, arc_guard.content_policies, and arc_guard.inspectors.code_injection and are documented in the operator-usage section below rather than the manifest.

## Migration

Zero migration burden for existing operators:

- Existing policy files using `strategy: ...` continue to load and evaluate identically. The `selector` field defaults to None.
- `PolicyRule.strategy: str` became `PolicyRule.strategy: str | None = None` (a typing relaxation, not a tightening). Any code reading `rule.strategy` and assuming non-None must now check `if rule.strategy is not None:` — but the only such code lives inside `arc_guard.pipeline` and the strategy-resolution helpers, all updated as part of this spec.
- The new `[code-injection]` extra is opt-in. Operators who don't install it import `arc_guard` normally; importing `SqlInjectionInspector` lazy-fails with a clear install hint.
- Code-injection lifecycle events carry a structured fingerprint by default — no raw matched text. Operators who explicitly want raw match capture pass `capture_raw_matches=True` per inspector.

## Operator usage examples

### Capability 1 — automatic masking

Before:

```yaml
rules:
  - id: pii-email
    match: pii.EMAIL_ADDRESS
    strategy: redact
  - id: pii-ssn
    match: pii.US_SSN
    strategy: hash
  - id: pii-credit-card
    match: pii.CREDIT_CARD
    strategy: block
  # ... 9 more rules ...
```

After:

```yaml
rules:
  - id: pii-email
    match: pii.EMAIL_ADDRESS
    selector: default
  - id: pii-ssn
    match: pii.US_SSN
    selector: default
  - id: pii-credit-card
    match: pii.CREDIT_CARD
    selector: default
```

Each rule's strategy is now picked at runtime by `DefaultStrategySelector` based on the finding's `entity_type`. Operators override per entity type via `DefaultStrategySelector(mapping={...})` and re-register.

### Capability 2 — semantic content policies

```python
from arc_guard.content_policies import SemanticContentPolicy, register_content_policy

policy = SemanticContentPolicy(
    name="competitor_pricing",
    exemplars=(
        "What does $competitor charge for tier-2 service?",
        "Compare $our_company prices vs $competitor",
        "How much does $competitor's enterprise plan cost?",
    ),
    similarity_threshold=0.78,
)
register_content_policy("competitor_pricing", policy)
```

The pipeline's content-policy evaluator (helper at `arc_guard.content_policies.aggregate`) iterates every registered policy, records each match as a separate finding, and assembles a refusal envelope citing the first-fired policy as the primary code with all firing policy names in `metadata.firing_policies`.

### Capability 3 — code-injection detection

```python
from arc_guard import GuardPipeline
from arc_guard.inspectors.code_injection import (
    SqlInjectionInspector,
    ShellInjectionInspector,
    TemplateInjectionInspector,
)

pipeline = GuardPipeline(
    inspectors=[
        SqlInjectionInspector(),         # default phase: post_process
        ShellInjectionInspector(),
        TemplateInjectionInspector(phases={"pre_process", "post_process"}),
    ],
)
```

Each inspector has a `phases=` constructor arg defaulting to `frozenset({"post_process"})` — operators with template-rendered prompts opt the template inspector into pre-process by passing both phases explicitly.

## Failure-mode summary

| Capability | Default failure | Closed-posture trigger |
|---|---|---|
| `DefaultStrategySelector` mapping miss | Falls back to `redact` + structured observability event identifying the unmapped entity type | — |
| `StrategySelector` raises | Pipeline emits closed-posture refusal (StrategyError → STRATEGY_FAILED via FAIL_RULE) | exception escapes select() |
| `SemanticContentPolicy` with missing `[semantic]` extra | No-op + warning event; deployment continues | — |
| `SemanticContentPolicy` with missing model artifact | `ConfigSchemaError` at construction, distinct from missing-extra | model load failure |
| Code-injection inspector unparseable input | No finding + `guard.code_injection.unparseable_input` event | — |
| Code-injection inspector raises | Pipeline emits closed-posture refusal (StrategyError → STRATEGY_FAILED) | parser bug |

## Where to look next

- Spec body: [spec.md](../../specs/011-detection-extensibility/spec.md)
- Plan: [plan.md](../../specs/011-detection-extensibility/plan.md)
- Contracts: [contracts/](../../specs/011-detection-extensibility/contracts/)
- Quickstart: [quickstart.md](../../specs/011-detection-extensibility/quickstart.md)
- Changelogs: [packages/core/CHANGELOG.md](../../packages/core/CHANGELOG.md), [packages/pip/CHANGELOG.md](../../packages/pip/CHANGELOG.md)
