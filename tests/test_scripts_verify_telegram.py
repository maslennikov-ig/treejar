from __future__ import annotations

from types import SimpleNamespace

import pytest
from scripts import verify_telegram


@pytest.mark.asyncio
async def test_live_verification_accepts_boolean_configuration_property(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sent_messages: list[str] = []

    class FakeTelegramClient:
        def __init__(self, *, bot_token: str, chat_id: str) -> None:
            self.is_configured = bool(bot_token and chat_id)

        async def send_message(self, text: str) -> None:
            sent_messages.append(text)

    monkeypatch.setattr(
        verify_telegram,
        "settings",
        SimpleNamespace(
            telegram_bot_token="synthetic-token",
            telegram_chat_id="synthetic-chat",
        ),
    )
    monkeypatch.setattr(
        "src.integrations.notifications.telegram.TelegramClient",
        FakeTelegramClient,
    )
    monkeypatch.setenv("SEND_TEST", "1")
    verify_telegram.passed = 0
    verify_telegram.failed = 0

    with pytest.raises(SystemExit) as exit_info:
        await verify_telegram.main()

    assert exit_info.value.code == 0
    assert sent_messages == [
        "🤖 TreeJar verification test — if you see this, notifications work!"
    ]
    assert "Test message sent to Telegram successfully" in capsys.readouterr().out
