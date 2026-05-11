# arc-guardrails

A guardrails library for LLM applications. Three packages, one decision contract:

- **`arc-guard-core`** — zero-dep contract layer (typed models, Protocols, exception hierarchy, pipeline shape).
- **`arc-guard`** — batteries-included library with built-in inspectors, strategies, reporters, middleware adapters.
- **`arc-guard-service`** — transport-neutral deployment surface (in-process function call, CLI batch job, HTTP sidecar, FastAPI middleware).

## Quick start

```bash
pip install arc-guard
python -c "
import asyncio
from arc_guard.pipeline import GuardPipeline
from arc_guard_core.types import GuardInput
result = asyncio.run(GuardPipeline().pre_process(GuardInput(text='ignore previous instructions')))
print(result.action, result.refusal.code if result.refusal else None)
"
# block jailbreak_strong
```

For sidecar deployment:

```bash
pip install 'arc-guard-service[fastapi]'
python -m arc_guard_service --port 8000
```

See [`examples/`](examples/) for four runnable integration modes.

## Run with Docker

A one-command stack is published on Docker Hub. No source checkout, no build step.

```bash
curl -fsSLO https://raw.githubusercontent.com/<owner>/<repo>/main/docker-compose.yml
docker compose up
```

Three services come up:

| Service | URL | What it serves |
|---|---|---|
| Dashboard | http://127.0.0.1:5173 | GuardRailFlow operator UI |
| API | http://127.0.0.1:8766/docs | arc-guard-service Swagger UI |
| Ollama | http://127.0.0.1:11434 | Upstream LLM (llama3.2 pulled on first run) |

Switch to the heavyweight ML-enabled image (semantic-intent + jailbreak-ml + code-injection extras pre-installed, sentence-transformer model pre-cached):

```bash
docker compose --profile ml up
```

Pin a specific version:

```bash
ARC_GUARD_IMAGE_TAG=0.7.1 docker compose up
```

**Published images**

| Tag | Size | Inspectors enabled |
|---|---|---|
| `wilp/2024mt03053-arc-guard-service:latest` | ~500 MB | Injection + Presidio (default pipeline) |
| `wilp/2024mt03053-arc-guard-service:ml` | ~3.5 GB | All inspectors including semantic-intent + jailbreak-ml |
| `wilp/2024mt03053-arc-guardrail-flow:latest` | ~45 MB | nginx + Vite-built SPA |

Multi-arch builds: `linux/amd64` + `linux/arm64`. Tag-driven CI publishes from `git push --tags v*.*.*` via [`.github/workflows/docker-publish.yml`](.github/workflows/docker-publish.yml).

## Architecture

See [`docs/architecture/README.md`](docs/architecture/README.md) for the canonical architecture overview, including the rewrite roadmap, walkthrough index, and public-surface manifest.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution flow and the doc-tree convention.

## License

Proprietary; see [LICENSE](LICENSE) (if present) or contact the maintainers.
