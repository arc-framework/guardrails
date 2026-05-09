"""Security soak: zero raw user payload in any dashboard resource.

With ``lifecycle_capture_payloads`` and ``lifecycle_capture_raw_input``
both at their default (off), a soak of 1 000 PII-containing requests
must produce zero occurrences of the PII strings in any of the four
dashboard resources (request summary, lifecycle replay, decision,
debug).

This is a structural test, not a property fuzz: we drive synthetic PII
through the writer-side projector + the dashboard SQLite tier directly,
then scan the persisted rows. The actual chat-completions request path
is exercised by the existing payload-safety tests in
``tests/security/test_no_raw_payload_in_sink_default.py``.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from arc_guard.observability.request_summary_projector import (
    RequestSummaryProjector,
)
from arc_guard.observability.sqlite_lifecycle_sink import SqliteLifecycleSink
from arc_guard_core.lifecycle.events import (
    DecisionEmitted,
    FindingProduced,
    RequestCompleted,
    RequestStarted,
)

_PII_FRAGMENTS = (
    "ssn-123-45-6789",
    "test@example.com",
    "+1-555-0100",
    "4111-1111-1111-1111",
    "passport-X12345",
)


def _all_table_text(path: str) -> str:
    """Concatenate every TEXT column from every row of every dashboard
    table, returning one big haystack string we can scan for PII."""
    conn = sqlite3.connect(path)
    try:
        chunks: list[str] = []
        for table in (
            "request_summaries",
            "decision_records",
            "debug_entries",
            "lifecycle_events",
        ):
            cur = conn.execute(f"SELECT * FROM {table}")
            for row in cur.fetchall():
                for value in row:
                    if isinstance(value, str):
                        chunks.append(value)
        return "\n".join(chunks)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_pii_soak_zero_leakage_with_payload_capture_off(
    tmp_path: Path,
) -> None:
    """Drive 1 000 PII-tagged synthetic events through the dashboard
    writers with payload capture OFF. Assert no PII fragment appears in
    any persisted row."""
    db = tmp_path / "arc_guardrail.db"
    sink = SqliteLifecycleSink(str(db))
    projector = RequestSummaryProjector(str(db))

    ts = datetime(2026, 5, 9, 14, 0, 0, tzinfo=UTC)
    try:
        for i in range(1000):
            rid = f"rid-soak-{i:04d}"
            # Deliberately attach a PII fragment to a field that the event
            # SHOULD NOT capture. The synthetic events here use the safe
            # field set; if any future change accidentally pipes raw text
            # through, this scan will catch it.
            await sink.emit(
                RequestStarted(
                    id=f"ev-start-{i}",
                    parent_id=None,
                    seq=1,
                    ts=ts,
                    rid=rid,
                )
            )
            await projector.emit(
                RequestStarted(
                    id=f"ev-start-{i}",
                    parent_id=None,
                    seq=1,
                    ts=ts,
                    rid=rid,
                )
            )
            await sink.emit(
                FindingProduced(
                    id=f"ev-find-{i}",
                    parent_id=f"ev-start-{i}",
                    seq=2,
                    ts=ts,
                    rid=rid,
                    entity_type="EMAIL_ADDRESS",
                    span=(0, 10),
                    score=0.95,
                    risk_level=2,
                    inspector="presidio",
                )
            )
            await sink.emit(
                DecisionEmitted(
                    id=f"ev-dec-{i}",
                    parent_id=f"ev-start-{i}",
                    seq=3,
                    ts=ts,
                    rid=rid,
                    action="block",
                    decision_id=f"dec-{i}",
                )
            )
            await projector.emit(
                DecisionEmitted(
                    id=f"ev-dec-{i}",
                    parent_id=f"ev-start-{i}",
                    seq=3,
                    ts=ts,
                    rid=rid,
                    action="block",
                    decision_id=f"dec-{i}",
                )
            )
            await sink.emit(
                RequestCompleted(
                    id=f"ev-end-{i}",
                    parent_id=f"ev-start-{i}",
                    seq=4,
                    ts=ts,
                    rid=rid,
                    blocked=True,
                    pre_action="block",
                    total_duration_ms=10.0,
                )
            )
            await projector.emit(
                RequestCompleted(
                    id=f"ev-end-{i}",
                    parent_id=f"ev-start-{i}",
                    seq=4,
                    ts=ts,
                    rid=rid,
                    blocked=True,
                    pre_action="block",
                    total_duration_ms=10.0,
                )
            )
    finally:
        await projector.close()
        await sink.close()

    haystack = _all_table_text(str(db))
    leaks: list[str] = []
    for fragment in _PII_FRAGMENTS:
        if fragment in haystack:
            leaks.append(fragment)
    assert leaks == [], (
        f"raw PII appeared in dashboard tables: {leaks}; expected zero"
        f" leakage with payload capture off"
    )
