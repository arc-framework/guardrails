# Technology Stack

## Core Languages and Frameworks

| Layer | Technology |
| --- | --- |
| Contract and runtime packages | Python 3.11+ |
| Workspace/package management | `uv` |
| Service layer | FastAPI + Pydantic settings |
| Dashboard | React + TypeScript + Vite |
| Docs site | VitePress |

## Runtime Libraries

| Area | Libraries |
| --- | --- |
| Detection | Presidio, optional sentence-transformers, optional transformers/torch |
| Observability | Optional OpenTelemetry adapters |
| Data validation | Pydantic v2 |
| Service transport | FastAPI, Uvicorn, HTTPX |

## Frontend and Operator Tooling

| Area | Libraries |
| --- | --- |
| Flow visualization | React Flow in the operator dashboard, Vue Flow in this docs site |
| State and data | TanStack Query, Zustand, TanStack Table |
| Build tooling | Vite, TypeScript, ESLint, Prettier, Vitest |

## Infrastructure

| Area | Technology |
| --- | --- |
| Containers | Docker and Docker Compose |
| Local model service | Ollama |
| Dev database viewer | SQLite-backed dashboard data and optional sqlite-web |
| Web serving | Nginx for the dashboard production image |

## Repository Tooling

The root Makefile coordinates install, smoke tests, service boot, Docker orchestration, linting, typing, testing, and architecture checks so contributors have one predictable command surface.