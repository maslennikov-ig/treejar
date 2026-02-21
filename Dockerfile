# ============================================================
# Stage 1: Base image with system dependencies
# ============================================================
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ============================================================
# Stage 2: Install Python dependencies
# ============================================================
FROM base AS deps

COPY pyproject.toml ./
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
COPY scripts/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["web"]
