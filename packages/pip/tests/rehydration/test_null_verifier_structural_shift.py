"""Null verifier rejects placeholders that shifted structural context."""

from __future__ import annotations

from arc_guard.rehydration.verifier import NullRehydrationVerifier


def test_value_to_literal_example_position_is_rejected() -> None:
    """A placeholder used as a value in the prompt but as a code-fenced
    literal example in the candidate is a structural shift."""
    verifier = NullRehydrationVerifier()
    verdict = verifier.verify(
        sanitized_prompt="Send the report to [EMAIL] tomorrow.",
        rehydration_candidate=(
            "Use a placeholder like `[EMAIL]` to mark recipient slots."
        ),
        entity_map={"[EMAIL]": "alice@acme.com"},
    )
    assert verdict.decision == "reject"
    assert verdict.reason == "structural_shift"


def test_same_surrounding_context_passes() -> None:
    verifier = NullRehydrationVerifier()
    verdict = verifier.verify(
        sanitized_prompt="Send the report to [EMAIL] tomorrow.",
        rehydration_candidate="Send the report to [EMAIL] tomorrow.",
        entity_map={"[EMAIL]": "alice@acme.com"},
    )
    assert verdict.decision == "accept"
