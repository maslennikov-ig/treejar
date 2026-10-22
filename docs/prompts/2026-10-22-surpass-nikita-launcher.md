Target: /home/me/code/treejar, Beads epic tj-asty (tj-asty.1 .. tj-asty.5).
Audience: исполнитель (Codex / Antigravity).
Entrypoint: Use $orchestrator-stage.

Goal: реализуй и протестируй все 5 задач эпика tj-asty (AC01–AC10), чтобы наш бот Noor гарантированно превосходил бота клиента «Никиту» по всем пунктам бенчмарка.

Context: прочитай AGENTS.md, .codex/orchestrator.toml, .codex/handoff.md, затем полный промпт docs/prompts/2026-10-22-surpass-nikita.md, спецификацию docs/specs/surpass-nikita/spec.md, план docs/plans/2026-10-22-surpass-nikita-plan.md и отчёт docs/reports/2026-10-22-nikita-vs-noor-benchmark.md. Выполни `export PATH="$HOME/.local/bin:$PATH"; bd show tj-asty && bd children tj-asty`.

Success criteria: AC01–AC10 из docs/specs/surpass-nikita/spec.md — (1) пакетная математика Qty × Unit = Subtotal + комплексный расчёт стол+кресла + 5% VAT excl./incl. и точная сверка с бюджетом в search_products/get_stock и claim_contract; (2) 3 бизнес-триггера передачи менеджеру (опт 20+ шт., мебель на заказ/нестандартные размеры, некаталожное спец. оборудование) с выдачей 2–3 референсных позиций из наличия с фото и сбором мини-брифа; (3) прямые ссылки на карточки товаров treejartrading.ae/product/<slug> вместе с WhatsApp-фото; (4) настраиваемое окно ожидания менеджера на 1-м сообщении (first_turn_manager_grace_seconds, по умолчанию 0) с авто-перехватом при ответе менеджера; (5) прогон сценариев A, B, C, D через scripts/scenario_replay.py, зелёные ruff/mypy/pytest, обновление статусов в Beads и отчёта docs/reports/2026-10-22-nikita-vs-noor-benchmark.md.

Constraints: сохранить все существующие преимущества Noor и некоммиченные файлы в docs/; локальные коммиты, тесты и scenario_replay разрешены; деплой на прод (noor.starec.ai) и отправка реальных сообщений в WhatsApp без отдельного подтверждения запрещены.

Output: готовый проверенный код, локальный коммит с SHA, результаты тестов и scenario_replay (A, B, C, D), обновлённый отчёт сравнения с Никитой и закрытые задачи в Beads.

Stop: только после полной локальной реализации и прохождения всех проверок AC01–AC10; не останавливайся на плане.
