from __future__ import annotations

from uuid import uuid4


def test_format_detailed_quality_review_renames_old_criteria_and_uses_fallbacks() -> (
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

    from src.quality.schemas import RULE_NAMES

    assert "Quality review" in text
    assert "Weighted breakdown" in text
    assert "What went well" in text
    assert "What weakened the conversation" in text
    assert "Recommendations" in text
    assert "Next action" in text
    assert "<b>Current stage:</b> Greeting" in text
    assert "other reason" in text

    # The rule number names the criterion, so a review stored with whatever
    # wording an older judge used still renders under today's canonical name.
    assert RULE_NAMES[1] in text
    assert RULE_NAMES[8] in text
    assert "Clarifying questions" not in text
    assert "Old English summary should not define the layout" not in text


def test_format_detailed_quality_review_uses_na_labels_when_context_missing() -> None:
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

    assert "<b>Reason:</b> n/a" in text
    assert "<b>Current stage:</b> n/a" in text


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

    assert "Next action" in text
    assert "agree a date and time for the next contact" in text.lower()
