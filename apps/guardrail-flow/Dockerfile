# GuardRailFlow operator dashboard — production image.
#
# Multi-stage build: a Node builder runs `pnpm build` to produce the static
# Vite output in /app/dist, then an nginx:alpine runtime serves those files
# plus reverse-proxies /api/* to the arc-guard-service container. The
# runtime image stays under ~50MB because none of the build toolchain (node,
# pnpm, sources, node_modules) is carried over.
#
# Build (from repo root):
#   docker build -f apps/guardrail-flow/Dockerfile -t arc-guardrail-flow apps/guardrail-flow
#
# The image expects to be reached on port 80 by default; docker-compose maps
# the host's 5173 to the container's 80 so the local URL stays familiar.

# ----------------------------- builder ----------------------------------
FROM node:20-alpine AS builder

ENV PNPM_HOME=/pnpm \
    PATH="/pnpm:$PATH"

RUN corepack enable && corepack prepare pnpm@9.12.0 --activate

WORKDIR /app

# Install dependencies first (cached layer when only sources change)
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Build inputs
COPY tsconfig.json tsconfig.build.json vite.config.ts vitest.config.ts \
     postcss.config.js tailwind.config.ts components.json index.html \
     eslint.config.js ./
COPY src ./src
COPY public ./public
COPY fixtures ./fixtures
COPY canvases ./canvases

# The build env determines the API base URL the SPA talks to. The default
# routes through nginx (relative /api/*), which the runtime image proxies
# to the api service. Operators wanting a different base URL pass
# `--build-arg VITE_DASHBOARD_API_URL=https://api.example.com` and rebuild.
ARG VITE_DASHBOARD_API_URL="/api"
ENV VITE_DASHBOARD_API_URL=${VITE_DASHBOARD_API_URL}
ARG VITE_DASHBOARD_MODE="live"
ENV VITE_DASHBOARD_MODE=${VITE_DASHBOARD_MODE}

RUN pnpm build

# ----------------------------- runtime ----------------------------------
FROM nginx:1.27-alpine AS runtime

# SPA-aware nginx config: serves /app and forwards /api/* to the api service.
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Vite build output
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# nginx:alpine's default CMD already runs nginx in the foreground; relying
# on the upstream default keeps the surface minimal.
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1/ > /dev/null 2>&1 || exit 1
