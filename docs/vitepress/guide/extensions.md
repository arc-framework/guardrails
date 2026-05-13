# Extension Patterns

arc-guardrails uses structural typing instead of inheritance for its main extension seams. In practice that means you implement the expected method shape and pass your implementation into the runtime; you do not need to subclass internal SDK base classes.

## Why Protocol-First Matters

- Downstream extensions avoid hard coupling to SDK inheritance trees.
- New behavior can be composed at pipeline construction time.
- Contract-heavy code stays in `arc-guard-core`, while concrete helpers remain optional in `arc-guard`.

## Main Extension Surfaces

| Surface | Role |
| --- | --- |
| `Inspector` | Produce `Finding` objects from input text or context |
| `ActionStrategy` | Transform text or stop execution based on policy decisions |
| `PolicyRouter` | Resolve actions from findings and risk bands |
| `LifecycleSink` | Capture typed events for replay, dashboards, or external audit systems |
| `Reporter` | Emit secondary reporting side effects without changing request outcomes |
| `IntentEncoder`, `FidelityScorer`, `RehydrationVerifier` | Extend the semantic verification and rehydration chain |

## Custom Inspector Example

```python
class CustomerIdInspector:
    def inspect(self, guard_input):
        findings = []
        text = guard_input.text
        marker = 'CUST-'

        start = text.find(marker)
        if start >= 0:
            findings.append(
                Finding(
                    inspector='customer_id',
                    entity_type='CUSTOMER_ID',
                    start=start,
                    end=start + 12,
                    risk_level=RiskLevel.MEDIUM,
                )
            )

        return findings
```

## Custom Strategy Example

```python
class PrefixTokenStrategy:
    def apply(self, text, findings):
        updated = text
        for finding in reversed(findings):
            token = f"[SAFE_{finding.entity_type}]"
            updated = updated[:finding.start] + token + updated[finding.end:]
        return updated
```

## Where To Add New Runtime Behavior

- Add protocol-safe types and interfaces under `packages/core` when the contract itself changes.
- Add concrete inspectors, strategies, selectors, or sinks under `packages/pip/src/arc_guard/...`.
- Add transport or route behavior under `packages/api/src/arc_guard_service/...` only when the change is HTTP-specific.

## Safe Integration Pattern

1. Implement the protocol shape you need.
2. Inject the implementation through the pipeline or service factory.
3. Validate behavior with package-local tests and the top-level Makefile checks.
4. Update docs if the public behavior or extension contract changes.

The public import contract for stable root-level symbols is summarized in [Public Surface](/reference/public-surface).