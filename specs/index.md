# Roadmap

Feature specifications and implementation plans for `arc-guardrails`.

## Baseline spec

| #   | Feature                                        | Status   |
| --- | ---------------------------------------------- | -------- |
| 001 | [Arc Guard Rails](001-arc-guard-rails/plan.md) | Baseline |

## Rewrite planning references

- `docs/superpowers/specs/2026-05-01-rewrite-roadmap.md`
- `docs/superpowers/specs/2026-05-01-universal-guardrail-revisit.md`
- `docs/walkthrough/`

## Planned next specs from the rewrite roadmap

Spec `002` is the current module-boundary spec. It maps the live packages `python/arc-guardrails` and `python/arc-common` toward the planned `packages/common`, `packages/core`, and `packages/api` split.

| #   | Feature                                              | Status  |
| --- | ---------------------------------------------------- | ------- |
| 002 | [Rewrite Foundation](002-rewrite-foundation/spec.md) | Draft   |
| 003 | Sanitization and Policy Core                         | Planned |
| 004 | Observability and Runtime Hardening                  | Planned |
| 005 | Safe Rehydration and Intent Fidelity                 | Planned |
| 006 | Jailbreak, Deception, and Evaluation                 | Planned |
| 007 | Integration, API, and Documentation                  | Planned |
