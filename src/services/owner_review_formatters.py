"""Pure owner-facing formatters for detailed quality and manager-style reviews."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from typing import Any
from uuid import UUID

from src.services.customer_identity import format_owner_identity_block
from src.services.report_localization import (
    owner_na,
    translate_criterion_status,
    translate_quality_rating,
    translate_quality_rule_name,
    translate_report_trigger,
    translate_sales_stage,
)

_QUALITY_RECOMMENDATIONS: dict[int, str] = {
    1: "Начать диалог с приветствия, имени клиента и краткого представления компании.",
    2: "Удерживать вежливый и профессиональный тон с первого сообщения.",
    3: "Сразу уточнять, как удобно обращаться к клиенту.",
    4: "Поддерживать дружелюбный тон и показывать, что запрос клиента услышан.",
    5: "Явно проявлять интерес к задаче клиента и его контексту.",
    6: "Добавлять уместную признательность или короткий комплимент по запросу клиента.",
    7: "Чётко формулировать ценность Treejar именно для этого клиента.",
    8: "Задавать больше уточняющих вопросов до предложения решения.",
    9: "Сильнее связывать ответы с конкретной задачей клиента.",
    10: "Предлагать комплексное решение только после достаточной диагностики.",
    11: "Использовать скидку, пакетное предложение или бонус, когда это уместно.",
    12: "Собрать недостающие контактные данные для CRM и следующего шага.",
    13: "Уточнить детали бизнеса клиента, чтобы предложение было точнее.",
    14: "Подтвердить договорённости и зафиксировать следующий шаг явно.",
    15: "Согласовать дату и время следующего контакта с клиентом.",
}


def _criterion_attr(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(key, default)
    return getattr(item, key, default)


def _normalize_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_criteria(criteria: Sequence[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in criteria:
        rule_number = _normalize_int(_criterion_attr(item, "rule_number"))
        score = _normalize_int(_criterion_attr(item, "score"), 0)
        max_score = _normalize_int(_criterion_attr(item, "max_score"), 2)
        rule_name = _criterion_attr(item, "rule_name")
        normalized.append(
            {
                "rule_number": rule_number,
                "score": score,
                "max_score": max_score,
                "label": translate_quality_rule_name(
                    rule_number,
                    rule_name,
                    surface="quality_review",
                    module="owner_review_formatters",
                ),
            }
        )
    return sorted(
        normalized,
        key=lambda item: (
            item["rule_number"] is None,
            item["rule_number"] if item["rule_number"] is not None else 999,
        ),
    )


def _recommendation_for_rule(rule_number: int | None) -> str:
    if rule_number is None:
        return "Уточнить, где именно просел диалог, и скорректировать следующий шаг."
    return _QUALITY_RECOMMENDATIONS.get(
        rule_number,
        "Уточнить проблемный критерий и скорректировать следующий шаг.",
    )


def _render_list(title: str, items: Sequence[str], *, empty_text: str) -> list[str]:
    lines = [f"<b>{title}</b>"]
    if items:
        lines.extend(f"• {escape(item)}" for item in items)
    else:
        lines.append(f"• {escape(empty_text)}")
    return lines


def format_detailed_quality_review(
    conversation_id: UUID,
    score: float,
    rating: str,
    criteria: Sequence[Any],
    *,
    current_stage: str | None = None,
    trigger: str | None = None,
    summary: str | None = None,
    phone: str | None = None,
    customer_name: str | None = None,
    inbound_channel_phone: str | None = None,
    conversation_created_at: datetime | None = None,
    last_activity_at: datetime | None = None,
) -> str:
    """Render a deterministic owner-facing quality review in Russian.

    The output is intentionally derived from structured criteria rather than from
    free-form LLM prose so older English summaries do not leak into Telegram.
    """
    del summary

    normalized = _normalize_criteria(criteria)
    rating_label = translate_quality_rating(
        rating,
        surface="quality_review",
        module="owner_review_formatters",
    )
    stage_label = (
        owner_na()
        if current_stage is None
        else translate_sales_stage(
            current_stage,
            surface="quality_review",
            module="owner_review_formatters",
        )
    )
    trigger_label = (
        owner_na()
        if trigger is None
        else translate_report_trigger(
            trigger,
            surface="quality_review",
            module="owner_review_formatters",
        )
    )

    breakdown_lines = ["<b>Взвешенная разбивка</b>"]
    if normalized:
        for item in normalized:
            rule_number = item["rule_number"]
            rule_prefix = f"{rule_number}. " if rule_number is not None else ""
            breakdown_lines.append(
                "• "
                f"{rule_prefix}{escape(item['label'])}: "
                f"{item['score']}/{item['max_score']} "
                f"({escape(translate_criterion_status(item['score']))})"
            )
    else:
        breakdown_lines.append(f"• {owner_na()}")

    strengths = [
        item["label"] for item in normalized if item["score"] == item["max_score"]
    ]
    weaknesses = [
        item["label"] for item in normalized if item["score"] < item["max_score"]
    ]
    weak_items = [item for item in normalized if item["score"] < item["max_score"]]
    weak_items.sort(
        key=lambda item: (
            item["score"],
            item["rule_number"] if item["rule_number"] is not None else 999,
        )
    )

    recommendations = [
        _recommendation_for_rule(item["rule_number"]) for item in weak_items
    ]
    deduped_recommendations = list(dict.fromkeys(recommendations))
    next_best_action = (
        deduped_recommendations[0]
        if deduped_recommendations
        else "Поддерживать текущий уровень качества и масштабировать удачные практики."
    )
    identity_block = format_owner_identity_block(
        phone=phone,
        customer_name=customer_name,
        inbound_channel_phone=inbound_channel_phone,
        conversation_created_at=conversation_created_at,
        last_activity_at=last_activity_at,
    )

    lines = [
        "⚠️ <b>Оценка качества</b>",
        f"<b>UUID диалога:</b> <code>{escape(str(conversation_id))}</code>",
        identity_block,
        f"<b>Оценка:</b> {score:.1f}/30 ({escape(rating_label)})",
        f"<b>Основание:</b> {escape(trigger_label)}",
        f"<b>Текущий этап:</b> {escape(stage_label)}",
        "",
    ]
    lines.extend(breakdown_lines)
    lines.append("")
    lines.extend(
        _render_list(
            "Что сделано хорошо",
            strengths,
            empty_text="Явно выраженные сильные стороны не зафиксированы.",
        )
    )
    lines.append("")
    lines.extend(
        _render_list(
            "Что ухудшило диалог",
            weaknesses,
            empty_text="Критичных провалов по критериям не выявлено.",
        )
    )
    lines.append("")
    lines.extend(
        _render_list(
            "Рекомендации",
            deduped_recommendations,
            empty_text="Поддерживать текущий стандарт качества.",
        )
    )
    lines.append("")
    lines.append("<b>Следующее действие</b>")
    lines.append(f"• {escape(next_best_action)}")
    return "\n".join(lines)
