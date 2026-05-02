"""FR-007: BoundedRedactor rejects values containing input substrings.

Once ``set_run_originals`` is called with the run's input text, any
attribute value that contains a >= 4-character chunk of that text is
rejected with ``reason="contains_input_substring"``. This is the
runtime enforcer that pairs with the CI-time leak scanner.
"""

from __future__ import annotations

from arc_guard.observability import (
    REASON_CONTAINS_INPUT_SUBSTRING,
    BoundedRedactor,
)


def test_rejects_value_containing_input_chunk() -> None:
    redactor = BoundedRedactor()
    redactor.set_run_originals(("My SSN is 123-45-6789, please mask it.",))

    result = redactor.sanitize("custom_key", "leaked: 123-45-6789")

    assert result.accepted is False
    assert result.reason == REASON_CONTAINS_INPUT_SUBSTRING


def test_rejects_when_attribute_overlaps_input() -> None:
    redactor = BoundedRedactor()
    redactor.set_run_originals(("Project Phoenix is on track.",))

    result = redactor.sanitize("user_note", "We discussed Phoenix today")

    assert result.accepted is False
    assert result.reason == REASON_CONTAINS_INPUT_SUBSTRING


def test_accepts_value_with_no_overlap() -> None:
    redactor = BoundedRedactor()
    redactor.set_run_originals(("My SSN is 123-45-6789.",))

    result = redactor.sanitize("stage", "validate")  # benign stage label

    assert result.accepted is True


def test_accepts_when_no_originals_set() -> None:
    redactor = BoundedRedactor()
    # No set_run_originals called — substring branch skipped.

    result = redactor.sanitize("custom_key", "anything goes")

    assert result.accepted is True


def test_short_originals_do_not_trigger_rejection() -> None:
    """Originals shorter than the 4-char threshold cannot match anything."""
    redactor = BoundedRedactor()
    redactor.set_run_originals(("hi",))

    result = redactor.sanitize("custom_key", "hi there")

    assert result.accepted is True
