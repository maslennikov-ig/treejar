# 🕵️‍♂️ Отчет о код-ревью: Refactoring Escalation → Tool-based Architecture

## 1. Контекст и цели
Был произведен рефакторинг двух-агентной системы эскалации (убраны 19 синхронных триггеров на каждое сообщение, добавлен асинхронный инструмент `escalate_to_manager`).

## 2. Анализ изменений

### 🔒 Архитектура и надежность (Architecture & Reliability)
**[High] Строгая типизация параметров для LLM Tool (`escalation_type`)**
- *Локация:* `src/llm/engine.py:escalate_to_manager` (сигнатура)
- *Проблема:* Параметр `escalation_type` задан как дефолтный `str`. LLM (PydanticAI) сгенерирует для этого параметра схему `{ "type": "string" }`, что означает, что модель потенциально может сгенерировать галлюцинацию (неверный тип). Код пытается спасти ситуацию словарем `type_map = {"order_confirmation": ..., ...}`, но это Defensive Programming на этапе исполнения.
- *Решение:* Привести параметр к типу `typing.Literal["order_confirmation", "human_requested", "general"]`. Pydantic-AI автоматически превратит это в **JSON Schema Enum**, и модель на уровне промпта/API уже будет ограничена только этими тремя вариантами. 

**[Medium] Избыточный `type_map`**
- *Локация:* `src/llm/engine.py:escalate_to_manager`
- *Проблема:* После того как мы поставим строгий `Literal` в сигнатуру, мэппинг значений становится избыточным, так как значения `Literal` 1:1 совпадают со значениями `EscalationType` (наследуемого от `StrEnum`).
- *Решение:* Инициализировать `EscalationType(escalation_type)` напрямую, убрав словарь-посредник `type_map`.

### 📖 Читаемость и Best Practices (Readability & Best Practices)
**[Low] Документирование аргументов для LLM-инструмента**
- *Локация:* `src/llm/engine.py:escalate_to_manager` (docstring)
- *Проблема:* Pydantic-AI (по умолчанию) может не считывать классические `Args:` докстринги без явной конфигурации парсера `docstring_format='google'`.
- *Решение:* Можно оставить как есть, если общий декоратор уже парсит докстринги, но самым надежным подходом Pydantic 2.x/Pydantic-AI является использование структуры `Annotated`: `reason: Annotated[str, Field(description="Clear explanation of WHY escalation is needed.")]`. Это гарантированно выведет описание в JSON Schema. Для текущего пула задач предлагаю просто обновить тип `Literal` — это уже закроет 95% рисков.

## 3. Резюме

**Общая оценка качества:** Отлично! Основной паттерн делегирования эскалации инструменту реализован чисто. Устранение `escalation.py` избавило от лишних вызовов.
- *Высокий приоритет (Баги/Архитектура)*: 1
- *Средний приоритет*: 1
- *Низкий приоритет*: 1

## 4. План действий (Action Plan)
Предлагаю оркестратору (Main AI):
1. **Beads Task 1**: Зарегистрировать issue "Fix LLM tool parameter schema restrictions for escalate_to_manager" (Priority: Low, Type: Task).
2. **Обязанность (Orchestrator)**: Параллельно применить исправления с `Literal` и убрать `type_map` непосредственно в текущем рабочем дереве `src/llm/engine.py` и дописать пропущенные аннотации Pydantic.
