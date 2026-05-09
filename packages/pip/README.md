# arc-guard

Batteries-included guardrails library, built on [`arc-guard-core`](../core/README.md).

`arc-guard` carries the concrete implementations — inspectors, strategies, reporters, flag providers, middleware, adapters — for in-process LLM guardrailing. Provider integrations (NATS, Unleash, OTEL, presidio, transformers) live behind optional extras.

## Install

```bash
pip install arc-guard               # all implementations included; presidio is the only heavy dep
```

Currently ships **zero optional extras**. The NATS reporter, Unleash
flag provider, OTEL middleware, semantic inspector, and webhook
reporter were trimmed during the rewrite. They will return as separate
distributions; see CHANGELOG.md for per-version status.

## Recent highlights

- **Composable policy routing** via `RuleBasedPolicyRouter`. Author a `PolicyRuleSet`, pass it to `GuardPipeline(policy_ruleset=...)`, and rules fire per finding with precedence-resolved conflicts.
- **Risk-adaptive bands** — LOW / MEDIUM / HIGH / CRITICAL drive `GuardResult.action` and `refusal`.
- **Typed placeholders** — `redact` strategy emits `[CREDIT_CARD]` / `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]` / etc. Custom entity types register via `register_placeholder`.
- **Clarification flow** — opt-in: ambiguous runs return a `GuardResult.clarification` instead of blocking.
- **Decision records** — every routed run emits a `DecisionRecord` through `Logger.event` and `MetricSink`. No raw payloads.
- **Custom strategies** — implement the `ActionStrategy` Protocol, register via `@strategy("name")`, reference by name in your `PolicyRuleSet`. No core changes required.

The active spec set under `../../specs/` documents the contracts in
detail; `../../docs/walkthrough/` carries the per-feature operator
guides.

## Migration

If you previously imported from `arc_guard.types`, `arc_guard.config`, `arc_guard.protocols`, or `arc_guard.registry`, your imports keep working through this release with a `DeprecationWarning` naming the new home. See `CHANGELOG.md` for the per-version removal schedule and the migration walkthroughs under `../../docs/walkthrough/` for worked examples.

## References

- [`arc-guard-core` README](../core/README.md)
- [CHANGELOG](./CHANGELOG.md)
