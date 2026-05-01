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

Spec `002` is implemented. The live workspace lives at [`packages/`](../packages/) and contains three packages: `core` (zero-dep contracts), `pip` (batteries-included library), `api` (deployment scaffold). The legacy `python/arc-guardrails/` is decommissioned to a deprecation README; `python/arc-common/` retirement is deferred to Spec 007 per [decisions/001-arc-common-retirement.md](002-rewrite-foundation/decisions/001-arc-common-retirement.md).

| #   | Feature                                              | Status      |
| --- | ---------------------------------------------------- | ----------- |
| 002 | [Rewrite Foundation](002-rewrite-foundation/spec.md) | Implemented |
| 003 | Sanitization and Policy Core                         | Planned     |
| 004 | Observability and Runtime Hardening                  | Planned     |
| 005 | Safe Rehydration and Intent Fidelity                 | Planned     |
| 006 | Jailbreak, Deception, and Evaluation                 | Planned     |
| 007 | Integration, API, and Documentation                  | Planned     |
