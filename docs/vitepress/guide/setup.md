# Setup

The repository already provides a practical local command surface through the root Makefile. Most contributors do not need to remember package-local commands once the workspace is installed.

## Prerequisites

- Python 3.11+
- `uv` for Python workspace management
- Node.js 20+ for the dashboard and documentation site
- Docker and Docker Compose for the optional full local stack

## First-Time Install

```bash
make init
```

That prepares the `packages/.venv` workspace environment with all extras and development tooling.

## Fastest Validation Path

```bash
make smoke
```

This runs the canonical in-process flow end-to-end using the installed runtime packages.

## Common Local Workflows

| Goal | Command |
| --- | --- |
| Boot the API locally | `make api-up` |
| Tail API logs | `make api-logs` |
| Exercise the running API | `make demo` |
| Open the SSE terminal dashboard | `make sse` |
| Bring up the full Docker stack | `make docker-up` |
| Run tests across packages | `make test` |
| Run lint + type checks | `make lint` and `make typecheck` |
| Run aggregate verification | `make all` |

## Package-Local Quality Gates

When you need tighter scope than the top-level Make targets, each package uses `uv` directly:

```bash
cd packages/core && uv run pytest tests/
cd packages/pip && uv run ruff check src tests
cd packages/api && uv run mypy src
```

## Documentation Site

The VitePress site lives in `docs/vitepress`, while the configuration stays at the repository root under `.vitepress`.

```bash
pnpm install
pnpm docs:dev
pnpm docs:build
```

If you prefer to stay on the Makefile surface, use the documentation targets described in the root help output.