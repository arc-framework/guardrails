"""``canonicalize(text)`` — produce a deterministic byte-stable form for hashing.

Per the intent-lock contract: NFC normalize → strip leading/trailing
whitespace → collapse internal whitespace runs to a single ASCII space
→ lowercase → encode as UTF-8 bytes (returned as ``str``; the caller
hashes ``.encode("utf-8")`` of the result).

The canonical form absorbs meaningless variation (formatting, casing,
leading whitespace) so two semantically-equivalent inputs produce the
same hash digest. The same algorithm is applied to original prompts,
sanitized prompts, and rehydrated answers — the auditor can join
records by content fingerprint.
"""

from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RUN: re.Pattern[str] = re.compile(r"\s+")


def canonicalize(text: str) -> str:
    """Return the canonical form of ``text`` per the intent-lock hashing rule."""
    nfc = unicodedata.normalize("NFC", text)
    stripped = nfc.strip()
    collapsed = _WHITESPACE_RUN.sub(" ", stripped)
    return collapsed.lower()


__all__ = ["canonicalize"]
