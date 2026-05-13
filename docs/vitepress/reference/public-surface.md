# Public Surface

The project distinguishes between what happens to be importable at runtime and what downstream users should actually treat as supported package-root API.

## Stability Bands

| Band | Meaning |
| --- | --- |
| `stable` | Expected to remain import-compatible across minor releases |
| `provisional` | Supported, but still allowed to evolve with migration guidance |
| `experimental` | Available for early adopters without the normal compatibility promise |

## Supported Root-Level Concepts

### `arc-guard-core`

This is the main public contract surface. It includes typed inputs and outputs, risk and refusal enums, the protocol types, and the contract-layer pipeline shape.

Representative stable symbols include:

- `GuardInput`
- `GuardResult`
- `Finding`
- `PolicyDecision`
- `DecisionRecord`
- `RefusalEnvelope`
- `RiskLevel`
- `GuardPipeline`
- `Inspector`, `ActionStrategy`, `PolicyRouter`, `Reporter`, `LifecycleSink`

### `arc-guard`

The package root is intentionally not the preferred long-term import surface for new code. Most downstream users should import concrete runtime helpers from their specific modules instead of relying on package-root convenience exports.

### `arc-guard-service`

The root service package exposes a smaller deployment-facing surface suitable for running the HTTP application and service entrypoints.

## Practical Rule

If a symbol is part of the contract layer and documented as stable or provisional, you can pin against it with confidence. If a runtime export is only present as a convenience import and is not documented, treat it as implementation detail.