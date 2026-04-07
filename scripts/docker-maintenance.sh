#!/usr/bin/env bash
# Safe Docker storage maintenance for the canonical Noor VPS.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/docker-maintenance.sh [--apply] [options]

Options:
  --apply                          Execute cleanup. Default is dry-run.
  --aggressive                     Remove all unused builder cache and all unused images.
  --target-dir <path>              Runtime directory used for health-check context. Default: /opt/noor
  --health-url <url>               Health endpoint to verify after cleanup. Default: http://127.0.0.1:8002/api/v1/health
  --builder-max-used-space <size>  Target builder cache cap for conservative mode. Default: 20gb
  --builder-reserved-space <size>  Reserved builder cache in conservative mode. Default: 5gb
  --image-until <value>            Retention filter for unused images in conservative mode. Default: 168h
  --log-file <path>                Append all output to a log file.
  -h, --help                       Show this help.
EOF
}

log() {
    printf '[%s] %s\n' "$(date -u +%FT%TZ)" "$*"
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        log "Required command missing: $cmd"
        exit 1
    fi
}

run_cmd() {
    log "+ $*"
    "$@"
}

APPLY=0
AGGRESSIVE=0
TARGET_DIR="/opt/noor"
HEALTH_URL="http://127.0.0.1:8002/api/v1/health"
BUILDER_MAX_USED_SPACE="20gb"
BUILDER_RESERVED_SPACE="5gb"
IMAGE_UNTIL="168h"
LOG_FILE=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply)
            APPLY=1
            shift
            ;;
        --aggressive)
            AGGRESSIVE=1
            shift
            ;;
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --health-url)
            HEALTH_URL="$2"
            shift 2
            ;;
        --builder-max-used-space)
            BUILDER_MAX_USED_SPACE="$2"
            shift 2
            ;;
        --builder-reserved-space)
            BUILDER_RESERVED_SPACE="$2"
            shift 2
            ;;
        --image-until)
            IMAGE_UNTIL="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [ -n "$LOG_FILE" ]; then
    mkdir -p "$(dirname "$LOG_FILE")"
    exec > >(tee -a "$LOG_FILE") 2>&1
fi

for cmd in docker df; do
    require_cmd "$cmd"
done

log "Docker maintenance start"
log "Runtime directory: $TARGET_DIR"
log "Mode: $( [ "$APPLY" -eq 1 ] && echo apply || echo dry-run )"
log "Aggressive: $( [ "$AGGRESSIVE" -eq 1 ] && echo yes || echo no )"

log "Filesystem usage before cleanup:"
run_cmd df -h /

log "Docker usage before cleanup:"
run_cmd docker system df

BUILDER_CMD=(docker builder prune --force --all)
IMAGE_CMD=(docker image prune --force --all)

if [ "$AGGRESSIVE" -eq 0 ]; then
    BUILDER_CMD+=(--max-used-space "$BUILDER_MAX_USED_SPACE" --reserved-space "$BUILDER_RESERVED_SPACE")
    IMAGE_CMD+=(--filter "until=$IMAGE_UNTIL")
fi

if [ "$APPLY" -eq 0 ]; then
    log "Dry-run only. Planned commands:"
    log "+ ${BUILDER_CMD[*]}"
    log "+ ${IMAGE_CMD[*]}"
    exit 0
fi

run_cmd "${BUILDER_CMD[@]}"
run_cmd "${IMAGE_CMD[@]}"

log "Docker usage after cleanup:"
run_cmd docker system df

log "Filesystem usage after cleanup:"
run_cmd df -h /

if command -v curl >/dev/null 2>&1; then
    log "Verifying health endpoint"
    run_cmd curl --fail --silent --show-error "$HEALTH_URL"
    printf '\n'
fi

log "Docker maintenance complete"
