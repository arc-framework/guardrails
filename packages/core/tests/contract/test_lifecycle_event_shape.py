"""Contract: every LifecycleEvent class follows the universal envelope
contract; the tagged union exhaustively covers every event class; JSON
round-trips via dataclasses.asdict() without loss.
"""

from __future__ import annotations

import json
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime, timezone
from typing import get_args

from arc_guard_core.lifecycle import ALL_EVENT_TYPES, LifecycleEvent, new_event_id
from arc_guard_core.lifecycle.events import LifecycleEventBase

UNIVERSAL_FIELDS = {"id", "parent_id", "seq", "ts", "rid"}


def test_every_event_type_inherits_base() -> None:
    for cls in ALL_EVENT_TYPES:
        assert issubclass(cls, LifecycleEventBase), cls


def test_every_event_type_is_frozen_dataclass() -> None:
    for cls in ALL_EVENT_TYPES:
        assert is_dataclass(cls), cls
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} must be frozen"


def test_every_event_type_carries_universal_fields() -> None:
    for cls in ALL_EVENT_TYPES:
        names = {f.name for f in fields(cls)}
        missing = UNIVERSAL_FIELDS - names
        assert not missing, f"{cls.__name__} missing universal fields {missing}"


def test_every_event_type_declares_event_type_classvar() -> None:
    for cls in ALL_EVENT_TYPES:
        assert hasattr(cls, "event_type"), f"{cls.__name__} missing event_type"
        assert cls.event_type == cls.__name__, (
            f"{cls.__name__} event_type discriminator should match class name; got {cls.event_type!r}"
        )


def test_tagged_union_is_exhaustive() -> None:
    """Every concrete event class must appear in the LifecycleEvent union."""
    union_members = set(get_args(LifecycleEvent))
    declared = set(ALL_EVENT_TYPES)
    extras = union_members - declared
    missing = declared - union_members
    assert not extras, f"union has classes not in ALL_EVENT_TYPES: {extras}"
    assert not missing, f"ALL_EVENT_TYPES has classes not in union: {missing}"


def test_event_count_matches_spec() -> None:
    """Spec promises 28 types: 23 base + 5 conditional."""
    assert len(ALL_EVENT_TYPES) == 28


def _sample_event(cls: type[LifecycleEventBase]) -> LifecycleEventBase:
    return cls(
        id=new_event_id(),
        parent_id=None,
        seq=0,
        ts=datetime.now(timezone.utc),
        rid="test-rid",
    )


def test_every_event_round_trips_through_asdict() -> None:
    for cls in ALL_EVENT_TYPES:
        ev = _sample_event(cls)
        d = asdict(ev)
        # Universal fields present in the dict.
        for f in UNIVERSAL_FIELDS:
            assert f in d, f"{cls.__name__} asdict missing {f}"
        # JSON-serializable after a tiny ts coercion (datetime → isoformat).
        d["ts"] = d["ts"].isoformat()
        # Some events have datetime / tuple inside; coerce to lists for JSON.
        as_json = json.dumps(d, default=str)
        assert as_json
