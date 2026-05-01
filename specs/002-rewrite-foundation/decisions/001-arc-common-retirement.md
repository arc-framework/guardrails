---
dependency: arc-common
status: deferred-to-spec-007
decided: 2026-05-01
spec: 002-rewrite-foundation
---

# ADR 001 — `python/arc-common/` retirement plan

## Decision

**`python/arc-common/` is NOT folded into `arc-guard-core` and is NOT
retired in Spec 002.** Retirement is deferred to Spec 007 (or a focused
follow-up spec) to keep Spec 002's scope strictly additive.

## Context

The roadmap §1.2 warns: "do not let existing arc-common become the new
guardrail common by accident." Research.md §3 carries that forward: there
is no module under `python/arc-common/` that `arc-guard-core` reuses,
and folding it in would violate Principle I (Generic-First Core) by
pulling `structlog`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`,
and `fastapi` into the contract layer's transitive closure.

### Current state of `python/arc-common/`

- Single module: `arc_common.observability` — A.R.C.-Platform-specific
  helpers for OTEL exporter wiring.
- Heavy dependencies: `structlog`, `opentelemetry-sdk`,
  `opentelemetry-exporter-otlp-proto-grpc`, `opentelemetry-instrumentation-fastapi`,
  `fastapi`.
- No callers in `python/arc-guardrails/` (verified by grep at Spec 002
  implementation time).

## Why defer

1. The constitution forbids implicit string-replace renames. Retiring
   `arc-common` is a separable change with its own deprecation window.
2. Spec 002's job is the rewrite foundation — package boundaries,
   contracts, validation, exception policy, concurrency policy. Anything
   that touches consumer code outside `arc-guardrails` belongs in a
   follow-up.
3. There may be other A.R.C. Platform services that depend on `arc-common`.
   Their retirement coordination lives in Spec 007's "future backlog
   capture" step, not here.

## Plan for Spec 007

When Spec 007 wires the full deployment surface and consolidates the
backlog, the follow-up spec should:

1. Audit consumers of `arc-common` across the A.R.C. Platform repos.
2. Either fold the OTEL helpers into `arc_guard.middleware.otel`
   (where `pip` already houses OTEL middleware) or migrate them to a
   new `arc-platform-observability` package.
3. Add a deprecation warning to `arc_common.observability` for one
   minor version, then remove the package.
4. Update `python/arc-common/README.md` with the migration note.

## Alternatives considered

- *Fold into `arc-guard-core`*: rejected. Pulls heavy provider deps into
  the zero-dep contract layer. Direct violation of Principle I.
- *Fold into `packages/pip/src/arc_guard/middleware/`*: rejected for
  Spec 002. The folding requires understanding non-arc-guard callers,
  which is out of scope here.
- *Delete in Spec 002*: rejected. Destructive change without a
  documented deprecation window or a survey of cross-platform consumers.
- *Rename to `arc-guard-common`*: rejected. The roadmap explicitly
  warns against this.

## Status

Deferred. `python/arc-common/` is left untouched by Spec 002 work.
Re-visit in Spec 007 or a focused successor.
