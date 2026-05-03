# OpenAI-compatible API that runs every chat completion through arc-guard.
#
# Build context: repo root (so the packages/ workspace is available).
#   docker build -f examples/api/Dockerfile -t arc-guard-api .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    BACKEND=echo \
    API_HOST=0.0.0.0 \
    API_PORT=8766

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

# uv for the workspace install
RUN pip install --no-cache-dir uv==0.5.*

WORKDIR /app

# Copy the workspace + the api example. We copy only what's needed
# for the api to run (no specs/, docs/, tools/, examples/cli-batch/, etc.).
COPY packages/ /app/packages/
COPY examples/api/main.py /app/main.py
COPY examples/api/schemas.py /app/schemas.py

# Install the workspace members + httpx into the system site-packages.
# --system avoids the per-user-venv indirection inside the container; the
# image IS the environment.
RUN cd /app/packages && \
    uv pip install --system \
      --editable ./core \
      --editable ./pip \
      --editable ./api \
      'arc-guard-service[fastapi]' \
      'httpx>=0.27' \
      uvicorn

EXPOSE 8766

# Healthcheck — api answers on / with a service descriptor JSON
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${API_PORT}/ > /dev/null || exit 1

# uvicorn launches via sh -c so API_HOST/API_PORT env vars are honored
CMD ["sh", "-c", "uvicorn --app-dir /app main:app --host ${API_HOST} --port ${API_PORT}"]
