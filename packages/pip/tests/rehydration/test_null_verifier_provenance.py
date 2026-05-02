"""Null verifier rejects invented placeholders."""

from __future__ import annotations

from arc_guard.rehydration.verifier import NullRehydrationVerifier


def test_invented_placeholder_is_rejected() -> None:
    verifier = NullRehydrationVerifier()
    verdict = verifier.verify(
        sanitized_prompt="Email [EMAIL] for help.",
        rehydration_candidate="Email [INVENTED] for help.",
        entity_map={"[EMAIL]": "alice@example.com"},
    )
    assert verdict.decision == "reject"
    assert verdict.reason == "invented_placeholder"


def test_provenance_match_passes() -> None:
    verifier = NullRehydrationVerifier()
    verdict = verifier.verify(
        sanitized_prompt="Email [EMAIL] for help.",
        rehydration_candidate="Email [EMAIL] for help.",
        entity_map={"[EMAIL]": "alice@example.com"},
    )
    assert verdict.decision == "accept"


def test_no_placeholders_in_candidate_accepts() -> None:
    verifier = NullRehydrationVerifier()
    verdict = verifier.verify(
        sanitized_prompt="Email [EMAIL] for help.",
        rehydration_candidate="Got it, I'll be in touch.",
        entity_map={"[EMAIL]": "alice@example.com"},
    )
    # No placeholders in candidate → nothing to check; accept.
    assert verdict.decision == "accept"
