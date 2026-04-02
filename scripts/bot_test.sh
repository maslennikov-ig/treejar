#!/usr/bin/env bash
# bot_test.sh - Send a single message to the bot webhook and poll for reply
#
# Usage:
#   ./scripts/bot_test.sh [OPTIONS] "Your message here"
#
# Options:
#   -p, --phone PHONE    Chat phone number (default: +70000000099)
#   -u, --url URL        Base URL (default: https://noor.starec.ai)
#   -a, --author TYPE    Author type: client|manager|bot (default: client)
#   -w, --wait SECS      Seconds to wait for bot reply (default: 20)
#   -h, --help           Show this help
#
# Example:
#   ./scripts/bot_test.sh "Hello, I need office chairs"
#   ./scripts/bot_test.sh -p +70000000001 "What chairs do you have?"

set -euo pipefail

# Defaults
BASE_URL="${BOT_TEST_URL:-https://noor.starec.ai}"
PHONE="${BOT_TEST_PHONE:-+70000000099}"
AUTHOR_TYPE="client"
WAIT_SECS=20

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--phone)   PHONE="$2";       shift 2 ;;
        -u|--url)     BASE_URL="$2";    shift 2 ;;
        -a|--author)  AUTHOR_TYPE="$2"; shift 2 ;;
        -w|--wait)    WAIT_SECS="$2";   shift 2 ;;
        -h|--help)
            sed -n '2,15p' "$0"
            exit 0
            ;;
        -*) echo "Unknown option: $1" >&2; exit 1 ;;
        *)  MESSAGE="$1"; shift ;;
    esac
done

if [[ -z "${MESSAGE:-}" ]]; then
    echo "❌ Error: message text is required." >&2
    echo "Usage: $0 \"Your message here\"" >&2
    exit 1
fi

# Generate unique messageId
MSG_ID="test-$(date +%s)-$(head -c4 /dev/urandom | xxd -p)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🤖 Bot Test | $(date '+%H:%M:%S')"
echo "   URL:    $BASE_URL"
echo "   Phone:  $PHONE"
echo "   Author: $AUTHOR_TYPE"
echo "   Msg:    $MESSAGE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Send message to webhook
PAYLOAD=$(cat <<EOF
{
  "messages": [{
    "messageId": "$MSG_ID",
    "chatId": "$PHONE",
    "chatType": "whatsapp",
    "authorType": "$AUTHOR_TYPE",
    "text": "$MESSAGE",
    "dateTime": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "type": "text",
    "status": "inbound"
  }]
}
EOF
)

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "$BASE_URL/api/v1/webhook/wazzup" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")

if [[ "$HTTP_STATUS" != "200" ]]; then
    echo "❌ Webhook returned HTTP $HTTP_STATUS"
    exit 1
fi

echo "✅ Webhook accepted (HTTP 200)"
echo -n "⏳ Waiting ${WAIT_SECS}s for bot reply"

# 2. Poll for bot reply
for i in $(seq 1 "$WAIT_SECS"); do
    sleep 1
    echo -n "."

    # Get conversations for this phone
    CONV_RESP=$(curl -s "$BASE_URL/api/v1/conversations?phone=$PHONE&page_size=1")
    CONV_ID=$(echo "$CONV_RESP" | python3 -c "
import json, sys
data = json.load(sys.stdin)
items = data.get('items', [])
print(items[0]['id'] if items else '')
" 2>/dev/null || echo "")

    if [[ -z "$CONV_ID" ]]; then
        continue
    fi

    # Get messages and check for assistant reply after our msgId timestamp
    MSG_RESP=$(curl -s "$BASE_URL/api/v1/conversations/$CONV_ID")
    LAST_BOT=$(echo "$MSG_RESP" | python3 -c "
import json, sys
data = json.load(sys.stdin)
msgs = data.get('messages', [])
# Find last assistant message
for m in reversed(msgs):
    if m.get('role') == 'assistant':
        print(m.get('content', '')[:500])
        sys.exit(0)
print('')
" 2>/dev/null || echo "")

    if [[ -n "$LAST_BOT" ]]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🤖 Bot reply (conv=$CONV_ID):"
        echo ""
        echo "$LAST_BOT"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        exit 0
    fi
done

echo ""
echo "⚠️  No bot reply received in ${WAIT_SECS}s. Check worker logs."
echo "   Conv ID: $CONV_ID"
exit 1
