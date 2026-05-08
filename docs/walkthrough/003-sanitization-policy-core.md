# Walkthrough — Spec 003: Sanitization and Policy Core

This page is the operator-facing summary of [Spec 003](../../specs/003-sanitization-policy-core/spec.md). It documents the typed-placeholder registry, the policy authoring flow, the four risk bands, the clarification flow, and what a decision record looks like.

## What changed

Spec 003 ships the **sanitize** stage of the rewrite roadmap's four-stage pipeline (sanitize → defend → generate → verify-and-rehydrate) and the **composable policy router** that drives it. Built-in strategies grew from 3 to 5 (added `warn`, `tokenize`); the redact strategy now emits typed placeholders per a registered set.

## Why

Spec 002's pipeline ran inspectors but had no shared way to decide what to do with their findings — every strategy made its own choice. Operators authoring policy had no typed declarative surface; partial-refusal (sanitize-and-warn) was impossible. Spec 003 introduces the policy router as the single decision point, the four risk bands as the dispatch ladder, and typed placeholders so sanitized text remains intelligible to the LLM. The clarification flow gives the system a third option between "pass" and "block" for ambiguous-band runs.

## Public surface

| Symbol | Kind | Band | Notes |
|---|---|---|---|
| `RiskBand` / `RiskThresholds` | enum / class | stable | Four-band risk ladder + tunable thresholds. |
| `PolicyRule` / `PolicyRuleSet` | class | stable | Declarative rule authoring. |
| `RoutedOutcome` / `TransformSummary` | dataclass | stable | Per-rule routing artifacts. |
| `DecisionRecord` / `FindingSummary` | dataclass | stable | Run-level audit record (extended by later specs). |
| `ClarificationRequest` | dataclass | stable | Ask-for-rephrase envelope; mutually exclusive with `action="block"`. |
| `RefusalTemplate` / `DEFAULT_REFUSAL_TEMPLATES` / `register_refusal_template` / `get_refusal_template` | class / function | stable | Refusal-text registry. |
| `DEFAULT_PLACEHOLDERS` / `register_placeholder` / `get_placeholder` / `format_placeholder` | dict / function | stable | Typed-placeholder registry (D2 multi-occurrence rule). |
| `PolicyRouter` | protocol | stable | Pluggable router; default `RuleBasedPolicyRouter` lives in `arc_guard`. |

See [`docs/public-surface.md`](../public-surface.md) for the complete manifest.

## Quick example

```python
from arc_guard_core.policy import PolicyRule, PolicyRuleSet, RiskThresholds
from arc_guard_core.types import GuardInput
from arc_guard.pipeline import GuardPipeline

policy = PolicyRuleSet(
    rules=(
        PolicyRule(id="r_email", match="EMAIL_ADDRESS", strategy="redact"),
        PolicyRule(id="r_card", match="CREDIT_CARD", strategy="hash"),
        PolicyRule(id="r_inj", match="INJECTION", strategy="block"),
        PolicyRule(id="r_name", match="CUSTOMER_NAME", strategy="warn"),
    ),
    risk_thresholds=RiskThresholds(),
)

pipeline = GuardPipeline(policy_ruleset=policy)
result = pipeline.pre_process_sync(
    GuardInput(text="Email alice@acme.com about card 4111-1111-1111-1111"),
)
print(result.text)              # sanitized text with typed placeholders
print(result.action)            # aggregate action (D3)
print(result.refusal)           # populated for HIGH or CRITICAL bands
print(result.clarification)     # populated when policy classifies as ambiguous
```

## Typed placeholder registry

Default labels (registered on import):

| Entity type | Label |
|---|---|
| `EMPLOYEE_NAME` | `[EMPLOYEE_NAME]` |
| `CUSTOMER_NAME` | `[CUSTOMER_NAME]` |
| `INTERNAL_PROJECT` | `[INTERNAL_PROJECT]` |
| `CONFIDENTIAL_LOCATION` | `[CONFIDENTIAL_LOCATION]` |
| `EMAIL_ADDRESS` | `[EMAIL_ADDRESS]` |
| `PHONE_NUMBER` | `[PHONE_NUMBER]` |
| `CREDIT_CARD` | `[CREDIT_CARD]` |
| `US_SSN` | `[US_SSN]` |
| `IP_ADDRESS` | `[IP_ADDRESS]` |
| `UNKNOWN_PII` | `[UNKNOWN_PII]` |

Multi-occurrence rule (D2): a single occurrence renders unsuffixed (`[CREDIT_CARD]`); multiple occurrences in the same input render as `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`, … in span order. Numbering resets per input.

Custom types register at startup:

```python
from arc_guard_core.placeholders import register_placeholder
register_placeholder("AADHAAR", "[AADHAAR]")
```

## The four risk bands (D3)

| Band | What the pipeline does |
|---|---|
| **LOW** | Sanitize and continue. `action` is policy-driven (typically `redact` / `hash` / `tokenize`). `refusal is None`. |
| **MEDIUM** | Sanitize and warn. `action` as for LOW; the leading decision's rationale flags `warn:`. `refusal is None`. |
| **HIGH** | **Partial refusal**. `text` is fully sanitized. `action` is policy-driven and **never** `block`. `refusal` is populated, describing what was withheld. Caller renders both at its discretion. |
| **CRITICAL** | Hard block. `action == "block"`, `text == ""`, `refusal` populated. |

Aggregation defaults: any HIGH finding → HIGH; any CRITICAL → CRITICAL; ≥3 LOW findings → MEDIUM. Override per `PolicyRuleSet.risk_thresholds`.

## Strategy precedence

When two rules match the same finding with different strategies, the most-restrictive wins:

```
block > redact > tokenize > hash > warn > pass
```

The losing rules are recorded in the winning `PolicyDecision.rationale`. Equal-precedence ties resolve by declaration order in the rule set.

## Built-in strategies

| Name | Output | Use case |
|---|---|---|
| `redact` | `[<TYPE>]` typed placeholder | Default privacy mask. Preserves intent for the LLM. |
| `hash` | `[HASH:<8 hex>]` HMAC-SHA256 prefix | Pseudonymization for analytics joins. |
| `tokenize` | `[<TYPE>_TOK_<N>]` per-input deterministic | LLM can refer to "the first card" by token. |
| `block` | empty span; router builds the `RefusalEnvelope` | Hard block. |
| `warn` | pass-through; rationale prefixed `warn:` | Observability marker without transformation. |

Custom strategies register via `arc_guard.strategies.registry.register_strategy(name, instance)` or the `@strategy("name")` decorator. They satisfy the `ActionStrategy` Protocol from `arc_guard_core.protocols.strategy`.

## Operator knobs

| Knob | Default | Effect |
|---|---|---|
| `PolicyRuleSet.risk_thresholds` | `RiskThresholds()` | Override the LOW/MEDIUM/HIGH/CRITICAL aggregation rules. |
| `PolicyRuleSet.clarification_enabled` | `False` | Opt into the third-option clarification flow for ambiguous-band runs. |
| `PolicyRuleSet.ambiguous_threshold` | `RiskBand.MEDIUM` | Which band triggers clarification rather than refusal. |
| `register_placeholder(entity_type, label)` | n/a | Register custom typed placeholders at startup. |
| Custom `PolicyRouter` impl | `RuleBasedPolicyRouter` | Plug a fully custom routing strategy via the `PolicyRouter` Protocol. |

## Clarification flow

Opt-in. When `PolicyRuleSet.clarification_enabled=True` and the run's aggregate band equals `ambiguous_threshold` (default `MEDIUM`), the router returns a `ClarificationRequest` instead of a hard refusal:

```python
policy = PolicyRuleSet(
    rules=(...),
    clarification_enabled=True,
    ambiguous_threshold=RiskBand.MEDIUM,
)

result = pipeline.pre_process_sync(GuardInput(text="my partial card 4111"))
if result.clarification is not None:
    print(result.clarification.suggested_rephrase)
    print(result.clarification.next_steps)
```

Critical findings never trigger clarification — they always block.

## Decision records

Every routed run produces a `DecisionRecord` summarizing what happened. The record is emitted through the Spec 002 observability hooks (`Logger.event("guard.decision", ...)`, `MetricSink.counter`, `MetricSink.histogram`) and exposed on `pipeline._last_decision` for tests.

The record never contains raw payloads (FR-023): findings carry only `(start, end, length)` offsets and the entity type; transforms carry strategy id and length deltas. The contract test `tests/contract/test_no_raw_payload_in_decision_record.py` automatically enforces this on every PR.

## What's next

Spec 004 wires real OTEL spans through the `Tracer` / `Logger` / `MetricSink` hooks Spec 003 emits to. Spec 005 reintroduces semantic inspection under the intent-fidelity contract. Spec 006 adds adversarial corpora and the comparative evaluation harness. Spec 007 wires the `arc-guard-service` deployment surface that consumes everything Spec 003 produces.

## References

- [Spec 003 — Sanitization and Policy Core](../../specs/003-sanitization-policy-core/spec.md)
- [Spec 003 contracts](../../specs/003-sanitization-policy-core/contracts/) — placeholder registry, policy DSL, decision-record schema
- [`docs/public-surface.md`](../public-surface.md) — stability bands for every Spec 003 symbol
- [`packages/core/CHANGELOG.md`](../../packages/core/CHANGELOG.md) — `[0.2.0]` release notes
- [`packages/pip/CHANGELOG.md`](../../packages/pip/CHANGELOG.md) — `[0.3.0]` release notes
- Contract test: `packages/core/tests/contract/test_no_raw_payload_in_decision_record.py`
