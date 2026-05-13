# Walkthrough — Spec 005 (Safe Rehydration and Intent Fidelity)

**Version**: arc-guard-core 0.4.0, arc-guard 0.5.0
**Status**: shipped 2026-05-02
**Branch**: `005-intent-fidelity-rehydration`

## What changed

Spec 005 is the research-contribution spec. It adds the thesis differentiator — semantic intent capture, fidelity measurement, and verified rehydration — on top of the contracts shipped in Specs 002 / 003 / 004.

Three new pipeline stages extend the closed `STAGE_DESCRIPTORS` set additively:

- **STAGE_DEFEND** — runs before sanitize, captures the user's intent representation via an `IntentEncoder`.
- **STAGE_VERIFY** — runs after generation, scores the answer's intent representation against the captured intent via a `FidelityScorer`, and applies the threshold-driven action ladder.
- **STAGE_REHYDRATE** — runs only when sanitization fired, gates placeholder reinsertion through a `RehydrationVerifier` instead of blind string substitution.

A new `intent_lock` field on `DecisionRecord` carries content-addressed hashes of the original prompt, sanitized prompt, and rehydrated answer — the auditable binding the thesis argument depends on.

## Why

Sanitization (Spec 003) protects privacy and policy compliance, but it can also damage what the LLM actually answers — replacing every email with `[EMAIL_ADDRESS]` may reshape the question enough that the model's response no longer addresses the user's intent. Until Spec 005 there was no way to measure this drift. Worse, rehydration (placeholder → original-value substitution) was a blind string replace with no safety check; an attacker could exploit the substitution path to smuggle content past the inspector chain. Spec 005 adds (a) a typed semantic-similarity score, (b) a threshold ladder that surfaces drift to operators, and (c) a verifier-gated rehydration path that catches placeholder-context shifts and safety regressions.

## Public surface

| Symbol | Kind | Band | Notes |
|---|---|---|---|
| `IntentEncoder` / `IntentRepresentation` | protocol / type alias | provisional | Pluggable encoder for "intent" representation. |
| `FidelityScorer` | protocol | provisional | Pluggable scorer with `compatible_with(encoder)` pairing check. |
| `RehydrationVerifier` / `RehydrationVerdict` / `RehydrationDecision` | protocol / dataclass / Literal | provisional | Three-way verdict (`accept` / `reject` / `partial`) with rejection reasons. |
| `FidelityScore` / `NOT_MEASURED` | dataclass / sentinel | provisional | Score with `value` + `sentinel` discriminator. |
| `IntentLock` | dataclass | provisional | SHA-256 hex digests of canonicalized text — content-addressed audit binding. |
| `FidelityThresholds` | class | provisional | Threshold ladder; ordering `warn > clarify > refuse`. |
| `RefusalCode.FIDELITY_DROP` | enum_member | provisional | Refusal code emitted by the refuse-band fidelity ladder. |
| `STAGE_DEFEND` / `STAGE_VERIFY` / `STAGE_REHYDRATE` | constant | provisional | New stage names appended to `STAGE_DESCRIPTORS`. |
| `IntentEncoderError` / `FidelityScorerError` / `RehydrationVerifierError` | class | provisional | New exception leaves with documented failure modes. |
| `from_sentence_transformers()` (under `[semantic]` extra) | function | provisional | Factory returning a `SemanticBundle` triple. |

## Quick example

```python
import asyncio
from arc_guard import GuardPipeline
from arc_guard_core.types import GuardInput

# Default offline path: null encoder + null scorer + null verifier.
# Fidelity score is the documented `not_measured` sentinel.
pipeline = GuardPipeline()
result = asyncio.run(pipeline.pre_process(GuardInput(text="Hello")))
print(result.fidelity_score)  # → FidelityScore(value=None, sentinel='not_measured')
print(result.fidelity_warning)  # → False
```

With the canned semantic backend:

```python
from arc_guard.middleware import from_sentence_transformers

bundle = from_sentence_transformers()  # requires arc-guard[semantic]
pipeline = GuardPipeline(
    intent_encoder=bundle.encoder,
    fidelity_scorer=bundle.scorer,
    rehydration_verifier=bundle.verifier,
)
result = asyncio.run(pipeline.pre_process(GuardInput(text="...")))
# result.fidelity_score is now a real cosine similarity in [0.0, 1.0].
```

## Stage extension

The new stages are in `arc_guard_core.stages`:

```python
from arc_guard_core.stages import STAGE_DEFEND, STAGE_VERIFY, STAGE_REHYDRATE
```

The canonical run-position invariant:

```text
validate → DEFEND → classify → sanitize → route → execute → REFUSAL? → VERIFY → REHYDRATE? → decision_emit → report
```

Every new stage emits the same span / event-pair / metric trio as existing stages, with the documented stage-specific attributes.

## Fidelity score + threshold ladder

`FidelityScore` is a frozen dataclass:

```python
from arc_guard_core.fidelity import FidelityScore, NOT_MEASURED

FidelityScore.measured(0.7)      # value in [0.0, 1.0]
FidelityScore.not_measured()     # sentinel for offline / null pair
NOT_MEASURED                     # module-level singleton
```

The threshold ladder dispatches based on `score.value`:

| Band | Score range | Result |
|---|---|---|
| above_warn | `score >= warn` | informational only |
| warn | `clarify <= score < warn` | `result.fidelity_warning = True` |
| clarify | `refuse <= score < clarify` | `result.clarification` populated |
| refuse | `score < refuse` | `result.refusal` populated, `action="block"` |

**Risk-precedence rule**: when `result.action == "block"` already (a risk-band refusal fired), the fidelity ladder is a no-op. Risk takes precedence over fidelity for safety-critical decisions.

## Rehydration safety

The `RehydrationVerifier` returns one of three verdicts — `accept`, `reject`, or `partial`. Every verifier runs at minimum:

- **Check 1 (placeholder provenance)** — every placeholder in the candidate also appears in the sanitized prompt.
- **Check 2 (structural shift)** — placeholder context (immediate adjacent character class) matches between prompt and candidate.

The canned semantic verifier from `arc-guard[semantic]` adds:

- **Check 3 (safety regression)** — re-runs the rehydrated text through the foundation `InjectionInspector`'s patterns; rejects if NEW injection findings appear that were not in the placeholder-bearing candidate.

When a verdict rejects (or partially rejects), the decision record records the reason; placeholders stay in place.

### `RehydrationVerified` event emission

The `RehydrationVerified` lifecycle event fires only when **both** conditions hold:

1. The pipeline run produced an `entity_map` (sanitization actually fired and the policy router decisions surfaced placeholder → original mappings).
2. A non-Null `RehydrationVerifier` is wired on the pipeline. The default `NullRehydrationVerifier` is silent — it accepts everything but records no event.

The bundled semantic verifier ships behind the `arc-guard[semantic]` extra:

```bash
pip install 'arc-guard[semantic]'
```

```python
from arc_guard.semantic.factory import from_sentence_transformers

bundle = from_sentence_transformers()  # encoder + scorer + verifier triple
pipeline = GuardPipeline(
    intent_encoder=bundle.encoder,
    fidelity_scorer=bundle.scorer,
    rehydration_verifier=bundle.verifier,
    # ...
)
```

Operators who don't want the heavyweight `sentence-transformers` dependency can wire any other `RehydrationVerifier` Protocol implementation; the event fires regardless of which non-Null verifier ships. Without the extra (or any custom verifier), the rehydrate stage still runs — it just stays silent on the event-stream side.

The dashboard's Diff/Replay tab surfaces `RehydrationVerified.text_before / text_after` only when the verifier is wired AND `lifecycle_capture_payloads=true`.

## Intent lock + audit binding

Every run that runs the defend stage emits a `DecisionRecord` with a populated `intent_lock`:

```python
@dataclass(frozen=True)
class IntentLock:
    original_intent_hash: str        # SHA-256 hex of canonical original prompt
    sanitized_prompt_hash: str       # SHA-256 hex of canonical sanitized prompt
    rehydrated_answer_hash: str | None  # None for refused-before-generation
    encoder_id: str | None           # None when null encoder is in use
```

Hashes are computed over the **canonical form** (NFC normalize → strip → collapse whitespace → lowercase → UTF-8). Same input → same hash, regardless of formatting variation.

The lock contains zero raw text. The leak scanner from Spec 004 sweeps captured `DecisionRecord` instances and asserts no original-input substring appears in any hash field.

## Operator knobs

`FidelityThresholds` is a frozen pydantic model nested inside `ObservabilityConfig`:

```python
from arc_guard_core.observability_config import (
    FidelityThresholds, ObservabilityConfig,
)
from arc_guard.config_env import GuardConfig
from arc_guard import GuardPipeline

config = GuardConfig(
    observability=ObservabilityConfig(
        fidelity_thresholds=FidelityThresholds(
            warn=0.85, clarify=0.6, refuse=0.4,
        ),
    ),
)
pipeline = GuardPipeline(config=config, ...)
```

Validation: `0.0 <= each <= 1.0` and strict ordering `warn > clarify > refuse`. Misordered tuples and out-of-range values fail at construction with a typed error.

Defaults are `(0.7, 0.5, 0.3)` — illustrative starting points. Operators tune for their measured drift profile.

## References

- Spec: `specs/005-intent-fidelity-rehydration/spec.md`
- Plan: `specs/005-intent-fidelity-rehydration/plan.md`
- Data model: `specs/005-intent-fidelity-rehydration/data-model.md`
- Contracts: `specs/005-intent-fidelity-rehydration/contracts/`
- CHANGELOGs: `packages/core/CHANGELOG.md`, `packages/pip/CHANGELOG.md`
