# Start work on Treejar (Noor) on Windows & Laptop

Эта папка (`C:\Users\masle\code\treejar`, **всего ~4.2 МБ**) при переносе содержит **только файлы из `.gitignore`**, которые не хранятся в GitHub:
- `.env`, `.env.dev`, `.mcp.json`
- `.beads/` (`issues.jsonl` со всеми 994 задачами и конфигурация)
- `.codex/config.toml` и `.codex/pilot-state/{pilot_state.json,nikita_report_state.json}` (состояние и курсоры обоих таймеров)
- `.tmp/ssh/{treejar_vps,treejar_vps.pub}` (SSH-ключ к прод-серверу `noor-server` `95.216.204.189:2222`)
- `.tmp/client_report_*.md` (клиентские отчёты по сменам Никиты) и `.tmp/model-bakeoff-20261109/` (сценарии и результаты bake-off)
- `docs/contract.md`, `docs/estimate.md`, `docs/dialogue-stats.csv`, `docs/offers/*.pdf`

Весь исходный код, тесты и кроссплатформенные скрипты таймеров (`scripts/pilot/*.py`) находятся в `main` (`https://github.com/maslennikov-ig/treejar.git`) и подтягиваются при первом старте.

---

## Стартовый промпт для Codex на Windows (также в `PROMPT.md`)

```text
Мы перешли из WSL на Windows Native (и продолжаем работу на ноутбуке). Открой рабочую папку `%USERPROFILE%\code\treejar` — в ней сейчас лежат только легковесные файлы из `.gitignore` (`.env`, `.env.dev`, `.beads/`, `.codex/pilot-state/`, `.tmp/ssh/treejar_vps`, `docs/contract.md`, `docs/estimate.md`, `docs/offers/`, `.tmp/`), а весь код находится в GitHub (`https://github.com/maslennikov-ig/treejar.git`, ветка `main`).

Сделай при старте следующее (используй PowerShell и нативные Windows-утилиты, отвечай мне на русском):
1. Если в `%USERPROFILE%\code\treejar` ещё нет `.git`, подтяни репозиторий из GitHub прямо поверх этой папки, сохранив все `.gitignore`-файлы на своих местах:
   - `git init -b main`
   - `git remote add origin https://github.com/maslennikov-ig/treejar.git`
   - `git fetch origin main --tags`
   - `git checkout -f -B main origin/main`
   - `git branch --set-upstream-to=origin/main main`
2. Прочитай `AGENTS.md`, `.codex/orchestrator.toml` и `.codex/handoff.md`.
3. Запусти `python scripts/pilot/setup_windows_timers.py` (при наличии ID текущего треда передай `--thread-id <ID>`), чтобы:
   - установить SSH-ключ из `.tmp/ssh/treejar_vps` в `%USERPROFILE%\.ssh\treejar_vps` с корректными правами Windows (`icacls`) и прописать `Host noor-server` (`95.216.204.189:2222`, `noor-dev`) в `%USERPROFILE%\.ssh\config`,
   - зарегистрировать и активировать оба наших регламентных таймера в Windows Codex (`%USERPROFILE%\.codex\automations\` и `codex.db`):
     a) `treejar-noor-pilot-monitor` — каждые 2 часа с 08:00 до 22:00 МСК по нечётным числам месяца (`python scripts/pilot/check_pilot.py --scheduled`): мониторинг живого пилота Noor, zero-hang дожим зависших диалогов/CRM/менеджеров и фундаментальные фиксы с немедленным деплоем в `main`.
     b) `treejar-nikita-shift-report` — в 10:00 МСК по нечётным числам месяца (`python scripts/pilot/collect_nikita_shift.py --scheduled`): аудит чётной смены Никиты, зеркальная самопроверка «А как бы справилась Нур?» с упреждающим деплоем фиксов и подготовка клиентского отчёта для `AiDevTeam/Виктор` (отправка отчёта в группу — только после моего подтверждения «Отправляй»).
   - Если в текущей среде доступен инструмент расписания (`schedule` / `automation`), также проверь или поставь эти два расписания активными.
4. Проверь `git status -sb`, `https://noor.starec.ai/api/v1/health` и выполни разовую проверку `python scripts/pilot/check_pilot.py`.
5. Дай мне короткую сводку на русском: статус репозитория на Windows, совпадение `release_sha` на проде с `HEAD`, статус SSH до `noor-server`, статус обоих таймеров и текущее состояние пилота.
```
