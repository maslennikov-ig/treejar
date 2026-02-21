#!/usr/bin/env bash
set -euo pipefail

case "${1:-web}" in
  worker)
    echo "Starting ARQ worker..."
    exec arq src.worker.WorkerSettings
    ;;
  web|"")
    echo "Starting Uvicorn web server on port ${APP_PORT:-8000}..."
    exec uvicorn src.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}"
    ;;
  *)
    echo "Unknown command: $1"
    echo "Usage: entrypoint.sh [web|worker]"
    exit 1
    ;;
esac
