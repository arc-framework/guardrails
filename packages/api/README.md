# arc-guard-service

Thin deployment surface for arc-guardrails.

**Spec 002 ships only the package skeleton.** Spec 007 owns the full deployment surface — route handlers, app factory, DI wiring, integration documentation. The skeleton exists so the boundary-enforcement rules (`api → pip → core`, never reversed) are testable today.

## What's included in 0.1.0

- `arc_guard_service.settings` — `pydantic-settings` skeleton
- `arc_guard_service.validators` — `validate_request_payload` returning a typed `GuardInput` or raising `ApiBoundaryValidationError`
- `arc_guard_service._placeholder` — Spec 007 handoff note

## References

- [Spec 002 — Rewrite Foundation](../../specs/002-rewrite-foundation/spec.md)
- [`arc-guard-core` README](../core/README.md)
- [`arc-guard` README](../pip/README.md)
- [CHANGELOG](./CHANGELOG.md)
