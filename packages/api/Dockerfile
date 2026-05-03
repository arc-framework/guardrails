# arc-guard-service container.
#
# Build context: repo root (so the packages/ workspace is available).
#   docker build -f packages/api/Dockerfile -t arc-guard-service .

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARC_GUARD_SERVICE_BIND=0.0.0.0 \
    ARC_GUARD_SERVICE_PORT=8766 \
    ARC_GUARD_SERVICE_BACKEND=echo \
    ARC_GUARD_SERVICE_LOG_LEVEL=INFO \
    ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH=/data/lifecycle.db

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

# uv for the workspace install
RUN pip install --no-cache-dir uv==0.5.*

WORKDIR /app

# Workspace members only — no examples, specs, docs, etc. The image IS
# the deployment surface.
COPY packages/ /app/packages/

# Install the workspace into the system site-packages. --system avoids the
# per-user-venv indirection inside the container; the image IS the env.
RUN cd /app/packages && \
    uv pip install --system \
      --editable ./core \
      --editable ./pip \
      --editable './api[fastapi]'

RUN mkdir -p /data
VOLUME /data

EXPOSE 8766

# Healthcheck — root endpoint returns a service descriptor JSON
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${ARC_GUARD_SERVICE_PORT}/ > /dev/null || exit 1

# python -m arc_guard_service routes through the CLI which configures
# stdlib logging once and then hands off to uvicorn.
CMD ["python", "-m", "arc_guard_service"]
