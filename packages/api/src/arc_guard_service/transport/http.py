"""FastAPI app factory for the arc-guard-service HTTP transport.

``create_app(settings, *, pipeline=None)`` returns a configured
``FastAPI`` instance. ``fastapi`` is lazy-imported inside the function
body; importing this module without the ``[fastapi]`` extra succeeds.

The HTTP surface ships ``POST /v1/chat/completions`` — the OpenAI-compatible
endpoint that runs every request through the full guard pipeline (inbound
user message via ``pre_process``, assistant response via ``post_process``).
Mounted only when ``ServiceSettings.enable_chat_completions`` is true.

Legacy: ``POST /v1/guard`` is a tombstone. Any request to it returns HTTP
410 Gone with a JSON envelope pointing at ``/v1/chat/completions``.

Default observability: when no ``pipeline`` is supplied, ``create_app``
constructs a ``GuardPipeline`` wired with ``LogReporter`` (post-decision
audit summary) and ``StdlibBridgeLogger`` (in-pipeline structured events
forwarded to stdlib logging). This makes pipeline activity visible in
``docker logs`` out of the box without any operator wiring.

Transport-layer errors map to HTTP statuses per
``transport.errors.pipeline_error_to_http``; pipeline-produced refusals
(normal ``result.action == "block"``) return HTTP 200 with the
``GuardResult`` body intact.

This module deliberately does NOT use ``from __future__ import annotations``:
FastAPI relies on runtime type-resolution for parameter annotations, and
deferred evaluation breaks the route-parameter introspection for the
lazily-imported FastAPI request types.
"""

import importlib
import logging
from contextlib import asynccontextmanager
from typing import Any

from arc_guard_service.observability import StdlibBridgeLogger
from arc_guard_service.schemas import ServiceDescriptor
from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.limits import (
    RequestSizeLimitMiddleware,
    RequestTimeoutMiddleware,
)

_LOG = logging.getLogger("arc-guard.api")

_FASTAPI_INSTALL_HINT = (
    "arc-guard-service[fastapi] is not installed. "
    "Install it with: pip install arc-guard-service[fastapi]"
)
_HTTPX_INSTALL_HINT = (
    "httpx is required for the chat-completions endpoint. "
    "Install it with: pip install arc-guard-service[fastapi]"
)


def _import_fastapi() -> Any:
    try:
        return importlib.import_module("fastapi")
    except ImportError as exc:
        raise ImportError(_FASTAPI_INSTALL_HINT) from exc


def _import_httpx() -> Any:
    try:
        return importlib.import_module("httpx")
    except ImportError as exc:
        raise ImportError(_HTTPX_INSTALL_HINT) from exc


def _resolve_pipeline_factory(dotted: str) -> Any:
    """Resolve a ``module.attr`` dotted path to the named callable."""
    if ":" in dotted:
        module_name, attr = dotted.split(":", 1)
    else:
        module_name, _, attr = dotted.rpartition(".")
    if not module_name or not attr:
        raise ValueError(f"pipeline_factory must be a dotted path; got {dotted!r}")
    module = importlib.import_module(module_name)
    factory = getattr(module, attr)
    if not callable(factory):
        raise TypeError(f"pipeline_factory {dotted!r} is not callable")
    return factory()


def _build_default_pipeline(lifecycle_hook: Any | None = None) -> Any:
    """Build a GuardPipeline with the recommended defaults for the api.

    Pre-builds Injection + Presidio inspectors ONCE so the analyzer engine
    isn't recreated per request. Wires LogReporter so non-clean decisions
    surface as WARNING lines, and StdlibBridgeLogger so in-pipeline events
    appear at INFO. The optional `lifecycle_hook` is passed through to enable
    per-request DAG capture for the operator dashboard. All can be replaced by
    setting ``ServiceSettings.pipeline_factory`` to a custom dotted path.
    """
    from arc_guard.config_env import GuardConfig
    from arc_guard.inspectors.injection import InjectionInspector
    from arc_guard.inspectors.presidio import PresidioInspector
    from arc_guard.pipeline import GuardPipeline
    from arc_guard.reporters.log_reporter import LogReporter

    _LOG.info("initializing arc-guard pipeline (loading Presidio + recognizers, ~1-3s)")
    config = GuardConfig.from_env()
    inspectors = [InjectionInspector(), PresidioInspector(config)]
    return GuardPipeline(
        inspectors=inspectors,
        config=config,
        reporter=LogReporter(),
        logger_hook=StdlibBridgeLogger(logging.getLogger("arc-guard.sdk")),
        lifecycle_hook=lifecycle_hook,
    )


def _start_sink_background_tasks(sink: Any) -> None:
    """Walk a (possibly composite) sink and call `start_cleanup_task` on
    every child that exposes one. Called from the FastAPI lifespan so the
    cleanup tasks attach to the running event loop.
    """
    candidates: list[Any] = [sink]
    children = getattr(sink, "_sinks", None)
    if children is not None:
        candidates.extend(children)
    for s in candidates:
        starter = getattr(s, "start_cleanup_task", None)
        if callable(starter):
            try:
                starter()
            except Exception as exc:  # pragma: no cover
                _LOG.warning(
                    "lifecycle sink %s.start_cleanup_task() raised: %s",
                    type(s).__name__,
                    exc,
                )


def _build_default_lifecycle_sink(settings: ServiceSettings, broadcaster: Any | None = None) -> Any:
    """Construct the recommended lifecycle sink composite for the api.

    Children, in order:
      1. RingBufferLifecycleSink — in-memory, sub-ms lookup, drop-oldest
      2. SqliteLifecycleSink — file-backed, restart-survivable (when
         `lifecycle_sqlite_path` is configured; pass None to skip)
      3. BroadcastingLifecycleSink — fan-out to live SSE subscribers
         (when one is supplied)

    Lookups walk children in order; ring buffer answers in microseconds for
    recent rids, SQLite answers in milliseconds for older ones. The
    composite handles per-child failure isolation; one failing child does
    NOT prevent siblings from receiving the emission.
    """
    from arc_guard.observability.composite_lifecycle_sink import (
        CompositeLifecycleSink,
    )
    from arc_guard.observability.ring_buffer_lifecycle_sink import (
        RingBufferLifecycleSink,
    )

    children: list[Any] = [
        RingBufferLifecycleSink(capacity=settings.lifecycle_buffer_capacity),
    ]
    if settings.lifecycle_sqlite_path:
        from arc_guard.observability.decision_record_recorder import (
            DecisionRecordRecorder,
        )
        from arc_guard.observability.request_summary_projector import (
            RequestSummaryProjector,
        )
        from arc_guard.observability.sqlite_lifecycle_sink import (
            SqliteLifecycleSink,
        )

        # Order matters: SqliteLifecycleSink runs first (creates schema v2
        # via its migration helper); the dashboard sinks read/write tables
        # that migration just created.
        children.append(
            SqliteLifecycleSink(
                path=settings.lifecycle_sqlite_path,
                max_rows=settings.lifecycle_sqlite_max_rows,
                max_age_days=settings.lifecycle_sqlite_max_age_days,
                cleanup_interval_seconds=settings.lifecycle_sqlite_cleanup_interval_seconds,
            )
        )
        children.append(RequestSummaryProjector(path=settings.lifecycle_sqlite_path))
        children.append(
            DecisionRecordRecorder(
                path=settings.lifecycle_sqlite_path,
                queue_capacity=settings.dashboard_decision_record_queue_capacity,
            )
        )
        # Stale-live sweeper rides alongside the other dashboard-tier sinks.
        # It emits RequestErrored events for stuck rows; the projector +
        # SQLite tier above handle the row update + persistence. When the
        # sweep interval is non-positive the sweeper's start_cleanup_task
        # is a no-op, so this child is inert.
        if settings.request_summary_sweep_interval_seconds > 0:
            from arc_guard.observability.stale_live_sweeper import (
                StaleLiveSweeper,
            )

            children.append(
                StaleLiveSweeper(
                    path=settings.lifecycle_sqlite_path,
                    lifecycle_sink=None,  # set below once composite is built
                    stale_threshold_seconds=(settings.request_summary_stale_threshold_seconds),
                    sweep_interval_seconds=(settings.request_summary_sweep_interval_seconds),
                )
            )
    if broadcaster is not None:
        children.append(broadcaster)

    if len(children) == 1:
        return children[0]
    composite = CompositeLifecycleSink(children)
    # The sweeper emits RequestErrored events back through the composite so
    # the projector / SQLite tier / SSE broadcaster all see the transition.
    # Bind the composite reference now that it's constructed; the sweeper's
    # own emit() is a no-op so the back-edge does not infinite-loop.
    for child in children:
        if hasattr(child, "_sink") and child.__class__.__name__ == "StaleLiveSweeper":
            child._sink = composite  # noqa: SLF001
    return composite


def create_app(
    settings: ServiceSettings | None = None,
    *,
    pipeline: Any | None = None,
) -> Any:
    """Build the FastAPI app. Requires the ``[fastapi]`` extra.

    Raises ``ImportError`` with a friendly install hint when the extra
    is missing.
    """
    fastapi = _import_fastapi()

    settings = settings or ServiceSettings()

    # Build the lifecycle sink stack ONCE per app. The same composite is
    # passed to GuardPipeline (so it receives every emission) AND used to
    # back the GET /events SSE endpoint and GET /lifecycle/{rid} replay
    # endpoint. When `lifecycle_enabled=False`, every consumer falls back to
    # the NullLifecycleSink and the SSE/replay endpoints are not mounted.
    from arc_guard_core.lifecycle import NullLifecycleSink

    lifecycle_sink: Any = NullLifecycleSink()
    sse_registry: Any = None
    if settings.lifecycle_enabled:
        from arc_guard_service.transport.events import (
            BroadcastingLifecycleSink,
            SubscriberRegistry,
        )

        sse_registry = SubscriberRegistry(
            queue_capacity=settings.lifecycle_sse_subscriber_queue_capacity
        )
        broadcaster = BroadcastingLifecycleSink(sse_registry)
        lifecycle_sink = _build_default_lifecycle_sink(settings, broadcaster)

    if pipeline is None:
        if settings.pipeline_factory:
            pipeline = _resolve_pipeline_factory(settings.pipeline_factory)
        else:
            pipeline = _build_default_pipeline(lifecycle_hook=lifecycle_sink)
    _LOG.info(
        "arc-guard api ready (backend=%s chat_completions=%s docs=%s lifecycle=%s)",
        settings.backend,
        settings.enable_chat_completions,
        settings.enable_docs,
        settings.lifecycle_enabled,
    )

    timeout_counter: list[int] = [0]

    def _on_timeout() -> None:
        timeout_counter[0] += 1

    JSONResponse = fastapi.responses.JSONResponse  # noqa: N806

    # Lifespan handles the shared httpx client used by the OpenAI transport
    # for upstream LLM calls. We construct it once at startup so connections
    # are pooled across requests instead of dialed per request.
    http_client_holder: dict[str, Any] = {}

    # Dashboard log-tap holders. Populated inside lifespan when the SQLite
    # tier is configured; cleaned up on shutdown.
    debug_writer_holder: dict[str, Any] = {}
    log_handler_holder: dict[str, Any] = {}

    @asynccontextmanager
    async def _lifespan(_app: Any) -> Any:
        # Start any per-sink background tasks (e.g., SqliteLifecycleSink's
        # retention cleanup loop) once the asyncio event loop is up.
        _start_sink_background_tasks(lifecycle_sink)
        # Wire the structured-logging tap when the SQLite tier is configured.
        if settings.lifecycle_sqlite_path:
            from arc_guard.observability.debug_entry_writer import DebugEntryWriter
            from arc_guard.observability.debug_log_handler import RidLogHandler

            writer = DebugEntryWriter(
                path=settings.lifecycle_sqlite_path,
                queue_capacity=settings.dashboard_debug_entry_queue_capacity,
            )
            handler = RidLogHandler(writer)
            logging.getLogger().addHandler(handler)
            debug_writer_holder["writer"] = writer
            log_handler_holder["handler"] = handler

        async def _shutdown() -> None:
            handler = log_handler_holder.get("handler")
            if handler is not None:
                logging.getLogger().removeHandler(handler)
            writer = debug_writer_holder.get("writer")
            if writer is not None:
                await writer.close()
            await lifecycle_sink.close()

        if settings.enable_chat_completions:
            httpx = _import_httpx()
            client = httpx.AsyncClient(timeout=settings.backend_timeout_seconds)
            http_client_holder["client"] = client
            try:
                yield
            finally:
                await client.aclose()
                await _shutdown()
        else:
            try:
                yield
            finally:
                await _shutdown()

    app = fastapi.FastAPI(
        title="arc-guard-service",
        version="0.3.0",
        summary=(
            "arc-guardrails deployment surface — OpenAI-compatible chat-completions "
            "endpoint with pre/post pipeline intercept."
        ),
        description=(
            "- `POST /v1/chat/completions` — OpenAI-compatible. Every request runs through "
            "`GuardPipeline.pre_process` (inbound user message) and `GuardPipeline.post_process` "
            "(assistant response). Blocked verdicts return `finish_reason='content_filter'`.\n\n"
            "- `POST /v1/guard` — **retired**. Returns HTTP 410 Gone with a pointer envelope to "
            "`/v1/chat/completions`.\n\n"
            "Backend selection via `ARC_GUARD_SERVICE_BACKEND`: `echo` (default, no LLM), "
            "`ollama` (local Ollama), `openai` (real OpenAI with `ARC_GUARD_SERVICE_OPENAI_API_KEY`)."
        ),
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
        lifespan=_lifespan,
    )

    @app.get(
        "/",
        response_model=ServiceDescriptor,
        summary="Service health / identity",
        tags=["health"],
    )
    async def root() -> ServiceDescriptor:  # type: ignore[no-untyped-def]
        endpoints: list[str] = []
        if settings.enable_chat_completions:
            endpoints.append("POST /v1/chat/completions")
            endpoints.append("GET /chat/examples")
        if settings.enable_docs:
            endpoints.append("GET /docs")
            endpoints.append("GET /openapi.json")
        return ServiceDescriptor(
            service="arc-guard-service",
            backend=settings.backend,
            endpoints=endpoints,
        )

    @app.api_route(
        "/v1/guard",
        methods=["POST", "GET", "PUT", "PATCH", "DELETE", "OPTIONS"],
        tags=["guard"],
        summary="Removed — use /v1/chat/completions",
        deprecated=True,
        include_in_schema=False,
    )  # type: ignore[untyped-decorator]
    async def guard_endpoint_removed() -> Any:  # type: ignore[valid-type]
        """Tombstone for the retired ``/v1/guard`` endpoint.

        Always returns HTTP 410 Gone with a stable, machine-readable
        envelope pointing at the replacement endpoint.
        """
        return JSONResponse(
            status_code=410,
            content={
                "error": {
                    "code": "endpoint_removed",
                    "message": (
                        "POST /v1/guard was retired. "
                        "Use POST /v1/chat/completions for full-pipeline behavior."
                    ),
                    "replacement": "/v1/chat/completions",
                    "retired_in_spec": "014-pipeline-instrumentation-completion",
                }
            },
        )

    if settings.enable_chat_completions:
        from arc_guard_service.observability import (
            SettingsBackedPayloadCapturePolicy,
        )
        from arc_guard_service.transport.chat_examples import build_chat_examples_router
        from arc_guard_service.transport.openai import build_router

        # The OpenAI router needs the shared httpx client; we wrap it in a
        # lazy proxy so the router can be built at app-construction time
        # but the client object is materialized at lifespan-startup time.
        class _LazyClient:
            async def post(self, *args: Any, **kwargs: Any) -> Any:
                client = http_client_holder.get("client")
                if client is None:
                    raise RuntimeError("http client not initialized — lifespan startup did not run")
                return await client.post(*args, **kwargs)

        capture_policy = SettingsBackedPayloadCapturePolicy(
            capture_payloads=settings.lifecycle_capture_payloads,
            capture_raw_input=settings.lifecycle_capture_raw_input,
        )
        openai_router = build_router(
            settings=settings,
            pipeline=pipeline,
            http_client=_LazyClient(),
            lifecycle_sink=lifecycle_sink,
            payload_capture_policy=capture_policy,
        )
        app.include_router(openai_router)
        chat_examples_router = build_chat_examples_router()
        app.include_router(chat_examples_router)

    if settings.lifecycle_enabled and sse_registry is not None:
        from arc_guard_service.transport.events import build_events_router
        from arc_guard_service.transport.lifecycle import build_lifecycle_router
        from arc_guard_service.transport.requests import build_requests_router

        events_router = build_events_router(
            registry=sse_registry,
            lifecycle_sink=lifecycle_sink,
        )
        app.include_router(events_router)
        lifecycle_router = build_lifecycle_router(settings=settings, lifecycle_sink=lifecycle_sink)
        app.include_router(lifecycle_router)
        requests_router = build_requests_router(settings=settings)
        app.include_router(requests_router)

    # Request-scope rid middleware: sets the ``rid_context_var`` so the
    # ``RidLogHandler`` (when wired to the root logger) can tag every log
    # record emitted during the request with the active rid. Resets on exit.
    @app.middleware("http")
    async def _rid_scope_middleware(request: Any, call_next: Any) -> Any:
        from arc_guard.observability.debug_log_handler import rid_context_var

        from arc_guard_service.transport._rid import resolve_rid

        rid = resolve_rid(request)
        token = rid_context_var.set(rid)
        try:
            response = await call_next(request)
        finally:
            rid_context_var.reset(token)
        # Echo the resolved rid in the response headers so clients can
        # correlate without parsing the body.
        response.headers["x-request-id"] = rid
        return response

    app.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.request_timeout_seconds,
        on_timeout=_on_timeout,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.max_request_bytes,
    )

    # CORS for the dashboard data plane. Only installed when the operator
    # configured an explicit allow-list — empty list (default) means no
    # cross-origin requests are permitted at the browser layer. The
    # ``ServiceSettings.dashboard_origins`` validator already rejects
    # wildcards, non-http(s) schemes, and path/query/fragment components
    # at startup; we just consume the validated list here.
    if settings.dashboard_origins:
        try:
            cors_module = importlib.import_module("starlette.middleware.cors")
        except ImportError as exc:
            raise ImportError(_FASTAPI_INSTALL_HINT) from exc
        cors_middleware = cors_module.CORSMiddleware

        app.add_middleware(
            cors_middleware,
            allow_origins=list(settings.dashboard_origins),
            allow_origin_regex=None,
            allow_credentials=False,
            allow_methods=["GET", "OPTIONS"],
            allow_headers=["Content-Type", "Cache-Control", "Last-Event-ID"],
            expose_headers=["X-Lifecycle-Tier", "X-Request-Id"],
            max_age=600,
        )

    app.state.arc_guard_metrics = {
        "timeout": timeout_counter,
    }
    app.state.arc_guard_pipeline = pipeline
    app.state.arc_guard_settings = settings
    app.state.arc_guard_lifecycle_sink = lifecycle_sink
    app.state.arc_guard_sse_registry = sse_registry

    return app


__all__ = ["create_app"]
