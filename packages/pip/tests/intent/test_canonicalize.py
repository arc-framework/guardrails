"""``canonicalize`` unit tests."""

from __future__ import annotations

from arc_guard.intent.canonicalize import canonicalize


def test_strips_leading_and_trailing_whitespace() -> None:
    assert canonicalize("   hello   ") == "hello"


def test_collapses_internal_whitespace_runs() -> None:
    assert canonicalize("hello   world") == "hello world"
    assert canonicalize("hello\n\n\tworld") == "hello world"


def test_lowercases_text() -> None:
    assert canonicalize("HELLO World") == "hello world"


def test_nfc_normalizes_combining_marks() -> None:
    """``é`` written as e + combining-acute (NFD) folds to single-char ``é`` (NFC)."""
    nfd_form = "é"  # e + combining acute
    nfc_form = "é"  # precomposed é
    assert canonicalize(nfd_form) == canonicalize(nfc_form)


def test_empty_input_returns_empty_string() -> None:
    assert canonicalize("") == ""
    assert canonicalize("   \n\t  ") == ""


def test_round_trips_through_utf8_encode() -> None:
    canonical = canonicalize("Hello, World")
    encoded = canonical.encode("utf-8")
    decoded = encoded.decode("utf-8")
    assert decoded == canonical
