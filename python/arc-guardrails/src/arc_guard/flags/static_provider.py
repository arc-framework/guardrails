from __future__ import annotations


class StaticFlagProvider:
    """In-memory flag provider backed by a plain dict — ideal for tests and static config."""

    def __init__(self, flags: dict[str, bool | str | list[str]]) -> None:
        self._flags = flags

    def is_enabled(self, flag: str, default: bool = False) -> bool:
        """Return the boolean value of *flag*, falling back to *default*."""
        value = self._flags.get(flag)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return default

    def get_string(self, flag: str, default: str = "") -> str:
        """Return the string value of *flag*, falling back to *default*."""
        value = self._flags.get(flag)
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return default

    def get_list(self, flag: str, default: list[str] | None = None) -> list[str]:
        """Return a list of strings for *flag*, falling back to *default*."""
        if default is None:
            default = []
        value = self._flags.get(flag)
        if value is None:
            return default
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",")]
        return default
