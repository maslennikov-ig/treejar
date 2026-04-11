# MacBook Continuation Prompt

Вставь этот prompt в новый Codex-сеанс на макбуке.

```text
Ты продолжаешь работу в репозитории treejar как technical orchestrator.

Говори со мной по-русски.
Сначала прочитай:
- /path/to/treejar/AGENTS.md
- /path/to/treejar/.codex/orchestrator.toml
- /path/to/treejar/.codex/handoff.md
- /path/to/treejar/.codex/stages/tj-6h30/summary.md

Актуальная truth на 11 апреля 2026:
- canonical host: https://noor.starec.ai
- canonical runtime path: /opt/noor
- live test recipient: +79262810921
- canonical Wazzup sender/channel: +971551220665
- channelId: b49b1b9d-757f-4104-b56d-8f43d62cc515
- Treejar Catalog API = single source of truth for customer-facing catalog discovery/assets
- Zoho = exact stock/price confirmation + order execution truth
- latest runtime-changing verified baseline: b2d9b6beb82f050ac44f8c026cd8f9936b06d5fd
- GitHub Actions deploy run 24286771354 succeeded

Что уже закрыто и не надо переоткрывать без нового evidence:
- Treejar catalog cutover landed
- exact quotation orchestration path landed
- inventory customer resolution for quotation landed
- quotation PDF image policy switched to Treejar-primary customer-facing asset logic
- Telegram review hardening landed
- post-deploy live verification stage tj-6h30 closed:
  - quotation path live-proven
  - Telegram manager-review path live-proven
  - smoke tooling repaired
  - synthetic smoke chatId fix deployed and verified
  - safe faq_global downgrade verified without polluting FAQ

Что осталось ближайшим реальным этапом:
- tj-5dbj: make canonical /opt/noor rebuild deterministic and CPU-only

Ограничения:
- не использовать dirty local root как базу для новых coding slices
- findings-first review обязателен
- use Context7 when docs matter
- не переоткрывать старые гипотезы без нового evidence
- deploy/prod mutation делать только когда это реально нужно и уже понятно зачем

Что нужно сделать первым:
- собрать evidence по текущему состоянию /opt/noor rebuild path и CI deploy artifacts
- определить, почему rebuild остаётся тяжёлым/non-deterministic
- отделить operational deploy/runtime track от product logic

Что уже подготовлено для owner-facing проверки:
- docs/client/victor-owner-guide-2026-04-11.md

Начинай от текущего origin/main, но не переоткрывай уже доказанные runtime-гипотезы без нового evidence.
Работай stage-based, коротко обновляй статус, и перед merge/deploy всегда прогоняй verification.
```
