# arc-guard

Batteries-included guardrails library, built on [`arc-guard-core`](../core/README.md).

`arc-guard` carries the concrete implementations — inspectors, strategies, reporters, flag providers, middleware, adapters — for in-process LLM guardrailing. Provider integrations (NATS, Unleash, OTEL, presidio, transformers) live behind optional extras.

## Install

```bash
pip install arc-guard               # core implementations + presidio
pip install arc-guard[nats]         # add NATS reporter
pip install arc-guard[unleash]      # add Unleash flag provider
pip install arc-guard[otel]         # add OTEL middleware
pip install arc-guard[semantic]     # add semantic inspector (torch + transformers)
pip install arc-guard[arc]          # NATS + Unleash + OTEL bundle
```

## Spec 001 → Spec 002 migration

If you previously imported from `arc_guard.types`, `arc_guard.config`, `arc_guard.protocols`, or `arc_guard.registry`, your imports keep working through this release with a `DeprecationWarning` naming the new home. The old paths are removed in `arc-guard 0.3.0`. See the [migration note](../../docs/walkthrough/002-rewrite-foundation.md#migration) for the full mapping and a worked example.

## References

- [Spec 002 — Rewrite Foundation](../../specs/002-rewrite-foundation/spec.md)
- [`arc-guard-core` README](../core/README.md)
- [Contracts](../../specs/002-rewrite-foundation/contracts/)
- [CHANGELOG](./CHANGELOG.md)
