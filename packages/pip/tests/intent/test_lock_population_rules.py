"""Population matrix: which fields are populated for which run kinds."""

from __future__ import annotations

import pytest

from arc_guard.intent.lock import build_intent_lock


def test_run_completed_with_sanitization_populates_all_fields() -> None:
    lock = build_intent_lock(
        original_text="prompt",
        sanitized_text="placeholder",
        rehydrated_text="answer",
        encoder_id="stub:1",
    )
    assert lock.original_intent_hash is not None
    assert lock.sanitized_prompt_hash is not None
    assert lock.rehydrated_answer_hash is not None
    assert lock.encoder_id == "stub:1"


def test_refused_before_generation_omits_rehydrated_answer() -> None:
    lock = build_intent_lock(
        original_text="prompt",
        sanitized_text="prompt",
        rehydrated_text=None,
        encoder_id="stub:1",
    )
    assert lock.rehydrated_answer_hash is None


def test_no_findings_run_has_equal_original_and_sanitized() -> None:
    """When sanitization had nothing to do, original_intent_hash == sanitized_prompt_hash."""
    same = "totally benign text"
    lock = build_intent_lock(
        original_text=same,
        sanitized_text=same,
        rehydrated_text=same,
        encoder_id="stub:1",
    )
    assert lock.original_intent_hash == lock.sanitized_prompt_hash


def test_null_encoder_run_has_none_encoder_id() -> None:
    lock = build_intent_lock(
        original_text="x",
        sanitized_text="x",
        rehydrated_text="x",
        encoder_id=None,
    )
    assert lock.encoder_id is None


def test_invalid_hash_length_rejected_at_construction() -> None:
    """Direct ``IntentLock`` construction validates the hex digest length."""
    from arc_guard_core.intent_lock import IntentLock

    with pytest.raises(ValueError, match="64-char SHA-256 hex digest"):
        IntentLock(
            original_intent_hash="too-short",
            sanitized_prompt_hash="a" * 64,
            rehydrated_answer_hash=None,
            encoder_id=None,
        )
