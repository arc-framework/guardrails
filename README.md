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

## Architecture

See [`docs/architecture/README.md`](docs/architecture/README.md) for the canonical architecture overview, including the rewrite roadmap, walkthrough index, and public-surface manifest.

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution flow and the doc-tree convention.

## License

Proprietary; see [LICENSE](LICENSE) (if present) or contact the maintainers.
