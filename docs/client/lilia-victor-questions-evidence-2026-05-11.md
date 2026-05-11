# Ответ Лилии по вопросам Виктора

Дата: 2026-05-11

Формат: короткий управленческий ответ + доказательства из документов/кода с прямыми ссылками на строки. Для первичных документов используем commit `b989bf0a1014acf01183e08f3f38ff224a67f66e`, чтобы строки не менялись.

## Короткий ответ Лилии

Виктор, я сверила вопросы с исходными материалами и текущей технической реализацией.

1. **Файлы/источники базы знаний:** текущая текстовая база знаний фактически индексирует `docs/faq.md`, `docs/04-sales-dialogue-guidelines.md` и `docs/05-company-values.md`. Каталог товаров, цены, категории и фото — это не файл, а Treejar Catalog API. Zoho CRM/Inventory — операционный контур. Примеры диалогов и КП есть как клиентские обучающие материалы/референсы, но не как основной текстовый индекс в текущем индексаторе.
2. **Правка про дешёвые стулья vs executive:** правка Виктора **в целом правильная**, если клиент явно просил дешёвые/бюджетные стулья или уже выбрал бюджетный сегмент. В таком случае дорогой executive chair нельзя подавать как равнозначную рекомендацию. Но это не абсолютный запрет на executive-модель: её можно показывать только как явно подписанный “premium option / альтернатива выше бюджета” и лучше после уточнения бюджета.
3. **Правила ведения диалога:** заложено 15 основных правил + 3 дополнительных правила: добавлять несколько вариантов в квоту, делать follow-up через сутки/3/7 дней, быстро понять потребность клиента и сделать квоту.
4. **Что должно быть в КП для клиента:** по исходным образцам КП обязательны имя клиента, компания, email и адрес. Номер телефона клиента в обязательных полях не указан. Телефон указан у менеджера в блоке `Quoted by`. В КП должны быть фото товара, SKU, описание, количество, цена за единицу, сумма по позиции, TOTAL, VAT 5%, GRAND TOTAL, terms and conditions. Доставка должна быть отражена: как delivery terms и, если есть стоимость/бонус, отдельной строкой в позициях КП.

## 1. Какие файлы Виктор изначально давал и что сейчас входит в базу знаний

### Что реально индексируется в текущую текстовую knowledge base

> `# 1. Parse FAQ`

Источник: `src/rag/indexer.py`, строка 35 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L35)
Что подтверждает: индексатор отдельно парсит FAQ.

> `faq_path = docs_dir / "faq.md"`

Источник: `src/rag/indexer.py`, строка 36 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L36)
Файл: `docs/faq.md`.

> `# 2. Parse Sales Rules`

Источник: `src/rag/indexer.py`, строка 43 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L43)
Что подтверждает: индексатор отдельно парсит правила продаж/диалога.

> `rules_path = docs_dir / "04-sales-dialogue-guidelines.md"`

Источник: `src/rag/indexer.py`, строка 44 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L44)
Файл: `docs/04-sales-dialogue-guidelines.md`.

> `# 3. Parse Company Values`

Источник: `src/rag/indexer.py`, строка 53 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L53)
Что подтверждает: индексатор отдельно парсит ценности компании.

> `values_path = docs_dir / "05-company-values.md"`

Источник: `src/rag/indexer.py`, строка 54 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/src/rag/indexer.py#L54)
Файл: `docs/05-company-values.md`.

### Что было предоставлено как исходные клиентские материалы

> “Правила ведения диалогов | ✅ Готово”

Источник: `docs/checklist-answers.md`, строка 50 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L50)
Практический файл в репозитории: `docs/04-sales-dialogue-guidelines.md`.

> “Преимущества компании | ✅ Готово”

Источник: `docs/checklist-answers.md`, строка 51 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L51)
Практический файл в репозитории: `docs/05-company-values.md`.

> “Каталог товаров | ✅ | Для Noor канонический каталог теперь закреплён за `https://new.treejartrading.ae/api/catalog`”

Источник: `docs/checklist-answers.md`, строка 53 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L53)
Что подтверждает: каталог не является локальным файлом; это API.

> “Частые вопросы клиентов (FAQ, топ-20) | ✅ Готово”

Источник: `docs/checklist-answers.md`, строка 65 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L65)
Практический файл в репозитории: `docs/faq.md`.

> “Примеры успешных диалогов ... | ✅ 7 успешных + 2 средних”

Источник: `docs/checklist-answers.md`, строка 62 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L62)
Практический файл-описание в репозитории: `docs/dialogue-examples/README.md`.

> “Пример идеального КП ... | ✅ 4 образца”

Источник: `docs/checklist-answers.md`, строка 64 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L64)
Практический файл-описание в репозитории: `docs/sample-quotations/README.md`.

### Что не было предоставлено как готовая база

> “Спеццены / таблица скидок | ⏳ TODO”

Источник: `docs/checklist-answers.md`, строка 54 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L54)
Вывод Лилии: если Виктор просит точные спеццены/правила скидок, в исходных материалах они отмечены как не предоставленные.

> “Типичные возражения и ответы | ⏳ TODO”

Источник: `docs/checklist-answers.md`, строка 66 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/checklist-answers.md#L66)
Вывод Лилии: готовая таблица “возражение → ответ” не была предоставлена.

## 2. Насколько правильная правка про дешёвые стулья и executive chair

Формулировка Виктора:

> “по картинке определил что стул - и предложил два правильно - дешевые стулья одно executive нет - на дешевые стулья предлагать дорогие не верно”

**Оценка Лилии:** правка частично корректная и полезная. Если клиент просит дешёвые стулья, бюджетные стулья или по контексту уже видно бюджетный сегмент, бот должен сначала показывать варианты в этом сегменте. Дорогой executive chair в таком ответе допустим только как отдельно подписанный premium-вариант, а не как основной релевантный вариант.

Почему правка обоснована:

> “Разобрать запрос (ключевые слова, ограничения: цена, цвет, размер).”

Источник: `docs/07-knowledge-base-spec.md`, строка 121 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/07-knowledge-base-spec.md#L121)
Что подтверждает: цена/бюджет — это ограничение запроса, его нужно учитывать при подборе.

> “Найти товары (`/kb/products`), отранжировать: наличие, цена, контент-скор.”

Источник: `docs/07-knowledge-base-spec.md`, строка 122 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/07-knowledge-base-spec.md#L122)
Что подтверждает: ранжирование должно учитывать цену, поэтому дорогой товар не должен попадать в подборку как равный бюджетным, если запрос бюджетный.

> “Наша задача — найти баланс между комфортом сотрудников, долговечностью мебели и вашим бюджетом.”

Источник: `docs/05-company-values.md`, строка 17 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/05-company-values.md#L17)
Что подтверждает: бюджет клиента должен учитываться, а не игнорироваться.

> “В квоту добавлять по возможности несколько вариантов, чтобы клиент мог выбрать ... (разный дизайн, разная ценновая группа)”

Источник: `docs/04-sales-dialogue-guidelines.md`, строка 21 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L21)
Что подтверждает: разные ценовые группы можно показывать, но именно как разные варианты, а не смешивать дорогой executive с бюджетными как одинаково подходящие.

> “Бюджет клиента — 942 AED за стул выше бюджета, но менеджер не спросил бюджет заранее”

Источник: `docs/dialogue-examples/README.md`, строка 379 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/dialogue-examples/README.md#L379)
Что подтверждает: в обучающих примерах отсутствие уточнения бюджета прямо отмечено как проблема.

> “При отсутствии товара/цвета — предлагать 2-3 альтернативы, а не одну”

Источник: `docs/dialogue-examples/README.md`, строка 348 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/dialogue-examples/README.md#L348)
Что подтверждает: альтернатива нужна, но она должна соответствовать ограничению клиента; если ограничение бюджетное, альтернативы тоже должны быть в подходящем ценовом коридоре.

Практическое правило для бота:

- Если клиент пишет “cheap”, “budget”, “affordable”, “low price”, “under X AED” или выбирает бюджетные модели, показываем сначала 2-3 бюджетных варианта.
- Если хочется показать executive chair, он должен идти отдельным блоком: “Premium option, дороже бюджета, но с такими-то преимуществами”.
- Если бюджет не указан, бот должен уточнить бюджет или показать варианты по разным ценовым группам с явными labels: Budget / Mid-range / Premium.
- Если распознавание по фото определило только тип “chair”, этого недостаточно, чтобы предлагать дорогой executive как основной вариант без учета цены, назначения и бюджета.

## 3. Какие правила ведения диалога были заложены

Заложено 15 основных правил и 3 дополнительных.

| # | Правило | Источник |
|---|---|---|
| 1 | Приветствие + имя клиента/бота Сияд + компания Treejar. | `docs/04-sales-dialogue-guidelines.md`, строка 5 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L5) |
| 2 | Вежливое приветствие и представление. | `docs/04-sales-dialogue-guidelines.md`, строка 6 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L6) |
| 3 | Спросить, как обращаться к клиенту. | `docs/04-sales-dialogue-guidelines.md`, строка 7 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L7) |
| 4 | Дружелюбный тон и активное слушание. | `docs/04-sales-dialogue-guidelines.md`, строка 8 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L8) |
| 5 | Создать ощущение интереса к клиенту. | `docs/04-sales-dialogue-guidelines.md`, строка 9 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L9) |
| 6 | Сделать искренний конкретный комплимент. | `docs/04-sales-dialogue-guidelines.md`, строка 10 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L10) |
| 7 | Коротко обозначить ценность Treejar. | `docs/04-sales-dialogue-guidelines.md`, строка 11 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L11) |
| 8 | Задавать уточняющие вопросы: для чего нужен товар, какую задачу решает. | `docs/04-sales-dialogue-guidelines.md`, строка 12 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L12) |
| 9 | Принцип “дрель и дырка”: клиент покупает решение задачи, не просто товар. | `docs/04-sales-dialogue-guidelines.md`, строка 13 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L13) |
| 10 | Формировать комплексное решение шире первоначального запроса. | `docs/04-sales-dialogue-guidelines.md`, строка 14 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L14) |
| 11 | Использовать скидку или бонус при комплексном заказе. | `docs/04-sales-dialogue-guidelines.md`, строка 15 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L15) |
| 12 | Уточнить имя, должность, компанию, email, канал связи. | `docs/04-sales-dialogue-guidelines.md`, строка 16 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L16) |
| 13 | Спросить, чем занимается компания, чтобы понять дополнительные возможности Treejar. | `docs/04-sales-dialogue-guidelines.md`, строка 17 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L17) |
| 14 | Закрытие сделки: подтвердить заказ, детали и следующий шаг. | `docs/04-sales-dialogue-guidelines.md`, строка 18 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L18) |
| 15 | Если клиент не готов: договориться о следующем контакте. | `docs/04-sales-dialogue-guidelines.md`, строка 19 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L19) |
| Доп. 1 | В квоту по возможности добавлять несколько вариантов: разный дизайн, разная ценовая группа. | `docs/04-sales-dialogue-guidelines.md`, строка 21 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L21) |
| Доп. 2 | Делать follow-up через сутки, 3 и 7 дней. | `docs/04-sales-dialogue-guidelines.md`, строка 23 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L23) |
| Доп. 3 | Задача — понять нужду клиента и сделать квоту в кратчайшие сроки. | `docs/04-sales-dialogue-guidelines.md`, строка 25 — [открыть](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/04-sales-dialogue-guidelines.md#L25) |

Отдельное подтверждение: эти же 15 правил включены в чек-лист оценки первичного диалога.

> “Чек-лист оценки первичного диалога / Dialogue Evaluation Checklist”

Источник: `docs/06-dialogue-evaluation-checklist.md`, строка 71 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/06-dialogue-evaluation-checklist.md#L71)

## 4. Какие данные должны быть отражены в КП для клиента

**Ответ Лилии:** в исходных образцах КП обязательными клиентскими данными указаны `Name / Company Name / Email / Address`. Номер телефона клиента в обязательных данных КП не указан. При этом телефон есть у менеджера в блоке `Quoted by`: имя + телефон + email менеджера. Стоимость товара обязательна: цена за единицу и итог по позиции. Также обязательны фото товара, SKU, описание, количество, TOTAL, VAT 5%, GRAND TOTAL и условия. Доставка должна быть отражена: как срок доставки в Terms and Conditions и отдельной строкой в позициях КП, если доставка платная, бесплатная или включает установку.

> “Данные клиента: Name / Company Name / Email / Address”

Источник: `docs/sample-quotations/README.md`, строки 17-18 — [открыть строки](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L17-L18)
Что подтверждает: обязательные клиентские поля в структуре КП — имя, компания, email, адрес. Номер телефона клиента здесь не указан.

> “Quoted by: имя + телефон + email менеджера”

Источник: `docs/sample-quotations/README.md`, строка 42 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L42)
Что подтверждает: телефон в КП предусмотрен для менеджера, который подготовил КП.

> “Reference Image | Фото товара (реальное или каталожное)”

Источник: `docs/sample-quotations/README.md`, строка 23 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L23)
Что подтверждает: в КП должно быть фото каждого товара.

> “Code/SKU | Код модели”

Источник: `docs/sample-quotations/README.md`, строка 24 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L24)
Что подтверждает: в КП должен быть SKU/код модели.

> “Description | Полное описание: материалы, размеры, цвет, гарантия”

Источник: `docs/sample-quotations/README.md`, строка 25 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L25)
Что подтверждает: описание должно включать материалы, размеры, цвет и гарантию.

> “QTY | Количество”

Источник: `docs/sample-quotations/README.md`, строка 26 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L26)
Что подтверждает: количество товара обязательно.

> “Unit Price | Цена за единицу (AED)”

Источник: `docs/sample-quotations/README.md`, строка 27 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L27)
Что подтверждает: стоимость единицы товара обязательна.

> “Total Price | Итого за позицию (AED)”

Источник: `docs/sample-quotations/README.md`, строка 28 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L28)
Что подтверждает: итоговая стоимость по каждой позиции обязательна.

> “TOTAL (сумма без НДС)”

Источник: `docs/sample-quotations/README.md`, строка 31 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L31)
Что подтверждает: общий итог без VAT нужен.

> “VAT 5%”

Источник: `docs/sample-quotations/README.md`, строка 32 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L32)
Что подтверждает: VAT 5% нужно указывать отдельно.

> “GRAND TOTAL”

Источник: `docs/sample-quotations/README.md`, строка 33 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L33)
Что подтверждает: финальная сумма КП обязательна.

> “Delivery: 02-08 working days from order confirmation”

Источник: `docs/sample-quotations/README.md`, строка 37 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L37)
Что подтверждает: срок доставки должен быть в Terms and Conditions.

> “DP | Delivery — FREE OF COST”

Источник: `docs/sample-quotations/README.md`, строка 59 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L59)
Что подтверждает: доставка может быть отдельной строкой позиции, даже если она бесплатная.

> “DP | Delivery + Installation | Professional installation charges”

Источник: `docs/sample-quotations/README.md`, строка 120 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L120)
Что подтверждает: доставка/установка может быть отдельной платной строкой в КП.

> “Delivery включать отдельной строкой (free для крупных заказов)”

Источник: `docs/sample-quotations/README.md`, строка 172 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/sample-quotations/README.md#L172)
Что подтверждает: правило для Noor — включать delivery отдельной строкой.

> “КП формировать и отправлять клиенту после подтверждения точных `SKU + quantity`”

Источник: `docs/03-ai-agent-requirements.md`, строка 29 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/03-ai-agent-requirements.md#L29)
Что подтверждает: КП должно строиться только после подтверждения точных SKU и количества.

> “Отправлять КП в PDF (индивидуальное, на основании данных CRM).”

Источник: `docs/03-ai-agent-requirements.md`, строка 32 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/03-ai-agent-requirements.md#L32)
Что подтверждает: КП должно быть индивидуальным и использовать данные CRM.

> “Бот производит актуальный рассчёт стоимости заказа (товар+доставка)”

Источник: `docs/02-tz-extended.md`, строка 52 — [открыть строку](https://github.com/maslennikov-ig/treejar/blob/b989bf0a1014acf01183e08f3f38ff224a67f66e/docs/02-tz-extended.md#L52)
Что подтверждает: доставка входит в расчет стоимости заказа по ТЗ.

**Итого по вопросу Виктора:** да, строка про доставку должна быть. В Terms and Conditions должен быть срок доставки, а в таблице позиций должна быть отдельная строка `Delivery` / `Delivery + Installation`, если доставка влияет на стоимость или предоставляется как бонус. Обязательность телефона клиента в первичных образцах КП не найдена; обязательны имя, компания, email и адрес.

## Что можно отправить Виктору по файлам

Список текущих доступных файлов/артефактов в репозитории:

- `docs/faq.md` — FAQ / база ответов на типовые вопросы.
- `docs/04-sales-dialogue-guidelines.md` — правила ведения диалога.
- `docs/05-company-values.md` — ценности и преимущества Treejar.
- `docs/dialogue-examples/README.md` — описание примеров успешных/неуспешных диалогов.
- `docs/sample-quotations/README.md` — описание образцов КП и правил формирования quote.
- `docs/06-dialogue-evaluation-checklist.md` — чек-лист оценки диалога.
- `docs/07-knowledge-base-spec.md` — спецификация источников базы знаний и правил работы с каталогом.

Важно: оригинальные скриншоты диалогов и PDF-КП в текущем git-дереве не лежат как отдельные файлы; в репозитории есть текстовые описания этих материалов. Если Виктор просит именно оригиналы файлов, их нужно отдельно запросить/поднять из клиентского хранилища.
