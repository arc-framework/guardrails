"""Contract: debug-entry cursor encoder/decoder roundtrip + error shapes.

Cursor format is opaque to clients, but the helpers preserve a stable
encode/decode roundtrip and raise ``ValueError`` on every malformed-token
case. The HTTP handler translates ``ValueError`` into HTTP 400; that
translation is asserted in a separate api-side test.
"""

from __future__ import annotations

import base64
import json

import pytest

from arc_guard_core.schemas.request_debug import (
    decode_debug_cursor,
    encode_debug_cursor,
)


def test_roundtrip_known_seq_and_rid() -> None:
    token = encode_debug_cursor(rid="01JABC0EVT", seq=42)
    assert isinstance(token, str)
    seq = decode_debug_cursor(token, expected_rid="01JABC0EVT")
    assert seq == 42


def test_roundtrip_zero_seq() -> None:
    token = encode_debug_cursor(rid="01JABC0EVT", seq=0)
    assert decode_debug_cursor(token, expected_rid="01JABC0EVT") == 0


def test_roundtrip_large_seq() -> None:
    token = encode_debug_cursor(rid="01JABC0EVT", seq=10_000_000)
    assert decode_debug_cursor(token, expected_rid="01JABC0EVT") == 10_000_000


def test_token_is_url_safe() -> None:
    """No `+`, `/`, or `=` (urlsafe base64; padding may legitimately appear,
    but plus/slash must not)."""
    token = encode_debug_cursor(rid="01JABC0EVT", seq=42)
    assert "+" not in token
    assert "/" not in token


def test_decode_rejects_non_base64() -> None:
    with pytest.raises(ValueError, match="not valid base64"):
        decode_debug_cursor("not!base64!at!all!", expected_rid="01JABC0EVT")


def test_decode_rejects_non_json_payload() -> None:
    bogus = base64.urlsafe_b64encode(b"this is not json").decode("ascii")
    with pytest.raises(ValueError, match="not valid JSON"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_non_object_payload() -> None:
    bogus = base64.urlsafe_b64encode(b"[1, 2, 3]").decode("ascii")
    with pytest.raises(ValueError, match="must be a JSON object"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_missing_seq() -> None:
    bogus = base64.urlsafe_b64encode(
        json.dumps({"rid": "01JABC0EVT"}).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(ValueError, match="missing required key 'seq'"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_missing_rid() -> None:
    bogus = base64.urlsafe_b64encode(
        json.dumps({"seq": 1}).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(ValueError, match="missing required key 'rid'"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_non_integer_seq() -> None:
    bogus = base64.urlsafe_b64encode(
        json.dumps({"seq": "42", "rid": "01JABC0EVT"}).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(ValueError, match="'seq' must be an integer"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_boolean_seq() -> None:
    """Subtle Python type quirk: ``isinstance(True, int)`` is True. Ensure
    we explicitly reject booleans even though they pass the int check."""
    bogus = base64.urlsafe_b64encode(
        json.dumps({"seq": True, "rid": "01JABC0EVT"}).encode("utf-8")
    ).decode("ascii")
    with pytest.raises(ValueError, match="'seq' must be an integer"):
        decode_debug_cursor(bogus, expected_rid="01JABC0EVT")


def test_decode_rejects_rid_mismatch() -> None:
    token = encode_debug_cursor(rid="01JABC0EVT", seq=42)
    with pytest.raises(ValueError, match="does not match requested rid"):
        decode_debug_cursor(token, expected_rid="01JZZZ0EVT")
