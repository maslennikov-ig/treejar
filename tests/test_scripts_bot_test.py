from __future__ import annotations

import datetime as dt
import http.client
import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BOT_TEST_MODULE_PATH = REPO_ROOT / "scripts" / "bot_test.py"


def _load_bot_test_module():
    spec = importlib.util.spec_from_file_location(
        "scripts.bot_test",
        BOT_TEST_MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_conversations_url_uses_trailing_slash_and_query_encoding() -> None:
    bot_test = _load_bot_test_module()

    url = bot_test.build_conversations_url(
        base_url="https://noor.starec.ai",
        phone="+79262810921",
        page_size=5,
    )

    assert (
        url
        == "https://noor.starec.ai/api/v1/conversations/?phone=%2B79262810921&page_size=5"
    )


def test_parse_json_response_rejects_html_body() -> None:
    bot_test = _load_bot_test_module()

    with pytest.raises(ValueError, match="Expected JSON"):
        bot_test.parse_json_response(
            body="<!doctype html><html><body>spa</body></html>",
            url="https://noor.starec.ai/api/v1/conversations?phone=%2B79262810921",
            content_type="text/html; charset=utf-8",
        )


def test_find_matching_assistant_reply_requires_matching_user_marker() -> None:
    bot_test = _load_bot_test_module()
    started_at = dt.datetime(2026, 4, 11, 15, 8, 10, tzinfo=dt.UTC)

    messages = [
        {
            "role": "user",
            "content": "Please send a quotation for 1 CSC-01 beige.",
            "created_at": "2026-04-11T15:08:12+00:00",
        },
        {
            "role": "assistant",
            "content": "Old pending reply that belongs to another attempt.",
            "created_at": "2026-04-11T15:08:20+00:00",
        },
    ]

    assert (
        bot_test.find_matching_assistant_reply(
            messages=messages,
            marker="[smoke:abc123]",
            started_at=started_at,
        )
        is None
    )


def test_find_matching_assistant_reply_returns_user_and_assistant_after_marker() -> (
    None
):
    bot_test = _load_bot_test_module()
    started_at = dt.datetime(2026, 4, 11, 15, 8, 10, tzinfo=dt.UTC)

    matching = bot_test.find_matching_assistant_reply(
        messages=[
            {
                "role": "assistant",
                "content": "Older assistant reply.",
                "created_at": "2026-04-11T15:08:11+00:00",
            },
            {
                "role": "user",
                "content": "Please send a quotation.\n[smoke:abc123]",
                "created_at": "2026-04-11T15:08:12+00:00",
            },
            {
                "role": "assistant",
                "content": "Quotation sent to the manager for review.",
                "created_at": "2026-04-11T15:08:15+00:00",
            },
        ],
        marker="[smoke:abc123]",
        started_at=started_at,
    )

    assert matching is not None
    user_message, assistant_message = matching
    assert user_message["role"] == "user"
    assert "[smoke:abc123]" in user_message["content"]
    assert assistant_message["role"] == "assistant"
    assert assistant_message["content"] == "Quotation sent to the manager for review."


def test_find_matching_user_message_tolerates_second_precision_api_timestamps() -> None:
    bot_test = _load_bot_test_module()
    started_at = dt.datetime(2026, 4, 11, 15, 48, 48, 900000, tzinfo=dt.UTC)

    matching = bot_test.find_matching_user_message(
        messages=[
            {
                "role": "user",
                "content": "Smoke helper tty proof.\n[smoke:154513de]",
                "created_at": "2026-04-11T15:48:48",
            },
            {
                "role": "assistant",
                "content": "I want to be accurate, so our manager will confirm this for you.",
                "created_at": "2026-04-11T15:48:54.818112",
            },
        ],
        marker="[smoke:154513de]",
        started_at=started_at,
    )

    assert matching is not None
    assert matching["role"] == "user"


def test_build_webhook_payload_includes_channel_id_and_marker() -> None:
    bot_test = _load_bot_test_module()
    sent_at = dt.datetime(2026, 4, 11, 15, 8, 10, tzinfo=dt.UTC)

    payload = bot_test.build_webhook_payload(
        phone="+79262810921",
        author_type="client",
        text="Smoke path check\n[smoke:abc123]",
        message_id="smoke-123",
        sent_at=sent_at,
        channel_id="b49b1b9d-757f-4104-b56d-8f43d62cc515",
    )

    message = payload["messages"][0]
    assert message["channelId"] == "b49b1b9d-757f-4104-b56d-8f43d62cc515"
    assert message["messageId"] == "smoke-123"
    assert "[smoke:abc123]" in message["text"]


def test_poll_for_reply_runs_final_grace_check_for_recent_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_test = _load_bot_test_module()
    started_at = dt.datetime(2026, 4, 11, 15, 14, 21, tzinfo=dt.UTC)
    conversation_id = "conv-123"

    responses = iter(
        [
            (
                200,
                {
                    "items": [
                        {
                            "id": conversation_id,
                            "updated_at": "2026-04-11T15:14:29+00:00",
                        }
                    ]
                },
            ),
            (
                200,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Smoke path check\n[smoke:abc123]",
                            "created_at": "2026-04-11T15:14:29+00:00",
                        }
                    ]
                },
            ),
            (
                200,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Smoke path check\n[smoke:abc123]",
                            "created_at": "2026-04-11T15:14:29+00:00",
                        },
                        {
                            "role": "assistant",
                            "content": "I want to be accurate, so our manager will confirm this for you.",
                            "created_at": "2026-04-11T15:14:30.948511+00:00",
                        },
                    ],
                    "updated_at": "2026-04-11T15:14:30.611628+00:00",
                },
            ),
        ]
    )

    def fake_http_json(
        url: str,
        *,
        data: dict[str, object] | None = None,
        timeout: float = 20.0,
    ) -> tuple[int, dict[str, object]]:
        del url, data, timeout
        return next(responses)

    monkeypatch.setattr(bot_test, "http_json", fake_http_json)
    monkeypatch.setattr(bot_test.time, "sleep", lambda _: None)

    matched_conversation_id, _, _, assistant_message = bot_test.poll_for_reply(
        base_url="https://noor.starec.ai",
        phone="+79262810921",
        marker="[smoke:abc123]",
        started_at=started_at,
        wait_secs=1,
    )

    assert matched_conversation_id == conversation_id
    assert assistant_message["role"] == "assistant"


def test_poll_for_reply_checks_phone_conversations_even_when_list_updated_at_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_test = _load_bot_test_module()
    started_at = dt.datetime(2026, 4, 11, 15, 17, 55, tzinfo=dt.UTC)
    conversation_id = "conv-123"

    responses = iter(
        [
            (
                200,
                {
                    "items": [
                        {
                            "id": conversation_id,
                            "updated_at": "2026-04-11T15:14:30.611628+00:00",
                        }
                    ]
                },
            ),
            (
                200,
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": "Smoke path check\n[smoke:stale]",
                            "created_at": "2026-04-11T15:17:55+00:00",
                        },
                        {
                            "role": "assistant",
                            "content": "Thank you for your message! A manager has been notified.",
                            "created_at": "2026-04-11T15:18:02.430073+00:00",
                        },
                    ],
                    "updated_at": "2026-04-11T15:14:30.611628+00:00",
                },
            ),
        ]
    )

    def fake_http_json(
        url: str,
        *,
        data: dict[str, object] | None = None,
        timeout: float = 20.0,
    ) -> tuple[int, dict[str, object]]:
        del url, data, timeout
        return next(responses)

    monkeypatch.setattr(bot_test, "http_json", fake_http_json)
    monkeypatch.setattr(bot_test.time, "sleep", lambda _: None)

    matched_conversation_id, _, _, assistant_message = bot_test.poll_for_reply(
        base_url="https://noor.starec.ai",
        phone="+79262810921",
        marker="[smoke:stale]",
        started_at=started_at,
        wait_secs=1,
    )

    assert matched_conversation_id == conversation_id
    assert assistant_message["content"].startswith("Thank you for your message!")


def test_http_json_retries_after_incomplete_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot_test = _load_bot_test_module()

    class FakeResponse:
        def __init__(self, *, body: str, fail_once: bool = False) -> None:
            self._body = body
            self._fail_once = fail_once
            self.headers = {"Content-Type": "application/json"}
            self.status = 200

        def read(self) -> bytes:
            if self._fail_once:
                self._fail_once = False
                partial = self._body[:20].encode("utf-8")
                raise http.client.IncompleteRead(
                    partial, len(self._body) - len(partial)
                )
            return self._body.encode("utf-8")

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

    responses = iter(
        [
            FakeResponse(body='{"ok": true}', fail_once=True),
            FakeResponse(body='{"ok": true}'),
        ]
    )

    def fake_urlopen(request: Any, timeout: float = 20.0) -> FakeResponse:
        del request, timeout
        return next(responses)

    monkeypatch.setattr(bot_test.urllib.request, "urlopen", fake_urlopen)

    status, payload = bot_test.http_json("https://noor.starec.ai/api/v1/test")

    assert status == 200
    assert payload == {"ok": True}
