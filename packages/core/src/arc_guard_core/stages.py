"""Pipeline stage descriptors for the observability layer.

The stage names are a closed initial set for the currently implemented
pipeline. Downstream specs extend the set by adding constants below and
appending to ``STAGE_DESCRIPTORS``; existing call sites do not change.

Form: module-level ``Final[str]`` constants plus a ``STAGE_DESCRIPTORS:
frozenset[str]`` allow-list. Constants over a ``StrEnum`` so the set
stays open to additive extension across specs.
"""

from __future__ import annotations

from typing import Final

STAGE_VALIDATE: Final[str] = "validate"
STAGE_DEFEND: Final[str] = "defend"
STAGE_CLASSIFY: Final[str] = "classify"
STAGE_DECEPTION_INSPECT: Final[str] = "deception_inspect"
STAGE_SANITIZE: Final[str] = "sanitize"
STAGE_ROUTE: Final[str] = "route"
STAGE_EXECUTE: Final[str] = "execute"
STAGE_REFUSAL: Final[str] = "refusal"
STAGE_VERIFY: Final[str] = "verify"
STAGE_REHYDRATE: Final[str] = "rehydrate"
STAGE_DECISION_EMIT: Final[str] = "decision_emit"
STAGE_REPORT: Final[str] = "report"

STAGE_DESCRIPTORS: frozenset[str] = frozenset({
    STAGE_VALIDATE,
    STAGE_DEFEND,
    STAGE_CLASSIFY,
    STAGE_DECEPTION_INSPECT,
    STAGE_SANITIZE,
    STAGE_ROUTE,
    STAGE_EXECUTE,
    STAGE_REFUSAL,
    STAGE_VERIFY,
    STAGE_REHYDRATE,
    STAGE_DECISION_EMIT,
    STAGE_REPORT,
})


__all__ = [
    "STAGE_VALIDATE",
    "STAGE_DEFEND",
    "STAGE_CLASSIFY",
    "STAGE_DECEPTION_INSPECT",
    "STAGE_SANITIZE",
    "STAGE_ROUTE",
    "STAGE_EXECUTE",
    "STAGE_REFUSAL",
    "STAGE_VERIFY",
    "STAGE_REHYDRATE",
    "STAGE_DECISION_EMIT",
    "STAGE_REPORT",
    "STAGE_DESCRIPTORS",
]
