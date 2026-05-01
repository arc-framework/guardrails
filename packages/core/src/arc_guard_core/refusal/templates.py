"""Refusal-template registry.

Maps each ``RefusalCode`` to a default ``RefusalTemplate``. Per-rule
overrides take precedence at build time; the registry provides the
fallback.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from arc_guard_core.refusal.codes import RefusalCode

_LOCK = threading.RLock()


@dataclass(frozen=True)
class RefusalTemplate:
    human_message: str
    next_steps: tuple[str, ...]


DEFAULT_REFUSAL_TEMPLATES: dict[RefusalCode, RefusalTemplate] = {
    RefusalCode.JAILBREAK: RefusalTemplate(
        human_message=(
            "This request was blocked because it appeared to attempt jailbreaking the system."
        ),
        next_steps=(
            "Rephrase without language that asks the assistant to ignore its rules.",
        ),
    ),
    RefusalCode.PII_CRITICAL: RefusalTemplate(
        human_message=(
            "This request contained sensitive personal information that cannot be processed."
        ),
        next_steps=(
            "Remove personally identifying details before re-submitting.",
            "Use a placeholder description instead of real names or numbers.",
        ),
    ),
    RefusalCode.STRATEGY_FAILED: RefusalTemplate(
        human_message=(
            "An internal processing step failed; the request was blocked as a safety measure."
        ),
        next_steps=(
            "Retry the request.",
            "Contact support if the issue persists.",
        ),
    ),
    RefusalCode.POLICY_BLOCK: RefusalTemplate(
        human_message="This request was blocked by policy.",
        next_steps=("Adjust the request and try again.",),
    ),
    RefusalCode.FIDELITY_DROP_PLACEHOLDER: RefusalTemplate(
        human_message="(reserved for fidelity-drop refusals — detector not yet implemented)",
        next_steps=(),
    ),
}


_REGISTRY: dict[RefusalCode, RefusalTemplate] = dict(DEFAULT_REFUSAL_TEMPLATES)


def register_refusal_template(code: RefusalCode, template: RefusalTemplate) -> None:
    with _LOCK:
        _REGISTRY[code] = template


def get_refusal_template(code: RefusalCode) -> RefusalTemplate:
    with _LOCK:
        return _REGISTRY[code]


__all__ = [
    "RefusalTemplate",
    "DEFAULT_REFUSAL_TEMPLATES",
    "register_refusal_template",
    "get_refusal_template",
]
