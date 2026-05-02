# arc-guard-service

Thin deployment surface for arc-guardrails.

**Currently ships only the package skeleton.** A future deployment-surface release will land the full route handlers, app factory, DI wiring, and integration documentation. The skeleton exists today so the boundary-enforcement rules (`api → pip → core`, never reversed) stay testable.

## What's included in 0.1.0

- `arc_guard_service.settings` — `pydantic-settings` skeleton
- `arc_guard_service.validators` — `validate_request_payload` returning a typed `GuardInput` or raising `ApiBoundaryValidationError`
- `arc_guard_service._placeholder` — handoff note for the future deployment-surface release

## References

- [`arc-guard-core` README](../core/README.md)
- [`arc-guard` README](../pip/README.md)
- [CHANGELOG](./CHANGELOG.md)
