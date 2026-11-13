"""Regression tests for mirror audit improvements following Nov 12 WhatsApp shift (tj-dqdv).

Validates:
1. FAQ Q25: Office chairs without wheels / cantilever visitor chairs (CH 240 V, CH 420 V).
2. FAQ Q26: Boundary on petty cash boxes, safes, and stationery.
3. System prompt Rule 17 (chair bases without wheels) and Rule 14 (cash box boundary).
4. Stage solution guidance for competitor price comparisons (Amazon/Noon links) per FAQ Q12.
"""

from unittest.mock import AsyncMock

from src.llm.prompts import BASE_SYSTEM_PROMPT, STAGE_RULES, build_system_prompt
from src.schemas.common import SalesStage
from src.services.canonical_admin_seed import canonical_faq_articles


def test_faq_contains_chair_wheel_and_cash_box_answers() -> None:
    articles = canonical_faq_articles()
    titles = {article.title for article in articles}

    assert "FAQ: Do you offer office chairs without wheels?" in titles
    assert "FAQ: Do you sell petty cash boxes, safes, or office stationery?" in titles

    wheel_faq = next(
        a
        for a in articles
        if a.title == "FAQ: Do you offer office chairs without wheels?"
    )
    assert "CH 240 V" in wheel_faq.content
    assert "CH 420 V" in wheel_faq.content
    assert "cantilever" in wheel_faq.content.lower()
    assert "without wheels" in wheel_faq.content.lower()

    cash_box_faq = next(
        a
        for a in articles
        if a.title == "FAQ: Do you sell petty cash boxes, safes, or office stationery?"
    )
    assert "STEL SSP-25" in cash_box_faq.content
    assert "petty cash boxes" in cash_box_faq.content.lower()
    assert "stationery" in cash_box_faq.content.lower()


def test_base_system_prompt_contains_mirror_audit_rules() -> None:
    assert "17. Office chairs and wheels:" in BASE_SYSTEM_PROMPT
    assert "CH 240 V" in BASE_SYSTEM_PROMPT
    assert "without wheels" in BASE_SYSTEM_PROMPT.lower()
    assert "petty cash boxes" in BASE_SYSTEM_PROMPT.lower()


def test_stage_solution_contains_competitor_comparison_guidance() -> None:
    solution_rules = STAGE_RULES["solution"]
    assert "price objection" in solution_rules.lower()
    assert "competitor" in solution_rules.lower()
    assert "FAQ Q12" in solution_rules


async def test_build_system_prompt_includes_mirror_audit_rules() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    prompt = await build_system_prompt(
        db, redis, SalesStage.SOLUTION.value, language="en"
    )
    assert "17. Office chairs and wheels:" in prompt
    assert "CH 240 V" in prompt
    assert "petty cash boxes" in prompt.lower()
    assert "competitor" in prompt.lower()
