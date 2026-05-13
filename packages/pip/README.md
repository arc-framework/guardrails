# arc-guard

Batteries-included guardrails library, built on [`arc-guard-core`](../core/README.md).

`arc-guard` carries the concrete implementations — inspectors, strategies, reporters, flag providers, middleware, adapters — for in-process LLM guardrailing. Provider integrations (NATS, Unleash, OTEL, presidio, transformers) live behind optional extras.

## Install

```bash
pip install arc-guard
pip install 'arc-guard[semantic]'  # optional semantic verifier / scorer / encoder bundle
```

Optional extras:

- `semantic` — installs `sentence-transformers` + `numpy` for the bundled
  semantic intent/fidelity/rehydration helpers.
- `otel` — OpenTelemetry middleware/exporter support.
- `jailbreak-ml` — transformer-backed jailbreak detector.
- `code-injection` — SQL/code-injection helper dependencies.

The old rewrite-era adapters such as NATS, Unleash, and webhook delivery
remain trimmed from this package and will return as separate distributions.
See `CHANGELOG.md` for the per-version status.

## Recent highlights

- **Composable policy routing** via `RuleBasedPolicyRouter`. Author a `PolicyRuleSet`, pass it to `GuardPipeline(policy_ruleset=...)`, and rules fire per finding with precedence-resolved conflicts.
- **Risk-adaptive bands** — LOW / MEDIUM / HIGH / CRITICAL drive `GuardResult.action` and `refusal`.
- **Typed placeholders** — `redact` strategy emits `[CREDIT_CARD]` / `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]` / etc. Custom entity types register via `register_placeholder`.
- **Clarification flow** — opt-in: ambiguous runs return a `GuardResult.clarification` instead of blocking.
- **Decision records** — every routed run emits a `DecisionRecord` through `Logger.event` and `MetricSink`. No raw payloads.
- **Custom strategies** — implement the `ActionStrategy` Protocol, register via `@strategy("name")`, reference by name in your `PolicyRuleSet`. No core changes required.

## Inspectors

The bundled inspectors implement the `Inspector` Protocol from `arc_guard_core.protocols.inspector`. Compose them into a `GuardPipeline(inspectors=[...])`; the pipeline runs each one in order during the configured phases.

| Inspector | Module | Default phases | Catches | Extra required |
|---|---|---|---|---|
| `InjectionInspector` | `arc_guard.inspectors.injection` | pre_process | "ignore previous instructions"-style override patterns | none |
| `PresidioInspector` | `arc_guard.inspectors.presidio` | pre_process | PII (EMAIL_ADDRESS, PHONE_NUMBER, US_SSN, CREDIT_CARD, IBAN_CODE, PERSON, …) | `presidio` |
| `ShellInjectionInspector` | `arc_guard.inspectors.code_injection.shell` | post_process | `$(...)`, backticks, dangerous pipe targets, command chaining | none |
| `SqlInjectionInspector` | `arc_guard.inspectors.code_injection.sql` | post_process | injection-shaped SQL fragments | `code-injection` |
| `TemplateInjectionInspector` | `arc_guard.inspectors.code_injection.template` | post_process | `{{...}}`, `${...}`, sandbox-escape patterns | none |
| `SemanticIntentInspector` | `arc_guard.inspectors.semantic_intent` | pre_process | paraphrased social engineering, policy violations, jailbreak intent | `semantic` |
| `CustomInspector` | `arc_guard.inspectors.custom` | pre_process | operator-supplied regex / functions | none |

Code-injection inspectors default to `post_process` — they screen the LLM's output by default. Pass `phases=("pre_process", "post_process")` to also screen user input.

`SemanticIntentInspector` uses sentence-transformers to embed the prompt and compare against per-category prototype embeddings (default 0.55 cosine similarity). It catches paraphrased threats that pattern-based inspectors miss — install the `semantic` extra:

```bash
pip install 'arc-guard[semantic]'
```

Without the extra the constructor raises `ImportError` with an install hint.

## Semantic verifier

`RehydrationVerified` lifecycle events fire only when a non-Null
`RehydrationVerifier` is wired on the pipeline. The bundled semantic
verifier lives behind the same `semantic` extra used by `SemanticIntentInspector`:

```bash
pip install 'arc-guard[semantic]'
```

Without that extra, or without a custom verifier implementation, the
rehydrate stage still runs but stays silent on the lifecycle stream.

The active spec set under `../../specs/` documents the contracts in
detail; `../../docs/walkthrough/` carries the per-feature operator
guides.

## Migration

If you previously imported from `arc_guard.types`, `arc_guard.config`, `arc_guard.protocols`, or `arc_guard.registry`, your imports keep working through this release with a `DeprecationWarning` naming the new home. See `CHANGELOG.md` for the per-version removal schedule and the migration walkthroughs under `../../docs/walkthrough/` for worked examples.

## References

- [`arc-guard-core` README](../core/README.md)
- [CHANGELOG](./CHANGELOG.md)
