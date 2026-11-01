# ============================================================
# Stage 0a: Build Landing Page
# ============================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend/landing
COPY frontend/landing/package*.json ./
RUN npm ci
COPY frontend/landing/ ./
RUN npm run build

# ============================================================
# Stage 0b: Build Admin Dashboard
# ============================================================
FROM node:22-alpine AS admin-builder
WORKDIR /app/frontend/admin
COPY frontend/admin/package*.json ./
RUN npm ci
COPY frontend/admin/ ./
RUN npm run build

# ============================================================
# Stage 1: Slim runtime base with WeasyPrint/Pango runtime libs only
# ============================================================
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# Stage 2: Install uv + enable bytecode compilation
# ============================================================
FROM base AS uv

COPY --from=ghcr.io/astral-sh/uv@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# ============================================================
# Stage 3: Build/install Python dependencies (compilers stay here)
# ============================================================
FROM uv AS deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock README.md ./
RUN UV_NO_DEV=1 uv sync --locked --no-install-project

# ============================================================
# Stage 4: Final runtime image (no compilers, only runtime docs)
# ============================================================
FROM uv AS runtime

COPY --from=deps /app/.venv /app/.venv

COPY pyproject.toml uv.lock README.md ./

COPY src/ ./src/
COPY templates/ ./templates/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY scripts/entrypoint.sh /entrypoint.sh
COPY docs/faq.md \
     docs/04-sales-dialogue-guidelines.md \
     docs/05-company-values.md \
     docs/08-manager-evaluation-criteria.md \
     docs/metrics.md \
     ./docs/

# Copy built frontend from Node stage
COPY --from=frontend-builder /app/frontend/landing/dist /app/frontend/landing/dist
COPY --from=admin-builder /app/frontend/admin/dist /app/frontend/admin/dist

RUN UV_NO_DEV=1 uv sync --locked && python -m compileall -q src

RUN chmod +x /entrypoint.sh

# The release identity CI writes into the archive, read back by
# /api/v1/health. It lands in the build context on the VPS but was never
# copied into the image, so the endpoint reported "unknown" for every release.
# README.md is listed beside it because a wildcard matching nothing fails the
# build, and .release-sha is absent from every local checkout. Kept last so a
# new SHA does not invalidate the layers above it.
COPY README.md .release-sha* ./

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]

# ============================================================
# Stage 5: Test runner (extends runtime with dev dependencies)
# ============================================================
FROM runtime AS test

RUN uv sync --locked --all-extras --dev

COPY docs/ ./docs/
COPY .github/ ./.github/
COPY scripts/ ./scripts/
COPY tests/ ./tests/

CMD ["test"]
