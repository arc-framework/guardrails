# Contract — Strategy Registry

The `StrategyRegistry` is the runtime lookup table that resolves a `PolicyRule.strategy` name (e.g. `"redact"`) to an `ActionStrategy` instance.

## Module

`arc_guard.strategies.registry` (lives in `pip`, not `core` — strategies are implementations, registry validation runs at policy-load time)

## Public API

```python
def register_strategy(name: str, strategy: ActionStrategy) -> None:
    """Register a strategy by name.

    Raises:
        ValueError: if `name` is empty.
        StrategyError: if `name` is already registered to a different
            instance (duplicate registration with the same instance is a
            no-op).
    """

def get_strategy(name: str) -> ActionStrategy:
    """Resolve a registered strategy by name.

    Raises:
        StrategyError: if `name` is not registered.
    """

def is_registered(name: str) -> bool:
    """Return True if `name` is registered."""

def list_registered() -> frozenset[str]:
    """Return all registered names (snapshot at call time)."""

def strategy(name: str):
    """Decorator form: ``@strategy("my_name")``."""
```

## Built-in registered names

These are registered when `arc_guard.strategies.__init__` is imported (which happens on any `arc_guard.pipeline` import):

| Name | Implementation module | Behavior |
|---|---|---|
| `redact` | `arc_guard.strategies.redact` | Replace span with typed placeholder per D2 |
| `hash` | `arc_guard.strategies.hash` | HMAC-SHA256 of the entity content + salt; emits `[HASH:<8 hex chars>]` |
| `block` | `arc_guard.strategies.block` | Returns empty span; the router builds the `RefusalEnvelope` |
| `warn` | `arc_guard.strategies.warn` | Pass-through; emits a `PolicyDecision` with `rationale="warn:..."` |
| `tokenize` | `arc_guard.strategies.tokenize` | `[<TYPE>_TOK_<N>]` per-input deterministic |

## Conflict resolution

When two policy rules both apply to the same finding with different strategies, the router selects the **most restrictive** strategy. Precedence (highest to lowest):

```
block > redact > tokenize > hash > warn > pass
```

The losing rule is recorded in the winning `PolicyDecision.rationale`:

```
"rule_id_X (strategy=block) overrode rule_id_Y (strategy=hash) for finding 2"
```

## Validation at policy-load time

`PolicyRuleSet` validation iterates `rules` and asserts every `rule.strategy` satisfies `is_registered(rule.strategy)`. Any unregistered name raises `ConfigCrossFieldError` naming the offending rule:

```
ConfigCrossFieldError(
    "PolicyRuleSet rule 'redact_emails_v1' references unknown strategy 'redactt'",
    code="config.unknown_strategy",
    details={"rule_id": "redact_emails_v1", "strategy": "redactt"}
)
```

## Thread-safety

The registry is backed by an `RLock`. Concurrent `register_strategy` from N threads is safe; concurrent `get_strategy` is lock-free read.

## Custom strategies — the contract

A custom strategy is any class satisfying the `ActionStrategy` Protocol from Spec 002:

```python
class TokenizeWithTenantSalt:
    name: str = "tokenize_tenant"

    def apply(
        self, text: str, findings: Sequence[Finding]
    ) -> tuple[str, Sequence[PolicyDecision]]: ...
```

The decorator form registers on definition:

```python
from arc_guard.strategies.registry import strategy

@strategy("tokenize_tenant")
class TokenizeWithTenantSalt:
    name: str = "tokenize_tenant"
    def apply(self, text, findings): ...
```

The contract test asserts that user strategies registered through this API are reachable from `PolicyRuleSet` validation immediately after registration.

## Registry inspection in tests

`tests/integration/test_strategy_registry.py` parametrizes over `list_registered()` to assert every built-in name maps to the expected class. Adding a new built-in name is a CHANGELOG event.

## Diff rules

| Diff kind | Outcome |
|---|---|
| New built-in registered name | Pass with CHANGELOG entry |
| Removal of a built-in name | Fail; deprecation flow required |
| Behavior change of a built-in (e.g. redact format) | Fail; treated as a contract change because callers' decision records would change |
| New helper in the public API (e.g. `unregister_strategy`) | Pass with CHANGELOG entry |
