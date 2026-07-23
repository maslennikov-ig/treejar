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

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        printf 'Required command missing: %s\n' "$cmd" >&2
        exit 1
    fi
}

reject_cron_unsafe_value() {
    local name="$1"
    local value="$2"
    if [[ "$value" == *$'\n'* || "$value" == *$'\r'* || "$value" == *%* ]]; then
        printf '%s contains characters that are unsafe in crontab\n' "$name" >&2
        exit 1
    fi
}

shell_quote() {
    local value="$1"
    printf "'%s'" "${value//\'/\'\"\'\"\'}"
}

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

require_cmd crontab
reject_cron_unsafe_value "target directory" "$TARGET_DIR"
reject_cron_unsafe_value "log directory" "$LOG_DIR"
reject_cron_unsafe_value "schedule" "$SCHEDULE"
read -r -a SCHEDULE_FIELDS <<< "$SCHEDULE"
if [ "${#SCHEDULE_FIELDS[@]}" -ne 5 ]; then
    echo "Schedule must contain exactly five cron fields" >&2
    exit 1
fi
for field in "${SCHEDULE_FIELDS[@]}"; do
    if [[ ! "$field" =~ ^[A-Za-z0-9*/,-]+$ ]]; then
        echo "Schedule contains unsupported cron syntax" >&2
        exit 1
    fi
done

mkdir -p "$LOG_DIR"

if [ ! -x "$SCRIPT_PATH" ]; then
    echo "Expected executable maintenance script at $SCRIPT_PATH" >&2
    exit 1
fi

TARGET_DIR_QUOTED="$(shell_quote "$TARGET_DIR")"
SCRIPT_PATH_QUOTED="$(shell_quote "$SCRIPT_PATH")"
CRON_LOG_QUOTED="$(shell_quote "$CRON_LOG")"
CRON_STDOUT_QUOTED="$(shell_quote "$CRON_STDOUT")"
ENTRY="$SCHEDULE cd $TARGET_DIR_QUOTED && bash $SCRIPT_PATH_QUOTED --apply --log-file $CRON_LOG_QUOTED >> $CRON_STDOUT_QUOTED 2>&1"
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

INSTALLED_CRONTAB="$(crontab -l 2>/dev/null || true)"
BEGIN_COUNT="$(printf '%s\n' "$INSTALLED_CRONTAB" | grep -Fxc "$MARKER_BEGIN" || true)"
END_COUNT="$(printf '%s\n' "$INSTALLED_CRONTAB" | grep -Fxc "$MARKER_END" || true)"
ENTRY_COUNT="$(printf '%s\n' "$INSTALLED_CRONTAB" | grep -Fxc "$ENTRY" || true)"
if [ "$BEGIN_COUNT" -ne 1 ] || [ "$END_COUNT" -ne 1 ] || [ "$ENTRY_COUNT" -ne 1 ]; then
    printf '%s\n' "$CURRENT_CRONTAB" | crontab -
    echo "Cron readback verification failed; previous crontab restored" >&2
    exit 1
fi

printf 'Installed Docker maintenance cron: %s\n' "$ENTRY"
printf 'Verified Docker maintenance cron readback: one managed entry\n'
