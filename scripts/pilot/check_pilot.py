#!/usr/bin/env python3
"""Cross-platform (Windows Native + Linux/WSL) 2-hour live-pilot monitor for Treejar Noor."""

from __future__ import annotations

import contextlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
MSK_TZ = timezone(timedelta(hours=3), name="MSK")

REMOTE_SCRIPT = r"""set -euo pipefail
WATERMARK_UTC="$1"
LOG_SINCE="$2"
PILOT_PAUSED="$3"

echo ""
echo "--- [1] HEALTH & CONTAINERS ---"
curl -sS -w '\nHTTP_STATUS:%{http_code}\n' http://127.0.0.1:8002/api/v1/health || echo "HEALTH_UNREACHABLE"
docker ps -a --filter "name=noor-" --format "{{.Names}}\t{{.Status}}"
if [ -f /opt/noor/ops/live-pilot-worker.enabled ]; then
  if [ "$PILOT_PAUSED" = "true" ]; then
    echo "live-pilot-worker.enabled: PRESENT (UNEXPECTED WHILE PAUSED!)"
  else
    echo "live-pilot-worker.enabled: PRESENT"
  fi
else
  if [ "$PILOT_PAUSED" = "true" ]; then
    echo "live-pilot-worker.enabled: ABSENT (EXPECTED — PILOT INTENTIONALLY PAUSED)"
  else
    echo "live-pilot-worker.enabled: MISSING (ALERT!)"
  fi
fi

echo ""
echo "--- [1B] CANONICAL KB SYNC CHECK ---"
docker exec -i noor-app-1 python3 - <<'PY'
import asyncio
from src.core.database import async_session_factory
from src.services.canonical_admin_seed import preview_canonical_knowledge_base

async def main() -> None:
    async with async_session_factory() as db:
        p = await preview_canonical_knowledge_base(db)
        outdated = getattr(p, "will_update", 0)
        if p.will_create > 0 or outdated > 0 or p.unindexed > 0:
            affected = [i.title for i in p.items if i.status in ("missing", "outdated", "unindexed")]
            print(
                f"ALERT: KB_SYNC_DRIFT | total_templates={p.total_templates} "
                f"| will_create={p.will_create} | will_update={outdated} "
                f"| unindexed={p.unindexed} | affected={affected}"
            )
        else:
            active_cnt = p.unchanged + p.customized
            print(
                f"KB_SYNC_STATUS: OK ({active_cnt}/{p.total_templates} active, "
                f"customized={p.customized}, deleted={p.deleted_or_archived})"
            )

asyncio.run(main())
PY

echo ""
echo "--- [2] ROUTER TRAFFIC (noor-nginx-1 last $LOG_SINCE) ---"
NGINX_WAZZUP="$(docker logs --since "$LOG_SINCE" noor-nginx-1 2>&1 | grep 'webhook/wazzup' || true)"
HTTPX_401_COUNT="$(printf '%s\n' "$NGINX_WAZZUP" | grep -c '" 401 .* "python-httpx/' || true)"
echo "Ignored duplicate stream (python-httpx 401): $HTTPX_401_COUNT"
echo "Client router (POST + node UA / 200) or non-scanner webhook requests:"
printf '%s\n' "$NGINX_WAZZUP" | grep -v '" 401 .* "python-httpx/' | grep -v '"GET /api/v1/webhook/wazzup .* 404 ' | grep -v '^$' || echo "(none)"

echo ""
echo "--- [2B] ODD-DAY ROUTER BLACKOUT & STICKY-LEAD BYPASS WATCHDOG ---"
PILOT_CHANNEL_ID="$(docker exec noor-app-1 python3 -c 'from src.core.config import settings; print(settings.wazzup_channel_id or "")')"
docker exec -i noor-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v pilot_paused="$1" -v watermark="$2" -v pilot_channel_id="$3" -P pager=off' -- "$PILOT_PAUSED" "$WATERMARK_UTC" "$PILOT_CHANNEL_ID" <<'SQL'
WITH msk_bounds AS (
  SELECT
    to_char(now() AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD') AS msk_date,
    (extract(day from now() AT TIME ZONE 'Europe/Moscow')::int % 2 = 1) AS is_odd_msk_day,
    ((date_trunc('day', now() AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'Europe/Moscow') AT TIME ZONE 'UTC') AS msk_day_start_utc
),
shadow_today AS (
  SELECT
    count(*) FILTER (WHERE NOT s.is_echo) AS shadow_inbound_msgs,
    count(DISTINCT regexp_replace(s.chat_id, '[^0-9]', '', 'g')) FILTER (WHERE NOT s.is_echo) AS shadow_inbound_chats,
    string_agg(DISTINCT '*' || right(regexp_replace(s.chat_id, '[^0-9]', '', 'g'), 4), ', ') FILTER (WHERE NOT s.is_echo) AS leaked_masks
  FROM shadow_webhook_events s
  CROSS JOIN msk_bounds b
  WHERE s.created_at >= b.msk_day_start_utc
    AND s.channel_id = :'pilot_channel_id'
    AND s.chat_type = 'whatsapp'
    AND s.message_type IS DISTINCT FROM 'missing_call'
    AND right(regexp_replace(s.chat_id, '[^0-9]', '', 'g'), 8) <> '551220665'
),
noor_today AS (
  SELECT
    count(*) FILTER (WHERE m.role = 'user') AS noor_inbound_msgs,
    count(DISTINCT m.conversation_id) FILTER (WHERE m.role = 'user') AS noor_inbound_chats,
    (SELECT max(m2.created_at) FROM messages m2 JOIN conversations c2 ON c2.id = m2.conversation_id WHERE m2.role = 'user' AND right(regexp_replace(c2.phone, '[^0-9]', '', 'g'), 8) <> '551220665') AS last_noor_inbound_utc
  FROM messages m
  JOIN conversations c ON c.id = m.conversation_id
  CROSS JOIN msk_bounds b
  WHERE m.created_at >= b.msk_day_start_utc
    AND right(regexp_replace(c.phone, '[^0-9]', '', 'g'), 8) <> '551220665'
)
SELECT
  CASE
    WHEN b.is_odd_msk_day AND :'pilot_paused' <> 'true' AND st.shadow_inbound_msgs > 0 AND nt.noor_inbound_msgs = 0
      THEN 'ALERT: ODD_DAY_ROUTER_BLACKOUT'
    ELSE 'OK'
  END AS router_status,
  b.msk_date,
  b.is_odd_msk_day,
  st.shadow_inbound_chats,
  st.shadow_inbound_msgs,
  nt.noor_inbound_chats,
  nt.noor_inbound_msgs,
  nt.last_noor_inbound_utc,
  coalesce(st.leaked_masks, '-') AS shadow_inbound_masks_today
FROM msk_bounds b
CROSS JOIN shadow_today st
CROSS JOIN noor_today nt;

\echo ''
\echo '--- STICKY NOOR CHATS BYPASSING ROUTER IN SHADOW STREAM (LAST 72H) ---'
WITH pilot_convs AS (
  SELECT c.id,
         c.phone,
         regexp_replace(c.phone, '[^0-9]', '', 'g') AS norm_phone,
         '*' || right(regexp_replace(c.phone, '[^0-9]', '', 'g'), 4) AS chat_ref,
         c.escalation_status,
         c.created_at AS conv_created_utc
  FROM conversations c
  WHERE c.created_at >= TIMESTAMP '2026-11-05 00:00:00'
    AND right(regexp_replace(c.phone, '[^0-9]', '', 'g'), 8) <> '551220665'
),
bypassed AS (
  SELECT pc.chat_ref,
         pc.id AS conv_id,
         pc.escalation_status,
         s.created_at AS shadow_utc,
         coalesce(s.message_type, 'text') AS msg_type,
         left(replace(coalesce(s.text, s.content_uri, ''), E'\n', ' '), 120) AS shadow_preview
  FROM shadow_webhook_events s
  JOIN pilot_convs pc
    ON pc.norm_phone = regexp_replace(s.chat_id, '[^0-9]', '', 'g')
  WHERE NOT s.is_echo
    AND s.channel_id = :'pilot_channel_id'
    AND s.chat_type = 'whatsapp'
    -- Noor intentionally ignores Wazzup missed-call notices at ingestion.
    AND s.message_type IS DISTINCT FROM 'missing_call'
    AND s.created_at >= (now() AT TIME ZONE 'UTC') - interval '72 hours'
    -- Noor stores the message only after batching, media reads, and the first-turn
    -- manager grace period. Wait before treating a shadow event as unmatched.
    AND s.created_at <= (now() AT TIME ZONE 'UTC') - interval '10 minutes'
    AND s.created_at >= pc.conv_created_utc
    AND NOT EXISTS (
      SELECT 1 FROM messages m
      WHERE m.wazzup_message_id = s.message_id
        AND m.role = 'user'
    )
)
SELECT 'ALERT: STICKY_NOOR_CHAT_BYPASSED_ROUTER' AS alert_type,
       chat_ref,
       conv_id,
       escalation_status,
       count(*) AS bypassed_msgs_72h,
       min(shadow_utc) AS first_bypass_utc,
       max(shadow_utc) AS last_bypass_utc,
       max(shadow_preview) AS sample_preview
FROM bypassed
GROUP BY chat_ref, conv_id, escalation_status
ORDER BY max(shadow_utc) DESC;

\echo ''
\echo '--- FIRST-SEEN ODD-DAY WHATSAPP CHATS MISSING FROM NOOR ---'
WITH recent_openings AS (
  SELECT DISTINCT ON (s.chat_id)
         s.chat_id, s.channel_id, s.created_at, s.message_id
  FROM shadow_webhook_events s
  WHERE :'pilot_paused' <> 'true'
    AND s.channel_id = :'pilot_channel_id'
    AND s.chat_type = 'whatsapp'
    AND NOT s.is_echo
    AND s.message_type IS DISTINCT FROM 'missing_call'
    AND right(regexp_replace(s.chat_id, '[^0-9]', '', 'g'), 8) <> '551220665'
    -- Include the previous run's grace window so advancing the watermark
    -- cannot skip an opening that was still waiting for ingestion.
    AND s.created_at > :'watermark'::timestamp - interval '10 minutes'
    AND s.created_at <= (now() AT TIME ZONE 'UTC') - interval '10 minutes'
  ORDER BY s.chat_id, s.created_at, s.message_id
)
SELECT 'ALERT: ODD_DAY_NEW_CHAT_MISSING_NOOR' AS alert_type,
       '*' || right(regexp_replace(r.chat_id, '[^0-9]', '', 'g'), 4) AS chat_ref,
       r.created_at AS first_shadow_utc
FROM recent_openings r
WHERE extract(day FROM r.created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Moscow')::int % 2 = 1
  AND NOT EXISTS (
    SELECT 1 FROM shadow_webhook_events older
    WHERE older.chat_id = r.chat_id AND older.channel_id = r.channel_id
      AND older.chat_type = 'whatsapp'
      AND NOT older.is_echo
      AND older.message_type IS DISTINCT FROM 'missing_call'
      AND older.created_at < r.created_at
  )
  AND NOT EXISTS (
    SELECT 1 FROM conversations c
    WHERE regexp_replace(c.phone, '[^0-9]', '', 'g') = regexp_replace(r.chat_id, '[^0-9]', '', 'g')
      AND c.metadata->>'inbound_channel_id' = r.channel_id
  )
  AND NOT EXISTS (
    SELECT 1 FROM messages m WHERE m.wazzup_message_id = r.message_id AND m.role = 'user'
  )
ORDER BY r.created_at;
SQL

echo ""
echo "--- [3] POSTGRES SUMMARY & NEW ACTIVITY SINCE $WATERMARK_UTC ---"
docker exec -i noor-db-1 sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v watermark="$1" -P pager=off' -- "$WATERMARK_UTC" <<'SQL'
SELECT 'conversations' AS tbl, count(*) AS total, max(updated_at) AS latest_utc,
       count(*) FILTER (WHERE updated_at > :'watermark'::timestamp) AS since_watermark
FROM conversations
UNION ALL
SELECT 'messages', count(*), max(created_at),
       count(*) FILTER (WHERE created_at > :'watermark'::timestamp)
FROM messages
UNION ALL
SELECT 'escalations', count(*), max(created_at),
       count(*) FILTER (WHERE created_at > :'watermark'::timestamp)
FROM escalations
UNION ALL
SELECT 'outbound_message_audits', count(*), max(created_at),
       count(*) FILTER (WHERE created_at > :'watermark'::timestamp)
FROM outbound_message_audits;

\echo ''
\echo '--- ACTIVE CONVERSATIONS SINCE WATERMARK ---'
WITH active_convs AS (
  SELECT DISTINCT id FROM conversations WHERE updated_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM messages WHERE created_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM escalations WHERE created_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM outbound_message_audits WHERE created_at > :'watermark'::timestamp
)
SELECT c.id,
       '*' || right(c.phone, 4) AS chat_ref,
       c.language,
       c.sales_stage,
       c.status,
       c.escalation_status,
       (c.zoho_contact_id IS NOT NULL) AS has_contact,
       (c.zoho_deal_id IS NOT NULL) AS has_deal,
       c.deal_amount,
       c.created_at,
       c.updated_at
FROM conversations c
JOIN active_convs ac ON ac.id = c.id
ORDER BY c.updated_at ASC;

\echo ''
\echo '--- END-TO-END TRANSCRIPTS FOR ACTIVE CONVERSATIONS ---'
\pset format unaligned
\pset fieldsep ' | '
WITH active_convs AS (
  SELECT DISTINCT id FROM conversations WHERE updated_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM messages WHERE created_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM escalations WHERE created_at > :'watermark'::timestamp
  UNION
  SELECT DISTINCT conversation_id FROM outbound_message_audits WHERE created_at > :'watermark'::timestamp
)
SELECT '*' || right(c.phone, 4) AS chat_ref,
       c.id AS conv_id,
       m.created_at AS msg_utc,
       m.role,
       m.message_type,
       coalesce(m.model, '-') AS model,
       replace(m.content, E'\n', ' \n ') AS content,
       replace(coalesce(m.transcription, ''), E'\n', ' ') AS transcription
FROM messages m
JOIN conversations c ON c.id = m.conversation_id
JOIN active_convs ac ON ac.id = c.id
ORDER BY c.updated_at ASC, m.created_at ASC;

\pset format aligned
\echo ''
\echo '--- ESCALATIONS SINCE WATERMARK ---'
SELECT '*' || right(c.phone, 4) AS chat_ref,
       e.conversation_id,
       e.created_at,
       e.status,
       e.reason,
       left(coalesce(e.notes, ''), 200) AS notes
FROM escalations e
JOIN conversations c ON c.id = e.conversation_id
WHERE e.created_at > :'watermark'::timestamp
ORDER BY e.created_at ASC;

\echo ''
\echo '--- OUTBOUND MESSAGE AUDITS SINCE WATERMARK ---'
SELECT '*' || right(c.phone, 4) AS chat_ref,
       o.conversation_id,
       o.created_at,
       o.message_type,
       o.source,
       o.status,
       coalesce(o.file_name, '') AS file_name,
       left(coalesce(o.content, o.caption, ''), 160) AS preview,
       coalesce(o.error_details::text, '') AS error_details
FROM outbound_message_audits o
JOIN conversations c ON c.id = o.conversation_id
WHERE o.created_at > :'watermark'::timestamp
ORDER BY o.created_at ASC;

\echo ''
\echo '--- [3B] STUCK / HANGING CONVERSATION WATCHDOG (LAST 72H) ---'
WITH recent_convs AS (
  SELECT c.*
  FROM conversations c
  WHERE c.updated_at > (now() AT TIME ZONE 'utc') - interval '72 hours'
    AND right(regexp_replace(c.phone, '\D', '', 'g'), 8) <> '551220665'
),
last_msg AS (
  SELECT DISTINCT ON (m.conversation_id)
         m.conversation_id,
         m.role AS last_role,
         m.created_at AS last_msg_utc,
         left(replace(m.content, E'\n', ' '), 120) AS last_preview
  FROM messages m
  JOIN recent_convs rc ON rc.id = m.conversation_id
  ORDER BY m.conversation_id, m.created_at DESC
),
conv_stats AS (
  SELECT rc.id,
         '*' || right(rc.phone, 4) AS chat_ref,
         rc.customer_name,
         rc.escalation_status,
         rc.zoho_contact_id,
         rc.zoho_deal_id,
         rc.deal_amount,
         rc.metadata->'order_runtime'->'quote_workflow'->>'lifecycle' AS quote_lifecycle,
         lm.last_role,
         lm.last_msg_utc,
         lm.last_preview,
         (SELECT count(*) FROM escalations e WHERE e.conversation_id = rc.id) AS esc_cnt,
         (SELECT max(e.created_at) FROM escalations e WHERE e.conversation_id = rc.id AND e.status = 'pending') AS pending_esc_utc,
         (SELECT count(*) FROM messages m WHERE m.conversation_id = rc.id AND m.role = 'manager') AS mgr_cnt,
         (SELECT max(m.created_at) FROM messages m WHERE m.conversation_id = rc.id AND m.role = 'manager') AS last_mgr_utc,
         EXISTS (
           SELECT 1 FROM outbound_message_audits o
           WHERE o.conversation_id = rc.id AND o.file_name ILIKE 'Quotation-%'
         ) AS has_quote_pdf,
         EXISTS (
           SELECT 1 FROM messages m
           WHERE m.conversation_id = rc.id
             AND m.role = 'assistant'
             AND m.content ~* '((i(''|’)ll|i will|we(''|’)ll|we will|let me)\s+(check|confirm|verify|ask)|team\s+will\s+(check|confirm|verify|contact|reach\s+out)|remain\s+unconfirmed|need(s)?\s+confirmation)'
         ) AS has_team_promise
  FROM recent_convs rc
  LEFT JOIN last_msg lm ON lm.conversation_id = rc.id
)
SELECT chat_ref,
       id AS conv_id,
       coalesce(customer_name, '-') AS customer,
       escalation_status,
       array_remove(ARRAY[
         CASE WHEN last_role = 'user'
               AND last_msg_utc < (now() AT TIME ZONE 'utc') - interval '3 minutes'
               AND escalation_status = 'none'
               AND mgr_cnt = 0
              THEN 'unanswered_inbound_gt_3m' END,
         CASE WHEN (quote_lifecycle = 'created' OR has_quote_pdf)
               AND (zoho_contact_id IS NULL OR zoho_deal_id IS NULL)
              THEN 'quote_missing_crm_contact_or_deal' END,
         CASE WHEN mgr_cnt > 0
               AND escalation_status NOT IN ('manual_takeover', 'resolved')
              THEN 'manager_replied_without_takeover' END,
         CASE WHEN has_team_promise
               AND escalation_status = 'none'
               AND esc_cnt = 0
               AND mgr_cnt = 0
              THEN 'unescalated_team_promise' END,
         CASE WHEN escalation_status IN ('pending', 'in_progress')
               AND pending_esc_utc IS NOT NULL
               AND pending_esc_utc < (now() AT TIME ZONE 'utc') - interval '60 minutes'
               AND (last_mgr_utc IS NULL OR last_mgr_utc < pending_esc_utc)
              THEN 'pending_escalation_unanswered_gt_60m' END,
         CASE WHEN escalation_status = 'manual_takeover'
               AND last_role = 'user'
               AND last_msg_utc < (now() AT TIME ZONE 'utc') - interval '30 minutes'
               AND (last_mgr_utc IS NULL OR last_mgr_utc < last_msg_utc - interval '4 hours')
              THEN 'stale_manual_takeover_unanswered_gt_4h' END
       ], NULL) AS hang_flags,
       last_role,
       last_msg_utc,
       last_preview
FROM conv_stats
WHERE (
  (last_role = 'user' AND last_msg_utc < (now() AT TIME ZONE 'utc') - interval '3 minutes' AND escalation_status = 'none' AND mgr_cnt = 0)
  OR ((quote_lifecycle = 'created' OR has_quote_pdf) AND (zoho_contact_id IS NULL OR zoho_deal_id IS NULL))
  OR (mgr_cnt > 0 AND escalation_status NOT IN ('manual_takeover', 'resolved'))
  OR (has_team_promise AND escalation_status = 'none' AND esc_cnt = 0 AND mgr_cnt = 0)
  OR (escalation_status IN ('pending', 'in_progress') AND pending_esc_utc IS NOT NULL AND pending_esc_utc < (now() AT TIME ZONE 'utc') - interval '60 minutes' AND (last_mgr_utc IS NULL OR last_mgr_utc < pending_esc_utc))
  OR (escalation_status = 'manual_takeover' AND last_role = 'user' AND last_msg_utc < (now() AT TIME ZONE 'utc') - interval '30 minutes' AND (last_mgr_utc IS NULL OR last_mgr_utc < last_msg_utc - interval '4 hours'))
)
ORDER BY last_msg_utc DESC;
SQL

echo ""
echo "--- [3C] REDIS INBOUND QUEUE & QUARANTINE WATCHDOG ---"
INBOUND_PREFIXES="$(docker exec noor-app-1 python3 -c '
from src.services.chat import INBOUND_BATCH_QUARANTINE_PREFIX
from src.services.inbound_batch import inbound_processing_key, inbound_queue_key
print(inbound_queue_key(""), inbound_processing_key(""), INBOUND_BATCH_QUARANTINE_PREFIX)
')"
read -r INBOUND_QUEUE_PREFIX INBOUND_PROCESSING_PREFIX INBOUND_QUARANTINE_PREFIX <<< "$INBOUND_PREFIXES"
docker exec noor-redis-1 sh -ec '
  echo "[Active inbound queues]:"
  redis-cli --scan --pattern "$1*" | head -n 20
  echo "[In-flight inbound batches]:"
  redis-cli --scan --pattern "$2*" | head -n 20
  echo "[Quarantined inbound batches]:"
  quarantined="$(redis-cli --scan --pattern "$3*" | head -n 20)"
  if [ -n "$quarantined" ]; then
    printf "%s\n" "$quarantined" "ALERT: INBOUND_BATCH_QUARANTINED"
  fi
' -- "${INBOUND_QUEUE_PREFIX:?}" "${INBOUND_PROCESSING_PREFIX:?}" "${INBOUND_QUARANTINE_PREFIX:?}"

echo ""
echo "--- [4] WORKER MEDIA, ATTACHMENTS, AND SERVICE LOGS (last $LOG_SINCE) ---"
echo "[Media & attachment signals in noor-worker-1]:"
docker logs --since "$LOG_SINCE" noor-worker-1 2>&1 | grep -E "Customer attachment has no downloadable URL|\[The customer sent|media_reader|inbound_media" || echo "(none)"

echo "[Errors / tracebacks in noor-worker-1]:"
docker logs --since "$LOG_SINCE" noor-worker-1 2>&1 | grep -Ei "traceback|exception|\bERROR\b|\bCRITICAL\b" | grep -v "Errors: 0" || echo "(none)"

echo "[Errors / tracebacks in noor-app-1]:"
docker logs --since "$LOG_SINCE" noor-app-1 2>&1 | grep -Ei "traceback|exception|\bERROR\b|\bCRITICAL\b| 50[0-9] " || echo "(none)"

echo ""
echo "--- [5] OPENROUTER CREDIT ---"
docker exec -i noor-app-1 python3 - <<'PY'
import json, urllib.request
from src.core.config import settings
raw = settings.openrouter_api_key
key = raw.get_secret_value() if hasattr(raw, "get_secret_value") else str(raw)
req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": f"Bearer {key}"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())["data"]
    print(json.dumps({
        "limit": data.get("limit"),
        "limit_remaining": round(float(data.get("limit_remaining") or 0), 4),
        "usage": round(float(data.get("usage") or 0), 4),
        "usage_daily": round(float(data.get("usage_daily") or 0), 4),
    }))
PY
"""


def candidate_state_paths() -> list[pathlib.Path]:
    home = pathlib.Path.home()
    return [
        REPO_ROOT / ".codex" / "pilot-state" / "pilot_state.json",
        home
        / ".codex"
        / "automations"
        / "treejar-noor-pilot-monitor"
        / "pilot_state.json",
        home
        / ".gemini"
        / "config"
        / "sidecars"
        / "treejar-noor-pilot-monitor"
        / "pilot_state.json",
    ]


def load_state() -> tuple[dict[str, object], list[pathlib.Path]]:
    paths = candidate_state_paths()
    existing = [p for p in paths if p.exists()]
    best_state: dict[str, object] | None = None
    best_ts = ""
    for p in existing:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            ts = str(data.get("last_run_utc", ""))
            if best_state is None or ts >= best_ts:
                best_state = data
                best_ts = ts
        except Exception:
            continue
    if best_state is None:
        best_state = {
            "watermark_utc": "2026-11-17T19:00:29",
            "last_run_utc": "2026-11-17T19:00:29Z",
            "expected_release_sha": "e8783cdc0b693c2994c581cf715ed16729274ed7",
            "pilot_paused": False,
            "pilot_paused_reason": "",
            "last_openrouter_remaining_usd": 7.5065,
            "router_traffic_seen": True,
            "last_router_blackout_alert_date_msk": "2026-11-17",
            "last_leaked_shadow_chats": 14,
            "notes": "",
        }
    return best_state, paths


def save_state(state: dict[str, object], paths: list[pathlib.Path]) -> None:
    payload = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    primary = paths[0]
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(payload, encoding="utf-8")
    for p in paths[1:]:
        if p.parent.exists():
            with contextlib.suppress(OSError):
                p.write_text(payload, encoding="utf-8")


@contextlib.contextmanager
def single_instance_lock(name: str) -> Iterator[bool]:
    lock_path = pathlib.Path(tempfile.gettempdir()) / name
    with lock_path.open("a+", encoding="utf-8") as fh:
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    acquired = False
            else:
                import fcntl

                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError:
                    acquired = False
            yield acquired
        finally:
            with contextlib.suppress(Exception):
                if acquired:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def resolve_ssh_command() -> list[str]:
    ssh_bin = shutil.which("ssh") or "ssh"
    home = pathlib.Path.home()
    key_candidates = [
        home / ".ssh" / "treejar_vps",
        REPO_ROOT.parent / ".treejar-tools" / "ssh" / "treejar_vps",
        REPO_ROOT / ".tmp" / "ssh" / "treejar_vps",
        home / "Treejar-Windows-Laptop-20261118" / "ssh" / "treejar_vps",
    ]
    ssh_config = home / ".ssh" / "config"
    has_alias = False
    if ssh_config.exists():
        with contextlib.suppress(OSError):
            has_alias = "Host noor-server" in ssh_config.read_text(encoding="utf-8")
    if has_alias:
        return [ssh_bin, "noor-server"]
    for key_path in key_candidates:
        if key_path.exists():
            return [
                ssh_bin,
                "-p",
                "2222",
                "-i",
                str(key_path),
                "-o",
                "IdentitiesOnly=yes",
                "-o",
                "StrictHostKeyChecking=no",
                "noor-dev@95.216.204.189",
            ]
    return [ssh_bin, "noor-server"]


def parse_utc(ts: str) -> datetime:
    cleaned = ts.strip().replace("Z", "+00:00").replace(" ", "T")
    dt = datetime.fromisoformat(cleaned)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def main() -> int:
    args = list(sys.argv[1:])
    scheduled_mode = False
    if args and args[0] == "--scheduled":
        scheduled_mode = True
        args.pop(0)

    with single_instance_lock("treejar-noor-pilot-monitor.lock") as locked:
        if not locked:
            print(
                "=== ANOTHER PILOT MONITOR CHECK IS CURRENTLY RUNNING — SKIPPING DUPLICATE ==="
            )
            return 0

        state, state_paths = load_state()
        prev_last_run_utc = str(state.get("last_run_utc", "2026-11-17T19:00:29Z"))
        now_utc = datetime.now(UTC)

        if scheduled_mode:
            try:
                last_dt = parse_utc(prev_last_run_utc)
                mins = (now_utc - last_dt).total_seconds() / 60.0
                if mins < 45.0:
                    print(
                        f"=== ALREADY CHECKED IN THIS SLOT AT {prev_last_run_utc} ({mins:.1f}m ago) — SKIPPING DUPLICATE ==="
                    )
                    return 0
            except Exception:
                pass
            state["last_run_utc"] = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
            save_state(state, state_paths)

        watermark_utc = (
            args[0]
            if len(args) >= 1
            else str(state.get("watermark_utc", "2026-11-17T19:00:29"))
        ).replace(" ", "T")

        if len(args) >= 2:
            log_since = args[1]
        else:
            try:
                last_dt = parse_utc(prev_last_run_utc)
                mins_since = int((now_utc - last_dt).total_seconds() // 60) + 15
                log_since = f"{max(135, mins_since)}m"
            except Exception:
                log_since = "135m"

        pilot_paused = "true" if state.get("pilot_paused") else "false"
        pilot_paused_reason = str(state.get("pilot_paused_reason", ""))

        now_utc_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        now_msk_str = now_utc.astimezone(MSK_TZ).strftime("%Y-%m-%d %H:%M:%S MSK")
        print(f"=== PILOT MONITOR RUN: {now_utc_str} (MSK: {now_msk_str}) ===")
        print(
            f"=== WATERMARK_UTC: {watermark_utc} | LOG_SINCE: {log_since} | PILOT_PAUSED: {pilot_paused} ==="
        )
        if pilot_paused == "true":
            print(f"=== INTENTIONAL PAUSE ACTIVE: {pilot_paused_reason} ===")
            print(
                "=== DO NOT RESTART noor-worker-1 OR ENABLE bot_enabled WITHOUT EXPLICIT OWNER AUTHORIZATION ==="
            )

        ssh_cmd = [
            *resolve_ssh_command(),
            "bash",
            "-s",
            "--",
            watermark_utc,
            log_since,
            pilot_paused,
        ]
        script_bytes = REMOTE_SCRIPT.replace("\r\n", "\n").encode("utf-8")
        proc = subprocess.run(ssh_cmd, input=script_bytes, check=False)
        return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
