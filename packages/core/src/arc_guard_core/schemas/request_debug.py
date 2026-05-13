"""Request-scoped debug-entry envelope + cursor pagination.

Cursor format: base64-urlsafe-encoded JSON ``{"seq": int, "rid": str}``.
Encoding is opaque to clients; the ``rid`` field is a defense-in-depth
check that prevents cross-request cursor reuse. Malformed tokens or rid
mismatches raise ``ValueError`` from ``decode_debug_cursor``; the FastAPI
handler translates that into HTTP 400 (``cursor_invalid`` /
``cursor_mismatch``).
"""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

DebugSeverity = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class RequestDebugEntry(BaseModel):
    """One row in the debug-entries table."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rid: str
    seq: int
    ts: datetime
    channel: str
    severity: DebugSeverity
    message: str
    metadata: dict[str, Any]


class RequestDebugPage(BaseModel):
    """Cursor-paginated response envelope for ``GET /requests/{rid}/debug``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rid: str
    items: tuple[RequestDebugEntry, ...]
    next_cursor: str | None
    page_size: int


def encode_debug_cursor(*, rid: str, seq: int) -> str:
    """Encode a cursor token as base64-urlsafe JSON."""
    payload = json.dumps({"seq": seq, "rid": rid}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")


def decode_debug_cursor(token: str, *, expected_rid: str) -> int:
    """Decode an opaque cursor token and return the embedded ``seq``.

    Raises:
        ValueError: token is not valid base64-urlsafe; decoded payload is not
            valid JSON; payload is missing required ``seq`` / ``rid`` keys;
            ``seq`` is not an integer; ``rid`` does not match ``expected_rid``.
    """
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"cursor is not valid base64-urlsafe: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"cursor payload is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("cursor payload must be a JSON object")
    if "seq" not in payload:
        raise ValueError("cursor JSON missing required key 'seq'")
    if "rid" not in payload:
        raise ValueError("cursor JSON missing required key 'rid'")
    seq = payload["seq"]
    if not isinstance(seq, int) or isinstance(seq, bool):
        raise ValueError("cursor 'seq' must be an integer")
    rid = payload["rid"]
    if not isinstance(rid, str):
        raise ValueError("cursor 'rid' must be a string")
    if rid != expected_rid:
        raise ValueError(f"cursor rid {rid!r} does not match requested rid {expected_rid!r}")
    return seq


__all__ = [
    "DebugSeverity",
    "RequestDebugEntry",
    "RequestDebugPage",
    "decode_debug_cursor",
    "encode_debug_cursor",
]
