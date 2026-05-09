import pytest
from pydantic import ValidationError

from arc_guard_service.examples_loader import ExpectedOutcome


def test_expected_outcome_block_requires_refusal_code():
    with pytest.raises(ValidationError, match="refusal_code"):
        ExpectedOutcome(
            action="block",
            phase="pre_process",
            refusal_code=None,
            findings=["JAILBREAK_DIRECT_OVERRIDE"],
        )


def test_expected_outcome_non_block_must_have_null_refusal_code():
    with pytest.raises(ValidationError, match="refusal_code"):
        ExpectedOutcome(
            action="redact",
            phase="pre_process",
            refusal_code="something",
            findings=["EMAIL_ADDRESS"],
        )


def test_expected_outcome_pre_process_default_tolerance_is_strict():
    eo = ExpectedOutcome(
        action="redact", phase="pre_process", refusal_code=None, findings=["EMAIL_ADDRESS"]
    )
    assert eo.tolerance == "strict"


def test_expected_outcome_post_process_default_tolerance_is_subset():
    eo = ExpectedOutcome(
        action="redact", phase="post_process", refusal_code=None, findings=[]
    )
    assert eo.tolerance == "subset"
