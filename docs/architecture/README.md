# arc-guardrails — architecture index

The canonical entry point for cross-cutting architecture documents. Operators, contributors, and reviewers start here.

## Architecture overview

- [Rewrite roadmap](rewrite-roadmap.md) — the staged plan from the original `arc-guard` to the post-rewrite five-package surface (Specs 002 → 007).
- [Universal-guardrail revisit](universal-guardrail-revisit.md) — the design rationale that motivated the rewrite (one-contract-many-modes, generic-first core, adapter isolation).

## Walkthroughs

Per-spec one-page summaries live in [`docs/walkthrough/`](../walkthrough/README.md). Each walkthrough follows the uniform five-section schema (What changed / Why / Public surface / Operator knobs / References).

## Public surface

The [public-surface manifest](../public-surface.md) records the supported
package-root imports across `arc_guard_core` and `arc_guard_service`, plus the
active `arc_guard` deprecation shims. Operators pin against Stable and
Provisional symbols; the surface check (`tools/check_public_surface.py`)
verifies that the documented supported imports still resolve at runtime.

## Spec index

| Spec                                                       | Title                                                                                        | Status      |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----------- |
| [002](../../specs/002-rewrite-foundation/spec.md)          | Rewrite foundation — package split, contract layer, deprecation flow                         | Implemented |
| [003](../../specs/003-sanitization-policy-core/spec.md)    | Sanitization & policy core — typed placeholders, four-band ladder, decision records          | Implemented |
| [004](../../specs/004-obs-runtime-hardening/spec.md)       | Observability & runtime hardening — STAGE_DESCRIPTORS, FAIL_RULE table, OTEL adapter         | Implemented |
| [005](../../specs/005-intent-fidelity-rehydration/spec.md) | Intent fidelity & rehydration — IntentEncoder/FidelityScorer/RehydrationVerifier, IntentLock | Implemented |
| [006](../../specs/006-jailbreak-deception-eval/spec.md)    | Jailbreak / deception / evaluation — stronger detectors, multi-turn deception, harness       | Implemented |
| [007](../../specs/007-integration-api-delivery/spec.md)    | Integration, API, and documentation completion — API package, surface manifest, examples     | Implemented |
| [008](../../specs/008-backlog.md)                          | Nice-to-have backlog — deferred roadmap §4 items for future planners                         | Backlog     |
| [009](../../specs/009-retire-pre-rewrite-tree/spec.md)     | Retire the pre-rewrite Python tree — single-source workspace under `packages/`               | Implemented |
| [010](../../specs/010-lifecycle-sink/spec.md)              | Per-request lifecycle sink — typed event substrate, SSE feed, replay, SQLite tier            | Implemented |
| [011](../../specs/011-detection-extensibility/spec.md)     | Detection extensibility — semantic content policies, automatic masking, code injection       | Implemented |
| [012](../../specs/012-dashboard-backend-data-plane/spec.md) | Dashboard backend data plane — paginated requests, workspace, filtered SSE, CORS allow-list  | Implemented |
| [013](../../specs/013-guardrailflow-dashboard/spec.md)      | GuardRailFlow dashboard — Vite SPA, 12-stage canvas, inspector + debug dock, fixture mode    | Implemented |

## Constitution

The project's invariants live in [`.specify/memory/constitution.md`](../../.specify/memory/constitution.md). Five principles:

1. **Generic-first core** — no platform / cloud / event-bus assumptions.
2. **One contract, many modes** — SDK / sidecar / CLI / framework-middleware / batch share the decision contract.
3. **Adapter isolation** — heavy or provider-specific deps live behind optional extras.
4. **Enterprise Python baseline** — pyproject.toml, src/ layout, ruff, mypy strict, pytest.
5. **Security, observability, resilience** — fail safely, observable, no raw payloads, threat-modeled.
