#!/usr/bin/env bash
# Install or update a managed user crontab entry for Docker maintenance.

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  scripts/install-docker-maintenance-cron.sh [options]

Options:
  --target-dir <path>  Runtime directory containing the deployed scripts. Default: /opt/noor
  --schedule <expr>    Cron schedule. Default: 17 3 * * *
  --log-dir <path>     Maintenance log directory. Default: <target-dir>/logs/maintenance
  -h, --help           Show this help.
EOF
}

TARGET_DIR="/opt/noor"
SCHEDULE="17 3 * * *"
LOG_DIR=""
MARKER_BEGIN="# BEGIN treejar-docker-maintenance"
MARKER_END="# END treejar-docker-maintenance"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --target-dir)
            TARGET_DIR="$2"
            shift 2
            ;;
        --schedule)
            SCHEDULE="$2"
            shift 2
            ;;
        --log-dir)
            LOG_DIR="$2"
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

LOG_DIR="${LOG_DIR:-$TARGET_DIR/logs/maintenance}"
SCRIPT_PATH="$TARGET_DIR/scripts/docker-maintenance.sh"
CRON_LOG="$LOG_DIR/docker-maintenance.log"
CRON_STDOUT="$LOG_DIR/docker-maintenance.cron.log"

mkdir -p "$LOG_DIR"

if [ ! -f "$SCRIPT_PATH" ]; then
    echo "Expected deployed maintenance script at $SCRIPT_PATH" >&2
    exit 1
fi

ENTRY="$SCHEDULE cd '$TARGET_DIR' && bash '$SCRIPT_PATH' --apply --log-file '$CRON_LOG' >> '$CRON_STDOUT' 2>&1"
CURRENT_CRONTAB="$(crontab -l 2>/dev/null || true)"
FILTERED_CRONTAB="$(printf '%s\n' "$CURRENT_CRONTAB" | awk -v begin="$MARKER_BEGIN" -v end="$MARKER_END" '
    $0 == begin { skip=1; next }
    $0 == end { skip=0; next }
    skip != 1 { print }
')"

NEW_CRONTAB="$FILTERED_CRONTAB"
if [ -n "$NEW_CRONTAB" ]; then
    NEW_CRONTAB="${NEW_CRONTAB}"$'\n'
fi
NEW_CRONTAB+="$MARKER_BEGIN"$'\n'
NEW_CRONTAB+="$ENTRY"$'\n'
NEW_CRONTAB+="$MARKER_END"

printf '%s\n' "$NEW_CRONTAB" | crontab -

printf 'Installed Docker maintenance cron: %s\n' "$ENTRY"
