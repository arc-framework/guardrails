"""Integration: lifecycle payload-capture defaults and overrides.

Covers the spec contracts for the two flags:

- `lifecycle_capture_payloads=True` populates POST-sanitization text on
  events that carry it (`SanitizationApplied.text_after`,
  `BackendResponded.response_text`). Raw input MUST NOT leak.

- `lifecycle_capture_raw_input=True` populates raw inbound text on
  `RequestStarted.raw_input`. This is the security-sensitive flag.

Both flags can be enabled independently. Default settings keep sanitized
payload capture on while raw-input capture stays off; the security soak
test validates that raw PII still never leaks under that default.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

# Use a TLD Presidio reliably classifies as EMAIL_ADDRESS so the
# sanitize-and-rewrite path actually fires. Tests of behavior under
# *non-sanitized* PII are the security soak's job, not this file.
PII_EMAIL = "alice.captureopts@example.com"


def _build_client(**overrides) -> TestClient:
    settings = ServiceSettings(backend="echo", **overrides)
    return TestClient(create_app(settings))


def _send_pii(client: TestClient, rid: str) -> dict:
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo",
            "messages": [{"role": "user", "content": f"my email is {PII_EMAIL} please advise"}],
        },
        headers={"x-request-id": rid},
    )
    assert r.status_code == 200
    return client.get(f"/lifecycle/{rid}").json()


def test_capture_payloads_true_captures_sanitized_text_only() -> None:
    """When `lifecycle_capture_payloads=True` and `lifecycle_capture_raw_input=False`:
    sanitized placeholder text appears; raw email NEVER appears."""
    with _build_client(lifecycle_capture_payloads=True) as client:
        body = _send_pii(client, "capture-sanitized-001")

    full = json.dumps(body)
    assert PII_EMAIL not in full, (
        f"raw email leaked even though raw_input flag is OFF; envelope: {full[:500]}"
    )
    assert "[EMAIL_ADDRESS]" in full, (
        "sanitized placeholder should appear in the envelope when capture_payloads is on"
    )

    # Find a SanitizationApplied event and confirm text_after is populated.
    sa_events = [e for e in body["events"] if e["event_type"] == "SanitizationApplied"]
    assert sa_events, "expected at least one SanitizationApplied event"
    for sa in sa_events:
        assert sa["text_after"] is not None, (
            f"SanitizationApplied.text_after should be populated; got {sa}"
        )
        assert PII_EMAIL not in (sa["text_after"] or ""), (
            f"SanitizationApplied.text_after contains raw PII: {sa['text_after']}"
        )


def test_capture_payloads_true_captures_response_text() -> None:
    """When `lifecycle_capture_payloads=True`, BackendResponded carries the
    actual response_text (echo backend's reply)."""
    with _build_client(lifecycle_capture_payloads=True) as client:
        body = _send_pii(client, "capture-resp-001")

    br_events = [e for e in body["events"] if e["event_type"] == "BackendResponded"]
    assert br_events, "expected at least one BackendResponded event"
    for br in br_events:
        assert br["response_text"] is not None, (
            f"BackendResponded.response_text should be populated; got {br}"
        )
        # Echo backend's response is a transformation of the (sanitized)
        # input; the raw email MUST NOT appear here.
        assert PII_EMAIL not in (br["response_text"] or "")


def test_capture_raw_input_true_captures_raw_text_on_request_started() -> None:
    """When `lifecycle_capture_raw_input=True`, the RequestStarted event
    carries the raw inbound text. Documented as security-sensitive."""
    with _build_client(lifecycle_capture_raw_input=True) as client:
        body = _send_pii(client, "capture-raw-001")

    rs_events = [e for e in body["events"] if e["event_type"] == "RequestStarted"]
    assert len(rs_events) == 1
    rs = rs_events[0]
    assert rs["raw_input"] is not None
    assert PII_EMAIL in rs["raw_input"], (
        f"raw input should contain the raw email; got {rs['raw_input']}"
    )


def test_default_settings_capture_sanitized_fields_only() -> None:
    """Default settings capture sanitized fields while leaving raw_input empty."""
    with _build_client() as client:
        body = _send_pii(client, "capture-default-001")

    rs = next(e for e in body["events"] if e["event_type"] == "RequestStarted")
    assert rs.get("raw_input") is None

    for ev in body["events"]:
        if ev["event_type"] == "SanitizationApplied":
            assert ev.get("text_after") is not None
        if ev["event_type"] == "BackendResponded":
            assert ev.get("response_text") is not None


def test_capture_flags_can_be_enabled_independently() -> None:
    """Sanitized capture without raw, and raw capture without sanitized,
    are both valid. Verify the matrix."""
    # raw=on, sanitized=off → raw_input populated, text_after/response_text None
    with _build_client(
        lifecycle_capture_payloads=False, lifecycle_capture_raw_input=True
    ) as client:
        body = _send_pii(client, "capture-matrix-raw-only")
    rs = next(e for e in body["events"] if e["event_type"] == "RequestStarted")
    assert rs["raw_input"] is not None
    sa = next((e for e in body["events"] if e["event_type"] == "SanitizationApplied"), None)
    if sa is not None:
        assert sa["text_after"] is None

    # raw=off, sanitized=on → text_after populated, raw_input None
    with _build_client(lifecycle_capture_payloads=True) as client:
        body = _send_pii(client, "capture-matrix-sanitized-only")
    rs = next(e for e in body["events"] if e["event_type"] == "RequestStarted")
    assert rs["raw_input"] is None
    sa = next((e for e in body["events"] if e["event_type"] == "SanitizationApplied"), None)
    if sa is not None:
        assert sa["text_after"] is not None
