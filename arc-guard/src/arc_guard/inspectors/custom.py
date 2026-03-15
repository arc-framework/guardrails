"""CustomInspector — hot-reloadable inspector driven by an EntityProvider."""

from __future__ import annotations

import logging

from arc_guard.protocols.entity_provider import EntityProvider
from arc_guard.types import Finding, GuardResult, RiskLevel

_LOG = logging.getLogger(__name__)

_PCI_PII_CATEGORIES = {"PCI", "PII"}


def _category_to_risk(category: str) -> RiskLevel:
    if category.upper() in _PCI_PII_CATEGORIES:
        return RiskLevel.HIGH
    return RiskLevel.MEDIUM


class CustomInspector:
    """Inspector driven by an EntityProvider for hot-reloadable entity definitions.

    On every inspect() call the provider is queried fresh — no caching — so
    entities can be added or removed at runtime without restarting the pipeline.

    Args:
        provider: Any object satisfying the EntityProvider protocol.
    """

    def __init__(self, provider: EntityProvider) -> None:
        self._provider = provider

    async def inspect(self, result: GuardResult) -> GuardResult:
        """Scan the result text against all currently registered entities.

        Entities are re-fetched from the provider on every call.
        Never raises — all exceptions are caught internally.
        """
        try:
            entities = self._provider.get_entities()
            if not entities:
                return result

            text = result.text
            new_findings = list(result.findings)

            for entity in entities:
                if entity.pattern is None:
                    continue
                for match in entity.pattern.finditer(text):
                    new_findings.append(
                        Finding(
                            entity_type=entity.name,
                            start=match.start(),
                            end=match.end(),
                            risk_level=_category_to_risk(entity.category),
                            inspector="custom",
                        )
                    )

            if len(new_findings) == len(result.findings):
                return result

            return GuardResult(
                text=result.text,
                action=result.action,
                findings=tuple(new_findings),
                bypass_reason=result.bypass_reason,
                phase=result.phase,
            )
        except Exception:
            _LOG.exception("CustomInspector encountered an unexpected error")
            return result
