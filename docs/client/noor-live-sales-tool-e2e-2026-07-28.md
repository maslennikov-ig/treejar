# Живое E2E-тестирование продаж Noor

**Дата:** 28 июля 2026 года  
**Контур:** production, `https://noor.starec.ai`  
**Проверенный релиз:** `0dd9615a…`, CI `30330683062`  
**Основная модель:** `z-ai/glm-5.2`  
**Вердикт:** **НЕ ПРИНЯТО — критические коммерческие пути работают неравномерно**

## Резюме

Проведено 11 изолированных многошаговых сценариев: 10 текстовых продажных диалогов и 1 голосовой сценарий. В production сохранены 39 входящих сообщений и 38 ответов Noor. В пяти ответах зафиксирована реальная генерация основной моделью: 32 481 входной и 4 356 выходных токенов. Остальные ответы прошли через детерминированные sales-guard маршруты.

Сильная часть продукта — реальный поиск и сравнение мебели. Noor нашла актуальные LUMA и NOVO, назвала SKU, цены и остатки, сравнила приватность и совместную работу, пересчитала конфигурацию после изменения команды с 8 до 12 человек. Ответы S03 и S04 уже похожи на работу компетентного консультанта.

Слабая часть — переходы между стадиями. После получения имени Noor иногда отвечает адресом шоурума вместо продолжения запроса, принимает исследовательский запрос за готовое КП, игнорирует возражение или промежуточный вопрос и требует реквизиты для PDF. Полное КП не создано: `create_quotation` был реально вызван, но создание клиента в Zoho Inventory завершилось HTTP `400`. CRM-возможность не создана. Голос трижды дошёл до production-обработчика, но провайдер распознавания трижды ответил HTTP `400`; текстовый fallback сработал.

Итоговая средняя оценка десяти текстовых диалогов по `docs/06-dialogue-evaluation-checklist.md` — **12,76/30**, то есть «плохо». Голосовой технический сценарий получил 0,75/30 и не включён в среднее продажных диалогов.

## Что именно проверено

- Английский и арабский языки.
- Значение `private-dash/private-desk`, актуальные семейства LUMA и NOVO.
- Поиск по бюджету и количеству, сравнение вариантов, точный SKU и live-остаток.
- Возражение по цене, более дешёвая конфигурация и cross-sell.
- Честный no-match.
- Память, исправление требования и прерывание вопросом о доставке/сборке.
- Попытка полного КП с тестовым клиентом, Zoho-readback и PDF.
- Попытка создания/продвижения CRM-возможности без КП.
- Эскалация и Telegram-уведомление.
- Карточки товаров и изображения через Wazzup.
- Голосовой файл и fallback.

## Метод и ограничения

Входящие сообщения подавались через существующий application-native production webhook и затем перечитывались из production PostgreSQL. Ответы отправлялись штатной Wazzup-интеграцией только на разрешённый тестовый номер. Это доказывает production-обработку, запись сообщения, работу модели/инструментов и исходящую доставку через провайдера, но **не является provider-originated входящим сообщением с физического WhatsApp-клиента**. Такой входящий canary нельзя безопасно имитировать серверным API без устройства владельца тестового номера.

Деловой текст ниже приведён дословно. Из tracked-отчёта удалены только внутренние корреляционные маркеры вида `[smoke:…]`, номера телефонов, chat/provider ID, URL голосового вложения и секреты. Полные raw-транскрипты, логи и аудиты находятся в защищённом локальном каталоге вне Git с правами `0700/0600`.

Два входящих сообщения были продублированы тестовым клиентом после неопределённого локального stdout: первый запрос S08 и имя `Yusuf` в S10. Дубликаты честно сохранены в production и показаны ниже; это дефект тестового драйвера, а не Noor. При расчёте задержек дублированный `Yusuf`, на который не было отдельного ответа, исключён.

## Сводка результатов

| ID | Сценарий | Результат | Оценка |
|---|---|---:|---:|
| S01 | EN: потребность, бюджет, кресла и столы | PARTIAL | 18,90/30 |
| S02 | AR: шесть приватных мест и кресла | FAIL | 7,40/30 |
| S03 | `private-dash`, LUMA и актуальные альтернативы | PASS с оговоркой по name gate | 18,15/30 |
| S04 | Сравнение LUMA/NOVO и рекомендация | PASS с оговоркой по переходу после имени | 18,90/30 |
| S05 | Бюджет, возражение, дешёвая конфигурация, cross-sell | FAIL | 6,40/30 |
| S06 | Точный SKU, цена и live-остаток | PARTIAL | 15,38/30 |
| S07 | Честный no-match и релевантные альтернативы | FAIL | 7,62/30 |
| S08 | Память, прерывание, исправление количества | PARTIAL | 15,60/30 |
| S09 | Полное КП, Zoho, PDF | BLOCKED/FAIL | 12,80/30 |
| S10 | CRM opportunity и следующий шаг без КП | FAIL | 6,40/30 |
| S11 | Голос/медиа и fallback | BLOCKED; fallback PASS | 0,75/30 |

## Реальные инструменты, модели и побочные эффекты

### Вызовы модели и инструментов

- 5 ответов основной `z-ai/glm-5.2` с ненулевыми токенами.
- 9 реальных `search_products`.
- 2 реальных model-tool вызова `get_stock`.
- 1 `advance_stage`.
- 1 `create_quotation`, завершившийся ошибкой до создания КП.
- `lookup_customer`, `create_deal` и model-tool `escalate_to_manager` в наблюдаемых traces не вызывались.
- Детерминированный stock/price route S06 делал live inventory readback, но не был model-tool вызовом; это различие важно для аудита.
- Поле стоимости в таблице сообщений не заполнялось, поэтому финансовую сумму провайдерских вызовов подтвердить по production-БД нельзя. Нельзя интерпретировать это как нулевую стоимость.

### Wazzup и медиа

- 58 outbound audit-записей, все в терминальном статусе `sent`.
- 47 записей имеют provider message ID.
- 33 обычных текстовых ответа, 2 escalation fallback, 1 voice fallback.
- 11 товарных изображений реально отправлены; ещё 11 связанных caption-аудитов не имеют отдельного provider ID.
- PDF не создан и не отправлен.
- Три сохранённых voice-fallback ответа дедуплицировались до одной исходящей Wazzup-записи. Для разных входящих voice message ID это подозрительно и вынесено в дефект.

### Zoho, CRM и эскалации

- В S09 выполнены успешные read-only проверки каталога/контакта, затем POST создания клиента Zoho Inventory вернул HTTP `400`.
- После ошибки не появились Zoho contact, deal, quotation или PDF.
- В S10 не появились Zoho contact/deal и не произошло продвижение стадии.
- S02, S07 и S09 создали три test-only эскалации и три ограниченных Telegram-уведомления.
- После сбора evidence ровно эти три записи были разрешены штатным production-сервисом. Readback: 3 `resolved`, 0 `pending`.
- Telegram callback от реального администратора не симулировался: безопасного способа совершить его без выдачи себя за администратора нет.

## Производительность

Задержка считается от ближайшего входящего сообщения до сохранённого ответа Noor.

| ID | Ответов | Средняя | Медиана | Максимум |
|---|---:|---:|---:|---:|
| S01 | 3 | 18,0 с | 10,1 с | 35,8 с |
| S02 | 3 | 11,1 с | 9,3 с | 15,1 с |
| S03 | 3 | 21,1 с | 25,8 с | 26,2 с |
| S04 | 3 | 18,6 с | 11,1 с | 33,9 с |
| S05 | 4 | 7,6 с | 7,0 с | 10,2 с |
| S06 | 3 | 11,1 с | 10,0 с | 13,9 с |
| S07 | 3 | 8,6 с | 9,5 с | 10,8 с |
| S08 | 6 | 16,6 с | 14,4 с | 35,3 с |
| S09 | 4 | 8,2 с | 8,1 с | 10,6 с |
| S10 | 3 | 10,3 с | 10,7 с | 13,6 с |
| S11 | 3 | 6,9 с | 6,8 с | 7,3 с |
| **Всего** | **38** | **12,6 с** | **10,0 с** | **35,8 с** |

## Аудит каждого хода

Все времена ниже — UTC 28 июля 2026 года. `In` — время сохранения входящего сообщения, `Out` — время сохранения ответа. Аргументы инструментов очищены от идентификаторов. Для детерминированных маршрутов отдельный tool-duration не инструментирован, поэтому вместо выдуманного числа указан только end-to-end latency.

Код качества: `F` — фактичность, `S` — продажная ценность, `I` — инициатива, `Q` — уместный вопрос, `P` — персонализация, `O` — обработка возражения, `N` — следующий шаг, `H` — отсутствие выдумок, `L` — язык. `+` — хорошо, `±` — частично, `−` — плохо, `—` — неприменимо.

| ID/ход | In → Out | Latency | Route/model | Tool, результат и duration | Side effect/readback | `F/S/I/Q/P/O/N/H/L` |
|---|---|---:|---|---|---|---|
| S01/1 | 18:30:21 → 18:30:31.083 | 10,1 с | `name-gate` | model-tool нет | Text `sent`, provider ID есть | `+/±/+/+/−/—/+/+/+` |
| S01/2 | 18:30:53 → 18:31:01.043 | 8,0 с | `showroom-location` | model-tool нет; нерелевантный deterministic route | Text `sent` | `+/−/−/−/±/—/−/+/+` |
| S01/3 | 18:31:15 → 18:31:50.819 | 35,8 с | `z-ai/glm-5.2` | `search_products("office desks", max=800)` → OK; `search_products("ergonomic chairs", max=800)` → OK; `advance_stage(greeting→needs_analysis)` → OK; наблюдаемое tool-окно ≈0,23 с | Text и 3 product media `sent`; live SKU/price/stock | `+/+/+/+/+/—/+/±/+` |
| S02/1 | 18:33:46 → 18:33:55.285 | 9,3 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S02/2 | 18:33:57 → 18:34:06.021 | 9,0 с | `showroom-location` | model-tool нет; нерелевантный deterministic route | Text `sent` | `+/−/−/−/±/—/−/+/+` |
| S02/3 | 18:34:07 → 18:34:22.093 | 15,1 с | `verified-policy` | model-tool нет; deterministic escalation | Text `sent`; Telegram HTTP `200`; escalation позже `resolved` | `+/−/−/−/−/—/±/+/+` |
| S03/1 | 18:34:50 → 18:35:01.139 | 11,1 с | `name-gate` | model-tool нет; inline имя/компания не использованы | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S03/2 | 18:35:02 → 18:35:28.211 | 26,2 с | `z-ai/glm-5.2` | `search_products("private workstation desk with privacy panels")` → OK; `search_products("enclosed workstation cubicle privacy screen")` → OK; ≈0,28 с | Text и product media `sent`; SKU/price/stock readback | `+/+/+/+/+/—/+/+/+` |
| S03/3 | 18:35:30 → 18:35:55.848 | 25,8 с | `z-ai/glm-5.2` | `search_products("LUMA 4 person workstation private panels")` → OK; `search_products("4 person private workstation with divider panels")` → OK; ≈0,26 с | Text и product media `sent`; LUMA/NOVO readback | `+/+/+/+/+/—/+/+/+` |
| S04/1 | 18:36:16 → 18:36:27.146 | 11,1 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S04/2 | 18:36:28 → 18:36:38.794 | 10,8 с | `product-quantity-clarify` | model-tool нет; intent искажён | Text `sent` | `−/−/−/±/+/—/±/−/+` |
| S04/3 | 18:36:40 → 18:37:13.919 | 33,9 с | `z-ai/glm-5.2` | `search_products("LUMA four-person workstation private")` → OK; `search_products("NOVO four-person workstation open")` → OK; `get_stock(LUMA 9719-4 SKU)` → 30; `get_stock(NOVO 2400 SKU)` → 36; ≈5,45 с | Text `sent`; два независимых stock readback | `+/+/+/+/+/—/+/±/+` |
| S05/1 | 18:37:38 → 18:37:44.112 | 6,1 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S05/2 | 18:37:45 → 18:37:55.159 | 10,2 с | `selection-confirmation` | model-tool нет; предложение ошибочно распознано как товар | Text `sent` | `−/−/−/±/+/—/−/−/+` |
| S05/3 | 18:37:56 → 18:38:02.937 | 6,9 с | `quote-resume-missing-items` | model-tool нет; рекомендация не выполнена | Text `sent` | `±/−/−/−/+/—/−/±/+` |
| S05/4 | 18:38:04 → 18:38:11.062 | 7,1 с | `quote-resume-missing-details` | model-tool нет; возражение/cross-sell не обработаны | Text `sent` | `±/−/−/−/+/−/−/±/+` |
| S06/1 | 18:38:35 → 18:38:44.969 | 10,0 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S06/2 | 18:38:47 → 18:38:56.600 | 9,6 с | `stock-price-options` | model-tool нет; deterministic live inventory readback, duration отдельно не записана | Text `sent`; CH 616 NEW: AED 295, stock 43 | `+/±/±/+/+/—/+/+/+` |
| S06/3 | 18:38:59 → 18:39:12.868 | 13,9 с | `stock-price-options` | model-tool нет; повторный live inventory readback | Text `sent`; 12 из 43 доступны, но добавлен лишний SKU | `+/±/−/±/+/—/±/+/+` |
| S07/1 | 18:39:32 → 18:39:41.463 | 9,5 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S07/2 | 18:39:42 → 18:39:52.764 | 10,8 с | `verified-policy` | model-tool нет; deterministic escalation вместо no-match | Text `sent`; Telegram HTTP `200`; escalation позже `resolved` | `+/−/−/−/−/—/±/+/+` |
| S07/3 | 18:39:55 → 18:40:00.670 | 5,7 с | `fallback` | model-tool нет | Escalation fallback `sent`; provider ID есть | `+/−/−/−/−/—/±/+/+` |
| S08/1 | 18:41:07 → 18:41:42.254 | 35,3 с | `z-ai/glm-5.2` | `search_products("LUMA 9719-4 workstation walnut", max=6000)` → OK; отдельный tool-duration не записан | Text и 3 product media `sent`; цена/stock readback | `+/+/+/+/−/—/+/±/+` |
| S08/2 | 18:42:02 → 18:42:19.409 | 17,4 с | `selection-confirmation` | model-tool нет; deterministic Zoho selection выбрал неверные модель/количество | Text `sent`; ошибочно LUMA 9719-2 × 8 | `−/−/−/+/−/—/±/−/+` |
| S08/3 | 18:43:32 → 18:43:41.721 | 9,7 с | `quote-resume-missing-details` | model-tool нет; имя сохранено, но quote-state не снят | Text `sent` | `+/−/−/−/+/—/−/+/+` |
| S08/4 | 18:43:43 → 18:44:01.034 | 18,0 с | `selection-confirmation` | model-tool нет; deterministic Zoho selection/readback | Text `sent`; LUMA 9719-4 × 2, total AED 3 766 | `+/±/±/+/+/—/±/+/+` |
| S08/5 | 18:44:02 → 18:44:13.477 | 11,5 с | `quote-resume-missing-details` | model-tool нет; delivery/assembly вопрос проигнорирован | Text `sent` | `−/−/−/−/+/—/−/±/+` |
| S08/6 | 18:44:15 → 18:44:22.688 | 7,7 с | `selection-confirmation` | model-tool нет; deterministic Zoho selection/readback | Text `sent`; коррекция LUMA 9719-4 × 3, total AED 5 649 | `+/±/±/+/+/—/+/+/+` |
| S09/1 | 18:45:13 → 18:45:18.864 | 5,9 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S09/2 | 18:45:36 → 18:45:45.966 | 10,0 с | `exact-quote-missing-details` | model-tool нет; корректный сбор обязательных реквизитов | Text `sent` | `+/±/+/+/+/—/+/+/+` |
| S09/3 | 18:45:48 → 18:45:58.632 | 10,6 с | `exact-quote-deterministic` | `create_quotation(CH 616 NEW black × 4)` → FAIL; Zoho contact POST HTTP `400`; от tool-call до ошибки ≈3,96 с | Text `sent`; Telegram HTTP `200`; contact/deal/PDF readback = 0; escalation позже `resolved` | `+/−/±/−/+/—/±/+/+` |
| S09/4 | 18:46:00 → 18:46:06.173 | 6,2 с | `fallback` | повторного tool-call нет | Escalation fallback `sent`; PDF отсутствует | `+/−/−/−/+/—/±/+/+` |
| S10/1 | 18:47:01 → 18:47:07.467 | 6,5 с | `name-gate` | model-tool нет | Text `sent` | `+/±/+/+/−/—/+/+/+` |
| S10/2 | 18:48:03 → 18:48:13.697 | 10,7 с | `exact-quote-missing-details` | `lookup_customer/create_deal` не вызваны; no-quote intent проигнорирован | Text `sent`; contact/deal readback = 0 | `±/−/−/−/+/—/−/±/+` |
| S10/3 | 18:48:15 → 18:48:28.627 | 13,6 с | `quote-resume-missing-details` | `lookup_customer/create_deal/advance_stage` не вызваны | Text `sent`; contact/deal/stage side effect отсутствует | `±/−/−/−/+/—/−/±/+` |
| S11/1 | 18:49:51 → 18:49:57.786 | 6,8 с | `voice_fallback` | transcription provider POST → HTTP `400`; ≈0,94 с | Fallback `sent`, provider ID есть; unreadable sentinel сохранён | `+/−/−/+/−/—/+/+/+` |
| S11/2 | 18:50:55 → 18:51:02.322 | 7,3 с | `voice_fallback` | transcription provider POST → HTTP `400`; ≈0,95 с | Новый assistant row; отдельной Wazzup-отправки нет из-за dedupe | `+/−/−/+/−/—/+/+/+` |
| S11/3 | 18:51:14 → 18:51:20.556 | 6,6 с | `voice_fallback` | transcription provider POST → HTTP `400`; ≈0,63 с | Новый assistant row; отдельной Wazzup-отправки нет из-за dedupe | `+/−/−/+/−/—/+/+/+` |

## Матрица expected tool → actual tool

| Инструмент/маршрут | Естественный ожидаемый повод | Фактическое использование | Оценка |
|---|---|---|---|
| `search_products` | S01–S05, S07, S08: подбор, private-dash, бюджет, no-match | 9 вызовов только в S01, S03, S04, S08 | Корректен там, где вызван; пропущен в Arabic S02, подборе/возражении S05 и no-match S07 |
| `get_stock` | S04, S06, S09: сравнение, exact SKU, КП | 2 model-tool вызова в S04; S06 и S09 использовали отдельные deterministic live readback | S04 корректно; S06 дублирует лишний SKU; S09 наличие подтверждено, но дальнейшее КП упало |
| `advance_stage` | После discovery и при коммерческом продвижении | 1 вызов в S01 | Сильно недоиспользован; S10 не продвинут |
| `lookup_customer` | Перед созданием КП/CRM opportunity в S09/S10 | 0 наблюдаемых model-tool вызовов; в S09 был внутренний Zoho contact GET | Model-tool пропущен; внутренний lookup не привёл к безопасному create/reuse |
| `create_deal` | S10: явная просьба записать возможность, бюджет и срок | 0 | Пропущен |
| `create_quotation` | S09: явное точное КП после сбора реквизитов | 1, с очищёнными аргументами `CH 616 NEW black × 4`; ошибка Zoho HTTP `400` | Выбран уместно, но транзакция не завершена; PDF отсутствует |
| `escalate_to_manager` | Только настоящий unsupported/no-match или terminal quote failure | 0 model-tool вызовов; 3 deterministic эскалации в S02, S07, S09 | S09 уместна после terminal failure; S02 лишняя; S07 безопасна, но вместо полезного no-match |
| Wazzup product media | S01/S03/S08 после каталожной рекомендации | 11 media + 11 caption audit rows | PASS, все media в `sent` |
| Voice transcription | S11 | 3 provider POST, все HTTP `400` | BLOCKED; fallback безопасен, но outbound dedupe неверен |

## Оценка по чек-листу

Формат вектора: `1/2/3/7 | 4/5/6/8/13 | 9/10/11 | 12/14/15`. Значение `—` означает `not applicable`. Баллы блоков рассчитаны строго по весам 6/9/9/6 из методики.

| ID | Вектор правил | Блоки: Opening / Discovery / Solution / Conversion | Итог |
|---|---|---|---:|
| S01 | `2/2/2/0 \| 2/2/0/2/0 \| 2/2/0 \| 1/1/—` | `4,50 / 5,40 / 6,00 / 3,00` | **18,90** |
| S02 | `2/2/2/0 \| 1/0/0/0/0 \| 0/0/0 \| 1/0/1` | `4,50 / 0,90 / 0,00 / 2,00` | **7,40** |
| S03 | `2/2/1/0 \| 2/2/0/2/0 \| 2/2/0 \| 1/1/—` | `3,75 / 5,40 / 6,00 / 3,00` | **18,15** |
| S04 | `2/2/2/0 \| 2/2/0/2/0 \| 2/2/0 \| 1/1/—` | `4,50 / 5,40 / 6,00 / 3,00` | **18,90** |
| S05 | `2/2/2/0 \| 1/0/0/0/0 \| 0/0/0 \| 1/0/0` | `4,50 / 0,90 / 0,00 / 1,00` | **6,40** |
| S06 | `2/2/2/0 \| 1/1/0/1/— \| 1/—/— \| 1/1/—` | `4,50 / 3,38 / 4,50 / 3,00` | **15,38** |
| S07 | `2/2/2/0 \| 1/0/0/0/— \| 0/0/— \| 1/0/1` | `4,50 / 1,12 / 0,00 / 2,00` | **7,62** |
| S08 | `2/2/0/0 \| 1/1/0/2/0 \| 2/1/0 \| 1/2/—` | `3,00 / 3,60 / 4,50 / 4,50` | **15,60** |
| S09 | `2/2/2/0 \| 1/0/0/1/0 \| 1/—/— \| 1/0/1` | `4,50 / 1,80 / 4,50 / 2,00` | **12,80** |
| S10 | `2/2/2/0 \| 1/0/0/0/0 \| 0/0/— \| 1/0/0` | `4,50 / 0,90 / 0,00 / 1,00` | **6,40** |
| S11 | `0/1/0/0 \| —/—/—/—/— \| —/—/— \| —/—/—` | `0,75 / 0,00 / 0,00 / 0,00` | **0,75** |

Повторяющиеся пробелы чек-листа: Noor почти никогда не обозначает ценность Treejar, не спрашивает профиль бизнеса, не делает искренний комплимент и не предлагает подтверждённый бонус/скидку за комплексный заказ. Главная практическая проблема, однако, не в этих «мягких» правилах, а в потере намерения и преждевременной фиксации quote-state.

## Дословные диалоги и разбор

<a id="evidence-s01"></a>

### S01 — EN: офис на 8 человек, бюджет AED 12 000

**Клиент:**  
Hi! We are furnishing a new office and I need help choosing furniture.

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
My name is Maya, and I am the facilities manager at Cedarline Test Offices.

**Noor:**  
Treejar showroom is in Dubai. Open the location on Google Maps: https://www.google.com/maps/place/Treejar+Trading/@24.9871463,55.1135981,17z

**Клиент:**  
We need desks and ergonomic chairs for 8 employees in Dubai. Our budget is around AED 12,000 total. What would you recommend first?

**Noor:**  
Great news, Maya! I found some solid options that fit well within your budget. Here's what I'd recommend:

---

### 🪑 Ergonomic Chairs (in stock)

1. **Skyland Operative Chair CH 240 M (Grey)** — AED 440 each
   - Breathable mesh back + fabric seat, 2D armrests with PU padding, height adjustment, 4-position lock, supports up to 120 kg. Stock: 12 ✅

2. **Operative Office Chair CH 616 NEW (Black)** — AED 295 each
   - Mesh back + fabric seat, height adjustment, plastic armrests, PU castors. Great value option. Stock: 43 ✅

3. **SkyLand Visitor Chair CH 240 V (Black)** — AED 380 each
   - Adjustable comfort, sleek modern design. Stock: 48 ✅

### 🖥️ Desk Option

- **Computer Desk COMP CD.1059 (White, 1000×600×750 mm)** — AED 123.08 each
   - Compact, elegant, 5-year warranty. **However, only 3 units are currently in stock** and you need 8.

---

### 💰 Budget Estimate (per workstation)

| Combo | Desk + Chair | Per Person | × 8 Total |
|-------|-------------|------------|-----------|
| Best ergonomic | AED 123.08 + AED 440 | AED 563.08 | **AED 4,504.64** |
| Best value | AED 123.08 + AED 295 | AED 418.08 | **AED 3,344.64** |

Both combos are comfortably within your AED 12,000 budget — you'd even have room left for extras like storage or a meeting table!

---

⚠️ **One concern:** The desk model I found only has 3 units available, but you need 8. Would you like me to look into restocking timelines for this desk, or would you prefer alternative desk options? This will help me put together the right recommendation for you.

**Разбор:** финальная рекомендация сильная, бюджет посчитан, дефицит стола назван честно. Провал — нерелевантный адрес шоурума после имени. Формулировка про будущий restocking timeline также обещает действие, которого Noor в диалоге не выполнила.

<a id="evidence-s02"></a>

### S02 — AR: приватные места и кресла для шести сотрудников

**Клиент:**  
مرحباً، أحتاج إلى تجهيز مكتب جديد وأريد مساعدتك في اختيار الأثاث.

**Noor:**  
مرحبًا، أنا Noor من Treejar. هل يمكنني معرفة اسمك لأخاطبك بشكل مناسب؟

**Клиент:**  
اسمي ليان، وأنا مديرة المرافق في شركة Cedarline Test Offices.

**Noor:**  
يقع معرض Treejar في دبي. يمكنك فتح الموقع على خرائط Google هنا: https://www.google.com/maps/place/Treejar+Trading/@24.9871463,55.1135981,17z

**Клиент:**  
نحتاج إلى محطات عمل خاصة وكراسي مريحة لستة موظفين في دبي، والميزانية ١٠٬٠٠٠ درهم. ماذا تقترحين؟

**Noor:**  
أريد أن أكون دقيقًا، لذلك سيتواصل معك مديرنا لتأكيد هذه المعلومة.

**Разбор:** арабский язык и приветствие корректны. Продажная задача не решена: после имени снова появился адрес шоурума, а обычный каталожный запрос ошибочно классифицирован как требующий проверки менеджером.

<a id="evidence-s03"></a>

### S03 — `private-dash/private-desk` и актуальное семейство LUMA

**Клиент:**  
Hi, my name is Omar and I buy for Northstar Test LLC. We need a private-dash setup for 4 staff. What does private-dash map to in your current catalog?

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
By private-desk I mean each person should have privacy panels or an enclosed private workstation, not an open bench.

**Noor:**  
Great question, Omar! I should be upfront: we don't have a product literally called "private desk" in our catalog, but here are the **closest alternatives** that provide privacy panels or enclosed workstations:

1. **Single Workstation SKYLAND LUMA 9719-1**
   - SKU: OF-HAI-Luma-Workstation-RJ 9719-1-Walnut
   - Price: **491.00 AED** each
   - Stock: 34 units available
   - Includes a **screen divider for privacy** and a three-drawer pedestal for storage. This is a dedicated single-person workstation — so for 4 staff you'd need 4 units (total ≈ 1,964 AED).

2. **4-Person Workstation SKYLAND NOVO 2400**
   - SKU: OF-YED-NOVO-Workstation-63LW-1.2T-6-white
   - Price: **1,813.00 AED** total
   - Stock: 31 units available
   - A 4-person face-to-face table with **grey fabric divider panels** for privacy. This covers all 4 staff in one unit.

3. **2-Person Workstation SKYLAND NOVO 1200**
   - SKU: OF-YED-NOVO-Workstation-63LW-1.2T-5-white
   - Price: **1,029.00 AED** each
   - Stock: 47 units available
   - Two-person setup with **privacy panels** per employee. You'd need 2 units for 4 staff (total ≈ 2,058 AED).

All three options provide divider/privacy panels, but they differ in layout — the LUMA gives the most individual privacy (fully separate desks), while the NOVO options are shared benches with dividers.

**One quick question to narrow this down:** Would you prefer 4 fully separate individual desks (most privacy), or would a shared 4-person bench with divider panels be acceptable for your team?

**Клиент:**  
Do you have LUMA or another current private workstation family for four people? Please use the latest catalog names, not a guessed model.

**Noor:**  
Thanks for your patience, Omar. To be upfront: the catalog search returned closest alternatives rather than an exact confirmed match for a "private-desk" product family. Here's what I found:

### Closest Alternatives for a 4-Person Private Workstation

1. **Four Person Workstation — SKYLAND LUMA 9719-4**
   - SKU: OF-HAI-Luma-Workstation-RJ 9719-4-Walnut
   - Price: **1,883.00 AED**
   - Stock: 30 units available
   - Key features: Screen dividers for each user, three-drawer mobile pedestals per person, 25mm E1 laminate chipboard tabletop, 40x40mm powder-coated metal U-shaped frames.
   - This is the LUMA family's 4-person model — each employee gets their own dedicated space with a privacy divider.

2. **4 Person Face-to-Face Table — SKYLAND NOVO 2400**
   - SKU: OF-YED-NOVO-Workstation-63LW-1.2T-6-white
   - Price: **1,813.00 AED**
   - Stock: 31 units available
   - Key features: Grey fabric divider panels for privacy, 25mm melamine-coated tabletop, powder-coated metal legs, integrated cable grommets.

3. **Two Person Workstation — SKYLAND LUMA 9719-2** (×2 units for 4 staff)
   - SKU: OF-HAI-Luma-Workstation-RJ 9719-2-Walnut
   - Price: **941.00 AED** each (×2 = **1,882.00 AED** total)
   - Stock: 13 units available
   - Key features: Screen dividers, mobile pedestals, sturdy metal frames — two 2-person units would give each pair their own enclosed space.

All three include divider panels for privacy. The LUMA 9719-4 is the closest to what you described — a single 4-person workstation with privacy dividers for each staff member.

**One quick question:** Does the LUMA 9719-4's screen-divider style of privacy work for your team, or do you need taller/full-height acoustic panels for more enclosed separation?

**Разбор:** один из лучших диалогов. Noor честно уточнила термин, выполнила четыре реальных поиска, использовала актуальные названия, SKU, цены и остатки, затем сузила выбор вопросом. Минус — проигнорировала имя и компанию, уже присутствующие в первом сообщении.

<a id="evidence-s04"></a>

### S04 — сравнение LUMA 9719-4 и NOVO 2400

**Клиент:**  
Hello. I want to compare a private LUMA four-person workstation with an open NOVO four-person setup for our design team.

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Nadia

**Noor:**  
I have these product references: Hello. I want to compare a private LUMA four-person workstation. Please confirm the quantity for each item so I can check availability and prepare the next step.

**Клиент:**  
Please compare privacy, collaboration, footprint and current price, then recommend one for four designers who collaborate often but need some acoustic separation.

**Noor:**  
Great news, Nadia — both models are in stock and ready to go. Here's a side-by-side comparison based on what the catalog confirms:

---

### 1. 🏷️ **LUMA 9719-4 — Four-Person Workstation**
- **Price:** 1,883.00 AED | **Stock:** 30 available
- **Privacy:** Comes with **screen dividers** between users and a **three-drawer mobile pedestal** for each person — giving each designer a more enclosed, personal zone.
- **Collaboration:** Designed to "foster team efficiency" while maintaining dedicated individual spaces — a balance-leaning-toward-privacy layout.
- **Footprint / Build:** 25 mm E1 laminate chipboard top with 40×40 mm powder-coated metal U-frames (sturdy, slightly heavier frame).
- **Best for:** Teams that lean toward independent focused work with some collaboration.

### 2. 🏷️ **NOVO 2400 — 4-Person Face-to-Face Workstation**
- **Price:** 1,813.00 AED | **Stock:** 36 available
- **Privacy:** Grey **fabric divider panels** between seats — lighter visual separation than full screens, but still provides a degree of acoustic dampening.
- **Collaboration:** Explicitly built for **open-plan offices**; face-to-face seating encourages spontaneous interaction and teamwork.
- **Footprint / Build:** 25 mm melamine-coated top with powder-coated metal legs and **integrated cable grommets** for a clean, organized surface.
- **Best for:** Teams that prioritize collaboration with light privacy.

---

### 📊 Quick Summary

| Dimension | LUMA 9719-4 | NOVO 2400 |
|---|---|---|
| **Privacy** | Higher (screen dividers + pedestals) | Moderate (fabric panels) |
| **Collaboration** | Balanced | Stronger (open, face-to-face) |
| **Price** | 1,883 AED | 1,813 AED |
| **Availability** | 30 in stock | 36 in stock |

---

### 💡 My Recommendation for Your Design Team

Since your four designers **collaborate often but need some acoustic separation**, I'd lean toward the **LUMA 9719-4**. Its screen dividers offer better acoustic and visual privacy per seat, while the shared layout still keeps everyone within arm's reach for teamwork. The individual pedestals also give designers a place to store tools and materials, which is valuable in a creative environment. The difference is only **70 AED** — a small premium for noticeably better separation.

That said, if your designers work very fluidly and constantly bounce ideas across the table, the NOVO's face-to-face open layout might suit that workflow better.

**One quick question:** Do your designers tend to work in longer focused sprints (where acoustic separation matters more), or do they frequently shift between individual and group work throughout the day? That would help me confirm the best fit.

**Разбор:** лучший консультационный ответ прогона. Выполнены два поиска и два точных `get_stock`; есть осмысленное сравнение и рекомендация под реальную работу команды. Промежуточный ответ после имени искажает исходный запрос и необоснованно требует количество.

<a id="evidence-s05"></a>

### S05 — 12 рабочих мест, возражение и дешёвая конфигурация

**Клиент:**  
I need chairs for 12 call-center staff under AED 400 each and compact desks. Could you help?

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Samir

**Noor:**  
I also captured these selected items for manager verification:
- 12 x call-center staff under AED 400 each and compact desks. Could you help?

Before I prepare the quotation, please confirm the exact catalog item or SKU for: 12 x call-center staff under AED 400 each and compact desks. Could you help?. I will use that to prepare the quotation accurately.

**Клиент:**  
They sit for about 8 hours a day, so lumbar support matters. What chair and desk combination would you recommend?

**Noor:**  
I have your details, but I still need the exact item(s) and quantity for each item before I can prepare the quotation.

**Клиент:**  
That still feels expensive. Please give me a cheaper configuration and one relevant cross-sell, but keep the total below AED 7,000.

**Noor:**  
Before I prepare the quotation, please share: company name, or confirm you are buying as an individual; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Разбор:** полный провал intent routing. Клиент просил помощь с выбором, но Noor преобразовала предложение в фиктивный товар, преждевременно зафиксировала quote-state, не ответила про поясницу, бюджет, более дешёвую конфигурацию или cross-sell.

<a id="evidence-s06"></a>

### S06 — точный SKU CH 616 NEW black

**Клиент:**  
Can you check the exact current price and stock for SKU CH 616 NEW black? I may need 12 units.

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Aisha

**Noor:**  
I found these options for 1 chair:

Option 1: Operative Office Chair CH 616 NEW black
- SKU: CH 616 NEW black
- Price: 295.00 AED each
- Stock: 43 available

Option 2: Executive Office Chair CH 616 black
- SKU: CH 616 black
- Price: 220.00 AED each
- Stock: 3 available

Which option would you prefer? I can prepare a formal quotation after that.

**Клиент:**  
Please confirm from live inventory whether 12 units of CH 616 NEW black are available and the exact unit price. Do not prepare a quotation yet.

**Noor:**  
I found these options for 12 chairs:

Option 1: Operative Office Chair CH 616 NEW black
- SKU: CH 616 NEW black
- Price: 295.00 AED each
- Stock: 43 available

Option 2: Executive Office Chair CH 616 black
- SKU: CH 616 black
- Price: 220.00 AED each
- Stock: 3 available

Which option would you prefer? I can prepare a formal quotation after that.

**Разбор:** требуемый SKU подтверждён: 43 штуки по AED 295, значит 12 доступны. Но ответ дважды добавляет похожий, фактически непригодный вариант с остатком 3 и продолжает предлагать КП вопреки явному `Do not prepare a quotation yet`.

<a id="evidence-s07"></a>

### S07 — no-match: лабораторные вытяжки и химстойкие столы

**Клиент:**  
Do you sell laboratory fume hoods and chemical-resistant lab benches for a research facility?

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Rami

**Noor:**  
I want to be accurate, so our manager will confirm this for you.

**Клиент:**  
If there is no exact catalog match, please say so honestly and suggest only relevant office-furniture alternatives that Treejar actually sells.

**Noor:**  
Thank you for your message! 🙏
A manager has been notified and will get back to you shortly.
Please bear with us.

**Разбор:** безопасного выдумывания товара нет, но no-match не обработан. Noor не сказала, что точного совпадения не найдено, не предложила релевантные офисные категории и без необходимости создала эскалацию.

<a id="evidence-s08"></a>

### S08 — память, прерывание и изменение команды с 8 до 12 человек

**Клиент:**  
We are furnishing a Dubai office for 8 people. I am considering two LUMA 9719-4 workstations, walnut finish, with a total furniture budget of AED 6,000.

**Noor:**  
Hello, I'm Noor from Treejar.

Great news — I found some very close matches in our catalog! I should note upfront that I can't confirm the exact item you referenced, but here are the three closest alternatives, all in walnut finish:

---

**1. Four-Person Workstation — SKYLAND LUMA 9719-4**
- **Price:** AED 1,883.00 each
- **Stock:** 30 available
- **Key features:** Four-person layout with screen dividers, three-drawer mobile pedestals per user, 25mm E1 laminate chipboard tabletop, 40×40mm powder-coated metal U-shaped frames.
- **Your plan:** Two of these would seat all 8 people at **AED 3,766 total** — comfortably within your AED 6,000 budget, leaving ~AED 2,234 for any additional items.

**2. Single Workstation — SKYLAND LUMA 9719-1**
- **Price:** AED 491.00 each
- **Stock:** 34 available
- **Features:** Spacious single work surface, screen divider, three-drawer pedestal. You'd need 8 of these = **AED 3,928 total**.

**3. Two-Person Workstation — SKYLAND LUMA 9719-2**
- **Price:** AED 941.00 each
- **Stock:** 13 available
- **Features:** Compact two-person layout with dividers, mobile pedestals, sturdy metal frames. You'd need 4 of these = **AED 3,764 total**.

---

All three options keep you well within your AED 6,000 budget for 8 people. The **LUMA 9719-4** (Option 1) is the closest to what you described and the most cost-efficient per seat.

One quick follow-up: would you like me to use the remaining budget (~AED 2,200) to suggest complementary items like office chairs or storage, or would you prefer to keep it to just the workstations?

**Клиент, повтор из-за неопределённого stdout тестового клиента:**  
We are furnishing a Dubai office for 8 people. I am considering two LUMA 9719-4 workstations, walnut finish, with a total furniture budget of AED 6,000.

**Noor:**  
Great, I can confirm the selected items from our catalog:

1. Two person workstation SKYLAND LUMA 9719-2
   Quantity: 8
   Availability: 14 available (Zoho-confirmed)
   Unit price: 941.00 AED
   Line total: 7,528.00 AED

Total: 7,528.00 AED

Would you like me to prepare a formal quotation for these selected items? I can use this WhatsApp number for the draft. To make the PDF complete, please share: company name, or confirm you are buying as an individual; email; specific delivery address.

**Клиент:**  
Leila

**Noor:**  
Before I prepare the quotation, please share: company name, or confirm you are buying as an individual; specific delivery address; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Клиент:**  
Please remember: 8 people, two LUMA 9719-4 units, walnut, Dubai, budget AED 6,000. Do not create a quotation yet.

**Noor:**  
Great, I can confirm the selected items from our catalog:

1. Four person workstation SKYLAND LUMA 9719-4
   Quantity: 2
   Availability: 30 available (Zoho-confirmed)
   Unit price: 1,883.00 AED
   Line total: 3,766.00 AED

Total: 3,766.00 AED

Would you like me to prepare a formal quotation for these selected items? I can use this WhatsApp number for the draft. To make the PDF complete, please share: company name, or confirm you are buying as an individual; email.

**Клиент:**  
Before we continue, do you provide delivery and assembly in Dubai?

**Noor:**  
Before I prepare the quotation, please share: company name, or confirm you are buying as an individual; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Клиент:**  
Correction: the team is now 12 people, so change the requirement to three LUMA 9719-4 units. Summarize the updated requirements and tell me the next step.

**Noor:**  
Great, I can confirm the selected items from our catalog:

1. Four person workstation SKYLAND LUMA 9719-4
   Quantity: 3
   Availability: 30 available (Zoho-confirmed)
   Unit price: 1,883.00 AED
   Line total: 5,649.00 AED

Total: 5,649.00 AED

Would you like me to prepare a formal quotation for these selected items? I can use this WhatsApp number for the draft. To make the PDF complete, please share: company name, or confirm you are buying as an individual; email.

**Разбор:** основная модель правильно нашла LUMA 9719-4 и рассчитала два места по четыре человека. После дубликата детерминированный маршрут ошибочно выбрал 8 двухместных LUMA 9719-2 и вышел за бюджет. Явное повторение требования восстановило правильный товар и количество; последующая коррекция на 12 человек тоже обработана верно. Прерывающий вопрос о доставке и сборке полностью проигнорирован, а запрет создавать КП не останавливает предложения перейти к PDF.

<a id="evidence-s09"></a>

### S09 — полное коммерческое предложение и PDF

**Клиент:**  
Please prepare a formal quotation for exactly 4 x CH 616 NEW black at the current confirmed price.

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Fatima

**Noor:**  
Before I prepare the quotation, please share: company name, or confirm you are buying as an individual; specific delivery address; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Клиент:**  
Name: Fatima Noor Test. Company: Cedarline E2E 20260728. Email: fatima.noor.e2e.20260728@example.com. Delivery address: Office 1204, Test Tower, Business Bay, Dubai, UAE. Please quote exactly 4 x CH 616 NEW black.

**Noor:**  
I couldn't finalize the exact quotation automatically. A manager has been asked to verify exact price and availability before we make a commitment.

**Клиент:**  
Yes, proceed with the quotation for exactly 4 x CH 616 NEW black. Send the PDF only to this test WhatsApp chat.

**Noor:**  
Thank you for your message! 🙏
A manager has been notified and will get back to you shortly.
Please bear with us.

**Разбор:** `create_quotation` действительно вызван с `CH 616 NEW black × 4`. После успешных read-only запросов POST создания клиента Zoho Inventory вернул HTTP `400`; Noor честно не выдумала КП и эскалировала. Однако целевой результат — клиент, сделка/КП, PDF, доставка и readback — не достигнут. В runtime metadata дополнительно видны ошибки извлечения: число из синтетического названия компании попало в кандидат телефона, а адрес был сокращён до первой части.

<a id="evidence-s10"></a>

### S10 — CRM opportunity без КП

**Клиент:**  
We are planning to buy 20 CH 616 NEW black chairs this month and want help moving the project forward, but no quotation yet.

**Noor:**  
Hello, I'm Noor from Treejar. May I know your name so I can address you properly?

**Клиент:**  
Yusuf

**Клиент, повтор из-за неопределённого stdout тестового клиента:**  
Yusuf

**Noor:**  
Before I prepare the quotation, please share: company name, or confirm you are buying as an individual; specific delivery address; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Клиент:**  
Company: Horizon E2E Test LLC. Budget: AED 7,000. Decision expected within two weeks. Please record this sales opportunity and tell me the next commercial step without creating a quotation.

**Noor:**  
Before I prepare the quotation, please share: specific delivery address; customer email. I need these details to put the correct customer and delivery information on the PDF.

**Разбор:** явные `no quotation yet` и `without creating a quotation` проигнорированы. Noor не вызвала `lookup_customer`, `create_deal` или `advance_stage`, не записала возможность и не предложила коммерческий следующий шаг.

<a id="evidence-s11"></a>

### S11 — голосовой файл

Один и тот же валидный публичный FLAC-пример речи был подан трижды с разными входящими message ID.

**Вход 1 / сохранённая транскрипция:**  
[System: Unreadable voice message (error during processing)]

**Noor:**  
Sorry, I couldn't understand the voice message. Could you please type it instead?

**Вход 2 / сохранённая транскрипция:**  
[System: Unreadable voice message (error during processing)]

**Noor:**  
Sorry, I couldn't understand the voice message. Could you please type it instead?

**Вход 3 / сохранённая транскрипция:**  
[System: Unreadable voice message (error during processing)]

**Noor:**  
Sorry, I couldn't understand the voice message. Could you please type it instead?

**Разбор:** production-обработчик распознал тип `voice`, но каждый запрос к провайдеру транскрипции получил HTTP `400 Bad Request`. Безопасный fallback корректен и появляется в БД примерно за 7 секунд. Из трёх разных входящих сообщений Wazzup-аудит содержит только одну исходящую fallback-отправку, поэтому повторная клиентская видимость не доказана. Поскольку файл пришёл не из Wazzup-хранилища, результат нельзя обобщать на provider-originated голосовой файл без отдельного ручного canary.

## Зафиксированные дефекты

| Beads | Приоритет | Дефект | Сценарии |
|---|---:|---|---|
| `tj-ee5f.6` | P1 | После name gate исходное намерение превращается в адрес шоурума, искажённое количество или преждевременное КП | [S01](#evidence-s01), [S02](#evidence-s02), [S03](#evidence-s03), [S04](#evidence-s04), [S05](#evidence-s05) |
| `tj-ee5f.7` | P1 | Обычный арабский подбор и честный no-match ошибочно эскалируются | [S02](#evidence-s02), [S07](#evidence-s07) |
| `tj-ee5f.8` | P1 | Quote-state перехватывает discovery, возражение, прерывание и CRM next-step | [S05](#evidence-s05), [S08](#evidence-s08), [S10](#evidence-s10) |
| `tj-ee5f.9` | P1 | Создание клиента Zoho Inventory возвращает `400`; КП и PDF не создаются | [S09](#evidence-s09) |
| `tj-ee5f.10` | P1 | Голос не транскрибируется; разные входящие сообщения дедуплицируют fallback | [S11](#evidence-s11) |

Дополнительное наблюдение для исправления вместе с `tj-ee5f.8`: exact-SKU маршрут S06 подтверждает нужный остаток, но навязывает похожую позицию с недостаточным количеством и продолжает предлагать КП после явного запрета.

## Рекомендации

1. Сначала исправить восстановление pending intent после name gate и запретить автоматический переход в quote-state без явного согласия клиента.
2. Затем исправить создание/поиск тестового клиента Zoho Inventory и разбор реквизитов; повторный live-тест КП должен доказать contact → quotation → PDF → Wazzup → readback → безопасную очистку.
3. Добавить регрессии на арабский каталог, no-match, возражение, прерывание вопросом и `no quotation yet`.
4. Проверить voice flow на настоящем provider-originated вложении с тестового WhatsApp и отдельно исправить дедупликацию fallback по входящему message ID.
5. Для exact-SKU запроса отвечать ровно по запрошенной позиции и количеству; похожие варианты показывать только по запросу или при недостаточном остатке.
6. Начать записывать duration/result каждого внешнего инструмента и фактическую стоимость model call в структурированный audit, а не восстанавливать их из текстового лога.
7. После исправлений повторить только проваленные сценарии, а затем один связный journey от первого запроса до КП и следующего контакта.

## Итоговое решение

Noor уже умеет выполнять полезную каталоговую консультацию и выдавать сильные, grounded рекомендации, особенно для LUMA/NOVO. Но релиз нельзя считать принятым как полноценный AI sales assistant: пять P1-дефектов затрагивают сохранение намерения, подбор, objection handling, CRM, КП/PDF и голос. Код и production-релиз в рамках этого теста не изменялись; исправления и повторные тесты не выполнялись.
