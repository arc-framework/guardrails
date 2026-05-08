"""Fingerprint helper for code-injection findings.

The fingerprint is the default representation of a matched substring in a
finding's ``metadata``: hash + length + char-class summary. Operators see
enough qualitative signal to triage without the literal payload being
permanently archived in the lifecycle store / SIEM by default; the
``raw_match`` key is added separately when ``capture_raw_matches=True``.

The char-class buckets are mutually exclusive and assigned in a fixed
precedence order (alpha, digit, whitespace, punct, non_printable) so each
character is counted in exactly one bucket and the buckets sum to
``length_chars``.
"""

from __future__ import annotations

import hashlib
import string
from typing import Any

_PUNCTUATION = frozenset(string.punctuation)


def compute_fingerprint(text: str) -> dict[str, Any]:
    """Compute the fingerprint dict for a matched substring.

    Returns a dict with keys ``hash`` (``"sha256:<hex>"``), ``length_chars``,
    ``length_bytes`` (UTF-8), and ``char_class`` (counts of alpha, digit,
    punct, whitespace, non_printable).

    Each character contributes to exactly one bucket; precedence is alpha,
    digit, whitespace, punct, non_printable.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

    alpha = 0
    digit = 0
    whitespace = 0
    punct = 0
    non_printable = 0

    for ch in text:
        if ch.isalpha():
            alpha += 1
        elif ch.isdigit():
            digit += 1
        elif ch.isspace():
            whitespace += 1
        elif ch in _PUNCTUATION:
            punct += 1
        elif not ch.isprintable():
            non_printable += 1
        else:
            # Printable but not alpha/digit/space/ASCII-punct (e.g. unicode
            # symbols outside string.punctuation). Folded into ``punct`` so
            # the bucket totals always sum to ``length_chars``.
            punct += 1

    return {
        "hash": f"sha256:{digest}",
        "length_chars": len(text),
        "length_bytes": len(text.encode("utf-8")),
        "char_class": {
            "alpha": alpha,
            "digit": digit,
            "punct": punct,
            "whitespace": whitespace,
            "non_printable": non_printable,
        },
    }


__all__ = ["compute_fingerprint"]
