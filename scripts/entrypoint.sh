#!/usr/bin/env bash
set -euo pipefail

case "${1:-web}" in
  test)
    echo "Running tests..."
    exec python -m pytest tests/ ${TEST_ARGS:--v --timeout=120 -m 'not integration'}
    ;;
  worker)
    echo "Starting ARQ worker..."
    exec arq src.worker.WorkerSettings
    ;;
  web|"")
    echo "Running Alembic migrations..."

    # Pre-flight: reconcile duplicate alembic_version rows (multiple DB heads)
    # using asyncpg via SQLAlchemy's async engine (psycopg2 is not installed).
    python3 - <<'PY' || echo "⚠️  alembic_version pre-flight skipped (table may not exist yet)"
import asyncio
import os
import sys
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine


def _async_url(raw: str) -> str:
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw[len("postgresql://") :]
    return raw


async def main() -> None:
    raw = os.environ.get("DATABASE_URL_DIRECT") or os.environ.get("DATABASE_URL", "")
    if not raw:
        return
    engine = create_async_engine(_async_url(raw))
    try:
        async with engine.begin() as conn:
            rows = (
                await conn.execute(
                    sqlalchemy.text("SELECT version_num FROM alembic_version")
                )
            ).scalars().all()
            if len(rows) <= 1:
                return
            print(
                f"⚠️  Found {len(rows)} rows in alembic_version ({list(rows)}) — "
                "reconciling to current script head...",
                file=sys.stderr,
            )
            from alembic.config import Config
            from alembic.script import ScriptDirectory

            script = ScriptDirectory.from_config(Config("alembic.ini"))
            head = script.get_current_head()
            if head and head in rows:
                await conn.execute(
                    sqlalchemy.text(
                        "DELETE FROM alembic_version WHERE version_num != :head"
                    ),
                    {"head": head},
                )
                print(f"  ✅ Reconciled alembic_version to {head}", file=sys.stderr)
            else:
                print(
                    f"  ⚠️  Script head {head!r} not in DB rows; leaving untouched",
                    file=sys.stderr,
                )
    finally:
        await engine.dispose()


asyncio.run(main())
PY

    alembic upgrade head
    echo "Starting Uvicorn web server on port ${APP_PORT:-8000}..."
    exec uvicorn src.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
    ;;
  *)
    echo "Unknown command: $1"
    echo "Usage: entrypoint.sh [web|worker|test]"
    exit 1
    ;;
esac
