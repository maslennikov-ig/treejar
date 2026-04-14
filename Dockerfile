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
# Stage 1: Base image with system dependencies
# ============================================================
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    fonts-noto \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# Stage 2: Install uv
# ============================================================
FROM base AS uv

COPY --from=ghcr.io/astral-sh/uv@sha256:b1e699368d24c57cda93c338a57a8c5a119009ba809305cc8e86986d4a006754 /uv /uvx /bin/

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# ============================================================
# Stage 3: Install Python dependencies
# ============================================================
FROM uv AS deps

COPY pyproject.toml uv.lock README.md ./
RUN UV_NO_DEV=1 uv sync --locked --no-install-project

# ============================================================
# Stage 4: Final runtime image
# ============================================================
FROM uv AS runtime

COPY --from=deps /app/.venv /app/.venv

COPY pyproject.toml uv.lock README.md ./

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY scripts/entrypoint.sh /entrypoint.sh
COPY docs/ docs/

# Copy built frontend from Node stage
COPY --from=frontend-builder /app/frontend/landing/dist /app/frontend/landing/dist
COPY --from=admin-builder /app/frontend/admin/dist /app/frontend/admin/dist

RUN UV_NO_DEV=1 uv sync --locked

RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]

# ============================================================
# Stage 5: Test runner (extends runtime with dev dependencies)
# ============================================================
FROM runtime AS test

RUN uv sync --locked --all-extras --dev

COPY tests/ ./tests/

CMD ["test"]
