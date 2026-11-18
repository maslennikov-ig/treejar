# Start work on Treejar (Noor) on Windows & Laptop

Work in `%USERPROFILE%\code\treejar` (`C:\Users\masle\code\treejar`). Open this folder in the Windows Codex application (Native Windows mode, not WSL). The repository is `maslennikov-ig/treejar` on `main`. Production runs at `https://noor.starec.ai` (`noor-server` -> `95.216.204.189:2222`, user `noor-dev`, SSH key `~/.ssh/treejar_vps`).

All gitignored project files (`.env`, `.env.dev`, `.mcp.json`, `.beads/`, `.codex/pilot-state/`, `.agents/`, `.claude/`, `docs/contract.md`, `docs/estimate.md`, `docs/dialogue-stats.csv`, `docs/offers/`, `.tmp/`) are already placed directly inside `C:\Users\masle\code\treejar` AND backed up with the SSH key (`treejar_vps`) and evaluation workspace (`model-bakeoff-20261109`) inside `C:\Users\masle\code\.treejar-tools\`.

## 1. Start & Verify in PowerShell (PC or Laptop after copying `C:\Users\masle\code`)

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
. "$env:USERPROFILE\code\.treejar-tools\Enter-Treejar.ps1"
python scripts/pilot/setup_windows_timers.py
python scripts/pilot/check_pilot.py
```

`setup_windows_timers.py` automatically:
1. Verifies/restores any missing gitignored files from `..\.treejar-tools\gitignored-overlay\`,
2. Copies `..\.treejar-tools\ssh\treejar_vps` into `%USERPROFILE%\.ssh\treejar_vps` with strict Windows `icacls` permissions and adds `Host noor-server` to `%USERPROFILE%\.ssh\config`,
3. Registers and activates both recurring pilot timers (`treejar-noor-pilot-monitor` and `treejar-nikita-shift-report`) in `%USERPROFILE%\.codex\automations\` and `%USERPROFILE%\.codex\sqlite\codex.db` (plus Antigravity sidecars).

## 2. Ready-to-Paste Starter Prompt for Codex on Windows (PC or Laptop)

Copy and paste the block below into your first Codex chat on Windows after opening `C:\Users\masle\code\treejar`:

```text
Мы перешли из WSL на Windows Native (и продолжаем работу на ноутбуке). Рабочая копия проекта Treejar (Noor) находится в `%USERPROFILE%\code\treejar` (все gitignored-файлы уже лежат внутри репозитория, а резервная копия оверлея, SSH-ключ `treejar_vps` и окружение — в соседней папке `%USERPROFILE%\code\.treejar-tools`).

Сделай при старте следующее:
1. Прочитай `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md` и `START-WINDOWS.md`. Общайся со мной на русском языке (кратко и по делу); код, коммиты и handoff веди на английском.
2. Запусти `python scripts/pilot/setup_windows_timers.py` из корня репозитория (при наличии ID текущего треда передай `--thread-id <ID>`), чтобы:
   - проверить наличие всех gitignored-файлов (`.env`, `.env.dev`, `.beads/`, `.codex/pilot-state/`, `docs/contract.md`, `docs/estimate.md`, `docs/offers/`, `.tmp/`), при необходимости докопировав их из `../.treejar-tools/gitignored-overlay`,
   - установить/проверить SSH-ключ `%USERPROFILE%\.ssh\treejar_vps` (из `../.treejar-tools/ssh/treejar_vps`) с корректными Windows ACL (`icacls`) и алиас `Host noor-server` (`95.216.204.189:2222`),
   - зарегистрировать и активировать оба наших регламентных таймера в Codex (`%USERPROFILE%\.codex\automations\` и `codex.db`):
     a) `treejar-noor-pilot-monitor` — каждые 2 часа с 08:00 до 22:00 МСК по нечётным числам месяца (`python scripts/pilot/check_pilot.py --scheduled`): мониторинг живого пилота Noor, zero-hang дожим зависших диалогов/CRM/менеджеров и фундаментальные фиксы с немедленным деплоем в `main`.
     b) `treejar-nikita-shift-report` — в 10:00 МСК по нечётным числам месяца (`python scripts/pilot/collect_nikita_shift.py --scheduled`): аудит чётной смены Никиты, зеркальная самопроверка «А как бы справилась Нур?» с упреждающим деплоем фиксов и подготовка клиентского отчёта для `AiDevTeam/Виктор` (отправка отчёта в группу — только после моего подтверждения «Отправляй»).
   - Если в текущей среде доступен инструмент расписания (`schedule` / `automation`), также проверь или поставь эти два расписания активными.
3. Проверь `git status -sb`, состояние задач в `.beads/issues.jsonl` (или `bd status`), доступность `https://noor.starec.ai/api/v1/health` и выполни разовую проверку `python scripts/pilot/check_pilot.py`.
4. Дай мне короткую сводку на русском: статус репозитория на Windows, совпадение `release_sha` на проде с `HEAD`, статус SSH до `noor-server`, статус обоих таймеров и текущее состояние пилота.
```

## 3. Recovery & Evaluation References

- `%USERPROFILE%\code\.treejar-tools\` contains `Enter-Treejar.ps1`, `Restore-TreejarOnLaptop.ps1`, `ssh\treejar_vps`, `gitignored-overlay\`, `treejar.bundle`, and the preserved `model-bakeoff-20261109\` evaluation workspace (`bakeoff\` + `scenario_replay.patch`).
