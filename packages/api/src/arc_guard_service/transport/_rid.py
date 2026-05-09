"""Shared request-id resolver for all api transports.

Single source of truth for how the api derives ``rid`` from an inbound HTTP
request. Both ``transport.openai`` (chat-completions) and the dashboard
request-scope middleware in ``transport.http`` call this helper so the
two paths cannot drift.

Precedence (matches the historical ``transport.openai`` shape):

1. ``X-Request-Id`` header value, if present and matches the rid regex.
2. Otherwise, a freshly minted 12-character lowercase hex token.

The accepted shape is bounded by the same regex the lifecycle replay
endpoint enforces: ``[A-Za-z0-9._-]{1,64}``. Header values that fail the
regex are treated as absent (the upstream sender chose an unsafe value;
we generate a fresh one rather than reflect it).
"""

from __future__ import annotations

import re
import uuid
from typing import Any

# Same regex used by the lifecycle replay endpoint.
_RID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _mint_rid() -> str:
    """Generate a fresh 12-character lowercase hex token."""
    return uuid.uuid4().hex[:12]


def resolve_rid(request: Any) -> str:
    """Return the rid for the inbound request.

    ``request`` is anything with a ``.headers`` mapping (FastAPI/Starlette
    request, pytest fixture, mock); ``None`` is also accepted and yields
    a freshly minted rid.
    """
    if request is None:
        return _mint_rid()
    headers = getattr(request, "headers", None)
    if headers is None:
        return _mint_rid()
    candidate = headers.get("x-request-id")
    if candidate and _RID_PATTERN.match(candidate):
        return str(candidate)
    return _mint_rid()


__all__ = ["resolve_rid"]
