"""``SemanticRehydrationVerifier`` — null verifier + Check 3 safety regression.

Inherits the placeholder-provenance and structural-shift checks from
``NullRehydrationVerifier`` and adds a third check: when the
rehydrated text re-passes the lightweight detection layer (the
foundation ``InjectionInspector``'s regex patterns), no NEW findings
appear that were not already present in the placeholder-bearing
candidate. New findings indicate a safety regression — rehydration
would re-introduce sensitive content.

The verifier reads the inspector's pattern set directly (rather than
calling ``inspect`` async) so the synchronous ``verify`` Protocol
method does not need to navigate event-loop semantics.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from arc_guard_core.exceptions import RehydrationVerifierError
from arc_guard_core.protocols.rehydration_verifier import RehydrationVerdict

from arc_guard.rehydration.verifier import NullRehydrationVerifier


@dataclass(frozen=True)
class _Finding:
    entity_type: str
    start: int
    end: int


def _scan_with_patterns(
    text: str, patterns: list[re.Pattern[str]],
) -> set[tuple[str, int, int]]:
    """Run regex patterns over ``text``; return ``(entity_type, start, end)`` triples."""
    findings: set[tuple[str, int, int]] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            findings.add(("INJECTION", match.start(), match.end()))
    return findings


class SemanticRehydrationVerifier(NullRehydrationVerifier):
    """Structural verifier + Check 3 safety regression via the injection inspector."""

    def __init__(self, *, injection_inspector: Any) -> None:
        # Read the inspector's compiled pattern list directly. The
        # foundation ``InjectionInspector`` exposes ``_all_patterns``
        # as the unified built-in + extra-patterns list.
        patterns = getattr(injection_inspector, "_all_patterns", None)
        if patterns is None:
            raise RehydrationVerifierError(
                "injection_inspector does not expose _all_patterns",
                code="rehydration_verifier.verifier_failed",
            )
        self._patterns: list[re.Pattern[str]] = list(patterns)

    def verify(
        self,
        *,
        sanitized_prompt: str,
        rehydration_candidate: str,
        entity_map: Mapping[str, str],
    ) -> RehydrationVerdict:
        # Run the structural checks first.
        structural_verdict = super().verify(
            sanitized_prompt=sanitized_prompt,
            rehydration_candidate=rehydration_candidate,
            entity_map=entity_map,
        )
        if structural_verdict.decision == "reject":
            return structural_verdict
        if not entity_map:
            return structural_verdict

        # Determine which placeholders we'd rehydrate post-structural pass.
        if structural_verdict.decision == "partial":
            accepts_map = dict(structural_verdict.per_placeholder)
        else:
            accepts_map = dict.fromkeys(entity_map, True)

        # Build the rehydrated text so we can scan it for new findings.
        rehydrated_text = rehydration_candidate
        for placeholder, original in entity_map.items():
            if accepts_map.get(placeholder, False):
                rehydrated_text = rehydrated_text.replace(placeholder, original)

        try:
            candidate_findings = _scan_with_patterns(
                rehydration_candidate, self._patterns,
            )
            rehydrated_findings = _scan_with_patterns(
                rehydrated_text, self._patterns,
            )
        except Exception as exc:
            raise RehydrationVerifierError(
                f"Safety inspector raised: {exc}",
                code="rehydration_verifier.verifier_failed",
                cause=exc,
            ) from exc

        # New findings (entity_type only — positions shift after rehydration
        # so we compare on type alone for the regression check).
        candidate_types = {entity_type for entity_type, _, _ in candidate_findings}
        rehydrated_types = {entity_type for entity_type, _, _ in rehydrated_findings}
        new_types = rehydrated_types - candidate_types

        if new_types:
            return RehydrationVerdict(
                decision="reject",
                reason="safety_regression",
            )
        return structural_verdict


__all__ = ["SemanticRehydrationVerifier"]
