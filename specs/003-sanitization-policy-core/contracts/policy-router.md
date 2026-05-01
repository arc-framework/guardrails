# Contract — `PolicyRouter` Protocol

The `PolicyRouter` Protocol is the seam between detected findings and applied strategies. Spec 003 defines its shape; `RuleBasedPolicyRouter` (in `pip`) is the default implementation.

## Module

`arc_guard_core.protocols.policy_router`

## Method-level contract

```python
@runtime_checkable
class PolicyRouter(Protocol):
    """Routes findings to strategies and aggregates the run-level outcome.

    Concurrency: sync. Implementations MUST be thread-safe — the pipeline
    may invoke from multiple coroutines / threads.

    Declared exceptions: ``PolicyRouterError`` (Spec 002 exception
    hierarchy).

    Failure mode: closed. A router error produces a ``RefusalEnvelope``
    with ``code = RefusalCode.STRATEGY_FAILED`` (or a more specific code
    if the router knows the cause). The pipeline never propagates a
    raw ``PolicyRouterError`` to the caller.
    """

    def route(
        self,
        result: GuardResult,
        ruleset: PolicyRuleSet,
    ) -> RoutedOutcome:
        ...
```

- **Inputs**: a `GuardResult` whose `findings` tuple is populated by the inspector chain (may be empty), and a validated `PolicyRuleSet`.
- **Output**: a `RoutedOutcome` (see [`public-types.md`](./public-types.md)) with the transformed text, per-finding decisions, aggregate band, optional refusal envelope, optional clarification request, and the transform summaries needed for the decision record.
- **Failure**: any internal exception MUST be caught and converted to a `PolicyRouterError` with a clear `code`. The pipeline wraps that into a `RefusalEnvelope`.

## Properties

| Property | Required | Description |
|---|---|---|
| Sync | yes | The pipeline calls `route` synchronously (no `await`). Async work, if any, is offloaded by the implementation. |
| Thread-safe | yes | Implementations MUST share no mutable per-call state. `RuleBasedPolicyRouter` carries the registry and rule set as constructor arguments — both immutable from the caller's perspective. |
| Pure | strongly preferred | Implementations should be pure functions over their inputs. Side effects (logging, metrics) belong on the pipeline's emitter, not on the router. |
| Deterministic | yes | Given the same `result` and `ruleset`, the same `RoutedOutcome` is returned. Order of decisions follows finding span order. |

## Invocation site

Inside `arc_guard.pipeline.GuardPipeline._run`:

```python
if self.config.policy is not None:
    outcome = self._policy_router.route(result, self.config.policy)
    result = self._apply_outcome(result, outcome)
    self._emit_decision(result, outcome)
```

`_apply_outcome` builds the new `GuardResult` from the original `findings`, the `RoutedOutcome.transformed_text`, the `decisions`, the optional `refusal`, and the optional `clarification`.

`_emit_decision` builds a `DecisionRecord` and emits it via the configured `Logger` / `MetricSink`.

## Snapshot format

The contract snapshot file `packages/core/tests/contract/snapshots/protocols.json` gains an entry like:

```json
{
  "name": "PolicyRouter",
  "module": "arc_guard_core.protocols.policy_router",
  "stability": "stable",
  "methods": [
    {
      "name": "route",
      "is_async": false,
      "params": [
        {"name": "result", "annotation": "GuardResult", "default": "<empty>"},
        {"name": "ruleset", "annotation": "PolicyRuleSet", "default": "<empty>"}
      ],
      "return": "RoutedOutcome"
    }
  ],
  "has_concurrency_line": true,
  "has_failure_mode_line": true,
  "has_thread_safety_line": true
}
```

The Spec 002 contract test enforces:
- `Concurrency:` line in docstring (FR-024 inherited).
- `Failure mode:` line.
- `Thread-safety:` line.

## Diff rules

| Diff kind | Outcome |
|---|---|
| New optional method with default impl | Pass with CHANGELOG entry |
| Method removal / rename / async-flip / signature change | Fail; requires deprecation flow |
| Failure-mode change (`closed` → `open`) | Fail; explicit migration required because callers depend on it |
| Concurrency change | Fail |
| Stability change | Fail (lowering) / pass with CHANGELOG (raising) |

## Adding a custom router

A custom router need only satisfy the Protocol structurally — no inheritance required. The pipeline accepts an optional `policy_router=` kwarg in its constructor (default: `RuleBasedPolicyRouter`). Tests that need a deterministic router can inject a `FakeRouter` that returns hand-crafted `RoutedOutcome` instances.

## Removing or renaming the Protocol

Same flow as removing any Spec 002 / 003 contract — see `../../002-rewrite-foundation/contracts/deprecation-policy.md`.
