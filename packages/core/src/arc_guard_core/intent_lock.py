"""IntentLock — content-addressed audit binding on the DecisionRecord.

The lock binds three artifacts of a single guard run — original intent,
sanitized prompt, and (when applicable) rehydrated answer — into a
single record. Each artifact is referenced by a SHA-256 hex digest of
its canonical form (NFC normalize → strip → collapse whitespace →
lowercase → UTF-8); raw text is never stored on the lock. The
``encoder_id`` field records which encoder captured the intent so
auditors can reconstruct the chain.

The hashes are deterministic so reviewers can join captured records by
content fingerprint without seeing raw payloads.
"""

from __future__ import annotations

from dataclasses import dataclass

_HEX_DIGEST_LEN = 64


@dataclass(frozen=True)
class IntentLock:
    """Auditable binding of original intent, sanitized prompt, rehydrated answer.

    All hash fields are SHA-256 hex digests (64 lowercase hex chars).
    ``rehydrated_answer_hash`` is ``None`` for runs that refused before
    generation. ``encoder_id`` is ``None`` when the null encoder is in
    use — the lock still emits but does not claim semantic encoding ran.
    """

    original_intent_hash: str
    sanitized_prompt_hash: str
    rehydrated_answer_hash: str | None
    encoder_id: str | None

    def __post_init__(self) -> None:
        _ensure_hex_digest("original_intent_hash", self.original_intent_hash)
        _ensure_hex_digest("sanitized_prompt_hash", self.sanitized_prompt_hash)
        if self.rehydrated_answer_hash is not None:
            _ensure_hex_digest(
                "rehydrated_answer_hash",
                self.rehydrated_answer_hash,
            )


def _ensure_hex_digest(field_name: str, value: str) -> None:
    if len(value) != _HEX_DIGEST_LEN:
        raise ValueError(f"IntentLock.{field_name} must be a 64-char SHA-256 hex digest")
    if any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"IntentLock.{field_name} must be lowercase hexadecimal")


__all__ = ["IntentLock"]
