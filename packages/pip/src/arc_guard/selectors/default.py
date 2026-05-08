"""DefaultStrategySelector — bundled entity-type to strategy-name selector.

Maps the entity classes recognised by the bundled inspectors to the
appropriate masking strategy:

- Free-text PII (email, phone, person, location)            -> ``redact``
- Stable identifiers (SSN, IBAN, IP, etc.)                  -> ``hash``
- Credentials (credit card, API key, token, password)       -> ``block``
- Internal identifiers (employee, project, customer codes)  -> ``tokenize``
- Low-sensitivity context (URL, datetime, NRP)              -> ``warn``

Unmapped entity types fall back to ``redact`` and emit a structured
``guard.selector.unmapped_entity_type`` event so operators can extend
the mapping without silently losing fidelity.

Operators construct overrides via::

    DefaultStrategySelector(
        mapping={**DefaultStrategySelector.DEFAULT_MAPPING, "MY_TYPE": "block"},
    )
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from arc_guard_core.observability import Logger, NullLogger
from arc_guard_core.types import Finding, GuardResult


class DefaultStrategySelector:
    """Maps detected entity types to registered strategy names.

    Concurrency: stateless and thread-safe. The mapping is read-only and
    the logger hook is the only mutable reference.
    Failure mode: never raises. Unknown entity types fall back to
    ``redact`` and emit an observability event.
    """

    DEFAULT_MAPPING: Mapping[str, str] = MappingProxyType(
        {
            # Free-text PII -> redact
            "EMAIL_ADDRESS": "redact",
            "PHONE_NUMBER": "redact",
            "PERSON": "redact",
            "LOCATION": "redact",
            # Stable identifiers -> hash
            "US_SSN": "hash",
            "US_DRIVER_LICENSE": "hash",
            "US_PASSPORT": "hash",
            "IBAN_CODE": "hash",
            "IP_ADDRESS": "hash",
            # Credentials -> block
            "CREDIT_CARD": "block",
            "US_BANK_NUMBER": "block",
            "API_KEY": "block",
            "PASSWORD": "block",
            "BEARER_TOKEN": "block",
            # Internal identifiers -> tokenize
            "EMPLOYEE_ID": "tokenize",
            "INTERNAL_PROJECT_CODE": "tokenize",
            "CUSTOMER_ID": "tokenize",
            # Low-sensitivity context -> warn
            "URL": "warn",
            "DATE_TIME": "warn",
            "NRP": "warn",
        }
    )

    def __init__(
        self,
        *,
        mapping: Mapping[str, str] | None = None,
        logger: Logger | None = None,
    ) -> None:
        self._mapping: Mapping[str, str] = (
            mapping if mapping is not None else self.DEFAULT_MAPPING
        )
        self._logger: Logger = logger if logger is not None else NullLogger()

    def select(self, finding: Finding, guard_result: GuardResult) -> str:  # noqa: ARG002
        strategy = self._mapping.get(finding.entity_type)
        if strategy is not None:
            return strategy
        self._logger.event(
            "guard.selector.unmapped_entity_type",
            level="warning",
            selector="default",
            entity_type=finding.entity_type,
            fallback_strategy="redact",
        )
        return "redact"


from arc_guard.selectors.registry import register_selector  # noqa: E402

register_selector("default", DefaultStrategySelector())


__all__ = ["DefaultStrategySelector"]
