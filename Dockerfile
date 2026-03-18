# ============================================================
# Stage 0a: Build Landing Page
# ============================================================
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend/landing
COPY frontend/landing/package*.json ./
RUN npm install
COPY frontend/landing/ ./
RUN npm run build

# ============================================================
# Stage 0b: Build Admin Dashboard
# ============================================================
FROM node:22-alpine AS admin-builder
WORKDIR /app/frontend/admin
COPY frontend/admin/package*.json ./
RUN npm install
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
# Stage 2: Install Python dependencies
# ============================================================
FROM base AS deps

COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir .

# ============================================================
# Stage 3: Final runtime image
# ============================================================
FROM base AS runtime

# Copy installed packages from deps stage
COPY --from=deps /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY scripts/entrypoint.sh /entrypoint.sh
COPY docs/ docs/

# Copy built frontend from Node stage
COPY --from=frontend-builder /app/frontend/landing/dist /app/frontend/landing/dist
COPY --from=admin-builder /app/frontend/admin/dist /app/frontend/admin/dist

RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
