# Noor CRM Admin: чеклист owner-приемки

Дата: 2026-05-09
Задача: `tj-pp3t`
Production: `https://noor.starec.ai`
Основная админка: `https://noor.starec.ai/dashboard/`
Технический fallback: `https://noor.starec.ai/admin/`

Этот чеклист нужен для приемки новой CRM-админки Noor владельцем/оператором. По умолчанию это read-only проверка интерфейса и данных, а не live WhatsApp E2E. Не отправляйте клиентские WhatsApp-сообщения, не запускайте широкие production-проверки, не выполняйте destructive actions и не меняйте production-конфигурацию без отдельного явного разрешения на конкретную synthetic-запись.

На дату документа последняя проверенная production-версия кода: `main@867b9330ee51427e0f533f919f6f7df9b1c0a53e`, GitHub Actions run `25597247650`. Перед каждой новой приемкой нужно снова записать фактический runtime SHA, потому что production мог измениться.

## Предусловия

- У проверяющего есть admin-доступ к `https://noor.starec.ai/admin/login`.
- Первый проход выполняется в desktop-браузере, желательно от 1440 px ширины.
- Если проверяющий умеет безопасно пользоваться DevTools, открыть Console и Network.
- Для проверки auth boundary начать из чистого профиля или incognito.
- Не использовать реальные клиентские номера и реальные клиентские записи для mutable-проверок.
- Без отдельного разрешения запрещены WhatsApp compose/send, рассылки, payment reminder send, reset execute, catalog sync, включение QA schedule и сохранение настроек.

## Что фиксируем как evidence

| Поле | Значение |
| --- | --- |
| Проверяющий | |
| Дата/время и timezone | |
| Браузер и OS | |
| Runtime SHA | |
| GitHub Actions run id, если известен | |
| Production URL | `https://noor.starec.ai` |
| Итог | `PASS`, `PASS WITH NOTES` или `BLOCKED` |
| Ссылки на issues / Beads | |

Для каждого проверенного экрана зафиксировать:

- имя файла или ссылку на screenshot;
- статус pass/fail;
- короткую заметку обо всем непонятном, медленном, отсутствующем или рискованном;
- console errors, page errors, request failures или HTTP `5xx`, если они были.

## Стоп-условия

Остановить проверку и завести узкую задачу, если происходит любое из этого:

- анонимный `https://noor.starec.ai/dashboard/` показывает приватные admin-данные;
- login не работает с корректными учетными данными;
- `/dashboard/` открывается, но отсутствует обязательный раздел навигации;
- экран пустой, бесконечно грузится или приложение падает;
- любой admin API request возвращает неожиданный `5xx`;
- в CRM dashboard видна возможность написать клиенту, отправить WhatsApp-сообщение, создать WhatsApp-рассылку или похожий customer-visible compose/send action;
- destructive action может выполниться без confirmation modal;
- reset, archive, delete, sync, QA run, report generation или settings change вызывает неожиданный внешний side effect;
- в UI, логах, screenshots или audit details видны raw secrets, tokens или credentials.

## Read-Only Acceptance Flow

### 1. Auth boundary

- [ ] Открыть `https://noor.starec.ai/dashboard/` без login.
- [ ] Убедиться, что приватные dashboard-данные не видны.
- [ ] Залогиниться через `https://noor.starec.ai/admin/login`.
- [ ] Открыть `https://noor.starec.ai/dashboard/`.
- [ ] Убедиться, что CRM admin shell открылся после login.

Ожидаемый результат: anonymous access закрыт, authenticated access работает, проверяющий попадает в CRM-админку.

### 2. Навигация и общий shell

- [ ] В левой навигации есть: `Обзор`, `Клиенты и диалоги`, `Очереди`, `База знаний`, `Правила бота`, `Каталог`, `Качество`, `Отчеты`, `Настройки`, `Аудит`.
- [ ] Переход между всеми разделами не ломает приложение.
- [ ] В shell нет WhatsApp compose/send/broadcast action.
- [ ] Пользовательские labels на русском; технические enum values остаются только там, где это уместно.

Ожидаемый результат: админка ощущается как единое CRM-рабочее место, а не как просмотр таблиц БД.

### 3. Обзор

- [ ] Метрики/карточки загрузились.
- [ ] Экран дает операционную картину по продажам, диалогам, очередям или качеству.
- [ ] Empty/low-data states понятны и не выглядят как поломка.
- [ ] При открытии экрана нет console/page/network errors.

Ожидаемый результат: владелец понимает текущее состояние системы без захода в SQLAdmin.

### 4. Клиенты и диалоги

- [ ] Экран устроен как трехпанельное рабочее место: список клиентов/диалогов, полный chat/timeline, правый inspector.
- [ ] Поиск по телефону/имени/Zoho/SO работает, если есть подходящие данные.
- [ ] Видны применимые фильтры по статусу, этапу, языку, эскалации, deal/order metadata, дате или сегменту.
- [ ] Клик по клиенту открывает полный timeline диалога, а не сырые строки БД.
- [ ] Timeline понятно показывает user/assistant/manager/system, media/audit markers и timestamps.
- [ ] Inspector показывает CRM/customer fields, stage/status, order/deal metadata, escalations, QA/manager reviews, feedback, outbound audit, source/UTM и applied bot rule ids, если они есть.
- [ ] Reset preview явно отделен от reset execute; cancel не меняет состояние.
- [ ] Нет ручного customer message composer и WhatsApp send button.

Ожидаемый результат: владелец может открыть клиента, понять весь контекст диалога, почему бот так ответил, и какие admin-действия безопасны.

### 5. Очереди

- [ ] Видны escalations, manager reviews, FAQ candidates или другие pending work queues.
- [ ] Queue item ведет обратно к релевантному клиенту/диалогу.
- [ ] Resolve/close/archive-like actions требуют confirmation, если меняют состояние.
- [ ] Ни одно queue action не отправляет WhatsApp-сообщение без отдельного внешнего разрешения.

Ожидаемый результат: очереди операционные, контекстные и защищены от случайных customer-visible sends.

### 6. База знаний

- [ ] Работают поиск и фильтры по category, source, language, status или аналогичной metadata.
- [ ] Detail/editor показывает поля, нужные для поддержки AI knowledge.
- [ ] Видны duplicate, unsafe, context-specific или indexing/embedding status, если применимо.
- [ ] Auto-FAQ candidates видны как очередь на подтверждение, а не публикуются автоматически.
- [ ] `Save and index`, soft-delete и reindex понятны и требуют осознанного действия.

Ожидаемый результат: владелец может управлять фактами отдельно от правил поведения бота.

### 7. Правила бота

- [ ] Список правил показывает title/type/status/scope/stage/language/segment/priority или эквивалентные операционные поля.
- [ ] Draft, active и archived статусы легко различимы.
- [ ] Preview объясняет, какие правила применятся к sample message или conversation.
- [ ] Test-on-conversation работает как inspection flow и не отправляет клиенту сообщение.
- [ ] Activation/archive/destructive actions требуют confirmation.
- [ ] Экран ясно отделяет behavior rules от factual knowledge-base entries.

Ожидаемый результат: пожелания владельца и playbooks управляются без редактирования основного prompt и без смешивания с FAQ.

### 8. Каталог

- [ ] Catalog status, sync status, product counts и recent sync information читаются.
- [ ] Product search/list/detail загружается для representative items.
- [ ] Manual catalog sync не запускается во время read-only приемки.
- [ ] Если sync action виден, он выглядит как privileged action и не запускается случайно от навигации.

Ожидаемый результат: владелец видит состояние каталога без изменения товарных данных.

### 9. Качество

- [ ] Загружаются bot QA, manager QA, review summaries или quality controls.
- [ ] Manual quality actions ясно подписаны и не включают scheduled automation случайно.
- [ ] Cost/safety posture виден, если применимо.
- [ ] Любое risky или budget-affecting action требует confirmation.

Ожидаемый результат: quality controls управляются владельцем и остаются disabled-safe, пока их явно не включили.

### 10. Отчеты

- [ ] Экран отчетов загружается без HTTP `500`.
- [ ] Existing analytics читаются.
- [ ] Report generation работает только как admin action и не отправляет customer messages.
- [ ] Если generation запускали с разрешения, результат виден в UI и не раскрывает secrets.

Ожидаемый результат: отчеты помогают owner review и не ломают admin session.

### 11. Настройки

- [ ] Settings screen безопасно загружает текущую конфигурацию.
- [ ] AI quality controls, payment reminders, prompts, provider/model settings или похожие controls читаются, если присутствуют.
- [ ] Во время read-only приемки настройки не сохраняются.
- [ ] Dangerous или externally visible settings требуют confirmation перед save.
- [ ] Secret values замаскированы.

Ожидаемый результат: владелец понимает runtime posture без утечки credentials и без изменения поведения системы.

### 12. Аудит

- [ ] Audit log показывает последние admin/system actions.
- [ ] Search/filter по entity/action/time работает, если есть подходящие данные.
- [ ] Before/after JSON достаточно понятен для расследования.
- [ ] Secrets и tokens замаскированы.
- [ ] Admin CRM, KB, bot rule, reset, catalog, report и settings actions попадают в audit, если такие действия выполнялись.

Ожидаемый результат: каждая meaningful admin mutation атрибутируема и проверяема.

### 13. SQLAdmin fallback

- [ ] После login открыть `https://noor.starec.ai/admin/`.
- [ ] Убедиться, что SQLAdmin доступен как технический fallback.
- [ ] Использовать SQLAdmin только для fallback inspection, а не как основной workflow для диалогов.

Ожидаемый результат: `/dashboard/` является owner CRM, а `/admin/` остается технической запасной панелью.

## Optional mutable checks

Запускать только после явного разрешения на synthetic-запись и назначенного проверяющего. Не использовать реальные клиентские диалоги.

| Проверка | Только если разрешено | Ожидаемое evidence |
| --- | --- | --- |
| Bot rule draft lifecycle | Создать или изменить безопасное draft-правило, preview, затем archive/delete если безопасно | Audit row с masked before/after, draft/archived rule не попадает в active runtime search |
| Knowledge-base test entry | Создать безопасную internal test Q&A, save/index, затем soft-delete | Видны embedding/index status, soft-delete и audit row |
| Conversation metadata update | Изменить status/stage/name на approved synthetic conversation | Inspector обновился, audit row записан, WhatsApp не отправлен |
| Reset preview | Preview reset для approved synthetic conversation | Preview показывает impact, mutation не происходит до execute |
| Reset execute | Только с отдельным явным разрешением | Conversation state изменился ровно как в preview, audit row записан, external send нет |
| Catalog sync | Только с отдельным явным разрешением и оператором рядом | Видны sync status/audit, нет unrelated product mutation |
| Manual QA/report action | Только с отдельным явным разрешением и принятым cost posture | Result виден в QA/report UI, audit row записан |

## Acceptance decision

Использовать один из итогов:

- `PASS`: все обязательные read-only checks прошли, blocking issues нет, unexpected errors нет.
- `PASS WITH NOTES`: основной owner workflow usable, но записаны non-blocking UX/content issues.
- `BLOCKED`: сработало одно или несколько стоп-условий, либо владелец не может безопасно использовать обязательный admin workflow.

Blocking issues должны стать узкими Beads/GitHub issues с:

- точным экраном и URL;
- runtime SHA;
- шагами воспроизведения;
- screenshot или console/network evidence;
- указанием, что блокируется: owner acceptance, live E2E, deploy или только polish.

## Sign-off

| Роль | Имя | Решение | Notes | Дата |
| --- | --- | --- | --- | --- |
| Owner/reviewer | | | | |
| Engineer | | | | |

## Gate перед live WhatsApp E2E

Owner acceptance админки не разрешает live customer-channel testing. Перед любым live WhatsApp/media/voice/payment/referral/feedback E2E нужно отдельное разрешение, в котором указаны:

- точный phone number и Wazzup channel;
- список сценариев и synthetic suffix policy;
- входят ли в scope product media, quotation PDFs, voice/audio, payment reminders, referrals или feedback;
- stop/abort contact path;
- cleanup/readback requirements;
- ожидаемое место финального artifact.

Для live E2E использовать `docs/testing/final-controlled-e2e-runbook-2026-04-29.md` как guardrail, если его не заменит более новый утвержденный runbook.
