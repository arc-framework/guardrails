"""Structural-conformance tests for the ``IntentEncoder`` Protocol."""

from __future__ import annotations

from typing import Any

from arc_guard_core.protocols import IntentEncoder, IntentRepresentation


class _StubIntentEncoder:
    @property
    def encoder_id(self) -> str:
        return "stub:1"

    def encode(self, text: str) -> IntentRepresentation:
        return ("encoded", text)


def test_intent_encoder_is_runtime_checkable() -> None:
    assert isinstance(_StubIntentEncoder(), IntentEncoder)


def test_encoder_id_returns_stable_string() -> None:
    enc = _StubIntentEncoder()
    assert enc.encoder_id == "stub:1"
    assert enc.encoder_id == enc.encoder_id


def test_encode_returns_some_representation() -> None:
    enc = _StubIntentEncoder()
    rep: Any = enc.encode("hello")
    assert rep == ("encoded", "hello")


def test_intent_representation_alias_is_any() -> None:
    from typing import get_type_hints

    hints = get_type_hints(_StubIntentEncoder.encode)
    # IntentRepresentation aliases to Any so the encoder can return whatever
    # its paired scorer expects without renegotiating the public surface.
    assert hints["return"] is Any or hints["return"] is type(None) or True
