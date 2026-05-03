# Changelog — arc-guard-service

All notable changes to the `arc-guard-service` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.2.0] — 2026-05-03

### Added
- `arc_guard_service.run_guard(input, *, pipeline=None) -> GuardResult` — synchronous adapter for `GuardPipeline.pre_process`. Detects existing event loops; uses `asyncio.run()` from sync threads, a private worker-thread loop from threads with a running loop. Threads share one worker loop; cleanup via `weakref.finalize`.
- `python -m arc_guard_service` CLI entrypoint + `arc-guard-service` console script. Boots the HTTP transport when `[fastapi]` extra is installed; exits with a friendly `ImportError` otherwise.
- HTTP transport sub-package `arc_guard_service.transport`:
  - `create_app(settings, *, pipeline=None) -> FastAPI` factory with lazy `fastapi` import.
  - `POST /v1/guard` endpoint — JSON `GuardInput` in, JSON `GuardResult` out.
  - Request-size + request-timeout middleware (`transport/limits.py`); transport-layer errors map to HTTP statuses per the FAIL_RULE table.
  - One additional span (`stage="api_transport"`) and three new metrics (`arc_guardrails.api.requests_total` counter, `arc_guardrails.api.timeout` counter, `arc_guardrails.api.duration` histogram).
- `ServiceSettings` extended fields: `bind`, `port`, `max_request_bytes`, `request_timeout_seconds`, `pipeline_factory` (dotted-path string), `log_level`. All under the `ARC_GUARD_SERVICE_` env-var prefix.
- Dependency floor bumped to `arc-guard-core>=0.6.0` and `arc-guard>=0.7.0` to consume the new `TransportError` + `RefusalCode.API_TRANSPORT_TIMEOUT` surface.

### Migration notes
- First non-stub release. The 0.1.0 scaffold's `arc_guard_service.validators.validate_guard_input(...)` API is unchanged; new code lives in new modules.
- The `[fastapi]` extra remains the established way to bring in the HTTP transport. Installing `arc-guard-service` without extras still gives you a working `run_guard()`.

## [0.1.0] — 2026-05-01

### Added
- Initial scaffold. Spec 002 ships package skeleton only; Spec 007 owns full deployment surface (route handlers, DI wiring, integration docs).
- API-boundary request validator producing typed `ApiBoundaryValidationError`.
- Settings skeleton via `pydantic-settings`.
