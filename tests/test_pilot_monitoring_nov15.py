"""Regression tests for Nov 13-15 live-pilot monitoring & mirror audit improvements (tj-32uk).

Validates:
1. FAQ Q27 (no furniture rental / short-term leasing) and updated FAQ Q26 (office electronics / shredders / plastic dining chairs).
2. Canonical 'Product categories Treejar supplies' article aligns with steel lockers and no safes/rental.
3. BASE_SYSTEM_PROMPT Rule 14 & Rule 18 (rental, office electronics, Skyland origin, TDS datasheet guidance).
4. Worker startup automatically runs canonical knowledge-base safe-sync when Redis context is active.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.services.canonical_admin_seed import (
    canonical_faq_articles,
    canonical_kb_articles,
)


def test_faq_covers_rental_and_electronics_boundaries() -> None:
    articles = canonical_faq_articles()
    by_title = {article.title: article for article in articles}

    rental_title = "FAQ: Do you offer office furniture rental or short-term leasing?"
    assert rental_title in by_title
    rental = by_title[rental_title]
    assert "does not offer short-term" in rental.content.lower()
    assert "rental" in rental.content.lower()
    assert "jebel ali" in rental.content.lower()

    cash_title = "FAQ: Do you sell petty cash boxes, safes, or office stationery?"
    assert cash_title in by_title
    cash_box = by_title[cash_title]
    assert "paper shredders" in cash_box.content.lower()
    assert "plastic dining chairs" in cash_box.content.lower()
    assert "STEL SSL-1" in cash_box.content


def test_canonical_product_categories_excludes_safes_and_rental() -> None:
    categories_article = next(
        article
        for article in canonical_kb_articles()
        if article.title == "Product categories Treejar supplies"
    )
    lower = categories_article.content.lower()
    assert "steel lockers" in lower
    assert "no safes" in lower
    assert "lockers and safes" not in lower


def test_base_system_prompt_contains_rental_origin_and_tds_guidance() -> None:
    lower = BASE_SYSTEM_PROMPT.lower()
    assert "paper shredders" in lower
    assert "plastic dining chairs" in lower
    assert "rental/leasing" in lower
    assert "18. Manufacturing origin and technical datasheets (TDS):" in (
        BASE_SYSTEM_PROMPT
    )
    assert "never claim skyland chairs or desks are european-made" in lower
    assert "technical datasheet (tds)" in lower


@pytest.mark.asyncio
async def test_worker_startup_safe_syncs_canonical_kb_when_redis_present() -> None:
    from src.worker import WorkerSettings

    fake_db = MagicMock()
    fake_db.commit = AsyncMock()

    @asynccontextmanager
    async def fake_session_factory() -> Any:
        yield fake_db

    sync_mock = AsyncMock(
        return_value={
            "created": 5,
            "updated": 0,
            "restored": 0,
            "unchanged": 26,
            "total_active": 31,
        }
    )

    with (
        patch("src.worker.EmbeddingEngine") as MockEngine,
        patch("src.worker.refresh_zoho_stock_snapshot", new=AsyncMock()),
        patch("src.worker.refresh_zoho_stock_delta", new=AsyncMock()),
        patch("src.core.database.async_session_factory", fake_session_factory),
        patch(
            "src.services.canonical_admin_seed.sync_canonical_knowledge_base",
            sync_mock,
        ),
    ):
        mock_engine = MockEngine.return_value
        mock_engine.warmup_async = AsyncMock()
        await WorkerSettings.on_startup({"redis": AsyncMock()})

    sync_mock.assert_awaited_once_with(fake_db, mock_engine, mode="safe")
    fake_db.commit.assert_awaited_once()
