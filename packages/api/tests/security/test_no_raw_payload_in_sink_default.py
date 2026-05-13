"""Security: under default settings, zero raw PII strings appear anywhere
in the lifecycle data captured during a soak test of N PII-containing
requests. This is the load-bearing safety guarantee of the payload
capture story.

Marked `slow` so the full 10k-request variant runs only on explicit
invocation. The default test run uses a 200-request smoke variant that
catches regressions in milliseconds.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

# Fixture-known PII strings — distinct per-request so we can test that
# NONE of them leak into any event field.
_EMAIL_FMT = "alice.test{i:05d}@fixture.invalid"
_PHONE_FMT = "555-867-{i:04d}"


@pytest.fixture(name="client")
def _client() -> TestClient:
    """Default settings — sanitized capture on, raw-input capture off."""
    app = create_app(ServiceSettings(backend="echo"))
    return TestClient(app)


def _send_pii_request(client: TestClient, i: int) -> str:
    rid = f"sec-test-{i:05d}"
    email = _EMAIL_FMT.format(i=i)
    phone = _PHONE_FMT.format(i=i)
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo",
            "messages": [
                {
                    "role": "user",
                    "content": f"my email is {email} and my phone is {phone}",
                }
            ],
        },
        headers={"x-request-id": rid},
    )
    assert r.status_code == 200
    return rid


def _no_raw_pii_in_lifecycle(client: TestClient, rid: str, i: int) -> None:
    """Fetch the rid's events and assert no raw PII string appears."""
    r = client.get(f"/lifecycle/{rid}")
    assert r.status_code == 200
    body_text = json.dumps(r.json())
    email = _EMAIL_FMT.format(i=i)
    phone = _PHONE_FMT.format(i=i)
    assert email not in body_text, f"raw email leaked into rid={rid} envelope (request {i})"
    assert phone not in body_text, f"raw phone leaked into rid={rid} envelope (request {i})"


def test_smoke_200_pii_requests_under_default_settings(client: TestClient) -> None:
    """Default-settings smoke variant — 200 distinct PII requests, asserting
    none leak. Runs in the default test suite to catch regressions fast."""
    rids = [(i, _send_pii_request(client, i)) for i in range(200)]
    for i, rid in rids:
        _no_raw_pii_in_lifecycle(client, rid, i)


@pytest.mark.slow
def test_soak_10k_pii_requests_under_default_settings(client: TestClient) -> None:
    """Full soak — 10,000 distinct PII requests under default settings.

    Run via `pytest -m slow tests/security/test_no_raw_payload_in_sink_default.py`.
    Skipped from the default fast suite (would add minutes to CI).
    """
    rids = [(i, _send_pii_request(client, i)) for i in range(10_000)]
    for i, rid in rids:
        _no_raw_pii_in_lifecycle(client, rid, i)


def test_default_capture_flags_enable_sanitized_payloads_only() -> None:
    """Sanity guard — keep sanitized capture on by default while raw-input
    capture stays opt-in and security-sensitive."""
    s = ServiceSettings()
    assert s.lifecycle_capture_payloads is True
    assert s.lifecycle_capture_raw_input is False
