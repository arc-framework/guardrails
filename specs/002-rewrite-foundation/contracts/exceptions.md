# Contract — Exception Hierarchy and Failure Modes

This contract pins:

1. The typed exception classes under `arc_guard_core.exceptions` (FR-021).
2. The fail-open vs fail-closed declaration per public stage (FR-022).
3. The "no internal exception leaks" rule at the public API boundary (FR-023).

## Hierarchy

```
ArcGuardError                          # base; never raised directly
├── ConfigError
│   ├── ConfigSchemaError              # missing/extra fields, type mismatches
│   └── ConfigCrossFieldError          # rule-level violations
├── ValidationError
│   ├── ApiBoundaryValidationError     # FR-017 — request/response validation
│   ├── PipelineContractValidationError # FR-018 — Finding / PolicyDecision shape checks
│   └── AdapterBoundaryValidationError # FR-019 — adapter input/output shape checks
├── PipelineError
│   ├── InspectorError                 # fail-open
│   ├── StrategyError                  # fail-closed
│   └── PolicyRouterError              # fail-closed (Spec 003 may refine)
├── AdapterError
│   ├── ReporterError                  # fail-open
│   ├── FlagProviderError              # fail-closed-conservative (returns False)
│   └── EntityProviderError            # fail-closed (config-time)
└── RefusalEnvelopeError               # fail-closed
```

## Class-level attributes

Every leaf exception class declares:

```python
class InspectorError(PipelineError):
    __failure_mode__: ClassVar[Literal["open", "closed", "closed-conservative"]] = "open"

    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: Mapping[str, Any] | None = None,
        cause: BaseException | None = None,
    ) -> None: ...
```

| Attribute | Required | Purpose |
|---|---|---|
| `__failure_mode__` | yes (depth ≥ 2) | Drives the pipeline's fail-open / fail-closed routing. |
| `code` | yes | Stable, machine-readable identifier (e.g. `"inspector.timeout"`). Drawn from a per-class registry. |
| `details` | optional | Structured context (stage name, finding count, adapter id). MUST NOT contain raw user content. |
| `cause` | optional | The original exception, attached via `raise X from cause` semantics. |

## Failure-mode table per public stage

The contract test asserts each row holds in code:

| Stage | Inputs | Failure mode | Visible result on failure |
|---|---|---|---|
| `Guard.pre_process` | `GuardInput` | open (aggregate) | `GuardResult(action="pass", bypass_reason="error", findings=())` |
| `Guard.post_process` | `GuardInput` | open (aggregate) | same as above |
| `Inspector.inspect` | `GuardResult` | open | `bypass_reason="error"` propagated up |
| `ActionStrategy.apply` | `(text, findings)` | closed | `RefusalEnvelope(code="strategy.failed", trigger="strategy", ...)` returned |
| `Reporter.report` | `GuardResult` | open | error counted via `MetricSink`, logged via `Logger`; pipeline result unchanged |
| `FlagProvider.is_enabled` | `(name, context)` | closed-conservative | returns `False` |
| `Middleware.before` / `Middleware.after` | varies | open | failure logged; pipeline continues |
| `EntityProvider.entities` | `()` | closed | startup-time `ConfigError` |
| Configuration load | path or env | closed | `ConfigError` raised; library is unusable |
| API boundary (request) | request payload | closed | `ApiBoundaryValidationError` returned to caller; no pipeline work runs |
| API boundary (response) | result payload | closed | `ApiBoundaryValidationError`; caller receives a typed error envelope |
| Pipeline contract | `Finding`, `PolicyDecision` | closed | `PipelineContractValidationError`; refusal envelope built |
| Adapter boundary | adapter request / response | closed | `AdapterBoundaryValidationError`; adapter call aborted |

## "No leak" rule (FR-023)

The public `Guard` API MUST NOT raise any internal exception unwrapped. The contract test asserts:

- Calling `pre_process` / `post_process` with a malformed `GuardInput` returns a `GuardResult` whose `bypass_reason` or `refusal` field reflects the failure — it does NOT raise.
- The only exceptions that cross the public API boundary are `ConfigError` (at startup) and `ApiBoundaryValidationError` (at the API package's boundary). Both are documented public exceptions.
- Tests inject every exception class above into every documented call site to verify wrapping.

## Code registry

Each leaf exception class maintains a class-level registry of its valid `code` values:

```python
class InspectorError(PipelineError):
    __valid_codes__: ClassVar[frozenset[str]] = frozenset({
        "inspector.timeout",
        "inspector.malformed_finding",
        "inspector.unhandled",
    })
```

The `__init__` validates `code in __valid_codes__` and raises `ValueError` if not. New codes are added to the registry in the same change that introduces them, with a CHANGELOG entry.

## Snapshot format

Each leaf entry in `tests/contract/snapshots/exceptions.json`:

```json
{
  "name": "InspectorError",
  "module": "arc_guard_core.exceptions",
  "parent": "PipelineError",
  "failure_mode": "open",
  "valid_codes": ["inspector.timeout", "inspector.malformed_finding", "inspector.unhandled"]
}
```

## Diff rules

| Diff kind | Outcome |
|---|---|
| New leaf class | Pass with CHANGELOG entry |
| Removed leaf class | Fail; requires deprecation flow |
| `failure_mode` change | Fail (callers depend on routing); requires explicit migration |
| New code in `__valid_codes__` | Pass with CHANGELOG entry |
| Removed code in `__valid_codes__` | Fail; requires deprecation flow |
| Parent class change | Fail |
| `__init__` signature change | Fail |

## Adding an exception

1. Add the class in `arc_guard_core/exceptions.py`.
2. Set `__failure_mode__` and `__valid_codes__`.
3. Add a row to the failure-mode table above.
4. Update the snapshot.
5. CHANGELOG entry.
