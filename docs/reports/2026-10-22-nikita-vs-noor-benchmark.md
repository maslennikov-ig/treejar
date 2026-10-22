# Сравнительный тест на идентичных сценариях: Никита (`+971 52 320 9235`) vs Noor (`gpt-6-luna`)

- **Дата прогона:** 22 октября 2026 (`11:41–12:04 UTC` / `14:41–15:04 МСК`)
- **Сырой лог перехваченных вебхуков Никиты:** `docs/reports/2026-10-22-nikita-shadow-test-raw.jsonl`
- **Эталонный прогон Noor на тех же сценариях:** `79262810921#tj-check-0924-A..I` и `docs/reports/2026-09-23-tester-feedback-replay-rerun-a.json`

---

## 1. Главный инсайт: кто такой «Никита»

При перехвате вебхуков с боевого канала `+971 52 320 9235` (`channelId: 13c71a7f-cf9d-4df2-8b27-11ea67e6b0d9`) выяснилось, что **«Никита» — это не живой менеджер, а сторонний текстовый ИИ-бот (`Nikita — our AI assistant` / `Treejar's virtual sales assistant`)**, подключённый через прокси `audit.treejartrading.ae`.

При этом сама инфраструктура клиента (`audit.treejartrading.ae`) **уже в реальном времени пересылает копии всех вебхуков Wazzup** на наш сервер `https://noor.starec.ai/api/v1/webhook/wazzup`.

---

## 2. Сводная таблица сравнения: Никита vs Noor

| Критерий / Сценарий | Бот «Никита» (`+971 52 320 9235`) | Наш бот «Noor» (`noor.starec.ai`) | Кто лучше и почему |
|---|---|---|---|
| **1. Скорость первого ответа по сути** | **7 мин 27 сек – 7 мин 48 сек** (сначала шлёт шаблонную заглушку «подождите до 15 минут», и только через ~7,5 минут отвечает по делу) | **20–40 секунд** (сразу отвечает по сути с реальными товарами, ценами и фото) | **Noor в 12–15 раз быстрее.** В WhatsApp ожидание 7–15 минут убивает конверсию горячего лида. |
| **2. Скорость ответа на 2-й и следующие ходы** | **5 мин 16 сек – 5 мин 33 сек** (`11:58:28` → `12:03:44`) — искусственная задержка/батчинг на каждом шаге диалога | **13–28 секунд** на каждый ход | **Noor отвечает в режиме живого диалога**, у Никиты клиент ждёт по 5+ минут каждого ответа. |
| **3. Распознавание имени клиента (EN и AR)** | **Провал в обоих языках:**<br>• На `"Hi, I'm Nadia..."` спрашивает: *"May I ask who I'm speaking with?"*<br>• На арабском `"مرحباً، اسمي ليان"` («Привет, меня зовут Лаян») через 6,5 минут пишет: *«Я заметил, что имя не пришло чётко в вашем сообщении — как вас зовут?»* (`لاحظت أن الاسم لم يصل بشكل واضح في رسالتكم — ما اسمكم الكريم؟`) | **100% распознавание:** сразу обращается по имени (`Nadia`, `Aisha`, `Layan`) и не переспрашивает то, что клиент уже сказал | **Noor.** Ошибка Никиты на арабском («ваше имя не пришло чётко», когда клиент написал `اسمي ليان` вторым словом) выглядит как откровенный сбой бота. |
| **4. Фотографии товаров в WhatsApp** | **0 фотографий (`type: text`).** Вместо картинок вставляет в текст сырые ссылки вида `https://treejartrading.ae/product/f4779ca19c9b4018b4a1f98cfa941f30` | **Настоящие фото товаров в WhatsApp** (`type: image`) по каждому предложенному артикулу + умение прислать фото повторно по просьбе | **Noor.** Покупатель мебели в WhatsApp выбирает глазами по фото, а не кликает по длинным ссылкам с UUID. |
| **5. Точность характеристик (`LUMA 9719-4` vs `NOVO 2400`)** | **2 фактические галлюцинации:**<br>1. Утверждает, что `NOVO 2400` — это *«fully open face-to-face bench, better suited to teams that want zero separation»* (хотя в каталоге у NOVO 2400 есть **серые тканевые перегородки** `Grey fabric divider panels`).<br>2. Забывает про **тумбы (3-drawer mobile pedestals)** у `LUMA 9719-4` и утверждает, что перегородки к LUMA докупаются отдельно через менеджера (*«we also do desk-mounted screen dividers that can be added to this workstation — our manager would quote those separately»*), хотя они уже входят в комплект! | **Строго по каталогу (Claim Contract):** точно указывает, что у `LUMA 9719-4` в комплекте перегородки и мобильная тумба на 3 ящика для каждого из 4 мест, а у `NOVO 2400` — серые тканевые перегородки и кабель-каналы. Честно говорит, что акустический рейтинг в каталоге не указан. | **Noor.** У нас работает двухуровневая защита от галлюцинаций (`claim_contract.py`), а Никита выдумывает комплектацию и отговаривает от `NOVO 2400` ложным тезисом про «zero separation». |
| **6. Доставка и сборка (Дубай, 3 станции `LUMA 9719-4`)** | **Выдумывает цену сборки:** пишет *«Assembly is 30 AED per item, so 3 workstations = 90 AED»* (30 дирхамов за сборку 4-местной станции с 4 тумбами) и тут же противоречит себе, говоря, что точный расчёт сделает менеджер. | **Честно и по регламенту (`docs/faq.md` Q9–Q10):** подтверждает доставку и профессиональную сборку в Дубае, считает точную сумму позиций (`3 × 1,883 = AED 5,649` при бюджете `AED 6,000`) и переводит к оформлению КП без выдуманных тарифов. | **Noor.** Выдуманная Никитой цена сборки 30 AED за 4-местную станцию приводит к прямым убыткам или конфликту с клиентом при выставлении реального счёта. |
| **7. Проверка точного SKU и микса (`1 × CH 616 NEW black + 3 × CH 460 black`)** | Считает арифметику (`295 + 2403 = 2698 AED`), но для `CH 616 NEW black` пишет `stock 3` (путает с устаревшим остатком другой модели `CH 616 black`), а в конце предлагает клиенту самому идти оформлять заказ на сайт (*«or do you want to go straight to checkout on the site?»*). | Проверяет живой снимок Zoho Inventory, фиксирует выбранный набор в состоянии диалога (`1 × CH 616 NEW black + 3 × CH 460 black = AED 2,698`) и сам формирует официальное PDF-КП прямо в чате. | **Noor.** |
| **8. Выход за пределы каталога (`Lab fume hoods`) и Эскалация (опт / стол 4.5 м на заказ)** | Корректно говорит, что лабораторных вытяжек нет, а стол 4.5 м и опт 55 рабочих мест передаст менеджеру (называя неподтверждённый срок *«4-6 weeks lead time typically»* и требуя *«Trade License and VAT certificate»*). | Честно отсекает нецелевой ассортимент без выдуманных сроков производства (поскольку они зависят от фабрики и объёма — `docs/faq.md` Q9) и создаёт карточку эскалации с кнопками в Telegram и в очереди `/dashboard/`. | **Noor** (безопаснее по обещаниям сроков и имеет готовую очередь эскалаций в Telegram + `/dashboard/`). |
| **9. Генерация PDF-КП (Quotation) и запись в Zoho CRM** | **Не умеет.** Отправляет клиента либо на сайт, либо ждать живого менеджера. | **Полный цикл:** сам создаёт `Sales Order / Estimate` в Zoho Inventory, генерирует брендированный PDF и отправляет файл прямо в WhatsApp + ведёт сделку в Zoho CRM. | **Noor.** |

---

## 3. Дословные цитаты из перехваченных ответов Никиты vs Noor

### Сценарий А (Надя — офис на 4 человек в Дубае, сравнение `LUMA 9719-4` и `NOVO 2400`)

- **Запрос клиента:**
  > Turn 1: `Hi, I'm Nadia. We're furnishing a new office in Dubai for four people. Can you help us choose the furniture?`
  > Turn 2: `Please compare LUMA 9719-4 and a NOVO 2400 four-person setup for our team. What are the differences in privacy, collaboration and current price?`
  > Turn 3: `We're a design team. We collaborate often, but each person needs some privacy. Which would you recommend for us, and why?`

- **Ответ Никиты (через 7 мин 48 сек на 1-й ход + ещё 5 мин 16 сек на 2-й ход):**
  > **Отбивка (11:41:54):** *"Hello and welcome to Treejar Trading! 👋 May I ask who I'm speaking with? Our first available manager will reply to you shortly. If no manager is free, Nikita — our AI assistant — will join within 15 minutes..."*
  >
  > **Ход 1–2 (11:49:31):** *"Good to meet you! Here's the comparison for your 4-person setup:*
  > *Four person workstation SKYLAND LUMA 9719-4 — 1883 AED https://treejartrading.ae/product/four-person-workstation-skyland-luma-9719-4 Walnut wood finish, warmer executive look. Layout gives each person a defined desk bay — a bit more visual privacy and separation between seats.*
  > *4 Person Face to Face Table SKYLAND NOVO 2400 — 1813 AED https://treejartrading.ae/product/4p-ws-table-skyland-novo-2400 White finish, open face-to-face bench layout — four people sit close together, better for teams that talk and collaborate a lot, less visual separation..."*
  >
  > **Ход 3 (12:03:44):** *"For your mix — frequent collaboration but each person still needs some privacy — I'd recommend the LUMA 9719-4... The NOVO 2400 is a fully open face-to-face bench, better suited to teams that want zero separation. If you want even more privacy per seat later, we also do desk-mounted screen dividers that can be added to this workstation — our manager would quote those separately."*

- **Ответ Noor (за 18–40 секунд + фотографии обеих станций в WhatsApp):**
  > **Ход 1:** *"Hello, I'm Noor from Treejar... Nadia, for your four-person Dubai office, these workstations are a good starting point:*
  > *• SKYLAND LUMA 9719-4 — AED 1,883. A four-person workstation with screen dividers and a three-drawer mobile pedestal for each user.*
  > *• SKYLAND NOVO 2400 — AED 1,813. A four-person face-to-face workstation with cable grommets and grey fabric divider panels."*
  >
  > **Ход 2–3:** *"For your four-person office, I’d lean toward LUMA 9719-4: it includes a three-drawer mobile pedestal for each person, plus screen dividers. It’s AED 1,883 for the full four-person workstation, with 30 currently in stock. NOVO 2400 is AED 1,813, with 21 in stock. I’d choose it if you prefer a face-to-face layout with integrated cable grommets. Would you like to proceed with LUMA as your preferred option?"*

---

### Сценарий В (Лаян — арабский язык, офис на 6 человек, бюджет 10 000 AED)

- **Запрос клиента:**
  > `مرحباً، اسمي ليان. أحتاج إلى تجهيز مكتب لستة موظفين في دبي بمحطات عمل توفر الخصوصية وكراسٍ مريحة. الميزانية ١٠٬٠٠٠ درهم. ماذا تقترحين؟`
  > *(«Здравствуйте, меня зовут Лаян. Нужно оборудовать офис для шести сотрудников в Дубае: рабочие места с приватностью и удобные кресла. Бюджет 10 000 дирхамов. Что предложите?»)*

- **Ответ Никиты (через 6 мин 40 сек):**
  > `مرحباً بكم في Treejar Trading! أنا نيكيتا، المساعدة الافتراضية للمبيعات. يسعدني مساعدتكم في تجهيز مكتب لستة موظفين.`
  > `لاحظت أن الاسم لم يصل بشكل واضح في رسالتكم — ما اسمكم الكريم؟` *(«Я заметил, что имя не пришло чётко в вашем сообщении — как вас зовут?» — хотя имя `ليان` написано во втором слове!)*

---

### Сценарий Г (Доставка и сборка в Дубае для 3 × `LUMA 9719-4`, бюджет 6 000 AED)

- **Запрос клиента:**
  > `We also need three LUMA 9719-4 workstations in walnut for 12 people in Dubai, budget AED 6,000. Do you provide delivery and assembly in Dubai, and how much does it cost?`

- **Ответ Никиты (через 5 мин 21 сек):**
  > *"3 x Four person workstation SKYLAND LUMA 9719-4 — 1883 AED each = 5649 AED... This comes to 5649 AED, which is already above your 6,000 AED budget once VAT is added (5649 + 5% VAT ≈ 5931 AED) [прим.: 5931 AED меньше 6000 AED, но Никита пишет «already above your 6,000 AED budget»!]... Assembly is 30 AED per item, so 3 workstations = 90 AED, optional at checkout."*

---

## 4. После эпика `tj-asty` (22 октября 2026): Noor закрывает все пункты, где Никита был сильнее

Ветка `codex/tj-asty-surpass-nikita`, проверка локальная, на прод **не выкатывалось**. Живой прогон через настоящую модель `openai/gpt-6-luna` сделан локально, без отправки сообщений в WhatsApp: `scripts/scenario_replay.py --live`, всего потрачено **$0.062** из разрешённых $0.08.

| Критерий, где Никита был сильнее | Никита | Noor после `tj-asty` | Доказательство |
|---|---|---|---|
| **Арифметика позиций и пакета** (`Qty × цена = итог`, станция + кресла) | Считает сам, без проверки | Итоги считает код и передаёт модели готовыми строками `Verified line math` / `Verified multi-item total` / `Verified turnkey package math`. Сценарий B: `1 × CH 616 NEW black + 3 × CH 460 black = 2,698 AED без НДС (2,832.90 AED с НДС)`. Сценарий Лаян: `NOVO 3600 + 6 × CH 145 = 6,060 AED без НДС / 6,363 AED с НДС, в рамках бюджета 10,000 AED` | `tool_evidence` в сценариях B и C-Layan: pass (live + dry) |
| **НДС 5% и сверка с бюджетом** | `5,931 AED` назвал «выше бюджета 6,000 AED» | Каждая цена в выдаче инструмента подписана «без НДС; X с НДС». Вердикт по бюджету считает код: «укладывается в бюджет и без НДС, и с НДС, остаётся 68.55 AED после НДС». Ответ Noor в D2: *«3 × SKYLAND LUMA 9719-4 fits your AED 6,000 total budget: AED 5,649 before VAT or AED 5,931.45 including 5% VAT, leaving AED 68.55 after VAT. There are 30 units in stock.»* | D-Rami turn 2: `tool_evidence` + `positive_answer`: pass |
| **Передача менеджеру** (опт 20+, мебель на заказ, товары вне каталога) | Передаёт, но называет неподтверждённые сроки («4-6 weeks») и требует Trade License | Три маршрута из правила Виктора. На опт и мебель на заказ Noor передаёт диалог менеджеру (статус `pending`). В том же ответе даёт 2–3 стандартных позиции из наличия с ценой без НДС, фото и ссылками, а в конце задаёт один вопрос для брифа: компания, сроки, место доставки. Сроки и скидки не выдумывает | C-Layan turn 2: `b2b_handoff_with_references` + `escalation_route`: pass |
| **Запрос товара вне каталога** (лабораторные вытяжки) | «Нет в ассортименте» | Честно говорит, что этого нет в каталоге, отправляет менеджеру запрос на поиск поставщика и **не ставит бота на паузу**: остальные вопросы клиента получают полный ответ в том же и следующем ходе | D-Rami: `escalation_route` (`pause_bot=false`, статус `none`): pass |
| **Ссылки на карточки товаров** | Ссылки текстом, 0 фото | И фото в WhatsApp, и ссылка `https://treejartrading.ae/product/<slug>` в одном ответе. Сырые ссылки на файлы изображений (`r2.dev`) в текст по-прежнему не попадают | A turn 2: `tool_evidence` + запрет `r2.dev`: pass |
| **Окно ожидания менеджера на 1-м сообщении** | 15 мин на первый ход и ~5 мин на каждый следующий | Настройка `first_turn_manager_grace_seconds`, по умолчанию 0, то есть ответ сразу. Окно действует только на первый ход нового диалога, по будням UAE (`first_turn_grace_weekdays_only`). Все следующие ходы ждут 5 с. Если ответил живой менеджер, бот замолкает (`manual_takeover`) | `tests/test_first_turn_grace.py` (18 тестов) |
| **Скорость** | 7.5 мин / 5.3 мин | Самый долгий ход в живом прогоне — 47 с (сценарий C, ход с расчётом), обычно 17–38 с | `elapsed_s` в квитанции |

Сохранены все прежние преимущества Noor: фото в WhatsApp, живой остаток из Zoho (`30 in stock`, `CH 616 NEW black = 1`), расчёт КП, отсутствие выдуманных характеристик, распознавание имени (`customer_name = ليان` в состоянии диалога), изоляция `test0665`.

**Квитанции прогона:**
- `docs/reports/2026-10-22-surpass-nikita-replay.json` — все 5 сценариев, $0.036.
- `docs/reports/2026-10-22-surpass-nikita-replay-rerun.json` — повтор C, C-Layan и D-Rami после правок, $0.017.
- `docs/reports/2026-10-22-surpass-nikita-replay-layan.json` — финальный C-Layan, все проверки pass, $0.009.

**Что осталось незакрытым (честно):**
- В спецификации сказано, что в `docs/faq.md` Q9–Q10 есть «бесплатная доставка по Дубаю от 2,000 AED, иначе 130 AED». Таких цифр в FAQ **нет**. Noor подтверждает доставку и сборку, но стоимость доставки не называет: «isn't confirmed and can be included in a quotation». Нужен ответ клиента о тарифах доставки, тогда их можно добавить в одобренный FAQ.
- Классификатор поиска иногда помечает подбор под общий запрос как «точного совпадения нет». Ответ это смягчает, но до конца не убирает. Это старая особенность, к `tj-asty` она не относится.
- Ответы модели немного различаются от прогона к прогону. Арифметику, вердикт по бюджету, маршруты передачи и ссылки гарантирует код, а не модель.
