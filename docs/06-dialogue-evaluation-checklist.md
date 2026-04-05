# **Методика оценки диалогов и чек-лист / Dialogue Evaluation Method and Checklist**

## **Методика оценки (RU)**

1\. Каждое правило оценивается по шкале 0–2:  
   • 2 – правило полностью выполнено.  
   • 1 – частично выполнено.  
   • 0 – не выполнено.

2\. Итоговая оценка остаётся по шкале 0–30, но считается по 4 weighted blocks:
   • **Opening & Trust** — 6.0 points (rules 1, 2, 3, 7)
   • **Relationship & Discovery** — 9.0 points (rules 4, 5, 6, 8, 13)
   • **Consultative Solution** — 9.0 points (rules 9, 10, 11)
   • **Conversion & Next Step** — 6.0 points (rules 12, 14, 15)

3\. Внутри блока используется та же шкала 0–2 для каждого правила, но итог блока считается так:
   • учитываются только **applicable** rules
   • `normalized_rule = score / 2`
   • `block_ratio = average(normalized_rule)`
   • `block_points = block_ratio × block_weight`

4\. Если блок ещё не достигнут по стадии диалога и в transcript нет соответствующих сигналов, правила блока помечаются как **not applicable / n_a**:
   • они не входят в знаменатель
   • они не тянут итоговый score вниз

5\. Интерпретация итоговой оценки:
   • 26–30 баллов – Отлично. Диалог на высоком уровне, продавец соблюдает все стандарты.  
   • 20–25 баллов – Хорошо. Есть мелкие недочёты, но структура диалога сохранена.  
   • 14–19 баллов – Удовлетворительно. Требуются доработки, часть этапов пропущена.  
   • Менее 14 баллов – Плохо. Диалог не соответствует стандартам.

6\. После оценки:
   • Указать сильные стороны диалога.  
   • Указать зоны для улучшения.  
   • Сформировать рекомендации для следующего контакта.

## **Evaluation Method (EN)**

1\. Each rule is rated on a 0–2 scale:  
   • 2 – the rule is fully followed.  
   • 1 – partially followed.  
   • 0 – not followed.

2\. The final score remains on a 0–30 scale, but it is calculated from 4 weighted blocks:
   • **Opening & Trust** — 6.0 points (rules 1, 2, 3, 7)
   • **Relationship & Discovery** — 9.0 points (rules 4, 5, 6, 8, 13)
   • **Consultative Solution** — 9.0 points (rules 9, 10, 11)
   • **Conversion & Next Step** — 6.0 points (rules 12, 14, 15)

3\. Inside each block, the same 0–2 rule score is used, but the block total is calculated as:
   • include only **applicable** rules
   • `normalized_rule = score / 2`
   • `block_ratio = average(normalized_rule)`
   • `block_points = block_ratio × block_weight`

4\. If the dialogue has not yet reached a block and the transcript contains no corresponding signals, the block rules are marked **not applicable / n_a**:
   • they are excluded from the denominator
   • they do not drag the final score down

5\. Score interpretation:
   • 26–30 points – Excellent. Dialogue at a very high level, all standards met.  
   • 20–25 points – Good. Minor issues, but overall structure maintained.  
   • 14–19 points – Satisfactory. Needs improvement, some stages skipped.  
   • Below 14 points – Poor. Dialogue does not meet standards.

6\. After scoring:
   • Identify the dialogue’s strengths.  
   • Highlight areas for improvement.  
   • Provide recommendations for the next contact.

## **Чек-лист оценки первичного диалога / Dialogue Evaluation Checklist**

| № | Правило (RU) | Rule (EN) | Оценка (0/1/2) | Комментарий |
| :---- | :---- | :---- | :---- | :---- |
| 1 | Всегда приветствие \+ имя (Сияд) \+ компания (Treejar). | Always greeting \+ name (Siyyad) \+ company (Treejar). |   |   |
| 2 | Вежливое приветствие и представление. | Polite greeting and introduction. |   |   |
| 3 | Вопрос: Как к вам обращаться? | Question: How should I address you? |   |   |
| 4 | Дружелюбный тон и активное слушание. | Friendly tone and active listening. |   |   |
| 5 | Создать ощущение интереса к клиенту. | Show interest in the client. |   |   |
| 6 | Сделать искренний комплимент. | Give a genuine compliment. |   |   |
| 7 | Коротко обозначить ценность Treejar. | Briefly show Treejar’s value. |   |   |
| 8 | Задавать уточняющие вопросы. | Ask clarifying questions. |   |   |
| 9 | Принцип “дрель и дырка”: клиент покупает не товар, а решение задачи. | “Drill and hole” principle: the client buys a solution, not just a product. |   |   |
| 10 | Поняв проблему, формировать комплексное решение шире запроса. | Once the problem is understood, form a comprehensive solution beyond the initial request. |   |   |
| 11 | Использовать скидку или бонус при комплексном заказе. | Use a discount or bonus for a complete package. |   |   |
| 12 | Уточнить имя, должность, компанию, e‑mail, канал связи. | Ask for name, position, company, email, preferred channel. |   |   |
| 13 | Спросить, чем занимается компания. | Ask what the company does. |   |   |
| 14 | Закрытие сделки: подтвердить заказ, детали и следующий шаг. | Closing the deal: confirm the order, details, and next step. |   |   |
| 15 | Если клиент не готов к сделке: договориться о следующем контакте. | If the client isn’t ready: agree on the next contact. |   |   |

Итоговая оценка / Final Score: \_\_\_\_ / 30

Сильные стороны диалога / Dialogue Strengths:

Зоны для улучшения / Areas for Improvement:
