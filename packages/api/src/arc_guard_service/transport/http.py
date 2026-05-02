"""FastAPI app factory for the arc-guard-service HTTP transport.

``create_app(settings, *, pipeline=None)`` returns a configured
``FastAPI`` instance. ``fastapi`` is lazy-imported inside the function
body; importing this module without the ``[fastapi]`` extra succeeds.

The single endpoint ``POST /v1/guard`` accepts a ``GuardInput`` JSON
payload and returns a ``GuardResult`` JSON payload. Transport-layer
errors map to HTTP statuses per ``transport.errors.pipeline_error_to_http``;
pipeline-produced refusals (normal ``result.action == "block"``) return
HTTP 200 with the ``GuardResult`` body intact.

This module deliberately does NOT use ``from __future__ import annotations``:
FastAPI relies on runtime type-resolution for parameter annotations, and
deferred evaluation breaks the route-parameter introspection for the
lazily-imported ``fastapi.Request`` class.
"""

import importlib
import time
import uuid
from collections.abc import Mapping
from dataclasses import asdict
from typing import Any

from arc_guard_core.exceptions import (
    ApiBoundaryValidationError,
    ArcGuardError,
)

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

_FASTAPI_INSTALL_HINT = (
    "arc-guard-service[fastapi] is not installed. "
    "Install it with: pip install arc-guard-service[fastapi]"
)


def _import_fastapi() -> Any:
    try:
        return importlib.import_module("fastapi")
    except ImportError as exc:
        raise ImportError(_FASTAPI_INSTALL_HINT) from exc


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
            from arc_guard.pipeline import GuardPipeline

            pipeline = GuardPipeline()

    timeout_counter: list[int] = [0]
    request_counter: list[int] = [0]
    duration_samples: list[float] = []

    def _on_timeout() -> None:
        timeout_counter[0] += 1

    # FastAPI class aliases captured locally so the route handler's annotations
    # (used by FastAPI's runtime introspection) resolve correctly without a
    # module-level fastapi import.
    Request = fastapi.Request  # noqa: N806
    JSONResponse = fastapi.responses.JSONResponse  # noqa: N806

    app = fastapi.FastAPI(
        title="arc-guard-service",
        version="0.2.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.post("/v1/guard")  # type: ignore[untyped-decorator]
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
