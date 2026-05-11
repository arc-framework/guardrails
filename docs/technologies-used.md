# Technologies Used

This is a direct-dependency inventory for the current repository.

Scope:

- Source of truth: direct dependencies and first-order platform/tooling declared in [packages/pyproject.toml](../packages/pyproject.toml), [packages/core/pyproject.toml](../packages/core/pyproject.toml), [packages/pip/pyproject.toml](../packages/pip/pyproject.toml), [packages/api/pyproject.toml](../packages/api/pyproject.toml), [apps/guardrail-flow/package.json](../apps/guardrail-flow/package.json), the Dockerfiles, the Compose files, and [.github/workflows/docker-publish.yml](../.github/workflows/docker-publish.yml).
- Excludes nested and transitive dependencies.
- GitNexus note: `npx gitnexus status` reported the index as stale on 2026-05-11, so the manifests above are the authoritative source for this snapshot.

## Python Libraries And Tooling

### Runtime baseline

| Technology      | Declared in                                                                                  | Notes                                   |
| --------------- | -------------------------------------------------------------------------------------------- | --------------------------------------- |
| Python `>=3.11` | `packages/pyproject.toml`, package-local `pyproject.toml` files                              | Workspace-wide Python baseline          |
| `uv`            | `packages/pyproject.toml`, API Dockerfiles, Makefile                                         | Workspace/package manager and installer |
| `hatchling`     | `packages/core/pyproject.toml`, `packages/pip/pyproject.toml`, `packages/api/pyproject.toml` | Python build backend                    |

### Workspace packages

| Package             | Declared in                    | Notes                          |
| ------------------- | ------------------------------ | ------------------------------ |
| `arc-guard-core`    | `packages/core/pyproject.toml` | Contract layer                 |
| `arc-guard`         | `packages/pip/pyproject.toml`  | Main Python guardrails package |
| `arc-guard-service` | `packages/api/pyproject.toml`  | Thin deployment/API surface    |

### Direct Python runtime dependencies

| Library               | Version   | Declared in                    |
| --------------------- | --------- | ------------------------------ |
| `pydantic`            | `>=2.0`   | `packages/core/pyproject.toml` |
| `arc-guard-core`      | `>=0.5.0` | `packages/pip/pyproject.toml`  |
| `presidio-analyzer`   | `>=2.2`   | `packages/pip/pyproject.toml`  |
| `presidio-anonymizer` | `>=2.2`   | `packages/pip/pyproject.toml`  |
| `arc-guard`           | workspace | `packages/api/pyproject.toml`  |
| `pydantic-settings`   | `>=2.0`   | `packages/api/pyproject.toml`  |
| `pyyaml`              | `>=6.0`   | `packages/api/pyproject.toml`  |

### Direct Python optional dependencies

| Extra            | Library                       | Version   | Declared in                   |
| ---------------- | ----------------------------- | --------- | ----------------------------- |
| `fastapi`        | `fastapi`                     | `>=0.110` | `packages/api/pyproject.toml` |
| `fastapi`        | `uvicorn`                     | `>=0.30`  | `packages/api/pyproject.toml` |
| `fastapi`        | `httpx`                       | `>=0.27`  | `packages/api/pyproject.toml` |
| `otel`           | `opentelemetry-api`           | `>=1.20`  | `packages/pip/pyproject.toml` |
| `otel`           | `opentelemetry-sdk`           | `>=1.20`  | `packages/pip/pyproject.toml` |
| `otel`           | `opentelemetry-exporter-otlp` | `>=1.20`  | `packages/pip/pyproject.toml` |
| `semantic`       | `sentence-transformers`       | `>=2.2`   | `packages/pip/pyproject.toml` |
| `semantic`       | `numpy`                       | `>=1.24`  | `packages/pip/pyproject.toml` |
| `jailbreak-ml`   | `transformers`                | `>=4.30`  | `packages/pip/pyproject.toml` |
| `jailbreak-ml`   | `torch`                       | `>=2.0`   | `packages/pip/pyproject.toml` |
| `code-injection` | `sqlparse`                    | `>=0.4`   | `packages/pip/pyproject.toml` |

### Python dev and quality tooling

| Tool             | Version  | Declared in               |
| ---------------- | -------- | ------------------------- |
| `ruff`           | `>=0.6`  | `packages/pyproject.toml` |
| `mypy`           | `>=1.10` | `packages/pyproject.toml` |
| `pytest`         | `>=8.0`  | `packages/pyproject.toml` |
| `pytest-asyncio` | `>=0.23` | `packages/pyproject.toml` |
| `pytest-cov`     | `>=4.1`  | `packages/pyproject.toml` |
| `import-linter`  | `>=2.0`  | `packages/pyproject.toml` |
| `rich`           | `>=13.0` | `packages/pyproject.toml` |

## JavaScript Libraries And Tooling

### Runtime baseline

| Technology     | Declared in                        | Notes                      |
| -------------- | ---------------------------------- | -------------------------- |
| Node.js `>=20` | `apps/guardrail-flow/package.json` | Dashboard runtime baseline |
| TypeScript     | `apps/guardrail-flow/package.json` | SPA language/toolchain     |
| Vite           | `apps/guardrail-flow/package.json` | Frontend build/dev server  |
| React          | `apps/guardrail-flow/package.json` | UI framework               |

### Direct JavaScript runtime dependencies

| Library                         | Version    |
| ------------------------------- | ---------- |
| `@codemirror/lang-json`         | `^6.0.1`   |
| `@codemirror/state`             | `^6.4.1`   |
| `@codemirror/theme-one-dark`    | `^6.1.2`   |
| `@codemirror/view`              | `^6.34.1`  |
| `@dagrejs/dagre`                | `^3.0.0`   |
| `@formkit/auto-animate`         | `^0.8.2`   |
| `@microsoft/fetch-event-source` | `^2.0.1`   |
| `@radix-ui/react-separator`     | `^1.1.8`   |
| `@radix-ui/react-slot`          | `^1.2.4`   |
| `@radix-ui/react-tabs`          | `^1.1.13`  |
| `@tanstack/react-query`         | `^5.59.0`  |
| `@tanstack/react-table`         | `^8.20.5`  |
| `@uiw/react-codemirror`         | `^4.23.5`  |
| `class-variance-authority`      | `^0.7.0`   |
| `clsx`                          | `^2.1.1`   |
| `lucide-react`                  | `^0.453.0` |
| `react`                         | `^18.3.1`  |
| `react-dom`                     | `^18.3.1`  |
| `react-error-boundary`          | `^4.1.2`   |
| `react-router-dom`              | `^6.27.0`  |
| `reactflow`                     | `^11.11.4` |
| `reaviz`                        | `^16.1.2`  |
| `tailwind-merge`                | `^2.5.4`   |
| `zustand`                       | `^4.5.5`   |

### Direct JavaScript dev, build, and test dependencies

| Library                            | Version    |
| ---------------------------------- | ---------- |
| `@eslint/js`                       | `^9.12.0`  |
| `@testing-library/dom`             | `^10.4.0`  |
| `@testing-library/jest-dom`        | `^6.6.2`   |
| `@testing-library/react`           | `^16.0.1`  |
| `@testing-library/user-event`      | `^14.5.2`  |
| `@types/node`                      | `^22.7.6`  |
| `@types/react`                     | `^18.3.11` |
| `@types/react-dom`                 | `^18.3.1`  |
| `@typescript-eslint/eslint-plugin` | `^8.9.0`   |
| `@typescript-eslint/parser`        | `^8.9.0`   |
| `@vitejs/plugin-react`             | `^4.3.2`   |
| `autoprefixer`                     | `^10.4.20` |
| `eslint`                           | `^9.12.0`  |
| `eslint-plugin-react-hooks`        | `^5.0.0`   |
| `eslint-plugin-react-refresh`      | `^0.4.12`  |
| `eslint-plugin-tailwindcss`        | `^3.17.5`  |
| `globals`                          | `^15.11.0` |
| `jsdom`                            | `^25.0.1`  |
| `postcss`                          | `^8.4.47`  |
| `prettier`                         | `^3.3.3`   |
| `prettier-plugin-tailwindcss`      | `^0.6.8`   |
| `tailwindcss`                      | `^3.4.14`  |
| `typescript`                       | `^5.6.3`   |
| `typescript-eslint`                | `^8.9.0`   |
| `vite`                             | `^5.4.9`   |
| `vitest`                           | `^2.1.3`   |

### JavaScript package management

| Tool       | Declared in                                                 | Notes                                           |
| ---------- | ----------------------------------------------------------- | ----------------------------------------------- |
| `pnpm`     | `apps/guardrail-flow/pnpm-lock.yaml`, dashboard Dockerfiles | JS package manager                              |
| `corepack` | `apps/guardrail-flow/Dockerfile`                            | Activates pinned `pnpm` in the production image |

## Infrastructure, Containers, And Delivery Tooling

### Container and local stack technologies

| Technology                      | Declared in                                                               | Notes                                       |
| ------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------- |
| Docker                          | root `docker-compose.yml`, `packages/api/docker-compose.yml`, Dockerfiles | Containerized local and publishable runtime |
| Docker Compose                  | root `docker-compose.yml`, `packages/api/docker-compose.yml`              | Local stack orchestration                   |
| `python:3.11-slim`              | API Dockerfiles                                                           | Base image for Python service               |
| `node:20-alpine`                | dashboard Dockerfiles                                                     | Base image for JS build/dev                 |
| `nginx:1.27-alpine`             | `apps/guardrail-flow/Dockerfile`                                          | Production dashboard runtime                |
| `nginx`                         | `apps/guardrail-flow/nginx.conf`                                          | SPA hosting and `/api` reverse proxy        |
| `ollama/ollama`                 | root `docker-compose.yml`, `packages/api/docker-compose.yml`              | Local LLM service                           |
| `coleifer/sqlite-web`           | `packages/api/docker-compose.yml`                                         | Dev-only SQLite browser                     |
| SQLite-backed lifecycle storage | Compose env + API runtime config                                          | Backing store for lifecycle events          |
| `curl`                          | API Dockerfiles                                                           | Healthcheck utility in containers           |
| `libgomp1`                      | `packages/api/Dockerfile.ml`                                              | Required by the ML image at import time     |

### CI and publish tooling

| Technology                      | Declared in                                                       | Notes                          |
| ------------------------------- | ----------------------------------------------------------------- | ------------------------------ |
| GitHub Actions                  | `.github/workflows/docker-publish.yml`                            | Release/publish automation     |
| `actions/checkout@v4`           | `.github/workflows/docker-publish.yml`                            | Repo checkout in CI            |
| `docker/setup-qemu-action@v3`   | `.github/workflows/docker-publish.yml`                            | Multi-arch emulation           |
| `docker/setup-buildx-action@v3` | `.github/workflows/docker-publish.yml`                            | Docker Buildx setup            |
| `docker/login-action@v3`        | `.github/workflows/docker-publish.yml`                            | Docker Hub auth                |
| `docker/build-push-action@v6`   | `.github/workflows/docker-publish.yml`                            | Multi-arch build and publish   |
| Docker Hub                      | `.github/workflows/docker-publish.yml`, root `docker-compose.yml` | Image registry and pull target |

### Repository-level developer tooling

| Tool     | Declared in                                   | Notes                                                     |
| -------- | --------------------------------------------- | --------------------------------------------------------- |
| GNU Make | `Makefile`                                    | Common developer command surface                          |
| `uv`     | `Makefile`, Python manifests, API Dockerfiles | Python install/run path used in local and container flows |

## What Is Intentionally Not Listed

- Transitive browser, Python, and container dependencies pulled in by the direct dependencies above.
- Dependencies implied only by source imports when they are not declared in a first-order manifest.
- Historical or decommissioned packages that are mentioned in docs but are not present in active manifests.
