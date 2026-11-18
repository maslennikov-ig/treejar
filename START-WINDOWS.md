# Start work on Treejar (Noor) on Windows & Laptop

Work in `%USERPROFILE%\code\treejar` (`C:\Users\masle\code\treejar`). Open this folder in the Windows Codex application (Native Windows mode, not WSL). The repository is `maslennikov-ig/treejar` on `main`. Production runs at `https://noor.starec.ai` (`noor-server` -> `95.216.204.189:2222`, user `noor-dev`, SSH key `~/.ssh/treejar_vps`).

## 1. Laptop USB Restore (one command on a new Windows laptop)

If starting on the laptop from the USB flash drive folder `Treejar-Windows-Laptop-20261118`, run in PowerShell from that USB folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.\Restore-TreejarOnLaptop.ps1
```

`Restore-TreejarOnLaptop.ps1` automatically:
1. Clones or restores `%USERPROFILE%\code\treejar` on `main` (using GitHub or the bundled offline `treejar.bundle`),
2. Overlays all gitignored files (`.env`, `.env.dev`, `.mcp.json`, `.beads/`, `.codex/config.toml`, `.codex/pilot-state/`, `.agents/`, `.claude/`, `docs/contract.md`, `docs/estimate.md`, `docs/dialogue-stats.csv`, `docs/offers/`, `.tmp/`),
3. Installs `treejar_vps` + `Host noor-server` into `%USERPROFILE%\.ssh\` with strict Windows `icacls` permissions,
4. Registers both recurring pilot timers (`treejar-noor-pilot-monitor` and `treejar-nikita-shift-report`) in `%USERPROFILE%\.codex\automations\` and `%USERPROFILE%\.codex\sqlite\codex.db`.

## 2. Start & Verify in PowerShell (PC or Laptop)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
. "$env:USERPROFILE\code\.treejar-tools\Enter-Treejar.ps1"
python scripts/pilot/setup_windows_timers.py
python scripts/pilot/check_pilot.py
```

## 3. Ready-to-Paste Starter Prompt for Codex on Windows (PC or Laptop)

Copy and paste the block below into your first Codex chat on Windows:

```text
Мы перешли из WSL на Windows Native (и продолжаем работу на ноутбуке). Рабочая копия проекта Treejar (Noor) находится в `%USERPROFILE%\code\treejar` (если её ещё нет на ноутбуке — разверни её из папки `Treejar-Windows-Laptop-20261118` на флешке/диске C через `powershell -ExecutionPolicy Bypass -File .\Restore-TreejarOnLaptop.ps1`).

Сделай при старте следующее:
1. Прочитай `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md` и `START-WINDOWS.md`. Общайся со мной на русском языке (кратко и по делу); код, коммиты и handoff веди на английском.
2. Запусти `python scripts/pilot/setup_windows_timers.py` из корня репозитория (при наличии ID текущего треда передай `--thread-id <ID>`), чтобы:
   - проверить/докопировать все gitignored-файлы (`.env`, `.env.dev`, `.beads/`, `.codex/pilot-state/`, `docs/contract.md`, `docs/estimate.md`, `docs/offers/`, `.tmp/`),
   - проверить SSH-ключ `%USERPROFILE%\.ssh\treejar_vps` и алиас `Host noor-server` (`95.216.204.189:2222`),
   - активировать оба наших регламентных таймера в Codex (`%USERPROFILE%\.codex\automations\` и `codex.db`):
     a) `treejar-noor-pilot-monitor` — каждые 2 часа с 08:00 до 22:00 МСК по нечётным числам месяца (`python scripts/pilot/check_pilot.py --scheduled`): мониторинг живого пилота Noor, zero-hang дожим зависших диалогов/CRM/менеджеров и фундаментальные фиксы с немедленным деплоем в `main`.
     b) `treejar-nikita-shift-report` — в 10:00 МСК по нечётным числам месяца (`python scripts/pilot/collect_nikita_shift.py --scheduled`): аудит чётной смены Никиты, зеркальная самопроверка «А как бы справилась Нур?» с упреждающим деплоем фиксов и подготовка клиентского отчёта для `AiDevTeam/Виктор` (отправка отчёта в группу — только после моего подтверждения «Отправляй»).
   - Если в текущей среде доступен инструмент расписания (`schedule` / `automation`), также проверь или поставь эти два расписания активными.
3. Проверь `git status -sb`, `bd status` (при наличии `bd` в PATH, иначе прочитай `.beads/issues.jsonl`), доступность `https://noor.starec.ai/api/v1/health` и выполни разовую проверку `python scripts/pilot/check_pilot.py`.
4. Дай мне короткую сводку на русском: статус репозитория на Windows, совпадение `release_sha` на проде с `HEAD`, статус SSH до `noor-server`, статус обоих таймеров и текущее состояние пилота.
```

## 4. Recovery & Evaluation References

- `%USERPROFILE%\Treejar-Windows-Laptop-20261118\README.md` contains the portable USB package manifest, `SHA256SUMS`, offline `treejar.bundle`, full `gitignored-overlay/`, SSH keys for `noor-server`, and the preserved `model-bakeoff-20261109` evaluation workspace (`bakeoff/` + `scenario_replay.patch`).
