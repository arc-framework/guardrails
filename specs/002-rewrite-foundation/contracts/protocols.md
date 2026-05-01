# Contract — Protocol Interfaces

Every cross-package, cross-stage, and cross-adapter seam in `arc-guardrails` is a `typing.Protocol`. This file pins the seven Spec 001 protocols (carried into `core` unchanged in shape) and the three new observability hook protocols (`@experimental` until Spec 004).

## Protocols at a glance

| Protocol | Module | Sync/Async | Thread-safety | Stability |
|---|---|---|---|---|
| `Guard` | `arc_guard_core.protocols.guard` | both | thread-safe | `@stable` |
| `Inspector` | `arc_guard_core.protocols.inspector` | sync | thread-safe (no instance mutation) | `@stable` |
| `ActionStrategy` | `arc_guard_core.protocols.strategy` | sync | thread-safe (no IO) | `@stable` |
| `Reporter` | `arc_guard_core.protocols.reporter` | async | thread-safe; bounded queue | `@stable` |
| `FlagProvider` | `arc_guard_core.protocols.flag_provider` | sync | thread-safe | `@stable` |
| `Middleware` | `arc_guard_core.protocols.middleware` | both | thread-safe | `@stable` |
| `EntityProvider` | `arc_guard_core.protocols.entity_provider` | sync | thread-safe | `@stable` |
| `Tracer` | `arc_guard_core.observability` | sync | thread-safe | `@experimental` |
| `Logger` | `arc_guard_core.observability` | sync | thread-safe | `@experimental` |
| `MetricSink` | `arc_guard_core.observability` | sync | thread-safe | `@experimental` |

## Method-level contracts

### `Guard`

```python
class Guard(Protocol):
    async def pre_process(self, input: GuardInput) -> GuardResult: ...
    async def post_process(self, input: GuardInput) -> GuardResult: ...
    def pre_process_sync(self, input: GuardInput) -> GuardResult: ...
    def post_process_sync(self, input: GuardInput) -> GuardResult: ...
```

- **Declared exceptions**: none. All errors MUST surface as a `GuardResult` (with `bypass_reason="error"` for fail-open failures, or `action="block"` with a `RefusalEnvelope` for fail-closed failures). FR-023.
- **Concurrency**: implementations MUST be safe to call from multiple threads / coroutines simultaneously.
- **Failure mode**: each underlying inspector / strategy / reporter has its own failure mode (see [`exceptions.md`](./exceptions.md)). The aggregate `Guard` is fail-open by default and can be configured fail-closed per stage.

### `Inspector`

```python
class Inspector(Protocol):
    name: str

    def inspect(self, result: GuardResult) -> GuardResult: ...
```

- **Declared exceptions**: `InspectorError` (all inspector failures are wrapped at this boundary).
- **Concurrency**: implementations MUST NOT mutate instance state across calls. The pipeline calls `inspect` from any thread.
- **Failure mode**: `InspectorError` is **fail-open** by default — the pipeline continues with `bypass_reason="error"` recorded.

### `ActionStrategy`

```python
class ActionStrategy(Protocol):
    name: str

    def apply(self, text: str, findings: Sequence[Finding]) -> tuple[str, Sequence[PolicyDecision]]: ...
```

- **Declared exceptions**: `StrategyError`.
- **Concurrency**: pure function over its inputs. No IO.
- **Failure mode**: `StrategyError` is **fail-closed** — the pipeline aborts with a `RefusalEnvelope`. A broken strategy is not safe to swallow because the user-facing text was not transformed.

### `Reporter`

```python
class Reporter(Protocol):
    async def report(self, result: GuardResult) -> None: ...
    async def close(self) -> None: ...
```

- **Declared exceptions**: `ReporterError`.
- **Concurrency**: implementations MUST not block the calling pipeline. Spec 001's bounded-queue pattern stays canonical.
- **Failure mode**: `ReporterError` is **fail-open** — reporters never propagate errors back to the pipeline. Failures are logged via the `Logger` hook and counted via `MetricSink`.

### `FlagProvider`

```python
class FlagProvider(Protocol):
    def is_enabled(self, name: str, *, context: GuardContext | None = None) -> bool: ...
```

- **Declared exceptions**: `FlagProviderError`.
- **Concurrency**: thread-safe; may cache.
- **Failure mode**: `FlagProviderError` is **fail-closed-conservative** — on error, `is_enabled` returns `False` so the pipeline takes the safer default. Documented in the docstring; enforced by the test suite.

### `Middleware`

```python
class Middleware(Protocol):
    name: str

    def before(self, input: GuardInput) -> None: ...
    def after(self, result: GuardResult) -> None: ...
    async def before_async(self, input: GuardInput) -> None: ...
    async def after_async(self, result: GuardResult) -> None: ...
```

- **Declared exceptions**: implementation-specific subclasses of `AdapterError`.
- **Concurrency**: thread-safe. Sync and async pairs are mutually optional; the pipeline calls whichever matches the active mode.
- **Failure mode**: middleware failures are **fail-open** by default. OTEL middleware (in `pip`) MUST follow this contract.

### `EntityProvider`

```python
class EntityProvider(Protocol):
    def entities(self) -> Iterable[EntityDefinition]: ...
```

- **Declared exceptions**: `EntityProviderError`.
- **Concurrency**: thread-safe; typically called once at startup.
- **Failure mode**: **fail-closed** — a missing entity provider is treated as a configuration error. Surfaces as `ConfigError` if invoked at startup.

### Observability hooks (`@experimental`)

Pinned in [`../data-model.md` §10](../data-model.md). Spec 004 stabilizes them; until then, implementations MUST be drop-in replaceable with the null implementations exported from `arc_guard_core.observability`.

## Snapshot format

Each protocol entry in `tests/contract/snapshots/protocols.json`:

```json
{
  "name": "Inspector",
  "module": "arc_guard_core.protocols.inspector",
  "stability": "stable",
  "methods": [
    {
      "name": "inspect",
      "signature": "(self, result: GuardResult) -> GuardResult",
      "is_async": false,
      "declared_exceptions": ["InspectorError"]
    }
  ],
  "attributes": [{"name": "name", "type": "str"}],
  "thread_safety": "thread-safe",
  "failure_mode": "open"
}
```

## Diff rules

| Diff kind | Outcome |
|---|---|
| New protocol | Pass with required CHANGELOG entry |
| Removed protocol | Fail; requires deprecation flow |
| New method without default | Fail (breaks structural conformance for existing implementers) |
| New method with default implementation | Pass with required CHANGELOG entry |
| Removed method | Fail |
| Signature change (param added/removed/renamed) | Fail |
| Async ↔ sync flip | Fail |
| `failure_mode` change | Fail; requires explicit migration entry because callers depend on it |
| `thread_safety` weakened | Fail |
| `stability` lowered | Fail |
| `stability` raised (experimental → stable) | Pass with CHANGELOG entry |

## Adding a new protocol

1. Define it in `arc_guard_core/protocols/<name>.py`.
2. Add a stability marker, declared exceptions list, and thread-safety note to the docstring.
3. Add the corresponding entry to this file and re-export from `arc_guard_core.protocols.__init__`.
4. Update the snapshot.
5. CHANGELOG entry.

## Renaming or removing a protocol

Same flow as renaming a public type — see [`deprecation-policy.md`](./deprecation-policy.md).
