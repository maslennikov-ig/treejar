from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


def _payload() -> dict[str, object]:
    return {
        "tester_name": "Owner <script>",
        "overall_comment": "Ready & reviewed",
        "items": [
            {
                "id": "exact-sku",
                "title": "Точный SKU <CH-410>",
                "status": "passed",
                "note": "",
            },
            {
                "id": "quotation-approval",
                "title": "Quotation <approval>",
                "status": "failed",
                "note": "Ожидал <b>approval</b>, получил generic escalation & noise",
            },
            {
                "id": "arabic",
                "title": "Arabic sanity",
                "status": "not_tested",
                "note": "Оставили на потом",
            },
        ],
    }


@pytest.mark.asyncio
async def test_client_self_test_submit_requires_admin_session(
    client: AsyncClient,
) -> None:
    with patch(
        "src.api.v1.admin.send_telegram_message",
        new_callable=AsyncMock,
        create=True,
    ) as send:
        response = await client.post(
            "/api/v1/admin/client-self-test/submit",
            json=_payload(),
        )

    assert response.status_code == 401
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_public_client_self_test_submit_sends_escaped_telegram_summary(
    client: AsyncClient,
) -> None:
    with patch(
        "src.api.v1.client_self_test.send_telegram_message",
        new_callable=AsyncMock,
        create=True,
    ) as send:
        response = await client.post(
            "/api/v1/client-self-test/submit",
            json=_payload(),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "submitted_count": 3}
    send.assert_awaited_once()

    message = send.await_args.args[0]
    assert "Owner &lt;script&gt;" in message
    assert "Ready &amp; reviewed" in message
    assert "Пройдено: 1" in message
    assert "Неверно: 1" in message
    assert "Не проверено: 1" in message
    assert "Quotation &lt;approval&gt;" in message
    assert "Ожидал &lt;b&gt;approval&lt;/b&gt;" in message
    assert "generic escalation &amp; noise" in message
    assert "<script>" not in message
    assert "<b>approval</b>" not in message


@pytest.mark.asyncio
async def test_client_self_test_submit_sends_escaped_telegram_summary(
    admin_client: AsyncClient,
) -> None:
    with patch(
        "src.api.v1.admin.send_telegram_message",
        new_callable=AsyncMock,
        create=True,
    ) as send:
        response = await admin_client.post(
            "/api/v1/admin/client-self-test/submit",
            json=_payload(),
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True, "submitted_count": 3}
    send.assert_awaited_once()

    message = send.await_args.args[0]
    assert "Owner &lt;script&gt;" in message
    assert "Ready &amp; reviewed" in message
    assert "Пройдено: 1" in message
    assert "Неверно: 1" in message
    assert "Не проверено: 1" in message
    assert "Quotation &lt;approval&gt;" in message
    assert "Ожидал &lt;b&gt;approval&lt;/b&gt;" in message
    assert "generic escalation &amp; noise" in message
    assert "<script>" not in message
    assert "<b>approval</b>" not in message


@pytest.mark.asyncio
async def test_client_self_test_submit_validates_payload_bounds(
    admin_client: AsyncClient,
) -> None:
    invalid_payload = _payload()
    invalid_payload["items"] = [
        {
            "id": "bad",
            "title": "Bad scenario",
            "status": "unknown",
            "note": "x" * 801,
        }
    ]

    with patch(
        "src.api.v1.admin.send_telegram_message",
        new_callable=AsyncMock,
        create=True,
    ) as send:
        response = await admin_client.post(
            "/api/v1/admin/client-self-test/submit",
            json=invalid_payload,
        )

    assert response.status_code == 422
    send.assert_not_awaited()
