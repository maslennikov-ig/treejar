# Метрики для админ-панели Noor

Текущий dashboard payload приходит из `DashboardMetricsResponse` и покрывает 7 прикладных блоков плюс служебное поле `period`.

## 1. Объём

| Поле | Описание |
|---|---|
| `total_conversations` | Количество диалогов за выбранный период |
| `unique_customers` | Количество уникальных клиентов |
| `new_vs_returning` | Разбиение на новые и повторные обращения |

## 2. Классификация

| Поле | Описание |
|---|---|
| `by_segment` | Распределение по сегментам из `Conversation.metadata.segment` |
| `by_language` | Распределение по языкам |
| `target_vs_nontarget` | Целевые vs нецелевые диалоги |

## 3. Эскалации

| Поле | Описание |
|---|---|
| `escalation_count` | Количество диалогов, переданных менеджерам |
| `escalation_reasons` | Разбивка по причинам эскалации |

## 4. Продажи

| Поле | Описание |
|---|---|
| `noor_sales` | Сделки, закрытые без эскалации |
| `post_escalation_sales` | Сделки, закрытые после эскалации |
| `conversion_rate` | Общая конверсия диалог -> сделка |
| `average_deal_value` | Средний чек по сделкам с заполненным `deal_amount` |

## 5. Качество бота

| Поле | Описание |
|---|---|
| `avg_conversation_length` | Среднее число сообщений в диалоге |
| `avg_quality_score` | Средний балл `QualityReview` |
| `avg_response_time_ms` | Среднее время ответа бота в миллисекундах |
| `llm_cost_usd` | Суммарная LLM-стоимость по сообщениям |

## 6. Показатели менеджеров

| Поле | Описание |
|---|---|
| `avg_manager_score` | Средний балл `ManagerReview` по шкале 0-20 |
| `avg_manager_response_time_seconds` | Среднее время первого ответа менеджера после эскалации |
| `manager_deal_conversion_rate` | Доля `ManagerReview` с `deal_converted=true` |
| `manager_leaderboard` | Топ менеджеров по среднему баллу |

## 7. Обратная связь клиентов

| Поле | Описание |
|---|---|
| `feedback_count` | Количество записей `Feedback` |
| `avg_rating_overall` | Средняя общая оценка клиента |
| `avg_rating_delivery` | Средняя оценка доставки |
| `nps_score` | Условный NPS на базе `recommend` |
| `recommend_rate` | Доля клиентов, готовых рекомендовать Noor |

## Notes

- Поле `period` принимает `day`, `week`, `month`, `all_time`.
- В текущем payload нет отдельного follow-up блока. Историческая 17-metric схема больше не совпадает с реальным backend response.
- Для графика новых/повторных обращений используется отдельный endpoint `GET /api/v1/admin/dashboard/timeseries/`.
