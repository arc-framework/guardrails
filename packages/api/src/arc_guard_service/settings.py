"""Settings skeleton for arc-guard-service.

This is a placeholder schema. The full settings model — env prefixes,
secret-loading rules, provider-specific settings nests — lands in a
future deployment-surface implementation.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Minimal settings model.

    Reads from environment variables prefixed ``ARC_GUARD_SERVICE__``. Spec
    Declares only `enabled` so the package is testable; real fields land
    in a future implementation.
    """

    model_config = SettingsConfigDict(
        env_prefix="ARC_GUARD_SERVICE__",
        env_nested_delimiter="__",
        extra="forbid",
    )

    enabled: bool = True


__all__ = ["ServiceSettings"]
