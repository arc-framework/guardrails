"""Settings skeleton for arc-guard-service.

Spec 002 ships only the placeholder schema. Spec 007 will fill in the env
prefixes, secret-loading rules, and provider-specific settings nests.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceSettings(BaseSettings):
    """Minimal settings model.

    Reads from environment variables prefixed ``ARC_GUARD_SERVICE__``. Spec
    002 declares only `enabled` so the package is testable; Spec 007 will
    add real fields.
    """

    model_config = SettingsConfigDict(
        env_prefix="ARC_GUARD_SERVICE__",
        env_nested_delimiter="__",
        extra="forbid",
    )

    enabled: bool = True


__all__ = ["ServiceSettings"]
