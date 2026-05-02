"""``IntentLock`` contains zero raw text — leak scanner returns empty."""

from __future__ import annotations

from arc_guard.intent.lock import build_intent_lock


def test_lock_fields_are_hex_digests_only() -> None:
    """No human-readable substring of the input survives the hash."""
    sensitive = "alice@acme.com SSN 123-45-6789"
    lock = build_intent_lock(
        original_text=sensitive,
        sanitized_text="contact [EMAIL] regarding [SSN]",
        rehydrated_text="contact alice@acme.com regarding [SSN]",
        encoder_id="stub:1",
    )
    # No substring of the original input appears in any hash field.
    for digest in (
        lock.original_intent_hash,
        lock.sanitized_prompt_hash,
        lock.rehydrated_answer_hash,
    ):
        assert digest is not None
        assert "alice" not in digest
        assert "@" not in digest
        assert "123-45" not in digest
        assert "SSN" not in digest


def test_lock_with_no_rehydrated_answer_emits_none_field() -> None:
    """Refused-before-generation runs have rehydrated_answer_hash=None."""
    lock = build_intent_lock(
        original_text="some prompt",
        sanitized_text="some prompt",
        rehydrated_text=None,
        encoder_id="stub:1",
    )
    assert lock.rehydrated_answer_hash is None
    assert lock.original_intent_hash is not None
    assert lock.sanitized_prompt_hash is not None


def test_lock_with_null_encoder_emits_none_encoder_id() -> None:
    lock = build_intent_lock(
        original_text="x",
        sanitized_text="x",
        rehydrated_text="x",
        encoder_id=None,
    )
    assert lock.encoder_id is None
