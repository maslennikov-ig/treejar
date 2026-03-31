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

    # Pre-flight: fix duplicate alembic_version rows (multiple DB heads)
    # This can happen if a migration was applied with wrong down_revision
    HEAD_COUNT=$(python3 -c "
import sqlalchemy, os
url = os.environ.get('DATABASE_URL', '')
if url:
    engine = sqlalchemy.create_engine(url.replace('+asyncpg', ''))
    with engine.connect() as conn:
        result = conn.execute(sqlalchemy.text('SELECT count(*) FROM alembic_version'))
        print(result.scalar())
else:
    print(0)
" 2>/dev/null || echo 0)

    if [ "$HEAD_COUNT" -gt 1 ]; then
      echo "⚠️  Found $HEAD_COUNT rows in alembic_version — fixing to keep only the latest head..."
      python3 -c "
import sqlalchemy, os
url = os.environ.get('DATABASE_URL', '').replace('+asyncpg', '')
engine = sqlalchemy.create_engine(url)
with engine.begin() as conn:
    rows = conn.execute(sqlalchemy.text('SELECT version_num FROM alembic_version')).scalars().all()
    print(f'  Current versions: {rows}')
    # Keep only the Alembic-resolved current head
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config('alembic.ini')
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    print(f'  Script head: {head}')
    if head in rows:
        conn.execute(sqlalchemy.text(\"DELETE FROM alembic_version WHERE version_num != :head\"), {'head': head})
        print(f'  ✅ Cleaned up, kept only {head}')
    else:
        print('  ⚠️  Head not in DB rows, skipping cleanup')
"
    fi

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
