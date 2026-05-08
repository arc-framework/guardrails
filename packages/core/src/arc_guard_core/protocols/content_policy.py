"""ContentPolicy protocol — predicate-shaped policy evaluation.

Distinct from ``Inspector``: content policies operate at the policy-rule
level and produce a policy-firing decision; inspectors produce
entity-level findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from arc_guard_core.refusal.codes import RefusalCode


@dataclass(frozen=True)
class ContentPolicyDecision:
    """Result of a ``ContentPolicy.evaluate()`` call.

    ``policy_name`` is populated by the dispatcher on dispatch; the policy
    implementation typically does not set it directly.
    """

    matched: bool
    confidence: float | None = None
    policy_name: str = ""
    refusal_code: RefusalCode | None = None


@runtime_checkable
class ContentPolicy(Protocol):
    """A predicate-shaped contract evaluating an input for policy match.

    Concurrency: sync. ``evaluate()`` MUST be functionally pure for a given
    ``text``. Internal caches (e.g., embedding caches) are allowed if they
    don't change observable behavior across calls.

    Failure mode: closed. Exceptions raised by ``evaluate()`` are caught at
    the pipeline boundary and converted to a closed-posture refusal using
    ``RefusalCode.INTERNAL_PIPELINE_ERROR``. Implementations SHOULD return
    ``ContentPolicyDecision(matched=False)`` for unparseable input rather
    than raising.

    Aggregate evaluation: when multiple ``ContentPolicy`` instances are
    configured, the pipeline MUST evaluate every configured policy without
    short-circuit. Each match is recorded as a separate finding.
    """

    def evaluate(self, text: str) -> ContentPolicyDecision:
        """Return whether this policy matches ``text``.

        Args:
            text: The input under inspection. Always pre-sanitization.

        Returns:
            A ``ContentPolicyDecision`` describing the match result.
        """
        ...


__all__ = ["ContentPolicy", "ContentPolicyDecision"]
