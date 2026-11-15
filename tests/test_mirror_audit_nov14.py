"""Regression tests for Nov 14 shift mirror audit improvements (tj-r62i.9).

Validates:
1. FAQ Q28 (no classroom/training chairs with attached writing tablet arm in ready stock; visitor chairs + tables recommendation; manager custom quote for bulk).
2. Canonical 'Product categories Treejar supplies' article excludes tablet-arm training chairs.
3. BASE_SYSTEM_PROMPT Rule 19 (3D/4D ergonomic chair adjustment terminology vs video confusion, beige leather 0 stock fact, and tablet arm guidance).
"""

from __future__ import annotations

from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.services.canonical_admin_seed import (
    canonical_faq_articles,
    canonical_kb_articles,
)


def test_faq_covers_tablet_arm_training_chairs() -> None:
    articles = canonical_faq_articles()
    by_title = {article.title: article for article in articles}

    tablet_title = "FAQ: Do you offer training or classroom chairs with an attached writing tablet (tablet arm)?"
    assert tablet_title in by_title
    tablet_art = by_title[tablet_title]
    lower = tablet_art.content.lower()

    assert "writing tablet" in lower
    assert "tablet arm" in lower
    assert "ch 240 v" in lower
    assert "ch 420 v" in lower
    assert "modular meeting or training tables" in lower
    assert "sales manager" in lower


def test_canonical_product_categories_excludes_tablet_arm_chairs() -> None:
    categories_article = next(
        article
        for article in canonical_kb_articles()
        if article.title == "Product categories Treejar supplies"
    )
    lower = categories_article.content.lower()
    assert "tablet-arm training chairs" in lower
    assert "steel lockers" in lower
    assert "no safes" in lower


def test_base_system_prompt_contains_3d_chair_and_tablet_arm_guidance() -> None:
    lower = BASE_SYSTEM_PROMPT.lower()
    assert "chair adjustments, upholstery colors & tablet arms" in lower
    assert "'3d' or '4d' adjustments" in lower
    assert "never confuse this with 3d video" in lower
    assert "beige leather executive chairs" in lower
    assert "0 ready stock" in lower
    assert "attached flip-up writing tablet arms" in lower
