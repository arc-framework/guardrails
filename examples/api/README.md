# OpenAI-compatible API → moved to `packages/api/`

The OpenAI-compatible chat-completions endpoint is no longer an example —
it ships as a first-class transport from the `arc-guard-service` package.

## Where the code lives now

| Concern | Location |
|---|---|
| OpenAI route handler | [`packages/api/src/arc_guard_service/transport/openai.py`](../../packages/api/src/arc_guard_service/transport/openai.py) |
| OpenAI schemas | [`packages/api/src/arc_guard_service/schemas/openai.py`](../../packages/api/src/arc_guard_service/schemas/openai.py) |
| App factory (mounts both `/v1/guard` + `/v1/chat/completions`) | [`packages/api/src/arc_guard_service/transport/http.py`](../../packages/api/src/arc_guard_service/transport/http.py) |
| Recommended settings (backend, ports, doc toggles) | [`packages/api/src/arc_guard_service/settings.py`](../../packages/api/src/arc_guard_service/settings.py) |
| Stdlib-bridge logger for SDK pipeline events | [`packages/api/src/arc_guard_service/observability.py`](../../packages/api/src/arc_guard_service/observability.py) |
| Dockerfile + Compose stack with Ollama | [`packages/api/Dockerfile`](../../packages/api/Dockerfile), [`packages/api/docker-compose.yml`](../../packages/api/docker-compose.yml) |

## How to run it

```bash
make docker-up   # boots arc-guard-service + ollama, auto-pulls llama3.2
make api-up      # local-only, no Docker, no LLM (BACKEND=echo)
```

Endpoints exposed by the running container/process:

- `POST /v1/guard` — generic guard (`GuardInput` → `GuardResult`)
- `POST /v1/chat/completions` — OpenAI-compatible
- `GET /docs` — Swagger UI with "Try it out"
- `GET /openapi.json` — for Postman / client-gen import
- `GET /` — health / identity

## Why this used to be an example

The OpenAI flavor was prototyped here under `examples/` while we
validated the intercept story end-to-end. Once the pattern proved out,
the handler moved into the SDK so every operator gets it for free —
no copy-paste required.

The other examples (`library-in-process`, `sidecar-http`, `cli-batch`,
`fastapi-middleware`) remain — they show consumption modes, not
deployments.
