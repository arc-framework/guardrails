"""Settings for arc-guard-service.

Reads from environment variables prefixed ``ARC_GUARD_SERVICE_``. The
HTTP transport (``arc_guard_service.transport.http``) consumes these
fields directly; the in-process ``run_guard()`` entrypoint ignores
transport-only fields like ``bind`` and ``port``.

Recommended defaults are tuned for an evaluator running the service
locally (or in Docker) with no external configuration: docs enabled,
chat-completions endpoint enabled, ``echo`` backend so the service
runs with no LLM dependency.
"""

from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Transport-layer configuration for arc-guard-service.

    Field semantics:

    - ``bind`` / ``port``: HTTP server bind address and port.
    - ``max_request_bytes``: hard upper bound on request body size; oversized
      requests are rejected with HTTP 413 + ``RefusalCode.API_INVALID_REQUEST``.
    - ``request_timeout_seconds``: maximum time the HTTP transport waits for
      ``pipeline.pre_process(...)``; on timeout the transport returns HTTP 504
      + ``RefusalCode.API_TRANSPORT_TIMEOUT`` and increments
      ``arc_guardrails.api.timeout``.
    - ``pipeline_factory``: optional dotted-path string. When set, the boot
      sequence imports the module and calls the named callable with no args;
      it must return a configured ``GuardPipeline``. When ``None`` the boot
      sequence constructs ``GuardPipeline()`` with defaults (Injection +
      Presidio inspectors, ``LogReporter``, and the stdlib-bridge Logger so
      pipeline events appear in ``docker logs`` out of the box).
    - ``log_level``: log level for the service's structured logger.
    - ``enable_chat_completions``: when true, mount the OpenAI-compatible
      ``POST /v1/chat/completions`` endpoint alongside the generic
      ``POST /v1/guard``. Disable when the service is being used purely as a
      sidecar that returns raw ``GuardResult`` payloads.
    - ``enable_docs``: when true, expose Swagger UI at ``/docs`` and the
      OpenAPI spec at ``/openapi.json``. ReDoc is intentionally not exposed
      — Swagger's "Try it out" button is the only doc surface most operators
      need; ReDoc is a read-only duplicate.
    - ``backend``: which downstream the chat-completions endpoint forwards
      to. ``echo`` is the no-LLM-needed default; ``ollama`` and ``openai``
      require their respective URLs / API keys.
    - ``ollama_url`` / ``openai_url``: backend URLs for the chat-completions
      endpoint when ``backend`` is set accordingly.
    - ``openai_api_key``: bearer token for ``backend=openai``. Empty when not
      using the OpenAI backend.
    - ``backend_timeout_seconds``: HTTP timeout for the upstream LLM call.
    """

    model_config = SettingsConfigDict(
        env_prefix="ARC_GUARD_SERVICE_",
        extra="forbid",
    )

    enabled: bool = True
    bind: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    max_request_bytes: int = Field(
        default=64 * 1024,
        ge=1024,
        le=16 * 1024 * 1024,
    )
    request_timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        le=600.0,
    )
    pipeline_factory: str | None = None
    log_level: str = "INFO"

    # Endpoint toggles
    enable_chat_completions: bool = True
    enable_docs: bool = True

    # Chat-completions backend
    backend: Literal["echo", "ollama", "openai"] = "echo"
    ollama_url: str = "http://localhost:11434/v1/chat/completions"
    openai_url: str = "https://api.openai.com/v1/chat/completions"
    openai_api_key: str = ""
    backend_timeout_seconds: float = Field(default=60.0, gt=0.0, le=600.0)

    # Per-request lifecycle observation.
    # Defaults wire the in-memory ring buffer + persistent SQLite composite so
    # operators get live SSE + cross-restart replay out of the box. Disable by
    # setting `lifecycle_enabled=False` to fall back to the NullLifecycleSink.
    lifecycle_enabled: bool = True
    lifecycle_buffer_capacity: int = Field(default=5000, ge=1, le=1_000_000)
    # Ring-only by default — no assumed filesystem path. Docker / production
    # deployments opt into persistent storage via the env var:
    #   ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH=/data/arc_guardrail.db
    # Setting this to None (default) keeps lifecycle storage in-memory only.
    lifecycle_sqlite_path: str | None = None
    lifecycle_sqlite_max_rows: int = Field(default=500_000, ge=1_000)
    lifecycle_sqlite_max_age_days: int = Field(default=7, ge=1, le=365)
    lifecycle_sqlite_cleanup_interval_seconds: float = Field(
        default=60.0, gt=0.0, le=3600.0
    )
    lifecycle_sse_subscriber_queue_capacity: int = Field(
        default=1000, ge=10, le=100_000
    )
    lifecycle_lookup_timeout_seconds: float = Field(default=5.0, gt=0.0, le=60.0)
    # Payload capture is OFF by default — events carry sizes/lengths only.
    # Enable `lifecycle_capture_payloads` to capture POST-sanitization text.
    # Enable `lifecycle_capture_raw_input` (separately, security-sensitive) to
    # capture the raw inbound text on RequestStarted.
    lifecycle_capture_payloads: bool = False
    lifecycle_capture_raw_input: bool = False

    # Dashboard data plane (additive HTTP routes + filtered SSE).
    # `dashboard_origins` is the strict CORS allow-list — empty means no
    # cross-origin requests are permitted. Wildcards / regex are forbidden;
    # entries must be fully-qualified http(s) URLs with no path/query/fragment.
    # When set via env, supply as a comma-separated list:
    #   ARC_GUARD_SERVICE_DASHBOARD_ORIGINS=http://127.0.0.1:5173,https://dashboard.example.com
    dashboard_origins: list[str] = Field(default_factory=list)
    dashboard_max_request_page_size: int = Field(default=200, ge=1, le=1000)
    dashboard_max_debug_page_size: int = Field(default=200, ge=1, le=1000)
    dashboard_decision_record_queue_capacity: int = Field(
        default=1000, ge=10, le=100_000
    )
    dashboard_debug_entry_queue_capacity: int = Field(
        default=5000, ge=10, le=100_000
    )

    @field_validator("dashboard_origins", mode="before")
    @classmethod
    def _coerce_origins_from_env(cls, value: object) -> object:
        """Accept either a list (from in-process construction) or a
        comma-separated string (from env var) and return a list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("dashboard_origins", mode="after")
    @classmethod
    def _validate_origins(cls, value: list[str]) -> list[str]:
        """Reject wildcards, non-http(s) schemes, and any path/query/fragment.
        Empty list (default) is allowed and means cross-origin requests are
        rejected at the CORS layer."""
        for entry in value:
            if "*" in entry:
                raise ValueError(
                    f'invalid origin "{entry}": wildcard not allowed'
                )
            if entry.endswith("/"):
                raise ValueError(
                    f'invalid origin "{entry}": trailing slash not allowed'
                )
            try:
                parsed = urlparse(entry)
            except ValueError as exc:
                raise ValueError(f'invalid origin "{entry}": {exc}') from exc
            if parsed.scheme not in ("http", "https"):
                raise ValueError(
                    f'invalid origin "{entry}": scheme must be http or https'
                )
            if not parsed.netloc:
                raise ValueError(
                    f'invalid origin "{entry}": missing host component'
                )
            if parsed.path:
                raise ValueError(
                    f'invalid origin "{entry}": path component not allowed'
                )
            if parsed.query:
                raise ValueError(
                    f'invalid origin "{entry}": query component not allowed'
                )
            if parsed.fragment:
                raise ValueError(
                    f'invalid origin "{entry}": fragment component not allowed'
                )
        return value


__all__ = ["ServiceSettings"]
