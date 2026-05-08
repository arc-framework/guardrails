"""Missing-model behavior — SemanticContentPolicy raises ConfigSchemaError.

When the ``[semantic]`` extra is installed but the encoder cannot load
its model artifact (e.g. an air-gapped deployment without the model
file on disk), construction MUST raise a load-time configuration error
distinct from the missing-extra warning path.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest
from arc_guard_core.exceptions import ConfigSchemaError

from arc_guard.content_policies.semantic import SemanticContentPolicy


def _install_failing_encoder_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace ``arc_guard.middleware.semantic.encoder`` with a module
    whose ``SentenceTransformerIntentEncoder`` constructor raises
    ``FileNotFoundError`` to simulate a missing model artifact.
    """
    fake_module = types.ModuleType("arc_guard.middleware.semantic.encoder")

    class _BrokenEncoder:
        def __init__(self, **kwargs: Any) -> None:
            raise FileNotFoundError(
                "model artifact not found at expected path",
            )

        def encode(self, text: str) -> Any:
            raise NotImplementedError

    fake_module.SentenceTransformerIntentEncoder = _BrokenEncoder  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules,
        "arc_guard.middleware.semantic.encoder",
        fake_module,
    )


def test_missing_model_raises_config_schema_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_encoder_module(monkeypatch)
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="topic_block",
            exemplars=("anything",),
            similarity_threshold=0.5,
        )
    msg = str(excinfo.value)
    assert "topic_block" in msg
    assert "[semantic] extra is installed" in msg
    assert "encoder model artifact is unavailable" in msg


def test_missing_model_message_distinguishes_from_missing_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_encoder_module(monkeypatch)
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=("anything",),
            similarity_threshold=0.5,
        )
    msg = str(excinfo.value)
    assert "pip install arc-guard[semantic]" not in msg
    assert "model artifact" in msg


def test_missing_model_preserves_original_exception_as_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_failing_encoder_module(monkeypatch)
    with pytest.raises(ConfigSchemaError) as excinfo:
        SemanticContentPolicy(
            name="x",
            exemplars=("anything",),
            similarity_threshold=0.5,
        )
    assert isinstance(excinfo.value.__cause__, FileNotFoundError)
