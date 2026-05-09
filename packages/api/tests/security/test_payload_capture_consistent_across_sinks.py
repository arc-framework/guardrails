"""Cross-sink payload consistency: when payload capture is enabled, the
ring-buffer tier and the SQLite tier MUST surface byte-identical
payload-bearing fields for the same rid; when capture is disabled,
neither tier surfaces payload text.

The composite sink writes every emission to both children, so the two
queries are over the same source events. This test asserts the
serialization round-trip through SQLite preserves the payload field
content exactly.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app

PII_EMAIL = "alice.consistency@example.com"


def _send_pii(client: TestClient, rid: str) -> None:
    r = client.post(
        "/v1/chat/completions",
        json={
            "model": "echo",
            "messages": [
                {"role": "user", "content": f"my email is {PII_EMAIL} please advise"}
            ],
        },
        headers={"x-request-id": rid},
    )
    assert r.status_code == 200


def _query_ring_directly(app, rid: str) -> list[dict]:
    """Query the ring-buffer child of the composite directly, bypassing HTTP.

    The default sink stack is `Composite([RingBuffer, Sqlite, Broadcast])`;
    we walk the children to find each tier and serialize through the
    same path the HTTP envelope uses.
    """

    sink = app.state.arc_guard_lifecycle_sink
    children = getattr(sink, "_sinks", [sink])
    ring = next(c for c in children if type(c).__name__ == "RingBufferLifecycleSink")
    import asyncio

    events = asyncio.run(ring.query(rid)) or []
    return [_to_jsonable(e) for e in events]


def _query_sqlite_directly(app, rid: str) -> list[dict]:
    sink = app.state.arc_guard_lifecycle_sink
    children = getattr(sink, "_sinks", [sink])
    sqlite = next(c for c in children if type(c).__name__ == "SqliteLifecycleSink")
    import asyncio

    events = asyncio.run(sqlite.query(rid)) or []
    return [_to_jsonable(e) for e in events]


def _to_jsonable(event) -> dict:
    """Produce a JSON-comparable dict for one event."""
    import dataclasses

    d = dataclasses.asdict(event)
    d["event_type"] = type(event).event_type
    return json.loads(json.dumps(d, default=str))


def _payload_bearing_fields(events: list[dict]) -> list[tuple[str, str | None]]:
    """Return (event_type, payload_text) pairs for payload-bearing events."""
    out: list[tuple[str, str | None]] = []
    for ev in events:
        et = ev["event_type"]
        if et == "RequestStarted":
            out.append((et, ev.get("raw_input")))
        elif et == "SanitizationApplied":
            out.append((et, ev.get("text_after")))
        elif et == "BackendResponded":
            out.append((et, ev.get("response_text")))
    return out


def _build_app(*, capture_payloads: bool):
    tmp = tempfile.TemporaryDirectory()
    sqlite_path = str(Path(tmp.name) / "lifecycle.db")
    settings = ServiceSettings(
        backend="echo",
        lifecycle_buffer_capacity=5000,
        lifecycle_sqlite_path=sqlite_path,
        lifecycle_capture_payloads=capture_payloads,
    )
    return TestClient(create_app(settings)), tmp


def test_capture_enabled_payload_fields_match_across_ring_and_sqlite() -> None:
    client, tmp = _build_app(capture_payloads=True)
    try:
        with client:
            rid = "consistency-capture-on"
            _send_pii(client, rid)

            ring_events = _query_ring_directly(client.app, rid)
            sqlite_events = _query_sqlite_directly(client.app, rid)

            assert ring_events, "ring buffer returned no events"
            assert sqlite_events, "sqlite tier returned no events"

            ring_payload = _payload_bearing_fields(ring_events)
            sqlite_payload = _payload_bearing_fields(sqlite_events)
            assert ring_payload == sqlite_payload, (
                f"payload-bearing fields differ across tiers\n"
                f"ring:   {ring_payload}\nsqlite: {sqlite_payload}"
            )

            ring_blob = json.dumps(ring_events, sort_keys=True)
            assert PII_EMAIL not in ring_blob, "raw email leaked despite raw flag off"
    finally:
        tmp.cleanup()


def test_capture_disabled_neither_tier_surfaces_payload_text() -> None:
    client, tmp = _build_app(capture_payloads=False)
    try:
        with client:
            rid = "consistency-capture-off"
            _send_pii(client, rid)

            ring_events = _query_ring_directly(client.app, rid)
            sqlite_events = _query_sqlite_directly(client.app, rid)

            for events, label in ((ring_events, "ring"), (sqlite_events, "sqlite")):
                pf = _payload_bearing_fields(events)
                for et, text in pf:
                    assert text is None, (
                        f"{label} tier event {et} carries payload text "
                        f"under default policy: {text!r}"
                    )
    finally:
        tmp.cleanup()
