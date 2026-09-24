#!/usr/bin/env bash
# VPS deployment script for the canonical Noor runtime.
# Deploys a release archive into the live runtime directory, preserves
# operational state, rebuilds the Docker Compose stack, and verifies health.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/vps-deploy.sh --archive <release.tar.gz> [options]

Options:
  --archive <path>         Path to the release archive to deploy. Required.
  --target-dir <path>      Runtime directory. Default: /opt/noor
  --compose-file <path>    Compose file relative to target dir. Default: docker-compose.yml
  --project-name <name>    Docker Compose project name. Default: basename of target dir.
  --health-url <url>       URL checked after deploy. Default: http://127.0.0.1:8002/api/v1/health
  --app-only               Start app; preserve a verified running test-only worker, otherwise stop worker.
  --preserve-test-worker   With --app-only, refresh an already-running test-only worker.
  -h, --help               Show this help.

The release archive should contain the tracked repository files plus optional
deployment metadata files such as .release-sha.
EOF
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: Required command '$cmd' is not available." >&2
        exit 1
    fi
}

ARCHIVE_PATH=""
TARGET_DIR="/opt/noor"
COMPOSE_FILE="docker-compose.yml"
PROJECT_NAME=""
HEALTH_URL="http://127.0.0.1:8002/api/v1/health"
APP_ONLY=false
PRESERVE_TEST_WORKER=false
REFRESH_TEST_WORKER=false
KEEP_PATHS=(
    ".agent"
    ".beads"
    ".claude"
    ".codex"
    ".codex-backups"
    ".coverage"
    ".env"
    ".env.dev"
    ".hotfix-backups"
    ".mcp.json"
    ".ruff_cache"
    ".worktrees"
    "debug.log"
    "logs"
    "ops"
)

while [ "$#" -gt 0 ]; do
    case "$1" in
        --archive)
            ARCHIVE_PATH="$2"
            shift 2
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --compose-file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        --project-name)
            PROJECT_NAME="$2"
            shift 2
            ;;
        --health-url)
            HEALTH_URL="$2"
            shift 2
            ;;
        --app-only)
            APP_ONLY=true
            PRESERVE_TEST_WORKER=true
            shift
            ;;
        --preserve-test-worker)
            PRESERVE_TEST_WORKER=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument '$1'." >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ "$PRESERVE_TEST_WORKER" = true ] && [ "$APP_ONLY" != true ]; then
    echo "Error: --preserve-test-worker requires --app-only." >&2
    exit 1
fi

if [ -z "$ARCHIVE_PATH" ]; then
    echo "Error: --archive is required." >&2
    usage >&2
    exit 1
fi

if [ ! -f "$ARCHIVE_PATH" ]; then
    echo "Error: Archive not found: $ARCHIVE_PATH" >&2
    exit 1
fi

mkdir -p "$TARGET_DIR"

if [ ! -f "$TARGET_DIR/.env" ]; then
    echo "Error: Missing $TARGET_DIR/.env. Seed runtime secrets before deploying." >&2
    exit 1
fi

for cmd in curl docker mktemp rsync tar; do
    require_cmd "$cmd"
done

PROJECT_NAME="${PROJECT_NAME:-$(basename "$TARGET_DIR")}"
STAGING_DIR="$(mktemp -d)"
BACKUP_DIR="$TARGET_DIR/.hotfix-backups"
CURRENT_RELEASE_SHA="unknown"

cleanup() {
    rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

# Read only the effective safety configuration, never source or print secrets.
# Importing WorkerSettings does not run startup or connect to runtime services.
TEST_WORKER_PROBE=$(cat <<'PYCODE'
import hashlib
import json
from src.core.config import settings
if not settings.test_channel_restore_mode:
    print("disabled")
else:
    from src.worker import WorkerSettings
    assert not WorkerSettings.cron_jobs, "test worker must have no cron jobs"
    # Allowlist, not an exact list, so the probe passes on both the running
    # worker and the candidate while a release adds or removes an allowed job.
    names = [f.name for f in WorkerSettings.functions]
    assert "process_incoming_batch" in names
    assert set(names) <= {"process_incoming_batch", "retry_pending_quotation", "refresh_conversation_summary"}
    fields = ("test_channel_restore_mode", "wazzup_channel_id",
              "wazzup_outbound_allowed_channel_id", "telegram_allowed_inbound_phone")
    state = {key: getattr(settings, key) for key in fields}
    assert state["wazzup_channel_id"] and state["wazzup_channel_id"] == state["wazzup_outbound_allowed_channel_id"]
    print(hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest())
PYCODE
)
if [ "$PRESERVE_TEST_WORKER" = true ] && [ -f "$TARGET_DIR/$COMPOSE_FILE" ]; then
    EXISTING_WORKER_ID="$(docker compose --project-name "$PROJECT_NAME" \
        -f "$TARGET_DIR/$COMPOSE_FILE" ps --status running --quiet worker)"
    if [ -n "$EXISTING_WORKER_ID" ]; then
        TEST_WORKER_STATE="$(docker exec "$EXISTING_WORKER_ID" python -c "$TEST_WORKER_PROBE")"
        if [[ "$TEST_WORKER_STATE" =~ ^[0-9a-f]{64}$ ]]; then
            REFRESH_TEST_WORKER=true
        elif [ "$TEST_WORKER_STATE" != disabled ]; then
            echo "Error: Cannot verify existing test-worker safety state." >&2
            exit 1
        fi
    fi
fi

if [ "$APP_ONLY" = true ] && [ "$REFRESH_TEST_WORKER" = false ] && [ -f "$TARGET_DIR/$COMPOSE_FILE" ]; then
    # The app-only gate must also contain an already-running worker. Stop it
    # before replacing the runtime tree or building the new application.
    docker compose --project-name "$PROJECT_NAME" \
        -f "$TARGET_DIR/$COMPOSE_FILE" stop worker
    RUNNING_WORKER_ID="$(
        docker compose --project-name "$PROJECT_NAME" \
            -f "$TARGET_DIR/$COMPOSE_FILE" \
            ps --status running --quiet worker
    )"
    if [ -n "$RUNNING_WORKER_ID" ]; then
        echo "Error: Worker is still running after the app-only stop gate." >&2
        exit 1
    fi
fi

if [ -f "$TARGET_DIR/.release-sha" ]; then
    CURRENT_RELEASE_SHA="$(tr -d ' \n' < "$TARGET_DIR/.release-sha")"
fi

echo "Deploying archive $ARCHIVE_PATH into $TARGET_DIR (project: $PROJECT_NAME)"
tar -xzf "$ARCHIVE_PATH" -C "$STAGING_DIR"

if [ ! -f "$STAGING_DIR/$COMPOSE_FILE" ]; then
    echo "Error: Release archive does not contain $COMPOSE_FILE." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"
if [ -f "$TARGET_DIR/$COMPOSE_FILE" ]; then
    TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
    BACKUP_PATH="$BACKUP_DIR/deploy-${TIMESTAMP}-from-${CURRENT_RELEASE_SHA}.tar.gz"
    TAR_EXCLUDES=()
    for path in "${KEEP_PATHS[@]}"; do
        TAR_EXCLUDES+=(--exclude="./$path")
    done
    tar "${TAR_EXCLUDES[@]}" -czf "$BACKUP_PATH" -C "$TARGET_DIR" .
    echo "Saved rollback backup to $BACKUP_PATH"
fi

BACKUP_FILES=()
while IFS= read -r backup_file; do
    BACKUP_FILES+=("$backup_file")
done < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'deploy-*.tar.gz' -print 2>/dev/null | LC_ALL=C sort -r)
if [ "${#BACKUP_FILES[@]}" -gt 5 ]; then
    printf '%s\0' "${BACKUP_FILES[@]:5}" | xargs -0r rm -f
fi

RSYNC_ARGS=(
    --archive
    --delete
)
for path in "${KEEP_PATHS[@]}"; do
    RSYNC_ARGS+=(--exclude="$path")
done

rsync "${RSYNC_ARGS[@]}" "$STAGING_DIR"/ "$TARGET_DIR"/
mkdir -p "$TARGET_DIR/logs/maintenance"

cd "$TARGET_DIR"
if [ "$REFRESH_TEST_WORKER" = true ]; then
    docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" build app worker
    CANDIDATE_TEST_STATE="$(docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" \
        run --rm --no-deps --entrypoint python worker -c "$TEST_WORKER_PROBE")"
    if [ "$CANDIDATE_TEST_STATE" != "$TEST_WORKER_STATE" ]; then
        echo "Error: Candidate changes test-worker boundaries; running containers preserved." >&2
        exit 1
    fi
    docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" \
        up -d --no-build --no-deps --timeout 180 app worker
    NEW_WORKER_ID="$(docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" \
        ps --status running --quiet worker)"
    if [ -z "$NEW_WORKER_ID" ] || \
        [ "$(docker exec "$NEW_WORKER_ID" python -c "$TEST_WORKER_PROBE")" != "$TEST_WORKER_STATE" ]; then
        docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" stop worker
        echo "Error: Refreshed worker failed safety verification; worker stopped." >&2
        exit 1
    fi
elif [ "$APP_ONLY" = true ]; then
    docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" \
        up -d --build --no-deps app
else
    docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" up -d --build
fi

MAX_ATTEMPTS=20
ATTEMPT=1
until curl --fail --silent --show-error "$HEALTH_URL" >/dev/null; do
    if [ "$ATTEMPT" -ge "$MAX_ATTEMPTS" ]; then
        echo "Health check failed after ${MAX_ATTEMPTS} attempts: $HEALTH_URL" >&2
        docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" ps || true
        docker compose --project-name "$PROJECT_NAME" -f "$COMPOSE_FILE" logs --tail=50 app worker nginx || true
        exit 1
    fi
    echo "Health check not ready yet (${ATTEMPT}/${MAX_ATTEMPTS}); retrying..."
    ATTEMPT=$((ATTEMPT + 1))
    sleep 3
done

DEPLOYED_RELEASE_SHA="unknown"
if [ -f "$TARGET_DIR/.release-sha" ]; then
    DEPLOYED_RELEASE_SHA="$(tr -d ' \n' < "$TARGET_DIR/.release-sha")"
fi

echo "Deployment successful. Active release: $DEPLOYED_RELEASE_SHA"
