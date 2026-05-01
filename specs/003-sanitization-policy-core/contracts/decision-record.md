# Contract — `DecisionRecord` Schema

`DecisionRecord` is the audit-grade summary emitted for every pipeline run when `GuardConfig.policy is not None`. It is the explainability artifact of Spec 003 (FR-021 — FR-024).

## Module

`arc_guard_core.decision`

## Schema

See [`../data-model.md` §9–§11](../data-model.md) for full field tables. Summary:

| Field | Type | Required | Description |
|---|---|---|---|
| `correlation_id` | `str \| None` | yes | Derived from `GuardContext.correlation_id` |
| `phase` | `Literal["pre_process", "post_process"]` | yes | Pipeline side |
| `aggregate_action` | `str` | yes | The driven action (`pass` / `redact` / `hash` / `block` / `tokenize`) |
| `aggregate_band` | `RiskBand` | yes | LOW / MEDIUM / HIGH / CRITICAL |
| `findings` | `tuple[FindingSummary, ...]` | yes | One per finding (no raw text) |
| `transforms` | `tuple[TransformSummary, ...]` | yes | One per applied strategy |
| `fired_rules` | `tuple[str, ...]` | yes | Rule ids |
| `refusal_code` | `str \| None` | yes | When refusal envelope was built |
| `clarification_present` | `bool` | yes | True iff `ClarificationRequest` was built |
| `latency_ms` | `float` | yes | Total `_run` duration |
| `metadata` | `dict[str, Any]` | yes | Extension point — MUST NOT contain raw payloads |

## The "no raw payload" rule (FR-023)

Every field in `DecisionRecord` MUST be safe to serialize to a structured log without exposing the raw input or the raw masked content. The contract test scans serialized records for forbidden substrings:

- The original `GuardInput.text` (or any substring of length ≥ 8 characters).
- The original entity content (e.g. credit-card digits, email addresses).

Implementations that need to carry context for downstream consumers MUST use offsets, lengths, and ids — never raw bytes.

The contract test fixture at `packages/core/tests/contract/test_no_raw_payload_in_decision_record.py` runs:

```python
INPUTS = [
    "Email Alice Johnson at alice@acme.com",
    "Card 4111-1111-1111-1111 expires 12/27",
    "Project Helios kicks off tomorrow",
]

@pytest.mark.parametrize("input_text", INPUTS)
def test_no_raw_payload(input_text: str) -> None:
    result = pipeline.pre_process_sync(GuardInput(text=input_text))
    record = pipeline._last_decision  # exposed for tests
    serialized = json.dumps(asdict(record))
    # Reject any substring of input_text that's ≥ 8 chars
    for length in range(8, len(input_text) + 1):
        for start in range(len(input_text) - length + 1):
            substr = input_text[start:start + length]
            assert substr not in serialized, (
                f"raw payload leak: {substr!r} appears in DecisionRecord"
            )
```

## Emission cadence (FR-022)

Once per `_run`, after strategies apply, before the reporter is invoked:

```python
record = self._decision_emitter.build(result, outcome, latency_ms)
self.config.logger.event("guard.decision", level="info", **dataclasses.asdict(record))
self.config.metrics.counter(
    "guard.decisions",
    attributes={"action": result.action, "risk_band": record.aggregate_band.value},
)
self.config.metrics.histogram("guard.findings_count", float(len(result.findings)))
```

The Spec 002 hooks are null-defaults. Spec 004 substitutes real OTEL backends. This contract is stable across both.

## JSON serialization

`DecisionRecord` is a frozen dataclass. The canonical serialization is:

```python
from dataclasses import asdict
import json
serialized = json.dumps(asdict(record), default=str)
```

The `default=str` handles `RiskBand` (StrEnum). The contract test verifies the serialized output round-trips:

```python
record_dict = json.loads(serialized)
assert record_dict["correlation_id"] == record.correlation_id
assert record_dict["aggregate_band"] == record.aggregate_band.value
```

## Diff rules

| Diff kind | Outcome |
|---|---|
| New optional field on `DecisionRecord` | Pass with CHANGELOG entry |
| New required field | Fail (existing serialized records would lack it) |
| Field rename | Fail; deprecation flow |
| Type change | Fail |
| New emission hook (e.g. forward to a span attribute) | Pass with CHANGELOG entry — Spec 004's job |

## Side-channel access for tests

`GuardPipeline._last_decision: DecisionRecord | None` is exposed as a private-but-stable attribute for the contract tests. Production callers use the `Logger` event channel; tests inspect the attribute directly. Spec 003 documents this as the explicit test contract; no other private attribute on the pipeline is part of any contract.
