"""RedactStrategy — typed-placeholder replacement."""

from __future__ import annotations

from collections.abc import Sequence

from arc_guard_core.placeholders import format_placeholder
from arc_guard_core.policy import TransformSummary
from arc_guard_core.types import Finding, PolicyDecision


class RedactStrategy:
    """Replaces each detected span with a typed placeholder.

    Per D2: single occurrences are unsuffixed (``[CREDIT_CARD]``); multiple
    occurrences of the same entity type in one input use a sequential
    suffix (``[CREDIT_CARD_1]``, ``[CREDIT_CARD_2]``, …) in span order.
    Numbering resets per input.
    """

    name: str = "redact"

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, tuple[PolicyDecision, ...]]:
        if not findings:
            return text, ()

        # Pass 1: count occurrences per entity_type.
        type_counts: dict[str, int] = {}
        for f in findings:
            type_counts[f.entity_type] = type_counts.get(f.entity_type, 0) + 1

        # Pass 2: walk findings in span order, emit replacements with the
        # right placeholder format. Apply substitutions in reverse-span
        # order so offsets stay stable.
        sorted_in_span_order = sorted(enumerate(findings), key=lambda pair: pair[1].start)
        per_type_seen: dict[str, int] = {}
        replacements: list[tuple[int, str, int, int]] = []  # (finding_idx, placeholder, start, end)
        for finding_idx, f in sorted_in_span_order:
            per_type_seen[f.entity_type] = per_type_seen.get(f.entity_type, 0) + 1
            occurrence = per_type_seen[f.entity_type]
            total = type_counts[f.entity_type]
            placeholder = format_placeholder(f.entity_type, occurrence, total)
            replacements.append((finding_idx, placeholder, f.start, f.end))

        # Apply substitutions right-to-left so offsets stay stable.
        out = text
        for _finding_idx, placeholder, start, end in sorted(
            replacements, key=lambda r: -r[2]
        ):
            out = out[:start] + placeholder + out[end:]

        decisions = tuple(
            PolicyDecision(
                finding_ids=(finding_idx,),
                strategy=self.name,
                severity=findings[finding_idx].risk_level,
                rationale=f"redacted {findings[finding_idx].entity_type} as {placeholder}",
                metadata={"placeholder": placeholder},
            )
            for finding_idx, placeholder, _start, _end in replacements
        )
        return out, decisions

    def transform_summaries(
        self,
        findings: Sequence[Finding],
        decisions: Sequence[PolicyDecision],
    ) -> tuple[TransformSummary, ...]:
        """Build TransformSummary entries — used by the decision emitter."""
        out: list[TransformSummary] = []
        for d in decisions:
            placeholder = d.metadata.get("placeholder", "")
            for fid in d.finding_ids:
                f = findings[fid]
                out.append(
                    TransformSummary(
                        strategy=self.name,
                        target_finding_index=fid,
                        before_length=f.end - f.start,
                        after_length=len(placeholder),
                        replacement_kind="placeholder",
                        metadata={"placeholder": placeholder},
                    )
                )
        return tuple(out)
