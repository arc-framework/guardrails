# Walkthrough Notes

One-page operator-facing summaries per spec. Reviewers, collaborators, and future maintainers open these instead of rereading full spec / plan / tasks files.

## Purpose

- A fast human-readable view of each spec.
- Architectural intent stays visible across rewrites.
- Easier to explain progress and scope to reviewers and collaborators.

## Schema

Every per-spec walkthrough follows the same five sections:

1. **What changed** — concrete deliverables, with paths.
2. **Why** — the problem the spec solves and the constraint it respects.
3. **Public surface** — the supported import anchors or user-visible API the
   spec adds; cross-references the public-surface manifest.
4. **Operator knobs** — configuration the spec exposes.
5. **References** — links to the full spec, plan, contracts, and code.

The `system-overview.md` and `system-canvas.md` files synthesize across multiple specs and follow a different shape.

## Current walkthroughs

| Spec          | File                                                                     | Status                       |
| ------------- | ------------------------------------------------------------------------ | ---------------------------- |
| Cross-cutting | [system-overview.md](system-overview.md)                                 | Stable                       |
| Cross-cutting | [system-canvas.md](system-canvas.md)                                     | Stable                       |
| 001           | [001-arc-guard-rails.md](001-arc-guard-rails.md)                         | Stable (historical baseline) |
| 002           | [002-rewrite-foundation.md](002-rewrite-foundation.md)                   | Stable                       |
| 003           | [003-sanitization-policy-core.md](003-sanitization-policy-core.md)       | Stable                       |
| 004           | [004-observability-runtime.md](004-observability-runtime.md)             | Stable                       |
| 005           | [005-intent-fidelity-rehydration.md](005-intent-fidelity-rehydration.md) | Stable                       |
| 006           | [006-jailbreak-deception-eval.md](006-jailbreak-deception-eval.md)       | Stable                       |
| 007           | [007-integration-api-delivery.md](007-integration-api-delivery.md)       | Stable                       |

## Related

- [Public-surface manifest](../public-surface.md) — the authoritative supported
  package-root API contract.
- [Architecture index](../architecture/README.md) — cross-cutting architecture references.
