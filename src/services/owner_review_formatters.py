"""Pure owner-facing formatters for detailed quality and manager-style reviews."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from html import escape
from typing import Any
from uuid import UUID

from src.services.customer_identity import format_owner_identity_block
from src.services.owner_presentation import (
    format_criterion_status,
    format_quality_rating,
    format_report_trigger,
    format_sales_stage,
    owner_na,
    quality_rule_name,
)

_QUALITY_RECOMMENDATIONS: dict[int, str] = {
    1: "Open with a greeting, the customer's name and a brief introduction of the company.",
    2: "Hold a polite and professional tone from the first message.",
    3: "Ask straight away how the customer prefers to be addressed.",
    4: "Keep a friendly tone and show that the customer's request was heard.",
    5: "Show explicit interest in the customer's job and their context.",
    6: "Add an apt note of appreciation or a short compliment on the customer's request.",
    7: "State Treejar's value clearly, for this customer specifically.",
    8: "Ask more clarifying questions before proposing a solution.",
    9: "Tie the answers more tightly to the customer's specific job.",
    10: "Propose a comprehensive solution only after enough diagnosis.",
    11: "Use a discount, bundle or bonus where it fits.",
    12: "Collect the missing contact details for the CRM and the next step.",
    13: "Establish the customer's business in more detail so the offer lands closer.",
    14: "Confirm what was agreed and record the next step explicitly.",
    15: "Agree a date and time for the next contact with the customer.",
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
                "label": quality_rule_name(rule_number, rule_name),
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
        return "Pin down where the conversation slipped and adjust the next step."
    return _QUALITY_RECOMMENDATIONS.get(
        rule_number,
        "Pin down the failing criterion and adjust the next step.",
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
    """Render a deterministic owner-facing quality review.

    The output is intentionally derived from structured criteria rather than from
    free-form LLM prose, so the report reads the same however the judge phrased
    its narrative.
    """
    del summary

    normalized = _normalize_criteria(criteria)
    rating_label = format_quality_rating(rating)
    stage_label = (
        owner_na() if current_stage is None else format_sales_stage(current_stage)
    )
    trigger_label = (
        owner_na()
        if trigger is None
        else format_report_trigger(
            trigger,
            surface="quality_review",
            module="owner_review_formatters",
        )
    )

    breakdown_lines = ["<b>Weighted breakdown</b>"]
    if normalized:
        for item in normalized:
            rule_number = item["rule_number"]
            rule_prefix = f"{rule_number}. " if rule_number is not None else ""
            breakdown_lines.append(
                "• "
                f"{rule_prefix}{escape(item['label'])}: "
                f"{item['score']}/{item['max_score']} "
                f"({escape(format_criterion_status(item['score']))})"
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
        else "Hold the current quality level and scale what is working."
    )
    identity_block = format_owner_identity_block(
        phone=phone,
        customer_name=customer_name,
        inbound_channel_phone=inbound_channel_phone,
        conversation_created_at=conversation_created_at,
        last_activity_at=last_activity_at,
    )

    lines = [
        "⚠️ <b>Quality review</b>",
        f"<b>Conversation UUID:</b> <code>{escape(str(conversation_id))}</code>",
        identity_block,
        f"<b>Score:</b> {score:.1f}/30 ({escape(rating_label)})",
        f"<b>Reason:</b> {escape(trigger_label)}",
        f"<b>Current stage:</b> {escape(stage_label)}",
        "",
    ]
    lines.extend(breakdown_lines)
    lines.append("")
    lines.extend(
        _render_list(
            "What went well",
            strengths,
            empty_text="No clearly stated strengths were recorded.",
        )
    )
    lines.append("")
    lines.extend(
        _render_list(
            "What weakened the conversation",
            weaknesses,
            empty_text="No critical failures against the criteria were found.",
        )
    )
    lines.append("")
    lines.extend(
        _render_list(
            "Recommendations",
            deduped_recommendations,
            empty_text="Hold the current quality standard.",
        )
    )
    lines.append("")
    lines.append("<b>Next action</b>")
    lines.append(f"• {escape(next_best_action)}")
    return "\n".join(lines)
