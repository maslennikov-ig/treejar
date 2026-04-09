**Проект:** База знаний для ИИ-продавца Treejar
**Дата:** 13.09.2025
**Владелец:** Treejar (Viktor)

---

## **1\) Цели**

* Единая, регулярно обновляемая база товаров на основе одного канонического источника: `https://new.treejartrading.ae/api/catalog`.
* Персонализация ответов ИИ по данным клиента из Zoho CRM (история, сегмент, цены/скидки, предпочтения).
* Устранение конфликтов между несколькими каталогами: customer-facing product data берутся только из Treejar Catalog API; Zoho Inventory остаётся операционным контуром.

---

## **2\) Источники данных**

* **Treejar Catalog API** (`https://new.treejartrading.ae/api/catalog`) — единственный источник истины по customer-facing catalog data: slug, SKU/артикул, название, описание, категории, фото, price, stockQuantity, availability.
* **Zoho Inventory (API)** — операционные данные для quotation / SaleOrder / служебных процессов; не канонический источник customer-facing каталога.
* **Прайс-листы / спецусловия (CSV/XLSX/Google Sheets)** — только если заказчик отдельно утверждает их как источник персональных ценовых правил.
* **Zoho CRM (API)** — клиенты, сегменты/прайс-типы, скидки, контакты, история покупок/лидов, предпочтения, адреса доставки, налоговый статус (VAT/TRN).

📌 Примечание: базовый ключ сопоставления — **SKU / артикул**; для customer-facing каталога canonical record приходит из Treejar Catalog API.

---

## **3\) Модель данных (основные таблицы)**

* **products:** sku\*, name\_en, name\_ru, category, subcategory, uom, base\_price\_aed, status, created\_at, updated\_at
* **product\_content:** sku\*, description\_en, description\_ru, spec\_json, keywords, source\_priority, last\_enriched\_from
* **media:** sku\*, image\_url, quality\_score, source, is\_primary, last\_checked\_at
* **inventory:** sku\*, warehouse, qty\_on\_hand, qty\_reserved, qty\_available, updated\_at
* **pricing:** sku\*, price\_type (base|promo|dealer|segment\_\*), currency, amount, valid\_from, valid\_to, source
* **price\_rules:** segment, min\_qty, discount\_type (percent/fixed), discount\_value, stackable(bool)
* **crm\_accounts:** account\_id\*, name, segment, vat\_number, billing\_address, shipping\_address, contacts\[\], preferences\_json, blacklisted(bool), updated\_at
* **crm\_history:** account\_id\*, event\_dt, event\_type (quote|order|return|support), payload\_json
* **lineage (журнал происхождения):** sku\*, field, value, source, fetched\_at, hash

(\*) ключевые поля

**Связи (ER-контуры):**

* products 1—\* product\_content / media / inventory / pricing
* crm\_accounts 1—\* crm\_history
* pricing связывается с products по sku; персонализация — через price\_rules \+ сегмент из crm\_accounts.

---

## **4\) Политика слияния данных (merge)**

* **Каталог, фото, описания, категории, customer-facing price/availability:** только Treejar Catalog API.
* **Операционные поля для внутренних процессов:** Zoho Inventory, если они нужны для quotation / SaleOrder / fulfilment.
* **Фото:** дедуп по URL и pHash; хранить 1 primary \+ до 6 secondary.
* **Конфликты данных:** если Treejar Catalog API и Zoho Inventory расходятся, для общего customer-facing каталога использовать Treejar Catalog API, но перед точным обещанием по цене/наличию Noor обязан подтвердить данные через Zoho.
* **Описание:** брать из Treejar Catalog API; дополнительные структурированные параметры складывать в `spec_json` при наличии.

### **4.1\) Правила поведения Noor при catalog/Zoho split**

* **Общий каталог:** Treejar Catalog API — единая truth для поиска, карточек, фото, категорий и первичного product discovery.
* **Точный вопрос о цене/наличии:** если клиент спрашивает про конкретную цену или наличие, Noor делает финальную проверку через Zoho перед обещанием клиенту.
* **Триггер на quotation:** КП создаётся только когда у клиента уже подтверждены точные `SKU + quantity`.
* **Отправка quotation:** даже после успешной Zoho-проверки сохраняется текущий `manager approval` перед отправкой КП клиенту.
* **Mismatch:** если товар есть в Treejar Catalog API, но отсутствует в Zoho, Noor может показать его как вариант, но не обещает цену/наличие, не создаёт КП, переводит разговор на менеджера и отправляет операционный bug alert в Telegram.
* **Владелец качества каталога:** заказчик подтверждает, что команда сайта отвечает за актуальность данных в Treejar Catalog API и исправление багов источника.

---

## **5\) Интеграции и расписание обновлений**

* **Treejar Catalog API:** базовый sync/catalog refresh по расписанию; частота зависит от SLA сайта и ограничений API.
* **Zoho Inventory API:** отдельный операционный sync для quotation / SaleOrder / service-level checks.
* **Прайс-листы / спецусловия:** ручная загрузка или sync только если заказчик подтверждает их как действующий источник персональных ценовых правил.
* **Zoho CRM API:** синк аккаунтов ежедневно, вебхуки для сделок/лидов.

---

## **6\) Качество и валидация**

* Минимум для публикации в ИИ: sku, name, base\_price\_aed, uom, ≥1 фото.
* Валидации: уникальный SKU, цена \> 0, остатки ≥ 0, валюта корректна.
* Автоправила нормализации названий (удаление дубликатов бренда, правильный кейсинг).
* Score карточки (0–100): полнота полей, качество фото, наличие RU-текста, spec\_json.
* Карточки \<70 → очередь «на улучшение».

---

## **7\) Персонализация для ИИ (на базе Zoho CRM)**

* Сегмент клиента (retail, dealer, b2b\_large, VIP и т.п.) → выбор price\_type и правил скидок.
* История покупок → рекомендации аналогов и сопутствующих товаров.
* Предпочтения (цвет, размер, стиль, бюджет) → фильтрация и ранжирование.
* Доставка и налоги → корректный расчёт VAT, сроки и стоимость.
* Канал коммуникации из CRM (WhatsApp/Email) → формат готового оффера.

---

## **8\) Схема полей (маппинг по источникам)**

* **Treejar Catalog API → products/product\_content/media:** sku, slug, name, description, image\_urls, category, price, currency, stockQuantity/inStock.
* **Zoho Inventory → operational inventory/pricing linkage:** sku, item\_id, service-level stock fields, quotation/SaleOrder linkage.
* **Прайс-листы / спецусловия → pricing:** sku, price\_type (dealer, promo и др.), amount, currency, valid\_from/to.
* **Zoho CRM → crm\_accounts/history/price\_rules:** account\_id, segment, contacts, addresses, vat, preferences, deals/orders.

---

## **9\) API для ИИ-продавца (чтение)**

* `GET /kb/products?query=&segment=&limit=` — поиск по названию/ключам, с учётом сегмента.
* `GET /kb/products/{sku}` — карточка товара (контент, цены, остатки, фото).
* `GET /kb/pricing/{sku}?account_id=` — персональная цена/скидки.
* `GET /kb/recommendations?sku=&account_id=` — аналоги/сопутствующие.
* `GET /kb/account/{account_id}` — сводка клиента.

---

## **10\) Алгоритм ответа ИИ**

1. Определить клиента (по телефону/лиду → account\_id, segment).
2. Разобрать запрос (ключевые слова, ограничения: цена, цвет, размер).
3. Найти товары (`/kb/products`), отранжировать: наличие, цена, контент-скор.
4. Для конкретных вопросов о цене/наличии подтвердить данные через Zoho перед обещанием клиенту.
5. Если подтверждены точные `SKU + quantity`, подготовить quotation flow и передать КП на manager approval.
6. Если Treejar item не найден в Zoho, сообщить клиенту о необходимости подтверждения менеджером, создать эскалацию и отправить Telegram bug alert.
7. Записать результат в crm\_history.

---

## **11\) Безопасность**

* Авторизация: OAuth/API-ключи для Zoho.
* Логи и lineage для аудита изменений.
* Персональные данные из CRM — минимизация (ИИ получает только нужные поля).
* Соответствие GDPR/PDPA.

---

## **12\) Этапы работ**

1. Схема БД и репозиторий (DDL \+ миграции).
2. Коннектор Treejar Catalog API (pull, валидация, маппинг).
3. Операционный коннектор Zoho Inventory (quotation / SaleOrder / служебные проверки).
4. Интеграция прайс-листов / спецусловий (если подтверждены заказчиком).
5. Интеграция Zoho CRM (accounts, сегменты, webhooks).
6. Нормализация и lineage для Treejar Catalog API.
7. API для ИИ \+ кэш.
8. Тесты: е2е кейсы, персонализация, офферы.
9. Мониторинг: дашборды цен/остатков, отчёт «карточки \<70».

---

## **13\) Критерии приёмки**

* ≥95% SKU из Inventory доступны через API.
* ≥90% SKU имеют ≥1 фото и описание.
* Цены из Inventory расходятся с другими источниками \<1% SKU.
* Персональные цены корректно учитывают сегменты CRM.
* Время генерации оффера ≤2 сек. (для топ-3 позиций).
* При Treejar/Zoho mismatch Noor не отправляет КП автоматически, создаёт manager escalation и Telegram alert об операционном баге.
