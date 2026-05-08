# Changelog — arc-guard-service

All notable changes to the `arc-guard-service` package are documented here. Format follows Keep a Changelog; this package adheres to Semantic Versioning.

## [0.5.0] — 2026-05-04

### Added
- `GET /events` Server-Sent Events endpoint — broadcasts every `LifecycleEvent` emitted across all in-flight requests as it happens. Each event arrives as one SSE message with the event's typed JSON in `data:` and the event's class name in `event:`. Subscribers connected before a request starts see all events for that request; a `Last-Event-ID` header is honored on reconnect for at-most-once gap recovery within the ring buffer's window.
- `GET /lifecycle/{rid}` replay endpoint — returns a JSON envelope `{rid, captured_at, phases, events}` with the request's full event list, ordered by `seq`. Returns 404 with `{detail: "rid not found in any configured lifecycle store"}` when the rid has been evicted from every configured tier. The response carries `X-Lifecycle-Tier` so callers can see which sink served the response (`ring-buffer` vs `sqlite`); `X-Lifecycle-Tier` request header forces tier selection for cross-sink consistency tests.
- `ServiceSettings` extended fields (all backward-compatible defaults):
  - `lifecycle_enabled` (default `True`)
  - `lifecycle_buffer_capacity` (default `5000`)
  - `lifecycle_sqlite_path` (default `None` — in-memory only)
  - `lifecycle_sqlite_max_rows` (default `500_000`)
  - `lifecycle_sqlite_max_age_days` (default `7`)
  - `lifecycle_sqlite_cleanup_interval_seconds`, `lifecycle_sse_subscriber_queue_capacity`, `lifecycle_lookup_timeout_seconds`
  - `lifecycle_capture_payloads` (default `False`) — opts in to capturing POST-sanitization text on `SanitizationApplied.text_after` and `BackendResponded.response_text`. The captured text has already had PII placeholders applied by the same logic the pipeline applies to the LLM's input.
  - `lifecycle_capture_raw_input` (default `False`) — security-sensitive: opts in to capturing raw inbound text on `RequestStarted.raw_input`. Only enable when the dashboard is appropriately authenticated.
- `RequestTimeoutMiddleware.skip_paths` now excludes `/events` so SSE long-lived connections are not interrupted by the request-timeout enforcement.
- Compose stack:
  - New named volume `lifecycle-data` mounted at `/data` in the api container; `ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH=/data/arc_guardrail.db` wires the persistent tier.
  - New `sqlite-ui` service (image `coleifer/sqlite-web`, port `8081`) under the `dev` profile; mounts `lifecycle-data` read-only so the browser cannot corrupt the active store.
  - `prod` profile suppresses `sqlite-ui`.
- `Makefile` updates:
  - `make docker-up` and `make docker-up-prod` now block on `curl -sf` health probes against the api root (and against the sqlite-ui port for the dev profile) before printing "Stack up:". This honors SC-010 (60 s clean-checkout-to-running).
  - `make docker-nuke` runs `down --volumes` for both dev+prod profiles, then explicitly removes `api_lifecycle-data` and `api_ollama-models` volumes; warning text now mentions "deletes lifecycle event history".
- New pytest marker `requires_docker` (registered in `pyproject.toml`); excluded from the default test run alongside `slow`. Opt-in: `pytest -m requires_docker`.
- Slow + Docker-requiring smoke test `tests/integration/test_docker_up_quickstart.py` exercises the bootstrap end-to-end.

### Migration notes
- Additive on the public surface. No breaking changes; no migration required.
- Operators upgrading in-place gain the `/events` and `/lifecycle/{rid}` endpoints automatically. The Composite sink (Ring + Sqlite + Broadcast) is wired by default; existing requests appear in the lifecycle store from first boot. Disable persistence by leaving `lifecycle_sqlite_path` unset.
- Both payload-capture flags default to `False` and remain so unless an operator explicitly enables them. Under default settings, no raw user text appears in any captured event field — verified by the security soak test `tests/security/test_no_raw_payload_in_sink_default.py`.

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
