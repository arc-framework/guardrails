from __future__ import annotations

import os


class EnvFlagProvider:
    """Flag provider that reads from environment variables with a configurable prefix."""

    def __init__(self, prefix: str = "GUARD_") -> None:
        self._prefix = prefix

    def _key(self, flag: str) -> str:
        return f"{self._prefix}{flag.upper()}"

    def is_enabled(self, flag: str, default: bool = False) -> bool:
        """Return the boolean value of the env var for *flag*, falling back to *default*."""
        raw = os.environ.get(self._key(flag))
        if raw is None:
            return default
        return raw.lower() in ("true", "1", "yes")

    def get_string(self, flag: str, default: str = "") -> str:
        """Return the string value of the env var for *flag*, falling back to *default*."""
        return os.environ.get(self._key(flag), default)

    def get_list(self, flag: str, default: list[str] | None = None) -> list[str]:
        """Return a list of strings for *flag* by splitting on ``","``."""
        if default is None:
            default = []
        raw = os.environ.get(self._key(flag))
        if raw is None:
            return default
        return [item.strip() for item in raw.split(",")]
