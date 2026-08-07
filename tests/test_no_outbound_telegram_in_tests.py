"""The suite must never be able to message the owner (tj-0ikw).

`conftest.py` already neutralised the OpenRouter and Wazzup credentials and had
never neutralised Telegram, so a run in a checkout with a populated `.env` sent
real alerts. It did, on 2026-08-06: four `LLM final failure` messages naming
`mock-model` arrived on the owner's phone at 20:53, from tests in
`test_llm_engine.py` that drive the safety wrapper to give up and — unlike the
tests in `test_llm_safety.py` — do not patch the notifier.

Emptying the token in `conftest` is the fix. This file is what stops it coming
back, because the failure is silent from inside the suite: everything passes
either way and only the owner's phone knows the difference.
"""

from __future__ import annotations

import pytest

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient


def test_the_runtime_telegram_credentials_are_not_loaded() -> None:
    assert settings.telegram_bot_token == ""
    assert settings.telegram_chat_id == ""


def test_a_client_built_from_settings_refuses_to_send() -> None:
    """`is_configured` is the last gate before the network call."""
    client = TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )

    assert client.is_configured is False


@pytest.mark.asyncio
async def test_the_llm_safety_notifier_reaches_no_network() -> None:
    """The exact path that produced the four alerts, run for real.

    Nothing is mocked: if the credentials ever leak back in, this call attempts
    a live send and the test stops being a no-op.
    """
    from src.llm.safety import notify_llm_safety_event

    await notify_llm_safety_event(
        event="final_failure",
        path="core_chat",
        model_name="mock-model",
        error=TimeoutError(),
    )


@pytest.mark.asyncio
async def test_send_telegram_message_reports_it_did_not_send() -> None:
    from src.services.notifications import send_telegram_message

    assert await send_telegram_message("this must not leave the machine") is False
