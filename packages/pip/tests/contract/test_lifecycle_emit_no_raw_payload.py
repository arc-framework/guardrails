"""Contract: under default settings (lifecycle_capture_payloads=False),
no event field captured in the lifecycle sink contains raw user input
text. Asserts the spec's payload-safety invariant at the pipeline-emission
level — no consumer-level redaction needed.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import datetime
from typing import Any

import pytest

from arc_guard.observability.ring_buffer_lifecycle_sink import RingBufferLifecycleSink
from arc_guard.pipeline import GuardPipeline
from arc_guard_core.lifecycle import LifecycleEmitter
from arc_guard_core.types import GuardContext, GuardInput

# Fixture-known PII that MUST NOT appear in any captured event field.
PII_EMAIL = "alice.fixturetestonly@example.com"
PII_PHONE = "555-867-5309"


def _event_to_jsonable(event: Any) -> str:
    d = dataclasses.asdict(event)
    d["event_type"] = type(event).event_type
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, tuple):
            d[k] = list(v)
    return json.dumps(d)


@pytest.mark.asyncio
async def test_pii_email_never_appears_in_any_lifecycle_event() -> None:
    sink = RingBufferLifecycleSink(capacity=100)
    rid = "no-payload-test-email"
    emitter = LifecycleEmitter(sink, rid)

    pipeline = GuardPipeline(lifecycle_hook=sink)
    await pipeline.pre_process(
        GuardInput(
            text=f"please redact my email {PII_EMAIL} thanks",
            context=GuardContext(
                metadata={
                    "_lifecycle_emitter": emitter,
                    "_lifecycle_parent_id": None,
                },
            ),
        )
    )

    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None and len(events) > 0
    for event in events:
        payload = _event_to_jsonable(event)
        assert PII_EMAIL not in payload, (
            f"raw email leaked into {type(event).__name__} payload: {payload}"
        )


@pytest.mark.asyncio
async def test_pii_phone_never_appears_in_any_lifecycle_event() -> None:
    sink = RingBufferLifecycleSink(capacity=100)
    rid = "no-payload-test-phone"
    emitter = LifecycleEmitter(sink, rid)
    pipeline = GuardPipeline(lifecycle_hook=sink)

    await pipeline.pre_process(
        GuardInput(
            text=f"call me at {PII_PHONE} when you can",
            context=GuardContext(
                metadata={
                    "_lifecycle_emitter": emitter,
                    "_lifecycle_parent_id": None,
                },
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    assert events is not None and len(events) > 0
    for event in events:
        payload = _event_to_jsonable(event)
        assert PII_PHONE not in payload, (
            f"raw phone leaked into {type(event).__name__} payload: {payload}"
        )


@pytest.mark.asyncio
async def test_placeholder_strings_are_allowed_to_appear() -> None:
    """Sanity check: redaction-target placeholders DO appear in the sink
    (the safe substitute). Ensures the test isn't trivially passing by
    capturing nothing."""
    sink = RingBufferLifecycleSink(capacity=100)
    rid = "no-payload-placeholders-ok"
    emitter = LifecycleEmitter(sink, rid)
    pipeline = GuardPipeline(lifecycle_hook=sink)

    await pipeline.pre_process(
        GuardInput(
            text=f"my email is {PII_EMAIL}",
            context=GuardContext(
                metadata={
                    "_lifecycle_emitter": emitter,
                    "_lifecycle_parent_id": None,
                },
            ),
        )
    )
    await asyncio.sleep(0.05)

    events = await sink.query(rid)
    full_blob = "\n".join(_event_to_jsonable(e) for e in (events or []))
    # The placeholder is what consumers see — it MUST be present (proves
    # the test sees the events, just not the raw content).
    assert "EMAIL_ADDRESS" in full_blob
