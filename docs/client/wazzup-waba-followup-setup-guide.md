# Инструкция: Wazzup WABA для WhatsApp follow-up после КП

Дата: 2026-05-21

Цель документа - дать ответственному человеку пошаговый чек-лист, чтобы подключить официальный WhatsApp Business API канал в Wazzup, подготовить шаблоны сообщений и прислать нам все данные, нужные для включения автоматических follow-up после КП.

## Зачем это нужно

Бот Noor уже умеет планировать follow-up после отправки КП:

1. Примерно через 23 часа, пока 24-часовое WhatsApp/WABA окно обычно еще открыто.
2. Через 3 дня.
3. Через 7 дней.

После любого ответа клиента follow-up останавливается. Если клиент согласился с КП, бот передает диалог менеджеру. Если клиент задает вопросы до согласия, бот отвечает сам.

Но WhatsApp/WABA ограничивает свободную переписку: когда 24-часовое окно после сообщения клиента закрыто, первым сообщением компании должен быть заранее одобренный WABA template. Поэтому первый follow-up бот старается отправить до закрытия окна обычным текстом, а для follow-up через 3 и 7 дней нужны подключенный WABA-канал и одобренные шаблоны.

## Что нужно подготовить до подключения WABA

Ответственный должен заранее проверить:

1. Есть доступ в Wazzup-аккаунт, где должен работать номер Treejar.
2. Есть личный Facebook-профиль с доступом администратора к Meta Business Portfolio компании.
3. Есть или будет создан Meta Business Portfolio.
4. Есть номер телефона для WABA.
5. Номер можно подтвердить по SMS или звонку.
6. Номер не должен одновременно быть активным в обычном WhatsApp/WhatsApp Business приложении, если Wazzup попросит освободить его для WABA.
7. На сайте компании есть публичные страницы и футер, которые Meta сможет проверить:
   - Privacy Policy или Personal Data Processing Policy отдельной веб-страницей, не PDF/Google Doc.
   - Юридическое название компании.
   - Юридический адрес.
   - Рабочий контактный телефон, если Meta запросит верификацию бизнеса.
8. Данные в документах, футере сайта и Meta Business Portfolio должны совпадать: название, адрес, сайт, email.

## Подключение официального WhatsApp WABA в Wazzup

Откройте Wazzup и выполните подключение официального WhatsApp по документации Wazzup.

Путь в интерфейсе:

1. Wazzup - `Channels`.
2. `WhatsApp`.
3. `WABA`.
4. `Continue`.
5. `Continue with Facebook`.

Дальше Wazzup откроет окно Meta/Facebook. Его нужно пройти до конца.

### Шаг 1. Meta Business Portfolio

Выберите существующий Meta Business Portfolio или создайте новый.

Если создаете новый, заполните:

1. Company Name - строго как в официальных документах.
2. Company Email.
3. Company Website - сайт должен соответствовать требованиям Meta.
4. Company Address - полный юридический адрес.

Важно: Wazzup отдельно предупреждает, что даже небольшие расхождения в названии или адресе могут привести к блокировке или отклонению.

### Шаг 2. WhatsApp Business Account

Выберите существующий WhatsApp Business Account или создайте новый.

При создании укажите:

1. Account name - внутреннее имя аккаунта.
2. Display name - имя, которое увидит клиент.
3. Time zone - для Treejar используйте `Asia/Dubai`, если в Wazzup/Meta доступен выбор.
4. Category.
5. Website.

Display name должен соответствовать бренду и правилам Meta. Если имя будет отклонено, исходящие возможности WABA могут быть ограничены.

### Шаг 3. Номер телефона

Добавьте номер для WABA и подтвердите его кодом из SMS или звонка.

Проверьте:

1. Номер подключается именно в тот Wazzup-аккаунт, где будет работать Treejar.
2. Номер успешно отображается как активный WABA-канал.
3. В Wazzup есть доступ к настройкам канала и шаблонов.

## Шаблоны для follow-up

Нам нужны WABA templates на языках, на которых бот общается с клиентами:

1. English.
2. Arabic.

Russian templates сейчас не нужны, потому что клиентские сообщения бота должны быть только на English или Arabic.

Нужны минимум 4 шаблона для follow-up через 3 и 7 дней:

| Step | When | Language | Purpose |
| --- | --- | --- | --- |
| FU2 | 3 days after quotation | English | Second follow-up |
| FU2 | 3 days after quotation | Arabic | Second follow-up |
| FU3 | 7 days after quotation | English | Final follow-up |
| FU3 | 7 days after quotation | Arabic | Final follow-up |

FU1 обычно не требует template, потому что Noor отправляет его примерно через 23 часа и перед отправкой проверяет, что 24-часовое окно еще открыто. Если окно уже закрыто из-за задержки очереди, выходных, нерабочего времени или поздней отправки КП относительно последнего сообщения клиента, FU1 без template не уйдет. Поэтому FU1 template можно подготовить дополнительно как fallback, но обязательными для запуска остаются FU2/FU3.

Если Wazzup или Meta требуют другой набор из-за категорий, пришлите нам фактический набор, который прошел модерацию.

### Как создать шаблон в Wazzup

Путь в интерфейсе может отличаться, но по документации Wazzup логика такая:

1. Откройте раздел templates/WABA templates.
2. Создайте новый WABA template.
3. Выберите категорию. Для follow-up по уже отправленному КП чаще всего подходит service/utility-сценарий, но итоговую категорию нужно выбрать в Wazzup по правилам Meta.
4. Выберите WABA-канал, с которого будет отправляться шаблон.
5. Укажите язык.
6. Вставьте текст.
7. Если используете переменные, заполните примеры значений для модерации.
8. Отправьте шаблон на модерацию.
9. Дождитесь статуса `Approved`.

Для первой версии лучше делать шаблоны без переменных. Так меньше риск ошибки в порядке переменных и проще подключение в коде.

## Рекомендуемые тексты шаблонов

Ниже тексты, которые можно использовать как основу. Если Wazzup/Meta предложит изменить формулировку, используйте одобренную версию и пришлите нам финальный текст.

### English FU1 free-form / optional fallback template

```text
Hello, this is Noor from Treejar. We sent your quotation earlier. Please let us know if the quotation works for you.
```

### English FU2

```text
Hello, this is Noor from Treejar. We are checking whether you had a chance to review the quotation. Please reply if you have any questions or if it works for you.
```

### English FU3

```text
Hello, this is Noor from Treejar. This is the final follow-up about the quotation we sent. If we do not hear back, we will mark the proposal as no response.
```

### Arabic FU1 free-form / optional fallback template

```text
مرحباً، معك نور من Treejar. أرسلنا لك عرض السعر سابقاً. يرجى إبلاغنا إذا كان العرض مناسباً لك.
```

### Arabic FU2

```text
مرحباً، معك نور من Treejar. نود التأكد مما إذا أتيحت لك فرصة مراجعة عرض السعر. يرجى الرد إذا كان لديك أي سؤال أو إذا كان العرض مناسباً.
```

### Arabic FU3

```text
مرحباً، معك نور من Treejar. هذه هي المتابعة الأخيرة بخصوص عرض السعر الذي أرسلناه. إذا لم نتلق رداً، سنسجل العرض كعدم رد.
```

## Что прислать нам после настройки

После подключения WABA и модерации шаблонов пришлите нам один список:

1. Название Wazzup-аккаунта.
2. WABA phone number.
3. Wazzup channel name.
4. Wazzup channel ID, если виден в интерфейсе или API.
5. Часовой пояс канала.
6. Подтверждение, что WABA-канал активен и может отправлять сообщения.
7. Подтверждение, что шаблоны можно отправлять клиентам вне 24-часового окна.
8. Таблицу по обязательным шаблонам FU2/FU3:

| Step | Language | Wazzup template ID/code | Category | Status | Exact approved text | Variables |
| --- | --- | --- | --- | --- | --- | --- |
| FU2 | English |  |  | Approved |  | none |
| FU2 | Arabic |  |  | Approved |  | none |
| FU3 | English |  |  | Approved |  | none |
| FU3 | Arabic |  |  | Approved |  | none |

Если дополнительно подготовили FU1 fallback template, добавьте его в эту же таблицу отдельными строками. Это не обязательно, но снижает риск пропущенного первого follow-up, если 24-часовое окно уже закрыто.

Если шаблон содержит переменные, вместо `none` укажите:

1. Список переменных в точном порядке.
2. Пример значения для каждой переменной.
3. Скриншот из Wazzup, где виден approved template.

## Что мы настроим после получения данных

После того как вы пришлете approved template IDs/codes, мы включим отправку follow-up в конфигурации Noor.

Нам нужно будет настроить:

1. Включение proposal follow-up.
2. Обычный EN/AR текст для FU1 внутри 24-часового окна.
3. Использование WABA template transport для FU2/FU3 и optional FU1 fallback.
4. Соответствие step + language -> template ID/code.
5. Ограничения на количество отправок за один запуск.
6. Проверку, что после любого ответа клиента follow-up останавливается.
7. Проверку, что при согласии клиента диалог передается менеджеру.

Без approved FU2/FU3 templates мы можем включить только первый follow-up внутри 24-часового окна. Отправку через 3 и 7 дней нельзя считать готовой без approved templates.

## Критерии готовности

Считаем настройку Wazzup/WABA готовой, когда:

1. WABA-канал активен в Wazzup.
2. Все 4 обязательных FU2/FU3 шаблона имеют статус `Approved`.
3. Для каждого шаблона есть template ID/code.
4. Нет русских customer-facing follow-up шаблонов.
5. Есть English и Arabic версии.
6. Если есть переменные, их порядок и примеры подтверждены.
7. Wazzup показывает, что шаблоны можно отправлять.
8. Ответственный прислал нам таблицу из раздела выше.

## Источники Wazzup

Документ подготовлен по официальной базе знаний Wazzup:

1. [How to connect the official WhatsApp (WABA)](https://wazzup24.com/help/how-to-set-up/how-to-connect-the-official-whatsapp-waba/)
2. [How to add a WABA template](https://wazzup24.com/help/how-to-set-up/how-to-add-a-waba-template/)
3. [How to work with WABA templates in chats](https://wazzup24.com/help/how-to-use-en/how-to-work-with-waba-templates-in-chats/)
4. [Sending messages](https://wazzup24.com/help/api-en/sending-messages/)
