"""Intent capture sub-package: encoder defaults + stage-orchestration helpers."""

from __future__ import annotations

from arc_guard.intent.capture import (
    NULL_INTENT_REPRESENTATION,
    NullIntentEncoder,
    capture_intent,
)

__all__ = [
    "NullIntentEncoder",
    "NULL_INTENT_REPRESENTATION",
    "capture_intent",
]
