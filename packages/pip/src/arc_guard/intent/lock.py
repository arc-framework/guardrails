"""``build_intent_lock`` — construct an ``IntentLock`` from text artifacts.

Hashes each artifact via ``canonicalize → SHA-256 → hex`` and returns a
frozen ``IntentLock`` ready to attach to a ``DecisionRecord``. The
``rehydrated_text`` argument is optional — for runs that refused before
generation, no answer exists and the corresponding hash field is
``None``. The ``encoder_id`` argument is optional — when the null
encoder is in use, the lock still emits but does not claim semantic
encoding ran.
"""

from __future__ import annotations

import hashlib

from arc_guard_core.intent_lock import IntentLock

from arc_guard.intent.canonicalize import canonicalize


def _digest(text: str) -> str:
    return hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()


def build_intent_lock(
    *,
    original_text: str,
    sanitized_text: str,
    rehydrated_text: str | None,
    encoder_id: str | None,
) -> IntentLock:
    """Construct a fully-validated ``IntentLock``."""
    return IntentLock(
        original_intent_hash=_digest(original_text),
        sanitized_prompt_hash=_digest(sanitized_text),
        rehydrated_answer_hash=(_digest(rehydrated_text) if rehydrated_text is not None else None),
        encoder_id=encoder_id,
    )


__all__ = ["build_intent_lock"]
