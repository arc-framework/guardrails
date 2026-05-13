"""Contract test: TransportError shape + FAIL_RULE wiring.

Asserts the additive transport-layer leaf exception declares the documented
``__failure_mode__`` posture, the documented ``__valid_codes__`` set, and
that ``lookup_rule()`` returns the matching FAIL_RULE entry with the right
severity and refusal code.
"""

from __future__ import annotations

import pytest

from arc_guard_core import (
    FAILURE_API_TRANSPORT,
    PipelineError,
    RefusalCode,
    TransportError,
    lookup_rule,
)


def test_transport_error_inherits_from_pipeline_error() -> None:
    assert issubclass(TransportError, PipelineError)


def test_transport_error_failure_mode_is_closed() -> None:
    assert TransportError.__failure_mode__ == "closed"


def test_transport_error_valid_codes() -> None:
    assert TransportError.__valid_codes__ == frozenset(
        {
            "transport.timeout",
            "transport.payload_too_large",
            "transport.invalid_state",
        }
    )


def test_transport_error_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="not in __valid_codes__"):
        TransportError("bogus", code="transport.bogus")


@pytest.mark.parametrize(
    "code",
    [
        "transport.timeout",
        "transport.payload_too_large",
        "transport.invalid_state",
    ],
)
def test_transport_error_accepts_valid_codes(code: str) -> None:
    exc = TransportError("hit", code=code)
    assert exc.code == code


def test_transport_error_lookup_rule_matches_documented_mapping() -> None:
    rule, posture = lookup_rule(TransportError)
    assert rule.failure_class == FAILURE_API_TRANSPORT
    assert rule.severity == "error"
    assert rule.refusal_code == RefusalCode.API_TRANSPORT_TIMEOUT
    assert posture == "closed"
