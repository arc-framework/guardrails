"""Settings for arc-guard-service.

Reads from environment variables prefixed ``ARC_GUARD_SERVICE_``. The
HTTP transport (``arc_guard_service.transport.http``) consumes these
fields directly; the in-process ``run_guard()`` entrypoint ignores
transport-only fields like ``bind`` and ``port``.
"""

from __future__ import annotations

from pydantic import Field
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
      sequence constructs ``GuardPipeline()`` with defaults.
    - ``log_level``: log level for the service's structured logger.
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


__all__ = ["ServiceSettings"]
