# Contract — `TypedPlaceholder` Registry

The typed-placeholder registry is the source of truth for the labels emitted by the redact strategy. It implements Decision D2 from spec.md (sequential per-type suffixes when multiple occurrences appear in one input).

## Module

`arc_guard_core.placeholders`

## Default labels

```python
DEFAULT_PLACEHOLDERS: dict[str, str] = {
    "EMPLOYEE_NAME":         "[EMPLOYEE_NAME]",
    "CUSTOMER_NAME":         "[CUSTOMER_NAME]",
    "INTERNAL_PROJECT":      "[INTERNAL_PROJECT]",
    "CONFIDENTIAL_LOCATION": "[CONFIDENTIAL_LOCATION]",
    "EMAIL_ADDRESS":         "[EMAIL_ADDRESS]",
    "PHONE_NUMBER":          "[PHONE_NUMBER]",
    "CREDIT_CARD":           "[CREDIT_CARD]",
    "US_SSN":                "[US_SSN]",
    "IP_ADDRESS":            "[IP_ADDRESS]",
    "UNKNOWN_PII":           "[UNKNOWN_PII]",
}
```

The keys are the canonical `Finding.entity_type` values. The values are the placeholder labels that appear in the sanitized text.

## Public API

```python
def register_placeholder(entity_type: str, label: str) -> None:
    """Register or override a typed placeholder.

    Raises:
        ValueError: if `label` does not start with `[` and end with `]`.
        ValueError: if `entity_type` is empty.
    """

def get_placeholder(entity_type: str) -> str:
    """Return the registered label for `entity_type`, or
    ``"[UNKNOWN_PII]"`` if not registered."""

def format_placeholder(entity_type: str, occurrence: int, total: int) -> str:
    """Return the placeholder string for one occurrence (D2).

    - If `total == 1`: returns the unsuffixed label, e.g. ``"[EMAIL_ADDRESS]"``.
    - If `total > 1`: returns ``"[<TYPE>_<occurrence>]"`` with `occurrence` 1-indexed.

    Raises:
        ValueError: if `occurrence < 1` or `occurrence > total` or `total < 1`.
    """

def list_registered() -> frozenset[str]:
    """Return all registered entity types."""
```

## Format rules (D2)

| Occurrence count in one input | Placeholder format |
|---|---|
| 1 | `[<TYPE>]` (e.g. `[CREDIT_CARD]`) |
| 2 | `[<TYPE>_1]`, `[<TYPE>_2]` (e.g. `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`) |
| N (N > 2) | `[<TYPE>_1]`, …, `[<TYPE>_N]` |

Numbering is **per-input** and **per-type**. Two different types in the same input each have their own counter.

The redact strategy implements this via a two-pass scan:

1. Pass 1: count occurrences per `entity_type` across `findings` (sorted by span start).
2. Pass 2: emit the replacements, calling `format_placeholder(entity_type, occurrence_n, total_count)` for each.

## Custom placeholder registration

Integrators register new entity types at startup:

```python
from arc_guard_core.placeholders import register_placeholder

register_placeholder("AADHAAR", "[AADHAAR]")
register_placeholder("NHS_NUMBER", "[NHS_NUMBER]")
```

After registration, any `Finding` with `entity_type="AADHAAR"` will be redacted with the registered label, and the multi-occurrence suffix logic applies automatically.

## Validation

- `entity_type` MUST be non-empty and case-sensitive (uppercase by convention).
- `label` MUST match the regex `^\[[A-Z][A-Z0-9_]*\]$`. Lowercase, spaces, and special characters are rejected.
- The registry is thread-safe (RLock).

## Span ordering

When emitting placeholders for an input with multiple findings, the redact strategy iterates findings in **ascending span-start order**. This ensures `_1` comes before `_2` in reading order:

```
input:  "Cards 4111-1111-1111-1111 and 5555-5555-5555-4444 are different"
output: "Cards [CREDIT_CARD_1] and [CREDIT_CARD_2] are different"
```

If two findings overlap, the router resolves the conflict before redaction runs (see [`strategy-registry.md` §"Conflict resolution"](./strategy-registry.md)).

## Diff rules

| Diff kind | Outcome |
|---|---|
| New default placeholder added to `DEFAULT_PLACEHOLDERS` | Pass with CHANGELOG entry |
| Removal of a default placeholder | Fail; deprecation flow |
| Format change (e.g. `[<TYPE>]` → `<TYPE>`) | Fail; serialized decision records would not match |
| Suffix scheme change (e.g. `_1` → `(1)`) | Fail; treated as a contract change |
| New helper in the public API | Pass with CHANGELOG entry |

## Snapshot

The contract test snapshots `DEFAULT_PLACEHOLDERS` and the `register_placeholder` / `format_placeholder` signatures. Format-rule changes show up as snapshot diffs.

## Tests

`packages/pip/tests/unit/test_typed_placeholder_format.py` runs at least:

| Input | Expected output |
|---|---|
| `"Email alice@acme.com"` (1 EMAIL_ADDRESS) | `"Email [EMAIL_ADDRESS]"` |
| `"Email alice@acme.com or bob@acme.com"` (2 EMAIL_ADDRESS) | `"Email [EMAIL_ADDRESS_1] or [EMAIL_ADDRESS_2]"` |
| Three credit-card numbers | three `[CREDIT_CARD_1]`, `[CREDIT_CARD_2]`, `[CREDIT_CARD_3]` in span order |
| Mixed types (one EMAIL_ADDRESS + two CREDIT_CARD) | EMAIL unsuffixed; cards suffixed `_1`, `_2` |
| Custom registered type with 1 occurrence | unsuffixed |
| Custom registered type with 2 occurrences | suffixed `_1`, `_2` |

## Removing a placeholder

Same flow as removing any Spec 002 / 003 contract entry — see `../../002-rewrite-foundation/contracts/deprecation-policy.md`.
