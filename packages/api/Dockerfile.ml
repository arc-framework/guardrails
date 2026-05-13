# arc-guard-service — ML-extras variant.
#
# Extends the slim default image with the heavyweight optional inspectors:
#   - [jailbreak-ml]    (transformers + torch ~1.5GB)
#   - [semantic]        (sentence-transformers ~500MB)
#   - [code-injection]  (sqlparse ~5MB)
#
# Build (from repo root):
#   docker build -f packages/api/Dockerfile.ml -t arc-guard-service-ml .
#
# This is the image tagged `:ml` on Docker Hub. Operators who want every
# inspector enabled by default pull `wilp/2024mt03053-arc-guard-service:ml`
# instead of the slim `:latest`. Final image is ~3-4GB; the slim default
# stays ~500MB.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ARC_GUARD_SERVICE_BIND=0.0.0.0 \
    ARC_GUARD_SERVICE_PORT=8766 \
    ARC_GUARD_SERVICE_BACKEND=echo \
    ARC_GUARD_SERVICE_LOG_LEVEL=INFO \
    ARC_GUARD_SERVICE_LIFECYCLE_SQLITE_PATH=/data/arc_guardrail.db \
    HF_HOME=/opt/hf-cache

# build-essential isn't required because we use prebuilt wheels for torch
# and transformers; libgomp1 is needed by torch at import time. curl is
# kept for the HEALTHCHECK below.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.5.*

WORKDIR /app

COPY packages/ /app/packages/

RUN cd /app/packages && \
    uv pip install --system \
      --editable ./core \
      --editable ./pip[code-injection,semantic,jailbreak-ml] \
      --editable './api[fastapi]'

# Pre-download the default semantic-intent model so the first request after
# container start doesn't pay the ~500MB download. Skip cleanly if either
# package isn't present (e.g. someone disabled the extras mid-build).
RUN python - <<'PY'
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    print("[ml] semantic model cached at /opt/hf-cache")
except Exception as exc:
    print(f"[ml] semantic model prefetch skipped: {exc}")
PY

RUN mkdir -p /data
VOLUME /data

EXPOSE 8766

HEALTHCHECK --interval=10s --timeout=3s --start-period=180s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${ARC_GUARD_SERVICE_PORT}/ > /dev/null || exit 1

CMD ["python", "-m", "arc_guard_service"]
