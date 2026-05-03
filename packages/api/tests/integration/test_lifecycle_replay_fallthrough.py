"""Integration: replay endpoint queries the configured composite sink and
falls through tiers correctly. Verifies the X-Lifecycle-Tier response
header reflects which tier actually served the response.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from arc_guard_service.settings import ServiceSettings
from arc_guard_service.transport.http import create_app


def _post(client: TestClient, rid: str) -> None:
    r = client.post(
        "/v1/chat/completions",
        json={"model": "demo", "messages": [{"role": "user", "content": "hello"}]},
        headers={"x-request-id": rid},
    )
    assert r.status_code == 200, r.text


def test_recent_request_served_from_ring_buffer(tmp_path: Path) -> None:
    """A request emitted moments ago lives in BOTH ring + SQLite; lookup
    must report `ring-buffer` (the first tier in the composite)."""
    db = tmp_path / "lc.db"
    settings = ServiceSettings(
        backend="echo",
        lifecycle_sqlite_path=str(db),
        lifecycle_buffer_capacity=100,
    )
    with TestClient(create_app(settings)) as client:
        _post(client, "tier-recent")
        r = client.get("/lifecycle/tier-recent")
        assert r.status_code == 200
        assert r.headers["x-lifecycle-tier"] == "ring-buffer"
        assert r.json()["served_from"] == "ring-buffer"


def test_evicted_request_falls_through_to_sqlite(tmp_path: Path) -> None:
    """When a rid is evicted from the ring buffer (capacity=1, then 2 distinct
    rids), the lookup MUST fall through to SQLite and still return the events.
    Header MUST surface `sqlite` so the operator knows the slow tier served it.
    """
    db = tmp_path / "lc.db"
    settings = ServiceSettings(
        backend="echo",
        lifecycle_sqlite_path=str(db),
        lifecycle_buffer_capacity=1,  # tiny — second rid evicts first
    )
    with TestClient(create_app(settings)) as client:
        _post(client, "tier-old-rid")
        _post(client, "tier-newer-rid")  # evicts "tier-old-rid" from ring

        r = client.get("/lifecycle/tier-old-rid")
        assert r.status_code == 200
        assert r.headers["x-lifecycle-tier"] == "sqlite"
        assert r.json()["served_from"] == "sqlite"
        assert len(r.json()["events"]) >= 9


def test_lookup_404_when_no_tier_has_the_rid(tmp_path: Path) -> None:
    db = tmp_path / "lc.db"
    settings = ServiceSettings(
        backend="echo", lifecycle_sqlite_path=str(db)
    )
    with TestClient(create_app(settings)) as client:
        r = client.get("/lifecycle/never-existed")
        assert r.status_code == 404
        assert r.json()["code"] == "rid_not_found"


def test_lookup_survives_app_restart(tmp_path: Path) -> None:
    """Boot app, send a request (writes to SQLite + ring), tear down app,
    boot a NEW app pointing at the same SQLite file (ring is empty), look
    up the rid → must return 200 from `sqlite` tier."""
    db = tmp_path / "lc.db"
    settings = ServiceSettings(
        backend="echo", lifecycle_sqlite_path=str(db)
    )

    # First app: send a request.
    with TestClient(create_app(settings)) as client1:
        _post(client1, "survives-restart")
        r = client1.get("/lifecycle/survives-restart")
        assert r.status_code == 200

    # Second app (fresh process state, same SQLite file).
    with TestClient(create_app(settings)) as client2:
        r = client2.get("/lifecycle/survives-restart")
        assert r.status_code == 200, r.text
        # The ring buffer in the new app instance is empty, so SQLite must serve.
        assert r.headers["x-lifecycle-tier"] == "sqlite"
        assert len(r.json()["events"]) >= 9


def test_app_works_when_sqlite_disabled(tmp_path: Path) -> None:
    """Setting `lifecycle_sqlite_path=None` falls back to ring-only;
    the app boots, the lookup endpoint works for recent rids, and there's
    no SQLite file involvement."""
    settings = ServiceSettings(
        backend="echo", lifecycle_sqlite_path=None
    )
    with TestClient(create_app(settings)) as client:
        _post(client, "ring-only-rid")
        r = client.get("/lifecycle/ring-only-rid")
        assert r.status_code == 200
        assert r.headers["x-lifecycle-tier"] == "ring-buffer"
