"""ULID generator for lifecycle event ids.

ULID is a 26-character, lexicographically sortable identifier. The first 10
characters encode a millisecond timestamp; the last 16 are random Crockford
base32. Sortable by id alone — no separate created_at index needed for
ordering.

This is a stdlib-only implementation; we avoid `python-ulid` to keep
`arc-guard-core`'s dependency surface at zero new runtime deps.
"""

from __future__ import annotations

import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_event_id() -> str:
    """Return a new ULID. Sortable; globally unique with negligible collision."""
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")

    chars = [""] * 26
    # 48-bit timestamp → 10 base32 chars
    for i in range(10):
        chars[9 - i] = _CROCKFORD[timestamp_ms & 0x1F]
        timestamp_ms >>= 5
    # 80-bit randomness → 16 base32 chars
    for i in range(16):
        chars[25 - i] = _CROCKFORD[randomness & 0x1F]
        randomness >>= 5

    return "".join(chars)


__all__ = ["new_event_id"]
