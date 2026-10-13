from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.integrations.messaging import wazzup_webhook as guard

_SUBSCRIPTIONS = {
    "messagesAndStatuses": True,
    "contactsAndDealsCreation": False,
    "channelsUpdates": True,
    "wabaTemplatesStatus": False,
}
_DISPLACED = "https://audit.example/webhook?s=private-query-secret"


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr(guard.settings, "wazzup_webhook_guard_enabled", True)
    monkeypatch.setattr(guard.settings, "wazzup_api_key", "fake-key")
    monkeypatch.setattr(guard.settings, "wazzup_api_url", "https://api.wazzup24.com/v3")
    monkeypatch.setattr(guard.settings, "wazzup_channel_id", "approved-channel")
    monkeypatch.setattr(
        guard.settings, "wazzup_outbound_allowed_channel_id", "approved-channel"
    )
    redis = AsyncMock()
    redis.set.return_value = True
    return {"redis": redis}


def _transport(monkeypatch: pytest.MonkeyPatch, handler: Any) -> None:
    original = httpx.AsyncClient
    monkeypatch.setattr(
        guard.httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )


def _response(callback: str = _DISPLACED, **extra: Any) -> dict[str, Any]:
    return {"webhooksUri": callback, "subscriptions": dict(_SUBSCRIPTIONS), **extra}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("wazzup_webhook_guard_enabled", False, "disabled"),
        ("wazzup_api_key", "", "unsafe_configuration"),
        ("wazzup_outbound_allowed_channel_id", "other", "unsafe_configuration"),
    ],
)
async def test_guard_does_not_run_without_opt_in_and_sender_authority(
    context: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: Any,
    expected: str,
) -> None:
    monkeypatch.setattr(guard.settings, field, value)
    client = MagicMock()
    monkeypatch.setattr(guard.httpx, "AsyncClient", client)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": expected}
    context["redis"].set.assert_not_awaited()
    client.assert_not_called()


@pytest.mark.asyncio
async def test_guard_requires_lease_and_skips_another_worker(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await guard.reconcile_wazzup_webhook({}) == {"status": "unavailable"}
    context["redis"].set.return_value = False
    client = MagicMock()
    monkeypatch.setattr(guard.httpx, "AsyncClient", client)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": "busy"}
    client.assert_not_called()
    context["redis"].eval.assert_not_awaited()


@pytest.mark.asyncio
async def test_matching_callback_is_read_only_and_releases_owned_lease(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_response(guard.WAZZUP_WEBHOOK_URL))

    _transport(monkeypatch, handler)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": "ok"}
    assert [(r.method, r.url.path) for r in requests] == [("GET", "/v3/webhooks")]
    redis = context["redis"]
    token = redis.set.await_args.args[1]
    redis.eval.assert_awaited_once_with(guard._RELEASE_LOCK, 1, guard._LOCK_KEY, token)
    assert redis.set.await_args.kwargs == {"ex": 45, "nx": True}


@pytest.mark.asyncio
async def test_repair_preserves_subscriptions_and_verifies_readback(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    import json

    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "PATCH":
            assert json.loads(request.content) == {
                "webhooksUri": guard.WAZZUP_WEBHOOK_URL,
                "subscriptions": _SUBSCRIPTIONS,
            }
            return httpx.Response(200, json={"ok": True})
        if len(requests) == 4:
            return httpx.Response(200, json=_response(guard.WAZZUP_WEBHOOK_URL))
        return httpx.Response(200, json=_response())

    _transport(monkeypatch, handler)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": "restored"}
    assert [r.method for r in requests] == ["GET", "GET", "PATCH", "GET"]
    assert "audit.example" in caplog.text
    assert "private-query-secret" not in caplog.text


@pytest.mark.asyncio
async def test_concurrent_configuration_change_aborts_repair(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        subscriptions = dict(_SUBSCRIPTIONS)
        if len(methods) == 2:
            subscriptions["channelsUpdates"] = False
        return httpx.Response(200, json=_response(subscriptions=subscriptions))

    _transport(monkeypatch, handler)
    assert await guard.reconcile_wazzup_webhook(context) == {
        "status": "changed_during_check"
    }
    assert methods == ["GET", "GET"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [None, {}, {"webhooksUri": _DISPLACED}, _response(subscriptions={"x": "true"})],
)
async def test_invalid_provider_read_never_mutates_configuration(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch, data: Any
) -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        return httpx.Response(200, json=data)

    _transport(monkeypatch, handler)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": "error"}
    assert methods == ["GET"]
    context["redis"].eval.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["rejected", "moved_again", "cancelled"])
async def test_failed_repair_is_not_claimed_successful_and_lease_is_released(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch, caplog: Any, failure: str
) -> None:
    methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append(request.method)
        if request.method == "PATCH":
            if failure == "cancelled":
                raise asyncio.CancelledError
            if failure == "rejected":
                return httpx.Response(429, text="private-query-secret")
        return httpx.Response(200, json=_response())

    _transport(monkeypatch, handler)
    if failure == "cancelled":
        with pytest.raises(asyncio.CancelledError):
            await guard.reconcile_wazzup_webhook(context)
    else:
        expected = "error" if failure == "rejected" else "restore_failed"
        assert await guard.reconcile_wazzup_webhook(context) == {"status": expected}
    context["redis"].eval.assert_awaited_once()
    assert methods.count("PATCH") == 1
    assert "private-query-secret" not in caplog.text


@pytest.mark.asyncio
async def test_admin_notification_is_throttled_and_never_exposes_query_secret(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard.settings, "telegram_bot_token", "fake-token")
    monkeypatch.setattr(guard.settings, "telegram_chat_id", "fake-admin")
    client = MagicMock(send_message=AsyncMock(), aclose=AsyncMock())
    monkeypatch.setattr(guard, "TelegramClient", MagicMock(return_value=client))
    await guard._notify(context["redis"], restored=True, displaced_host="audit.example")
    message = client.send_message.await_args.args[0]
    assert "restored" in message
    assert "audit.example" in message
    assert "private-query-secret" not in message
    context["redis"].set.assert_awaited_with(
        f"{guard._ALERT_KEY}:restored", "1", ex=3600, nx=True
    )
    context["redis"].set.return_value = False
    await guard._notify(
        context["redis"], restored=False, displaced_host="audit.example"
    )
    client.send_message.assert_awaited_once()
    assert client.aclose.await_count == 2


@pytest.mark.asyncio
async def test_notification_failure_does_not_change_verified_repair_result(
    context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(guard.settings, "telegram_bot_token", "fake-token")
    monkeypatch.setattr(guard.settings, "telegram_chat_id", "fake-admin")
    client = MagicMock(
        send_message=AsyncMock(side_effect=TimeoutError), aclose=AsyncMock()
    )
    monkeypatch.setattr(guard, "TelegramClient", MagicMock(return_value=client))
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        data = (
            _response(guard.WAZZUP_WEBHOOK_URL) if len(requests) == 4 else _response()
        )
        return httpx.Response(200, json=data)

    _transport(monkeypatch, handler)
    assert await guard.reconcile_wazzup_webhook(context) == {"status": "restored"}
    context["redis"].eval.assert_awaited_once()
