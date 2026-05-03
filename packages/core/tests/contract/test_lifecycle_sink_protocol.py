"""Contract: NullLifecycleSink satisfies the LifecycleSink Protocol; query
returns None for any rid; emit + close return None and don't raise.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from arc_guard_core.lifecycle import (
    LifecycleSink,
    NullLifecycleSink,
    RequestStarted,
    new_event_id,
)


def test_null_sink_satisfies_protocol() -> None:
    assert isinstance(NullLifecycleSink(), LifecycleSink)


def test_null_sink_emit_is_no_op() -> None:
    sink = NullLifecycleSink()
    ev = RequestStarted(
        id=new_event_id(),
        parent_id=None,
        seq=0,
        ts=datetime.now(timezone.utc),
        rid="test",
    )
    # Should not raise; should return None.
    result = asyncio.run(sink.emit(ev))
    assert result is None


def test_null_sink_query_returns_none() -> None:
    sink = NullLifecycleSink()
    result = asyncio.run(sink.query("any-rid"))
    assert result is None


def test_null_sink_close_is_idempotent() -> None:
    sink = NullLifecycleSink()
    asyncio.run(sink.close())
    asyncio.run(sink.close())  # second call must not raise
