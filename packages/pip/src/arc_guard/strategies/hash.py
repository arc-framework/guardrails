from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from collections.abc import Sequence
from pathlib import Path

from arc_guard_core.types import Finding, PolicyDecision

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
    """HMAC-SHA256 pseudonymization. Replaces each span with ``[HASH:<8hex>]``."""

    name: str = "hash"

    def __init__(self) -> None:
        self._key = _load_or_create_key()

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        if not findings:
            return text, ()

        decisions: list[PolicyDecision] = []
        # Apply right-to-left so earlier offsets stay stable.
        for finding_idx, finding in sorted(enumerate(findings), key=lambda pair: -pair[1].start):
            span = text[finding.start : finding.end]
            digest = hmac.new(self._key, span.encode("utf-8"), hashlib.sha256).hexdigest()[:8]
            replacement = f"[HASH:{digest}]"
            text = text[: finding.start] + replacement + text[finding.end :]
            decisions.append(
                PolicyDecision(
                    finding_ids=(finding_idx,),
                    strategy=self.name,
                    severity=finding.risk_level,
                    rationale=f"hashed {finding.entity_type}",
                    metadata={"digest_prefix": digest, "replacement": replacement},
                )
            )
        # Reverse so decisions are in span-order
        return text, tuple(reversed(decisions))
