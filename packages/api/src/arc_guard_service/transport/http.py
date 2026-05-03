"""FastAPI app factory for the arc-guard-service HTTP transport.

``create_app(settings, *, pipeline=None)`` returns a configured
``FastAPI`` instance. ``fastapi`` is lazy-imported inside the function
body; importing this module without the ``[fastapi]`` extra succeeds.

Two transports ship from the same app:

- ``POST /v1/guard`` — generic guard endpoint. Accepts a ``GuardInput``
  JSON payload, returns a ``GuardResult`` JSON payload. This is the
  transport-neutral surface for non-Python callers.
- ``POST /v1/chat/completions`` — OpenAI-compatible chat-completions
  endpoint. Drop-in for any OpenAI client; runs ``pre_process`` on the
  inbound user message and ``post_process`` on the assistant response.
  Mounted only when ``ServiceSettings.enable_chat_completions`` is true.

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
lazily-imported ``fastapi.Request`` class.
"""

import importlib
import logging
import time
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from arc_guard_core.exceptions import (
    ApiBoundaryValidationError,
    ArcGuardError,
)

from arc_guard_service.observability import StdlibBridgeLogger
from arc_guard_service.schemas import ServiceDescriptor
from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.errors import (
    envelope_for_invalid_request,
    pipeline_error_to_http,
)
from arc_guard_service.transport.limits import (
    RequestSizeLimitMiddleware,
    RequestTimeoutMiddleware,
)
from arc_guard_service.validators import validate_request_payload

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


def _build_default_pipeline() -> Any:
    """Build a GuardPipeline with the recommended defaults for the api.

    Pre-builds Injection + Presidio inspectors ONCE so the analyzer engine
    isn't recreated per request. Wires LogReporter so non-clean decisions
    surface as WARNING lines, and StdlibBridgeLogger so in-pipeline events
    appear at INFO. Both can be replaced by setting
    ``ServiceSettings.pipeline_factory`` to a custom dotted path.
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
    )


def _result_to_dict(result: Any) -> dict[str, Any]:
    """Convert a ``GuardResult`` dataclass to a JSON-friendly dict."""
    return asdict(result)


def _envelope_to_dict(envelope: Any) -> dict[str, Any]:
    return {
        "code": envelope.code,
        "trigger": envelope.trigger,
        "policy": envelope.policy,
        "human_message": envelope.human_message,
        "next_steps": list(envelope.next_steps),
        "metadata": dict(envelope.metadata),
    }


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

    if pipeline is None:
        if settings.pipeline_factory:
            pipeline = _resolve_pipeline_factory(settings.pipeline_factory)
        else:
            pipeline = _build_default_pipeline()
    _LOG.info(
        "arc-guard api ready (backend=%s chat_completions=%s docs=%s)",
        settings.backend,
        settings.enable_chat_completions,
        settings.enable_docs,
    )

    timeout_counter: list[int] = [0]
    request_counter: list[int] = [0]
    duration_samples: list[float] = []

    def _on_timeout() -> None:
        timeout_counter[0] += 1

    Request = fastapi.Request  # noqa: N806
    JSONResponse = fastapi.responses.JSONResponse  # noqa: N806

    # Lifespan handles the shared httpx client used by the OpenAI transport
    # for upstream LLM calls. We construct it once at startup so connections
    # are pooled across requests instead of dialed per request.
    http_client_holder: dict[str, Any] = {}

    @asynccontextmanager
    async def _lifespan(_app: Any) -> Any:
        if settings.enable_chat_completions:
            httpx = _import_httpx()
            client = httpx.AsyncClient(timeout=settings.backend_timeout_seconds)
            http_client_holder["client"] = client
            try:
                yield
            finally:
                await client.aclose()
        else:
            yield

    app = fastapi.FastAPI(
        title="arc-guard-service",
        version="0.3.0",
        summary=(
            "arc-guardrails deployment surface — generic guard endpoint plus an "
            "OpenAI-compatible chat-completions endpoint with pre/post intercept."
        ),
        description=(
            "Two transports:\n\n"
            "- `POST /v1/guard` — generic guard. Send a `GuardInput`, get a `GuardResult`.\n"
            "- `POST /v1/chat/completions` — OpenAI-compatible. Every request runs through "
            "`GuardPipeline.pre_process` (inbound user message) and `GuardPipeline.post_process` "
            "(assistant response). Blocked verdicts return `finish_reason='content_filter'`.\n\n"
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
        endpoints = ["POST /v1/guard"]
        if settings.enable_chat_completions:
            endpoints.append("POST /v1/chat/completions")
        if settings.enable_docs:
            endpoints.append("GET /docs")
            endpoints.append("GET /openapi.json")
        return ServiceDescriptor(
            service="arc-guard-service",
            backend=settings.backend,
            endpoints=endpoints,
        )

    @app.post("/v1/guard", tags=["guard"])  # type: ignore[untyped-decorator]
    async def guard_endpoint(request: Request) -> Any:  # type: ignore[valid-type]
        request_counter[0] += 1
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        try:
            payload = await request.json()  # type: ignore[attr-defined]
        except Exception:
            envelope = envelope_for_invalid_request(trigger="api.malformed_payload")
            return JSONResponse(
                status_code=400,
                content=_envelope_to_dict(envelope),
                headers={"x-request-id": request_id},
            )

        if not isinstance(payload, Mapping):
            envelope = envelope_for_invalid_request(trigger="api.malformed_payload")
            return JSONResponse(
                status_code=400,
                content=_envelope_to_dict(envelope),
                headers={"x-request-id": request_id},
            )

        try:
            guard_input = validate_request_payload(payload)
        except ApiBoundaryValidationError as exc:
            status, envelope = pipeline_error_to_http(exc)
            return JSONResponse(
                status_code=status,
                content=_envelope_to_dict(envelope),
                headers={"x-request-id": request_id},
            )

        try:
            result = await pipeline.pre_process(guard_input)
        except ArcGuardError as exc:
            status, envelope = pipeline_error_to_http(exc)
            return JSONResponse(
                status_code=status,
                content=_envelope_to_dict(envelope),
                headers={"x-request-id": request_id},
            )

        duration_samples.append(time.perf_counter() - start)
        return fastapi.responses.JSONResponse(
            status_code=200,
            content=_result_to_dict(result),
            headers={"x-request-id": request_id},
        )

    if settings.enable_chat_completions:
        from arc_guard_service.transport.openai import build_router

        # The OpenAI router needs the shared httpx client; we wrap it in a
        # lazy proxy so the router can be built at app-construction time
        # but the client object is materialized at lifespan-startup time.
        class _LazyClient:
            async def post(self, *args: Any, **kwargs: Any) -> Any:
                client = http_client_holder.get("client")
                if client is None:
                    raise RuntimeError(
                        "http client not initialized — lifespan startup did not run"
                    )
                return await client.post(*args, **kwargs)

        openai_router = build_router(
            settings=settings,
            pipeline=pipeline,
            http_client=_LazyClient(),
        )
        app.include_router(openai_router)

    app.add_middleware(
        RequestTimeoutMiddleware,
        timeout_seconds=settings.request_timeout_seconds,
        on_timeout=_on_timeout,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_bytes=settings.max_request_bytes,
    )

    app.state.arc_guard_metrics = {
        "requests_total": request_counter,
        "timeout": timeout_counter,
        "duration": duration_samples,
    }
    app.state.arc_guard_pipeline = pipeline
    app.state.arc_guard_settings = settings

    return app


__all__ = ["create_app"]
