"""Same input → same hash digests across calls."""

from __future__ import annotations

from arc_guard.intent.lock import build_intent_lock


def test_same_inputs_produce_identical_locks() -> None:
    lock_a = build_intent_lock(
        original_text="Tell me about widgets.",
        sanitized_text="Tell me about [PRODUCT].",
        rehydrated_text="Tell me about widgets.",
        encoder_id="stub:1",
    )
    lock_b = build_intent_lock(
        original_text="Tell me about widgets.",
        sanitized_text="Tell me about [PRODUCT].",
        rehydrated_text="Tell me about widgets.",
        encoder_id="stub:1",
    )
    assert lock_a == lock_b
    assert lock_a.original_intent_hash == lock_b.original_intent_hash
    assert lock_a.sanitized_prompt_hash == lock_b.sanitized_prompt_hash
    assert lock_a.rehydrated_answer_hash == lock_b.rehydrated_answer_hash


def test_different_originals_produce_different_hashes() -> None:
    lock_a = build_intent_lock(
        original_text="Tell me about widgets.",
        sanitized_text="placeholder",
        rehydrated_text="placeholder",
        encoder_id=None,
    )
    lock_b = build_intent_lock(
        original_text="Tell me about gizmos.",
        sanitized_text="placeholder",
        rehydrated_text="placeholder",
        encoder_id=None,
    )
    assert lock_a.original_intent_hash != lock_b.original_intent_hash
    assert lock_a.sanitized_prompt_hash == lock_b.sanitized_prompt_hash


def test_canonicalize_collapses_meaningless_variation() -> None:
    """Different formatting → same hash (NFC + strip + collapse + lowercase)."""
    lock_a = build_intent_lock(
        original_text="  Hello   World!  ",
        sanitized_text="x",
        rehydrated_text="x",
        encoder_id=None,
    )
    lock_b = build_intent_lock(
        original_text="HELLO WORLD!",
        sanitized_text="x",
        rehydrated_text="x",
        encoder_id=None,
    )
    assert lock_a.original_intent_hash == lock_b.original_intent_hash


def test_each_hash_is_64_char_hex() -> None:
    lock = build_intent_lock(
        original_text="anything",
        sanitized_text="anything",
        rehydrated_text="anything",
        encoder_id="stub:1",
    )
    for digest in (
        lock.original_intent_hash,
        lock.sanitized_prompt_hash,
        lock.rehydrated_answer_hash,
    ):
        assert digest is not None
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)
