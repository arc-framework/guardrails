"""UnleashFlagProvider — maps the FlagProvider protocol to an UnleashClient."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("arc_guard")

try:
    import UnleashClient as _unleash_mod  # type: ignore[import-not-found]  # noqa: F401, N813

    _UNLEASH_AVAILABLE = True
except ImportError:
    _UNLEASH_AVAILABLE = False


class UnleashFlagProvider:
    """FlagProvider implementation backed by an already-initialised UnleashClient.

    The client is type-erased to ``Any`` so that ``arc-guard`` itself does not
    import UnleashClient at module load time — the hard dependency is only
    resolved when this class is instantiated.

    All flag keys are namespaced automatically: a call for flag ``"lite_mode"``
    resolves to the Unleash toggle ``"arc.guard.lite_mode"``.

    Args:
        client: An already-initialised ``UnleashClient`` instance.

    Raises:
        ImportError: If ``UnleashClient`` is not installed
            (hint: ``pip install arc-guard[unleash]``).
    """

    def __init__(self, client: Any) -> None:
        if not _UNLEASH_AVAILABLE:
            raise ImportError(
                "UnleashClient is required for UnleashFlagProvider. "
                "Install it with: pip install arc-guard[unleash]"
            )
        self._client = client

    def _toggle(self, flag: str) -> str:
        return f"arc.guard.{flag}"

    def is_enabled(self, flag: str, default: bool = False) -> bool:
        """Return the boolean value of *flag* from Unleash, falling back to *default*."""
        try:
            return bool(self._client.is_enabled(self._toggle(flag), default=default))
        except Exception as exc:
            logger.warning(
                "UnleashFlagProvider.is_enabled(%r) raised: %s — returning default", flag, exc
            )
            return default

    def get_string(self, flag: str, default: str = "") -> str:
        """Return the string variant payload for *flag*, falling back to *default*.

        Calls ``get_variant()`` on the Unleash client and extracts
        ``variant["payload"]["value"]``. Returns *default* if the variant is
        disabled, if there is no payload, or if any exception occurs.
        """
        try:
            variant = self._client.get_variant(self._toggle(flag))
            if not variant.get("enabled", False):
                return default
            payload = variant.get("payload")
            if payload is None:
                return default
            return str(payload.get("value", default))
        except Exception as exc:
            logger.warning(
                "UnleashFlagProvider.get_string(%r) raised: %s — returning default", flag, exc
            )
            return default

    def get_list(self, flag: str, default: list[str] | None = None) -> list[str]:
        """Return a list of strings for *flag* by splitting the variant value on ``,``.

        Falls back to *default* (or ``[]`` if *default* is ``None``) on any
        error or when the flag is disabled.
        """
        if default is None:
            default = []
        raw = self.get_string(flag, default="")
        if not raw:
            return default
        return [item.strip() for item in raw.split(",")]
