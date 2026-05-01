"""Refusal envelope support — code registry, helper builders, templates."""

from __future__ import annotations

from arc_guard_core.refusal.codes import RefusalCode
from arc_guard_core.refusal.templates import (
    DEFAULT_REFUSAL_TEMPLATES,
    RefusalTemplate,
    get_refusal_template,
    register_refusal_template,
)

__all__ = [
    "RefusalCode",
    "RefusalTemplate",
    "DEFAULT_REFUSAL_TEMPLATES",
    "register_refusal_template",
    "get_refusal_template",
]
