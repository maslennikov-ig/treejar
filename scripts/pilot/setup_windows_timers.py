#!/usr/bin/env python3
"""Cross-platform setup & timer registration for Treejar on Windows Native / Laptop."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

SSH_HOST_BLOCK = """
# TreeJar Production Server (new)
Host noor-server
    HostName 95.216.204.189
    Port 2222
    User noor-dev
    IdentityFile ~/.ssh/treejar_vps
    IdentitiesOnly yes
    StrictHostKeyChecking no
"""


def build_pilot_monitor_prompt(repo_root: pathlib.Path) -> str:
    repo = str(repo_root)
    return (
        f"Run the scheduled 2-hour live-pilot monitor check for Treejar Noor "
        f"(Beads `tj-r62i`, WhatsApp +971523209235, odd Moscow dates -> Noor via client router "
        f"`audit.treejartrading.ae`). Communicate user-facing summaries in Russian; write code, "
        f"commits, Beads notes, and handoff updates in English.\n\n"
        f"1. Read `{repo}/AGENTS.md`, `{repo}/.codex/orchestrator.toml`, `{repo}/.codex/handoff.md`, "
        f"and `{repo}/.codex/pilot-state/pilot_state.json`.\n"
        f'2. Execute `python "{repo}/scripts/pilot/check_pilot.py" --scheduled` (connects to `noor-server` via SSH). '
        f"If it outputs `SKIPPING DUPLICATE`, emit a one-line Russian note and finish immediately.\n"
        f"3. Inspect the output against `pilot_state.json`:\n"
        f"   - `[1B] CANONICAL KB SYNC CHECK`: if `ALERT: KB_SYNC_DRIFT` appears, immediately run "
        f'`sync_canonical_knowledge_base(db, mode="safe")` on `noor-worker-1` via `ssh noor-server`.\n'
        f"   - Router traffic (`node` UA + 200 = client router; `python-httpx` 401 = passive shadow mirror) "
        f"AND `[2B] ODD-DAY ROUTER BLACKOUT & STICKY-LEAD BYPASS WATCHDOG`:\n"
        f"     * NEVER output `✅ Прод в норме` or claim the pilot is nominal when `ALERT: ODD_DAY_ROUTER_BLACKOUT` "
        f"or `ALERT: STICKY_NOOR_CHAT_BYPASSED_ROUTER` is present! Track `last_router_blackout_alert_date_msk` and "
        f"`last_leaked_shadow_chats` in `pilot_state.json`: emit a clear Russian alert "
        f"`⚠️ Блэкаут клиентского роутера audit.treejartrading.ae` with leaked chat counts/masks on the first "
        f"detection of the day or when new leaked chats appear, and a concise 1-line "
        f"`⚠️ Роутер audit.treejartrading.ae всё ещё не пересылает нечётную смену в Noor (...)` tick on subsequent runs.\n"
        f"   - New conversations, messages, escalations, and `outbound_message_audits` in Postgres since `watermark_utc`.\n"
        f"   - `[3B] STUCK / HANGING CONVERSATION WATCHDOG` and `[3C] REDIS INBOUND QUEUE & QUARANTINE WATCHDOG`.\n"
        f"   - Read EVERY new or updated dialogue end-to-end like a senior sales reviewer: wrong or invented facts/prices/stock, "
        f"repeated questions, ignored attachments, missing product photos on offered items, double replies, missed 20+ unit handoffs, "
        f"unescalated deferred promises or open quotation closing terms, missing Zoho CRM Contact/Deal on issued quotations, "
        f"replies after a manager took over, off-topic personal chat, CRM name duplication, or language mismatch.\n"
        f"   - Errors/tracebacks in `noor-app-1` and `noor-worker-1`, `/api/v1/health` (`release_sha` vs `expected_release_sha`, "
        f"`live-pilot-worker.enabled` PRESENT), and OpenRouter credit remaining.\n"
        f"4. Standing Zero-Hang Prod Remediation Authority (granted by Igor on 2026-11-09 — NOTHING MAY HANG UNATTENDED):\n"
        f"   - Whenever `[3B]`/`[3C]` or transcript review reveals a live conversation hanging in prod, remediate it IMMEDIATELY "
        f"on prod via `ssh noor-server` (`docker exec -i noor-worker-1 python3 -` or Postgres update): trigger "
        f"`notify_manager_escalation`, run `_ensure_crm_opportunity_for_quotation`, set `escalation_status = 'manual_takeover'` "
        f"if a manager already replied, or re-enqueue a stuck inbound turn.\n"
        f"5. Fundamental Root-Cause Engineering (granted by Igor on 2026-11-08 & 2026-11-09):\n"
        f'   - Fix every code/prompt/dialogue defect FUNDAMENTALLY (`prose_guards_mode = "trust_model"` on `anthropic/claude-sonnet-5.5` '
        f"— NEVER add hardcoded regexes to `non_sales_intent.py` or regex prose mutators).\n"
        f"   - Bundle `.codex/handoff.md` + `repin_traceability_sources.py` in the same commit, pass quality gates, push `main`, "
        f"watch GitHub Actions CI + Deploy (`gh run watch`), verify live `/api/v1/health` `release_sha == git rev-parse HEAD`, "
        f"and update `{repo}/.codex/pilot-state/pilot_state.json`.\n"
        f"   - Hard boundaries: NEVER send unprompted WhatsApp messages directly to customers, NEVER send formal reports or "
        f"commercial commitments without Igor's confirmation, NEVER mutate prod `.env` secrets, NEVER force-push.\n"
        f"6. Output a concise, plain-language Russian report (chat phones masked to `*XXXX`) without internal script tags."
    )


def build_nikita_report_prompt(repo_root: pathlib.Path) -> str:
    repo = str(repo_root)
    return (
        f"Prepare the scheduled 10:00 MSK odd-day QA report on Nikita's preceding even-day WhatsApp shift for Treejar "
        f"(`tj-pf5x` / `tj-r62i`), run a mirror capability audit against Noor, and ship fundamental Noor fixes for any "
        f"uncovered gap before presenting the report. Communicate with Igor in Russian; write code, commits, Beads notes, "
        f"and handoff updates in English.\n\n"
        f"1. Read `{repo}/AGENTS.md`, `{repo}/.codex/orchestrator.toml`, `{repo}/.codex/handoff.md`, "
        f"`{repo}/.codex/pilot-state/nikita_report_state.json`, and `{repo}/docs/faq.md`.\n"
        f'2. Run `python "{repo}/scripts/pilot/collect_nikita_shift.py" --scheduled` (read-only via `ssh noor-server`). '
        f"If it outputs `SKIPPING DUPLICATE`, post a one-line Russian note and stop.\n"
        f"3. Audit EVERY Nikita / non-Noor dialogue thoroughly like a meticulous senior sales QA lead, paying strict attention "
        f"to `0. STICKY NOOR CHATS LEAKED TO NIKITA` and `0B. SHIFT BUCKET BREAKDOWN BY MOSCOW DATE` (`EVEN_SCHEDULED` vs "
        f"`ODD_LEAKED_ROUTER_BLACKOUT`):\n"
        f"   - Keep headline shift metrics focused on Nikita's scheduled even-day shift (`EVEN_SCHEDULED`), adding a calm factual "
        f"routing note if `ODD_LEAKED_ROUTER_BLACKOUT` or sticky Noor chats landed in Nikita.\n"
        f"   - Verify every model name, SKU, price, +5% VAT math, configuration/dimensions, and stock claim against live `products` "
        f"in `noor-db-1` and Zoho Inventory stock (`ssh noor-server`), plus `docs/faq.md`.\n"
        f"   - Measure exact response latency, attachment handling, and 20+ unit / custom / B2C order handoffs.\n"
        f"4. Mirror Noor Self-Check & Proactive Fundamental Fixes ('А как бы справилась Нур?'):\n"
        f"   - Verify against Noor's actual codebase (`src/llm/`, `src/services/`, `docs/faq.md`) whether Noor handles every "
        f"observed scenario cleanly.\n"
        f"   - If Noor would stumble, fix the structural class of problem FUNDAMENTALLY right now before finalizing the report "
        f'(`prose_guards_mode = "trust_model"` on `anthropic/claude-sonnet-5.5`), bundle `.codex/handoff.md` + '
        f"`repin_traceability_sources.py`, push `main`, watch CI + Deploy, and verify live `/api/v1/health` `release_sha == HEAD`.\n"
        f"5. Update `{repo}/.codex/pilot-state/nikita_report_state.json` (`last_run_utc`, `last_reported_shift_date_msk`, `watermark_utc`).\n"
        f"6. Save the executive-grade Russian client report to `{repo}/.tmp/client_report_<even_date>.md` and present both "
        f"(a) Noor's internal mirror-check summary and (b) the exact formatted report text for `AiDevTeam/Виктор` in this chat, "
        f"asking Igor to confirm (`«Отправляй»`) before sending."
    )


def ensure_overlay_copied(
    repo_root: pathlib.Path, overlay_dir: pathlib.Path | None
) -> list[str]:
    copied: list[str] = []
    candidates = []
    if overlay_dir:
        candidates.append(overlay_dir)
    home = pathlib.Path.home()
    candidates.extend(
        [
            repo_root.parent / ".treejar-tools" / "gitignored-overlay",
            repo_root.parent / "Treejar-Windows-Laptop-20261118" / "gitignored-overlay",
            home / "Treejar-Windows-Laptop-20261118" / "gitignored-overlay",
            repo_root.parent.parent
            / "Treejar-Windows-Laptop-20261118"
            / "gitignored-overlay",
        ]
    )
    src_root = next((c for c in candidates if c.exists()), None)
    if src_root is None:
        return copied

    for item in src_root.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src_root)
        dest = repo_root / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            copied.append(str(rel))
    return copied


def ensure_ssh_setup(
    repo_root: pathlib.Path, ssh_bundle_dir: pathlib.Path | None
) -> dict[str, object]:
    home = pathlib.Path.home()
    ssh_dir = home / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)

    key_dest = ssh_dir / "treejar_vps"
    pub_dest = ssh_dir / "treejar_vps.pub"

    bundle_candidates = []
    if ssh_bundle_dir:
        bundle_candidates.append(ssh_bundle_dir)
    bundle_candidates.extend(
        [
            repo_root.parent / ".treejar-tools" / "ssh",
            repo_root / ".tmp" / "ssh",
            home / "Treejar-Windows-Laptop-20261118" / "ssh",
            repo_root.parent / "Treejar-Windows-Laptop-20261118" / "ssh",
        ]
    )
    for b in bundle_candidates:
        if not key_dest.exists() and (b / "treejar_vps").exists():
            shutil.copy2(b / "treejar_vps", key_dest)
        if not pub_dest.exists() and (b / "treejar_vps.pub").exists():
            shutil.copy2(b / "treejar_vps.pub", pub_dest)

    if key_dest.exists():
        if os.name == "nt":
            username = os.environ.get("USERNAME") or os.getlogin()
            with contextlib.suppress(Exception):
                subprocess.run(
                    [
                        "icacls",
                        str(key_dest),
                        "/inheritance:r",
                        "/grant:r",
                        f"{username}:R",
                    ],
                    check=False,
                    capture_output=True,
                )
        else:
            with contextlib.suppress(OSError):
                key_dest.chmod(0o600)

    config_path = ssh_dir / "config"
    existing_cfg = (
        config_path.read_text(encoding="utf-8") if config_path.exists() else ""
    )
    if "Host noor-server" not in existing_cfg:
        updated_cfg = existing_cfg.rstrip() + "\n" + SSH_HOST_BLOCK.lstrip()
        config_path.write_text(updated_cfg, encoding="utf-8")
        if os.name != "nt":
            with contextlib.suppress(OSError):
                config_path.chmod(0o600)

    return {
        "key_present": key_dest.exists(),
        "key_path": str(key_dest),
        "config_path": str(config_path),
        "host_alias_configured": "Host noor-server"
        in config_path.read_text(encoding="utf-8")
        if config_path.exists()
        else False,
    }


def write_codex_automation_files(
    repo_root: pathlib.Path,
    thread_id: str | None = None,
) -> list[str]:
    home = pathlib.Path.home()
    auto_root = home / ".codex" / "automations"
    auto_root.mkdir(parents=True, exist_ok=True)
    now_ms = int(time.time() * 1000)

    specs = [
        {
            "id": "treejar-noor-pilot-monitor",
            "name": "Treejar Noor · Мониторинг живого пилота (2ч)",
            "prompt": build_pilot_monitor_prompt(repo_root),
            "rrule": "RRULE:FREQ=MONTHLY;BYMONTHDAY=1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31;BYHOUR=8,10,12,14,16,18,20,22;BYMINUTE=0;BYSECOND=0",
            "state_file": "pilot_state.json",
        },
        {
            "id": "treejar-nikita-shift-report",
            "name": "Treejar · QA-аудит смены Никиты и сверка Нур (10:00 МСК)",
            "prompt": build_nikita_report_prompt(repo_root),
            "rrule": "RRULE:FREQ=MONTHLY;BYMONTHDAY=1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31;BYHOUR=10;BYMINUTE=0;BYSECOND=0",
            "state_file": "nikita_report_state.json",
        },
    ]

    written: list[str] = []
    cwd_escaped = str(repo_root).replace("\\", "\\\\")
    for spec in specs:
        d = auto_root / str(spec["id"])
        d.mkdir(parents=True, exist_ok=True)
        prompt_str = str(spec["prompt"])
        sha = hashlib.sha256(prompt_str.encode("utf-8")).hexdigest()
        kind = "heartbeat" if thread_id else "cron"
        toml_lines = [
            "version = 1",
            f'id = "{spec["id"]}"',
            f'kind = "{kind}"',
            f"name = {json.dumps(spec['name'], ensure_ascii=False)}",
            f"prompt = {json.dumps(prompt_str, ensure_ascii=False)}",
            f'model_prompt_sha256 = "{sha}"',
            'status = "ACTIVE"',
            f'rrule = "{spec["rrule"]}"',
            'execution_environment = "local"',
            f'cwds = ["{cwd_escaped}"]',
        ]
        if thread_id:
            toml_lines.append(f'target_thread_id = "{thread_id}"')
        toml_lines.extend(
            [
                f"created_at = {now_ms}",
                f"updated_at = {now_ms}",
                "",
            ]
        )
        toml_path = d / "automation.toml"
        toml_path.write_text("\n".join(toml_lines), encoding="utf-8")
        written.append(str(toml_path))

        repo_state = repo_root / ".codex" / "pilot-state" / str(spec["state_file"])
        auto_state = d / str(spec["state_file"])
        if repo_state.exists():
            shutil.copy2(repo_state, auto_state)

    sqlite_dir = home / ".codex" / "sqlite"
    for db_name in ("codex.db", "codex-dev.db"):
        db_path = sqlite_dir / db_name
        if not db_path.exists():
            continue
        try:
            conn = sqlite3.connect(str(db_path), timeout=3.0)
            cur = conn.cursor()
            for spec in specs:
                kind = "heartbeat" if thread_id else "cron"
                cwds_json = json.dumps([str(repo_root)])
                cur.execute(
                    """
                    INSERT INTO automations (
                        id, name, prompt, status, cwds, rrule, created_at, updated_at,
                        kind, target_thread_id, execution_environment
                    ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, 'local')
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        prompt = excluded.prompt,
                        status = 'ACTIVE',
                        cwds = excluded.cwds,
                        rrule = excluded.rrule,
                        updated_at = excluded.updated_at,
                        kind = excluded.kind,
                        target_thread_id = COALESCE(excluded.target_thread_id, automations.target_thread_id),
                        execution_environment = 'local'
                    """,
                    (
                        spec["id"],
                        spec["name"],
                        spec["prompt"],
                        cwds_json,
                        spec["rrule"],
                        now_ms,
                        now_ms,
                        kind,
                        thread_id,
                    ),
                )
            conn.commit()
            conn.close()
            written.append(f"{db_path} (SQLite updated)")
        except sqlite3.Error as exc:
            written.append(f"{db_path} (SQLite locked/skipped: {exc})")

    return written


def write_antigravity_sidecars(repo_root: pathlib.Path) -> list[str]:
    home = pathlib.Path.home()
    sidecar_root = home / ".gemini" / "config" / "sidecars"
    sidecar_root.mkdir(parents=True, exist_ok=True)
    repo_uri = repo_root.as_uri()
    written: list[str] = []

    specs = [
        {
            "id": "treejar-noor-pilot-monitor",
            "cron": "CRON_TZ=Europe/Moscow 0 8,10,12,14,16,18,20,22 1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31 * *",
            "display_name": "Treejar Noor Pilot Monitor",
            "description": "Every 2 hours (08:00-22:00 Europe/Moscow) on odd dates, monitors the Treejar Noor live pilot, enforces zero-hang prod remediation, ships fundamental code fixes, and drafts client policy clarifications.",
            "prompt": build_pilot_monitor_prompt(repo_root),
            "state_file": "pilot_state.json",
        },
        {
            "id": "treejar-nikita-shift-report",
            "cron": "CRON_TZ=Europe/Moscow 0 10 1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31 * *",
            "display_name": "Treejar Nikita Shift Report",
            "description": "At 10:00 AM (Europe/Moscow) on odd dates, audits Nikita's preceding even-day shift, runs a mirror check on Noor (proactively fixing & deploying any Noor gap first), and prepares the client QA report for Igor's approval.",
            "prompt": build_nikita_report_prompt(repo_root),
            "state_file": "nikita_report_state.json",
        },
    ]

    for spec in specs:
        d = sidecar_root / str(spec["id"])
        d.mkdir(parents=True, exist_ok=True)
        payload = {
            "builtin": "schedule",
            "args": [
                spec["cron"],
                "agentapi",
                "new-conversation",
                "--",
                spec["prompt"],
            ],
            "restart_policy": "always",
            "display_name": spec["display_name"],
            "description": spec["description"],
            "agent_permissions": {
                "workspace_uris": [repo_uri],
                "access_grants": [
                    f"read_file({d})",
                    f"write_file({d})",
                    f"read_file({repo_root})",
                    f"write_file({repo_root})",
                    "command(python)",
                    "command(python3)",
                    "command(uv)",
                    "command(bd)",
                    "command(git)",
                    "command(gh)",
                    "command(curl)",
                    "command(ssh noor-server)",
                    "read_url(noor.starec.ai)",
                    "read_url(github.com)",
                ],
            },
        }
        sc_path = d / "sidecar.json"
        sc_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        written.append(str(sc_path))

        repo_state = repo_root / ".codex" / "pilot-state" / str(spec["state_file"])
        sc_state = d / str(spec["state_file"])
        if repo_state.exists() and not sc_state.exists():
            shutil.copy2(repo_state, sc_state)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Setup Treejar Windows timers and environment."
    )
    parser.add_argument("--repo-root", type=pathlib.Path, default=REPO_ROOT)
    parser.add_argument("--overlay-dir", type=pathlib.Path, default=None)
    parser.add_argument("--ssh-bundle-dir", type=pathlib.Path, default=None)
    parser.add_argument("--thread-id", type=str, default=None)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    copied_overlay = ensure_overlay_copied(repo_root, args.overlay_dir)
    ssh_info = ensure_ssh_setup(repo_root, args.ssh_bundle_dir)
    codex_files = write_codex_automation_files(repo_root, thread_id=args.thread_id)
    sidecar_files = write_antigravity_sidecars(repo_root)

    summary = {
        "repo_root": str(repo_root),
        "platform": os.name,
        "env_present": (repo_root / ".env").exists(),
        "beads_jsonl_present": (repo_root / ".beads" / "issues.jsonl").exists(),
        "pilot_state_present": (
            repo_root / ".codex" / "pilot-state" / "pilot_state.json"
        ).exists(),
        "nikita_state_present": (
            repo_root / ".codex" / "pilot-state" / "nikita_report_state.json"
        ).exists(),
        "overlay_files_copied": len(copied_overlay),
        "ssh": ssh_info,
        "codex_automations": codex_files,
        "antigravity_sidecars": sidecar_files,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
