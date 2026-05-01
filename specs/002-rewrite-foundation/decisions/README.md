# Spec 002 — Decisions

This directory holds adopt-vs-build records for any new runtime dependency added to `packages/core/` (FR-031, FR-032). Lightweight adoptions (e.g. dev tooling) live as a single line in `.specify/memory/libraries.md` instead.

## When to file an ADR here

File an ADR (rather than just a `libraries.md` line) when **any** of the following holds:

- The new dependency adds runtime weight to `arc-guard-core`'s install closure.
- The dependency replaces a custom subsystem (validation, retries, observability, etc.).
- The choice has license, supply-chain, or security implications.
- The constitution's "reuse before build" rule (Principle V) demands a reasoned comparison.

## Front matter

Each ADR file MUST start with YAML front matter that names the dependency:

```yaml
---
dependency: <pypi-name>
status: adopted | rejected | superseded
decided: YYYY-MM-DD
spec: 002-rewrite-foundation
---
```

The `dependency:` key is what `tools/check_adopt_vs_build.py` looks for when it audits a PR that adds a new runtime dep.

## ADR body

Each ADR should answer:

1. **What problem does this dependency solve?**
2. **What at-least-one credible alternative was considered?** (custom build, another OSS option)
3. **Why was this dependency chosen?**
4. **What are the install-weight, license, supply-chain, and maintenance implications?**
5. **What does the dependency NOT cover that we'll need to revisit?**

## Naming

`NNN-<short-slug>.md` — e.g. `001-pydantic-v2-validation.md`. Numbers are sequential within this directory.

## Reference

- Constitution Principle V: Security, Observability, Resilience.
- Roadmap §1.9 — "Reuse before build".
- Spec 002 §FR-031 / §FR-032.
- Research §10 — `tools/check_adopt_vs_build.py` design.
