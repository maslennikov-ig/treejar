"""Regression tests for Nov 14 shift mirror audit & stale takeover follow-up (tj-r62i.9 / tj-k4pc).

Validates:
1. FAQ Q28 (no classroom/training chairs with attached writing tablet arm in ready stock; visitor chairs + tables recommendation; manager custom quote for bulk).
2. Canonical 'Product categories Treejar supplies' article excludes tablet-arm training chairs.
3. BASE_SYSTEM_PROMPT Rule 19 & CUSTOMER ATTACHMENTS: 3D/4D ergonomic chair adjustment terminology vs video confusion, live tool-grounded upholstery stock checks (no hardcoded SKU stock), photo colour/price-tier matching (*9860), and tablet arm guidance.
4. Stale manual_takeover follow-up alert (*0247): when a customer writes back in a manager-handled chat after >= 2h of manager silence, Noor stays silent in WhatsApp while alerting managers in Telegram (with 30m cooldown).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.services.canonical_admin_seed import (
    canonical_faq_articles,
    canonical_kb_articles,
)
from src.services.chat import _notify_stale_manual_takeover_followup


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


def test_base_system_prompt_contains_3d_chair_photo_tier_and_tablet_guidance() -> None:
    lower = BASE_SYSTEM_PROMPT.lower()
    assert "chair adjustments, upholstery colors & tablet arms" in lower
    assert "'3d' or '4d' adjustments" in lower
    assert "never confuse this with 3d video" in lower
    assert "verify live colour availability" in lower
    assert "beige leather executive chairs" in lower
    assert "0 ready stock" in lower
    assert "ch 300 beige" not in lower  # never hardcode live SKU stock in prompt
    assert "attached flip-up writing tablet arms" in lower
    assert "match the visible colour and style first" in lower
    assert "budget/mid-range and premium price tiers" in lower


@pytest.mark.asyncio
async def test_stale_manual_takeover_followup_alerts_telegram_without_whatsapp_reply() -> (
    None
):
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        phone="971501230247",
        metadata_={
            "last_manager_message_at": (
                datetime.now(UTC) - timedelta(hours=72)
            ).isoformat()
        },
    )
    redis = AsyncMock()
    redis.get.return_value = None

    with (
        patch("src.services.chat.settings.telegram_bot_token", "test-token"),
        patch("src.services.chat.settings.telegram_chat_id", "-100123456"),
        patch(
            "src.integrations.notifications.telegram.TelegramClient"
        ) as MockTelegramClient,
    ):
        tg_instance = MockTelegramClient.return_value
        tg_instance.send_message = AsyncMock()
        tg_instance.aclose = AsyncMock()

        await _notify_stale_manual_takeover_followup(
            conv, "Good Evening\nNo one came back to me", redis
        )

    redis.setex.assert_awaited_once()
    tg_instance.send_message.assert_awaited_once()
    sent_html = tg_instance.send_message.await_args.args[0]
    assert "Customer returned to manager-handled chat" in sent_html
    assert "+971501230247" in sent_html
    assert "No one came back to me" in sent_html


@pytest.mark.asyncio
async def test_recent_manual_takeover_does_not_spam_telegram() -> None:
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        phone="971501230247",
        metadata_={
            "last_manager_message_at": (
                datetime.now(UTC) - timedelta(minutes=15)
            ).isoformat()
        },
    )
    redis = AsyncMock()

    await _notify_stale_manual_takeover_followup(conv, "Thanks, waiting!", redis)

    redis.get.assert_not_awaited()
    redis.setex.assert_not_awaited()
