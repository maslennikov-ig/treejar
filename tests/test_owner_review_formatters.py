from __future__ import annotations

from uuid import uuid4


def test_format_detailed_quality_review_localizes_old_criteria_and_uses_russian_fallbacks() -> (
    None
):
    from src.services.owner_review_formatters import format_detailed_quality_review

    text = format_detailed_quality_review(
        conversation_id=uuid4(),
        score=11.0,
        rating="poor",
        criteria=[
            {"rule_number": 1, "rule_name": "Greeting", "score": 2, "max_score": 2},
            {
                "rule_number": 8,
                "rule_name": "Clarifying questions",
                "score": 0,
                "max_score": 2,
            },
            {"rule_number": 14, "rule_name": "Closing", "score": 0, "max_score": 2},
        ],
        current_stage="greeting",
        trigger="mystery_english_reason",
        summary="Old English summary should not define the layout",
    )

    assert "Оценка качества" in text
    assert "Взвешенная разбивка" in text
    assert "Что сделано хорошо" in text
    assert "Что ухудшило диалог" in text
    assert "Рекомендации" in text
    assert "Следующее действие" in text
    assert "приветствие" in text
    assert "иная причина" in text
    assert "Greeting" not in text
    assert "Clarifying questions" not in text
    assert "Old English summary should not define the layout" not in text


def test_format_detailed_quality_review_uses_russian_na_labels_when_context_missing() -> (
    None
):
    from src.services.owner_review_formatters import format_detailed_quality_review

    text = format_detailed_quality_review(
        conversation_id=uuid4(),
        score=28.0,
        rating="excellent",
        criteria=[],
        current_stage=None,
        trigger=None,
        summary=None,
    )

    assert "<b>Основание:</b> н/д" in text
    assert "<b>Текущий этап:</b> н/д" in text


def test_format_detailed_quality_review_selects_next_best_action_from_weakest_rule() -> (
    None
):
    from src.services.owner_review_formatters import format_detailed_quality_review

    text = format_detailed_quality_review(
        conversation_id=uuid4(),
        score=13.0,
        rating="poor",
        criteria=[
            {
                "rule_number": 15,
                "rule_name": "Next contact agreed",
                "score": 0,
                "max_score": 2,
            }
        ],
        current_stage="closing",
        trigger="low_score",
        summary=None,
    )

    assert "Следующее действие" in text
    assert "согласовать дату и время следующего контакта" in text.lower()
