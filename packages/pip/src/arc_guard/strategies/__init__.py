"""arc_guard.strategies — built-in ActionStrategy implementations.

Importing this package triggers self-registration of all built-in
strategies into the module-level ``StrategyRegistry``. User strategies
register via ``register_strategy(name, instance)`` or the ``@strategy``
decorator from ``arc_guard.strategies.registry``.
"""

from __future__ import annotations

from arc_guard.strategies.block import BlockStrategy
from arc_guard.strategies.hash import HashStrategy
from arc_guard.strategies.redact import RedactStrategy
from arc_guard.strategies.registry import register_strategy
from arc_guard.strategies.tokenize import TokenizeStrategy
from arc_guard.strategies.warn import WarnStrategy

# Register built-ins (idempotent — duplicate same-instance registration is a no-op).
register_strategy("redact", RedactStrategy())
register_strategy("hash", HashStrategy())
register_strategy("block", BlockStrategy())
register_strategy("warn", WarnStrategy())
register_strategy("tokenize", TokenizeStrategy())


__all__ = [
    "BlockStrategy",
    "HashStrategy",
    "RedactStrategy",
    "TokenizeStrategy",
    "WarnStrategy",
    "register_strategy",
]
