# arc-guard

Batteries-included guardrails library, built on [`arc-guard-core`](../core/README.md).

`arc-guard` carries the concrete implementations — inspectors, strategies, reporters, flag providers, middleware, adapters — for in-process LLM guardrailing. Provider integrations (NATS, Unleash, OTEL, presidio, transformers) live behind optional extras.

## Install

```bash
pip install arc-guard               # all implementations included; presidio is the only heavy dep
```

Spec 002 ships **zero optional extras**. The NATS reporter, Unleash flag
provider, OTEL middleware, semantic inspector, and webhook reporter were
all trimmed per the rewrite roadmap §4 ("nice-to-have features — future
expansion"). Specs 004 (OTEL), 005 (semantic / intent fidelity), and 007
(transports) own their respective reintroductions.

## What's new in 0.3.0 (Spec 003 — Sanitization and Policy Core)

- **Composable policy routing** via `RuleBasedPolicyRouter`. Author a `PolicyRuleSet`, pass it to `GuardPipeline(policy_ruleset=...)`, and rules fire per finding with precedence-resolved conflicts.
- **Risk-adaptive bands** — LOW / MEDIUM / HIGH / CRITICAL drive `GuardResult.action` and `refusal` per D3.
- **Typed placeholders** — `redact` strategy emits `[CREDIT_CARD]` / `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]` / etc. Custom entity types register via `register_placeholder`.
- **Clarification flow** — opt-in: ambiguous runs return a `GuardResult.clarification` instead of blocking.
- **Decision records** — every routed run emits a `DecisionRecord` through `Logger.event` and `MetricSink`. No raw payloads.
- **Custom strategies** — implement the `ActionStrategy` Protocol, register via `@strategy("name")`, reference by name in your `PolicyRuleSet`. No core changes required.

See [`specs/003-sanitization-policy-core/quickstart.md`](../../specs/003-sanitization-policy-core/quickstart.md) for the operator / integrator / contributor walkthroughs and [`docs/walkthrough/003-sanitization-policy-core.md`](../../docs/walkthrough/003-sanitization-policy-core.md) for the policy authoring guide.

## Spec 001 → Spec 002 migration

If you previously imported from `arc_guard.types`, `arc_guard.config`, `arc_guard.protocols`, or `arc_guard.registry`, your imports keep working through this release with a `DeprecationWarning` naming the new home. The old paths are removed in `arc-guard 0.3.0`. See the [migration note](../../docs/walkthrough/002-rewrite-foundation.md#migration) for the full mapping and a worked example.

## References

- [Spec 002 — Rewrite Foundation](../../specs/002-rewrite-foundation/spec.md)
- [`arc-guard-core` README](../core/README.md)
- [Contracts](../../specs/002-rewrite-foundation/contracts/)
- [CHANGELOG](./CHANGELOG.md)
