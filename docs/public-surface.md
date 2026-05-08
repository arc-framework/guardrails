# arc-guardrails public surface

This manifest records the supported direct-import surface for the published
packages. It is intentionally smaller than the full runtime export set.

The goal is to document what downstream users may safely pin against at the
package root, not to mirror every convenience constant, compatibility shim, or
legacy name that still happens to resolve at runtime.

Run the verifier from `packages/`:

```bash
uv run --package arc-guard python ../tools/check_public_surface.py
```

## Scope

- `arc_guard_core` lists the contract-layer names we support as direct imports.
- `arc_guard` package-root imports are **not** the supported API for new code.
  The root package mostly keeps deprecation shims alive while callers migrate.
- `arc_guard_service` lists the small deployment entry surface we support at the
  package root.

If a runtime export is not listed here, treat it as undocumented convenience or
compatibility behavior rather than part of the supported API contract.

## Stability bands

- **`stable`** — expected to remain import-compatible across minor releases;
  removals require the documented deprecation flow.
- **`provisional`** — supported for early adopters, but still allowed to
  change shape across a future minor release with migration guidance.
- **`experimental`** — intentionally unstable research-track surface; available
  to try, but not yet covered by the normal compatibility promise.

## Manifest schema

Each entry records the supported symbol name, runtime kind, stability band, and
the spec/version where that contract was introduced.

```yaml
- name: GuardInput
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
```

## Package: arc_guard_core

```yaml
- name: ArcGuardError
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: GuardConfig
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: RiskLevel
  kind: enum
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: GuardContext
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: GuardInput
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: Finding
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: PolicyDecision
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: RefusalEnvelope
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: ClarificationRequest
  kind: dataclass
  stability_band: stable
  introduced_in: '003'
  stabilized_in: '0.4.0'
- name: GuardResult
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: EntityDefinition
  kind: dataclass
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: DecisionRecord
  kind: dataclass
  stability_band: stable
  introduced_in: '003'
  stabilized_in: '0.4.0'
- name: GuardPipeline
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: EntityRegistry
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: register_entity
  kind: function
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: RefusalCode
  kind: enum
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: PolicyRule
  kind: class
  stability_band: stable
  introduced_in: '003'
  stabilized_in: '0.4.0'
- name: PolicyRuleSet
  kind: class
  stability_band: stable
  introduced_in: '003'
  stabilized_in: '0.4.0'
- name: Guard
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: Inspector
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: ActionStrategy
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: Reporter
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: FlagProvider
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: Middleware
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: EntityProvider
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: PolicyRouter
  kind: class
  stability_band: stable
  introduced_in: '003'
  stabilized_in: '0.4.0'
- name: Tracer
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: Logger
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: MetricSink
  kind: class
  stability_band: stable
  introduced_in: '002'
  stabilized_in: '0.3.0'
- name: ObservabilityConfig
  kind: class
  stability_band: provisional
  introduced_in: '004'
  stabilized_in: 'TBD'
- name: IntentEncoder
  kind: class
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: FidelityScorer
  kind: class
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: FidelityScore
  kind: dataclass
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: RehydrationVerifier
  kind: class
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: RehydrationVerdict
  kind: dataclass
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: RehydrationDecision
  kind: constant
  stability_band: provisional
  introduced_in: '005'
  stabilized_in: 'TBD'
- name: JailbreakDetector
  kind: class
  stability_band: provisional
  introduced_in: '006'
  stabilized_in: 'TBD'
- name: ConversationTurnInspector
  kind: class
  stability_band: provisional
  introduced_in: '006'
  stabilized_in: 'TBD'
- name: EvaluationHarness
  kind: class
  stability_band: experimental
  introduced_in: '006'
- name: DEFAULT_PLACEHOLDERS
  kind: constant
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: DEFAULT_REFUSAL_TEMPLATES
  kind: constant
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: FindingSummary
  kind: class
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: RefusalTemplate
  kind: class
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: RiskBand
  kind: enum
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: RiskThresholds
  kind: class
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: RoutedOutcome
  kind: class
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: TransformSummary
  kind: class
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: format_placeholder
  kind: function
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: get_placeholder
  kind: function
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: get_refusal_template
  kind: function
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: register_placeholder
  kind: function
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: register_refusal_template
  kind: function
  stability_band: stable
  introduced_in: "003"
  stabilized_in: "003"
- name: AttributeRedactor
  kind: class
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: FAIL_RULE
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: FailureRule
  kind: class
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: LogLevelFloor
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: RedactionResult
  kind: class
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_CLASSIFY
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_DECISION_EMIT
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_DESCRIPTORS
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_EXECUTE
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_REFUSAL
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_REPORT
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_ROUTE
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_SANITIZE
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: STAGE_VALIDATE
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: Severity
  kind: constant
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: lookup_rule
  kind: function
  stability_band: stable
  introduced_in: "004"
  stabilized_in: "004"
- name: FidelityScorerError
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: FidelityThresholds
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: IntentEncoderError
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: IntentLock
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: IntentRepresentation
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: NOT_MEASURED
  kind: constant
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: RehydrationVerifierError
  kind: class
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: STAGE_DEFEND
  kind: constant
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: STAGE_REHYDRATE
  kind: constant
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: STAGE_VERIFY
  kind: constant
  stability_band: stable
  introduced_in: "005"
  stabilized_in: "005"
- name: Configuration
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: ConfigurationMetrics
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: ConversationState
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: CorpusCategory
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: CorpusEntry
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: DECEPTION_NOT_MEASURED
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: DeceptionScore
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: DeceptionThresholds
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: EvaluationReport
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: ExpectedOutcome
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: JailbreakCategory
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: JailbreakSignal
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: JailbreakThresholds
  kind: class
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: STAGE_DECEPTION_INSPECT
  kind: constant
  stability_band: stable
  introduced_in: "006"
  stabilized_in: "006"
- name: FAILURE_API_TRANSPORT
  kind: constant
  stability_band: stable
  introduced_in: "007"
  stabilized_in: "007"
- name: TransportError
  kind: class
  stability_band: stable
  introduced_in: "007"
  stabilized_in: "007"
  stabilized_in: 'TBD'
- name: StrategySelector
  kind: class
  stability_band: stable
  introduced_in: '011'
  stabilized_in: '011'
- name: ContentPolicy
  kind: class
  stability_band: stable
  introduced_in: '011'
  stabilized_in: '011'
- name: ContentPolicyDecision
  kind: class
  stability_band: stable
  introduced_in: '011'
  stabilized_in: '011'
```

## Package: arc_guard

The package root is kept mainly for migration compatibility. New code should
import contract types from `arc_guard_core` and implementation details from the
relevant `arc_guard.*` submodule instead of relying on `arc_guard.<name>`.

## Package: arc_guard_service

```yaml
- name: ServiceSettings
  kind: class
  stability_band: provisional
  introduced_in: '007'
  stabilized_in: 'TBD'
- name: run_guard
  kind: function
  stability_band: provisional
  introduced_in: '007'
  stabilized_in: 'TBD'
```

## Renamed (deprecation shims active)

| Old name                   | New name                                                | Deprecation introduced | Removal target |
| -------------------------- | ------------------------------------------------------- | ---------------------- | -------------- |
| arc_guard.RiskLevel        | arc_guard_core.types.RiskLevel                          | 0.2.0                  | 0.3.0          |
| arc_guard.GuardContext     | arc_guard_core.types.GuardContext                       | 0.2.0                  | 0.3.0          |
| arc_guard.GuardInput       | arc_guard_core.types.GuardInput                         | 0.2.0                  | 0.3.0          |
| arc_guard.Finding          | arc_guard_core.types.Finding                            | 0.2.0                  | 0.3.0          |
| arc_guard.GuardResult      | arc_guard_core.types.GuardResult                        | 0.2.0                  | 0.3.0          |
| arc_guard.EntityDefinition | arc_guard_core.types.EntityDefinition                   | 0.2.0                  | 0.3.0          |
| arc_guard.GuardConfig      | arc_guard.config_env.GuardConfig                        | 0.2.0                  | 0.3.0          |
| arc_guard.EntityRegistry   | arc_guard_core.registry.EntityRegistry                  | 0.2.0                  | 0.3.0          |
| arc_guard.register_entity  | arc_guard_core.registry.register_entity                 | 0.2.0                  | 0.3.0          |
| arc_guard.Guard            | arc_guard_core.protocols.guard.Guard                    | 0.2.0                  | 0.3.0          |
| arc_guard.Inspector        | arc_guard_core.protocols.inspector.Inspector            | 0.2.0                  | 0.3.0          |
| arc_guard.ActionStrategy   | arc_guard_core.protocols.strategy.ActionStrategy        | 0.2.0                  | 0.3.0          |
| arc_guard.Reporter         | arc_guard_core.protocols.reporter.Reporter              | 0.2.0                  | 0.3.0          |
| arc_guard.FlagProvider     | arc_guard_core.protocols.flag_provider.FlagProvider     | 0.2.0                  | 0.3.0          |
| arc_guard.Middleware       | arc_guard_core.protocols.middleware.Middleware          | 0.2.0                  | 0.3.0          |
| arc_guard.EntityProvider   | arc_guard_core.protocols.entity_provider.EntityProvider | 0.2.0                  | 0.3.0          |

## Removed

| Old name   | Removed in | Reason | Replacement |
| ---------- | ---------- | ------ | ----------- |
| (none yet) |            |        |             |
