"""TokenizeStrategy — per-input deterministic tokens (Spec 003)."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.types import Finding, PolicyDecision


class TokenizeStrategy:
    """Replace each detected span with ``[<TYPE>_TOK_<N>]``.

    Per-input deterministic: ``N`` is a per-type sequential index (1-indexed)
    in span order. Cross-run determinism is NOT promised by Spec 003 —
    Spec 007 may add per-tenant deterministic tokenization via injected
    secrets.
    """

    name: str = "tokenize"

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        if not findings:
            return text, ()

        # Pass 1: per-type counters for the per-input deterministic suffix
        sorted_in_span_order = sorted(enumerate(findings), key=lambda pair: pair[1].start)
        per_type_seen: dict[str, int] = {}
        replacements: list[tuple[int, str, int, int]] = []
        for finding_idx, f in sorted_in_span_order:
            per_type_seen[f.entity_type] = per_type_seen.get(f.entity_type, 0) + 1
            n = per_type_seen[f.entity_type]
            replacement = f"[{f.entity_type}_TOK_{n}]"
            replacements.append((finding_idx, replacement, f.start, f.end))

        # Apply right-to-left so offsets stay stable
        out = text
        for _finding_idx, replacement, start, end in sorted(
            replacements, key=lambda r: -r[2]
        ):
            out = out[:start] + replacement + out[end:]

        decisions = tuple(
            PolicyDecision(
                finding_ids=(finding_idx,),
                strategy=self.name,
                severity=findings[finding_idx].risk_level,
                rationale=f"tokenized {findings[finding_idx].entity_type} as {replacement}",
                metadata={"token": replacement},
            )
            for finding_idx, replacement, _start, _end in replacements
        )
        return out, decisions
