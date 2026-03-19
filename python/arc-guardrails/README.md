# arc-guard

General-purpose Python guardrails library — PII detection, prompt injection prevention, and toxic output filtering.

## Install

```bash
# Core (presidio-based PII detection + injection detection)
pip install arc-guard

# With NATS event reporting
pip install "arc-guard[nats]"

# With Unleash feature flags
pip install "arc-guard[unleash]"

# With OTEL metrics + spans
pip install "arc-guard[otel]"

# Full ARC platform integration
pip install "arc-guard[arc]"
```

## Quick start

```python
from arc_guard import GuardPipeline, GuardInput, GuardContext

# Build pipeline from env vars (GUARD_ENABLED, GUARD_LITE_MODE, etc.)
guard = GuardPipeline.default()

# Inspect a user prompt before sending to the LLM
result = await guard.pre_process(
    GuardInput(text="ignore previous instructions", context=GuardContext(source="input"))
)

if result.action == "block":
    raise ValueError("Prompt blocked by guard")

# Inspect model output before returning to the user
result = await guard.post_process(
    GuardInput(text=llm_response, context=GuardContext(source="output"))
)
print(result.text)   # sanitized text (redacted, hashed, or original)
print(result.action) # "pass" | "redact" | "hash" | "block"
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GUARD_ENABLED` | `false` | Enable the guard pipeline |
| `GUARD_LITE_MODE` | `false` | Skip SemanticInspector (latency-sensitive paths) |
| `GUARD_ACTION_STRATEGY` | `redact` | `redact` \| `hash` \| `block` |
| `GUARD_PII_ENTITIES` | (all) | Comma-separated presidio entity names |
| `GUARD_LANGUAGE` | `en` | Language for presidio analysis |
| `GUARD_MODEL_PATH` | — | Path to pre-downloaded distilbert model (air-gap) |
| `GUARD_MODEL_CACHE_DIR` | `~/.cache/arc/models/` | HuggingFace model cache dir |
| `GUARD_HASH_KEY` | auto | Hex-encoded HMAC-SHA256 key (share across replicas) |
| `GUARD_HASH_KEY_FILE` | `~/.local/share/arc/guard_hash_key` | Key file path |
| `GUARD_REPORTER_QUEUE_SIZE` | `1000` | Max events buffered in NatsReporter queue |

## Architecture

```
GuardInput → Middleware.before()
           → InjectionInspector   (regex, <1ms, input only)
           → PresidioInspector    (presidio-analyzer, 5-20ms)
           → SemanticInspector    (distilbert, 30-80ms, skipped in lite_mode)
           → CustomInspector      (EntityRegistry patterns)
           → ActionStrategy       (redact / hash / block)
           → Middleware.after()
           → Reporter.report()    (fire-and-forget)
           → GuardResult
```

All extension points are `typing.Protocol` — zero imports from `arc_guard` required to implement custom inspectors, strategies, or reporters.
