# Example: sidecar-http

Deploy `arc-guard-service` as an HTTP sidecar; call it from any language
that can speak JSON over HTTP.

## What this shows

The "transport-neutral entrypoint" mode: the guard pipeline runs in its
own process; an application written in any language POSTs JSON to
`/v1/guard` and gets a `GuardResult` JSON payload back.

## Run

```bash
cd examples/sidecar-http
pip install 'arc-guard-service[fastapi]'

# Boot the service (in a background terminal):
python -m arc_guard_service --bind 127.0.0.1 --port 8000

# In another terminal:
./client.sh
```

Expected output:

```json
{"text": "What is 2 + 2?", "action": "pass", ...}
```

For the jailbreak prompt:

```json
{"text": "...", "action": "block", "refusal": {"code": "jailbreak_strong", ...}}
```

## JSON payload schema

```json
POST /v1/guard
Content-Type: application/json
{
  "text": "the user prompt to evaluate",
  "context": {                         // optional
    "source": "input",                 // or "output"
    "user_id": "...",                  // optional
    "session_id": "...",               // optional
    "correlation_id": "...",           // optional
    "metadata": {}                     // optional
  },
  "policy_hints": []                   // optional list of strings
}
```

Response:

```json
{
  "text": "(possibly sanitized) text",
  "action": "pass" | "block" | "redact" | "hash" | "tokenize",
  "findings": [...],
  "refusal": null | { "code": "...", "human_message": "...", ... },
  "fidelity_score": null | { "value": ..., "sentinel": "..." },
  ...
}
```

Error responses use the same `RefusalEnvelope` shape with non-200 HTTP status:

- 400 → `{ "code": "api_invalid_request", ... }` (malformed JSON or schema)
- 413 → `{ "code": "api_invalid_request", ... }` (body too large)
- 504 → `{ "code": "api_transport_timeout", ... }` (pipeline timeout)

## Trade-offs

- **Pros**: language-agnostic; single update point for guard config;
  observability lives in one place.
- **Cons**: per-request network hop; sidecar must be deployed and
  monitored separately.
