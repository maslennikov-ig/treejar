from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_prefers_conversation_value() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    crm_client = AsyncMock()

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name="Treejar HQ",
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "Treejar HQ"
    redis.get.assert_not_awaited()
    crm_client.find_contact_by_phone.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_ignores_generic_placeholder() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    crm_client = AsyncMock()
    crm_client.find_contact_by_phone = AsyncMock(
        return_value={
            "First_Name": "Aisha",
            "Last_Name": "Khan",
            "Segment": "B2B",
        }
    )

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name="Valued Customer",
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "Aisha Khan"
    crm_client.find_contact_by_phone.assert_awaited_once_with("+971501234567")


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_uses_cached_crm_profile() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    redis.get = AsyncMock(
        return_value=json.dumps({"Name": "Cached Contact", "Segment": "Unknown"})
    )
    crm_client = AsyncMock()

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name=None,
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "Cached Contact"
    crm_client.find_contact_by_phone.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_fetches_and_caches_zoho_contact() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    crm_client = AsyncMock()
    crm_client.find_contact_by_phone = AsyncMock(
        return_value={
            "First_Name": "Aisha",
            "Last_Name": "Khan",
            "Segment": "B2B",
        }
    )

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name="",
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "Aisha Khan"
    crm_client.find_contact_by_phone.assert_awaited_once_with("+971501234567")
    redis.set.assert_awaited_once()
    assert redis.set.await_args.args[0] == "crm_profile:+971501234567"
    cached_payload = json.loads(redis.set.await_args.args[1])
    assert cached_payload == {"Name": "Aisha Khan", "Segment": "B2B"}
    assert redis.set.await_args.kwargs["ex"] == 3600


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_returns_placeholder_when_missing() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    crm_client = AsyncMock()
    crm_client.find_contact_by_phone = AsyncMock(return_value=None)

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name=None,
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "не указано"


@pytest.mark.asyncio
async def test_resolve_owner_customer_name_fails_soft_on_cache_and_crm_errors() -> None:
    from src.services.customer_identity import resolve_owner_customer_name

    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=RuntimeError("redis down"))
    crm_client = AsyncMock()
    crm_client.find_contact_by_phone = AsyncMock(side_effect=RuntimeError("crm down"))

    result = await resolve_owner_customer_name(
        phone="+971501234567",
        conversation_customer_name=None,
        redis=redis,
        crm_client=crm_client,
    )

    assert result == "не указано"


def test_format_owner_identity_block_converts_to_uae_and_uses_placeholders() -> None:
    from src.services.customer_identity import format_owner_identity_block

    msg = format_owner_identity_block(
        phone=None,
        customer_name=None,
        inbound_channel_phone=None,
        conversation_created_at=datetime(2026, 4, 9, 9, 5),
        last_activity_at=datetime(
            2026,
            4,
            9,
            11,
            15,
            tzinfo=timezone(timedelta(hours=1)),
        ),
    )

    assert "<b>Телефон клиента:</b> не указан" in msg
    assert "<b>Имя клиента:</b> не указано" in msg
    assert "<b>Входящий номер:</b> не указан" in msg
    assert "<b>Начат (UAE):</b> 09.04.2026 13:05" in msg
    assert "<b>Последняя активность (UAE):</b> 09.04.2026 14:15" in msg
    assert "None" not in msg
    assert "2026-04-09T09:05:00" not in msg
