from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import Literal

from arc_guard.types import Finding

logger = logging.getLogger("arc_guard")

_DEFAULT_KEY_FILE = Path.home() / ".local" / "share" / "arc" / "guard_hash_key"


def _load_or_create_key() -> bytes:
    env_hex = os.environ.get("GUARD_HASH_KEY")
    if env_hex:
        return bytes.fromhex(env_hex)

    key_file_path = Path(os.environ.get("GUARD_HASH_KEY_FILE", str(_DEFAULT_KEY_FILE)))
    if key_file_path.exists():
        return bytes.fromhex(key_file_path.read_text().strip())

    key = secrets.token_bytes(32)
    key_file_path.parent.mkdir(parents=True, exist_ok=True)
    key_file_path.write_text(key.hex())
    logger.info("arc_guard: generated new hash key, stored at %s", key_file_path)
    return key


class HashStrategy:
    """HMAC-SHA256 pseudonymization — replaces each detected span with a 16-char hex digest."""

    def __init__(self) -> None:
        self._key = _load_or_create_key()

    def apply(self, text: str, findings: tuple[Finding, ...]) -> tuple[str, Literal["hash"]]:
        """Replace spans in *text* with truncated HMAC-SHA256 digests.

        Spans are replaced from right to left to preserve earlier offsets.
        """
        if not findings:
            return (text, "hash")

        for finding in sorted(findings, key=lambda f: f.start, reverse=True):
            span = text[finding.start : finding.end]
            digest = hmac.new(self._key, span.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
            text = text[: finding.start] + digest + text[finding.end :]

        return (text, "hash")
