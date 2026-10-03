Target: /home/me/code/treejar, Beads tj-uvld.
Audience: новый исполнитель Codex.
Entrypoint: Use $orchestrator-stage.

Goal: реализуй и сразу протестируй оптимизацию обновления остатков Zoho.

Context: прочитай AGENTS.md, .codex/orchestrator.toml, .codex/handoff.md,
затем полный промпт docs/prompts/2026-10-03-zoho-stock-sync-optimization.md
и спецификацию docs/specs/zoho-stock-sync-optimization/spec.md. Выполни bd show tj-uvld.

Success criteria: AC01–AC12 спецификации; код, проверки, измерение расхода API,
локальные коммиты и отчёт.

Constraints: отдельная ветка/worktree, сохранить чужую работу. Следуй полномочиям
полного промпта: выкладка и внешние операции требуют отдельного разрешения.

Output: проверенный результат с SHA, тестами и явно обозначенными live-проверками.

Stop: только на недостающем разрешении/существенных данных после независимой
локальной работы; не завершай задачей-планом и не выдавай mocks за live-доказательство.
