#!/usr/bin/env python3
"""Cross-platform (Windows Native + Linux/WSL) read-only collector for Nikita even-day shift QA reports."""

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

SQL_TEMPLATE = r"""\echo '=== 0. STICKY NOOR CHATS LEAKED TO NIKITA / SHADOW STREAM SINCE WATERMARK ==='
WITH pilot_convs AS (
    SELECT c.id,
           regexp_replace(c.phone, '[^0-9]', '', 'g') AS norm_phone,
           '*' || right(regexp_replace(c.phone, '[^0-9]', '', 'g'), 4) AS mask,
           c.escalation_status,
           c.created_at AS conv_created_utc
    FROM conversations c
    WHERE c.created_at >= TIMESTAMP '2026-11-05 00:00:00'
      AND regexp_replace(c.phone, '[^0-9]', '', 'g') != ''
      AND right(regexp_replace(c.phone, '[^0-9]', '', 'g'), 8) <> '551220665'
)
SELECT
    pc.mask,
    pc.id AS noor_conv_id,
    pc.escalation_status,
    min(s.created_at) AS first_leaked_utc,
    max(s.created_at) AS last_leaked_utc,
    count(*) FILTER (WHERE NOT s.is_echo) AS shadow_client_msgs,
    count(*) FILTER (WHERE s.is_echo) AS shadow_echo_msgs
FROM shadow_webhook_events s
JOIN pilot_convs pc ON pc.norm_phone = regexp_replace(s.chat_id, '[^0-9]', '', 'g')
WHERE s.created_at >= '__WATERMARK_UTC__'
  AND NOT EXISTS (
      SELECT 1 FROM messages m
      WHERE m.conversation_id = pc.id
        AND m.created_at BETWEEN s.created_at - interval '10 minutes' AND s.created_at + interval '10 minutes'
  )
GROUP BY pc.mask, pc.id, pc.escalation_status
ORDER BY min(s.created_at) ASC;

\echo ''
\echo '=== 0B. SHIFT BUCKET BREAKDOWN BY MOSCOW DATE (NON-NOOR SHADOW CHATS SINCE WATERMARK) ==='
WITH noor_phones AS (
    SELECT DISTINCT regexp_replace(phone, '[^0-9]', '', 'g') AS norm_phone
    FROM conversations
    WHERE regexp_replace(phone, '[^0-9]', '', 'g') != ''
),
chat_first_window AS (
    SELECT regexp_replace(s.chat_id, '[^0-9]', '', 'g') AS norm_chat,
           min(s.created_at) FILTER (WHERE s.created_at >= '__WATERMARK_UTC__') AS first_window_utc,
           count(*) FILTER (WHERE s.created_at >= '__WATERMARK_UTC__' AND NOT s.is_echo) AS client_msgs_window,
           count(*) FILTER (WHERE s.created_at >= '__WATERMARK_UTC__' AND s.is_echo) AS echo_msgs_window
    FROM shadow_webhook_events s
    WHERE NOT EXISTS (
        SELECT 1 FROM noor_phones np
        WHERE np.norm_phone = regexp_replace(s.chat_id, '[^0-9]', '', 'g')
    )
    GROUP BY regexp_replace(s.chat_id, '[^0-9]', '', 'g')
    HAVING count(*) FILTER (WHERE s.created_at >= '__WATERMARK_UTC__') > 0
)
SELECT
    to_char((first_window_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD') AS first_msk_date,
    CASE
        WHEN extract(day from (first_window_utc AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Moscow')::int % 2 = 0
            THEN 'EVEN_SCHEDULED'
        ELSE 'ODD_LEAKED_ROUTER_BLACKOUT'
    END AS shift_bucket,
    count(*) AS chats_count,
    sum(client_msgs_window) AS client_msgs,
    sum(echo_msgs_window) AS echo_msgs
FROM chat_first_window
GROUP BY 1, 2
ORDER BY 1 ASC;

\echo ''
\echo '=== 1. SHADOW EVENTS OVERVIEW SINCE WATERMARK (EXCLUDING NOOR CONVERSATIONS) ==='
WITH noor_phones AS (
    SELECT DISTINCT regexp_replace(phone, '[^0-9]', '', 'g') AS norm_phone
    FROM conversations
    WHERE regexp_replace(phone, '[^0-9]', '', 'g') != ''
),
nikita_events AS (
    SELECT s.*,
           regexp_replace(s.chat_id, '[^0-9]', '', 'g') AS norm_chat
    FROM shadow_webhook_events s
    WHERE NOT EXISTS (
        SELECT 1 FROM noor_phones np
        WHERE np.norm_phone = regexp_replace(s.chat_id, '[^0-9]', '', 'g')
    )
)
SELECT
    right(norm_chat, 4) AS mask,
    left(md5(norm_chat), 6) AS chat_ref,
    to_char((min(created_at) FILTER (WHERE created_at >= '__WATERMARK_UTC__') AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD') AS window_msk_date,
    CASE
        WHEN extract(day from (min(created_at) FILTER (WHERE created_at >= '__WATERMARK_UTC__') AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Moscow')::int % 2 = 0
            THEN 'EVEN_SCHEDULED'
        ELSE 'ODD_LEAKED_ROUTER_BLACKOUT'
    END AS shift_bucket,
    min(created_at) AS first_seen_utc,
    min(created_at) FILTER (WHERE created_at >= '__WATERMARK_UTC__') AS first_in_window_utc,
    max(created_at) AS last_seen_utc,
    count(*) FILTER (WHERE created_at >= '__WATERMARK_UTC__' AND NOT is_echo) AS client_msgs,
    count(*) FILTER (WHERE created_at >= '__WATERMARK_UTC__' AND is_echo) AS echo_msgs,
    count(*) FILTER (WHERE created_at >= '__WATERMARK_UTC__' AND status = 'error') AS error_msgs,
    count(*) FILTER (WHERE created_at >= '__WATERMARK_UTC__' AND message_type IS DISTINCT FROM 'text') AS media_msgs
FROM nikita_events
WHERE norm_chat IN (
    SELECT DISTINCT norm_chat FROM nikita_events WHERE created_at >= '__WATERMARK_UTC__'
)
GROUP BY norm_chat
ORDER BY min(created_at) FILTER (WHERE created_at >= '__WATERMARK_UTC__') ASC;

\echo ''
\echo '=== 2. FULL CHRONOLOGICAL DIALOGUE TRANSCRIPTS (NIKITA / NON-NOOR CHATS) ==='
WITH noor_phones AS (
    SELECT DISTINCT regexp_replace(phone, '[^0-9]', '', 'g') AS norm_phone
    FROM conversations
    WHERE regexp_replace(phone, '[^0-9]', '', 'g') != ''
),
nikita_events AS (
    SELECT s.*,
           regexp_replace(s.chat_id, '[^0-9]', '', 'g') AS norm_chat
    FROM shadow_webhook_events s
    WHERE NOT EXISTS (
        SELECT 1 FROM noor_phones np
        WHERE np.norm_phone = regexp_replace(s.chat_id, '[^0-9]', '', 'g')
    )
)
SELECT
    right(norm_chat, 4) AS mask,
    left(md5(norm_chat), 6) AS chat_ref,
    to_char((created_at AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Moscow', 'YYYY-MM-DD HH24:MI:SS') AS seen_msk,
    created_at AS seen_utc,
    provider_timestamp,
    is_echo,
    status,
    coalesce(author_type, '-') AS author_type,
    coalesce(author_name, '-') AS author_name,
    coalesce(message_type, 'text') AS msg_type,
    coalesce(content_uri, '') AS content_uri,
    replace(coalesce(text, ''), E'\n', ' \n ') AS text
FROM nikita_events
WHERE norm_chat IN (
    SELECT DISTINCT norm_chat FROM nikita_events WHERE created_at >= '__WATERMARK_UTC__'
)
ORDER BY norm_chat, created_at ASC;

\echo ''
\echo '=== 3. NOOR PRECEDING 48H LIVE BENCHMARK STATS (FOR CALM FACTUAL REFERENCE) ==='
SELECT
    count(DISTINCT c.id) AS noor_chats_48h,
    count(m.id) FILTER (WHERE m.role = 'user') AS noor_user_msgs_48h,
    count(m.id) FILTER (WHERE m.role = 'assistant') AS noor_bot_msgs_48h,
    count(m.id) FILTER (WHERE m.role = 'manager') AS noor_mgr_msgs_48h,
    count(m.id) FILTER (WHERE m.role = 'user' AND m.content LIKE '[The customer sent a %') AS noor_attachments_read_48h
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
WHERE c.created_at >= (NOW() AT TIME ZONE 'UTC') - INTERVAL '48 hours';
"""


def candidate_state_paths() -> list[pathlib.Path]:
    home = pathlib.Path.home()
    return [
        REPO_ROOT / ".codex" / "pilot-state" / "nikita_report_state.json",
        home
        / ".codex"
        / "automations"
        / "treejar-nikita-shift-report"
        / "nikita_report_state.json",
        home
        / ".gemini"
        / "config"
        / "sidecars"
        / "treejar-nikita-shift-report"
        / "nikita_report_state.json",
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
            "watermark_utc": "2026-11-17T07:00:15",
            "last_run_utc": "2026-11-17T07:00:29Z",
            "last_reported_shift_date_msk": "2026-11-16",
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


def main() -> int:
    scheduled = len(sys.argv) > 1 and sys.argv[1] == "--scheduled"

    with single_instance_lock("treejar-nikita-shift-report.lock") as locked:
        if not locked:
            print(
                "SKIPPING DUPLICATE: another Nikita shift report collector is currently running"
            )
            return 0

        now_utc = datetime.now(UTC)
        now_utc_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        now_msk = now_utc.astimezone(MSK_TZ)
        now_msk_str = now_msk.strftime("%Y-%m-%d %H:%M:%S MSK (day=%d)")

        state, state_paths = load_state()
        watermark_utc = str(state.get("watermark_utc", "2026-11-09T07:30:00"))
        last_run_utc = str(state.get("last_run_utc", "1970-01-01T00:00:00Z"))

        if scheduled:
            try:
                last_dt = datetime.fromisoformat(last_run_utc.replace("Z", "+00:00"))
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=UTC)
                age_min = (now_utc - last_dt).total_seconds() / 60.0
                if age_min < 60.0:
                    print(
                        f"SKIPPING DUPLICATE: last Nikita shift report ran at {last_run_utc} (now {now_utc_str})"
                    )
                    return 0
            except Exception:
                pass
            state["last_run_utc"] = now_utc_str
            save_state(state, state_paths)

        print("=== NIKITA SHIFT COLLECTOR ===")
        print(f"NOW_UTC: {now_utc_str}")
        print(f"NOW_MSK: {now_msk_str}")
        print(f"WATERMARK_UTC: {watermark_utc}")
        print()

        sql_text = SQL_TEMPLATE.replace("__WATERMARK_UTC__", watermark_utc).replace(
            "\r\n", "\n"
        )
        ssh_cmd = [
            *resolve_ssh_command(),
            'docker exec -i noor-db-1 sh -c \'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -P pager=off\'',
        ]
        proc = subprocess.run(
            ssh_cmd,
            input=sql_text.encode("utf-8"),
            check=False,
        )
        return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
