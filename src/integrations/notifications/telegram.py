"""Telegram Bot API client for sending notifications.

Sends text messages and documents via the Telegram Bot API.
Silently no-ops when bot_token is empty (not configured).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
MAX_RETRIES = 3
RETRY_DELAYS = [0.5, 1.0, 2.0]


class TelegramClient:
    """Async Telegram Bot API client."""

    def __init__(self, bot_token: str = "", chat_id: str = "") -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._base_url = f"{TELEGRAM_API_BASE}/bot{bot_token}"
        self._http: httpx.AsyncClient | None = None

    def _get_http(self) -> httpx.AsyncClient:
        """Lazily create a reusable httpx.AsyncClient."""
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=10.0)
        return self._http

    @property
    def is_configured(self) -> bool:
        """Check if Telegram is configured with valid credentials."""
        return bool(self.bot_token)

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any] | None:
        """Send a text message via Telegram Bot API.

        Args:
            text: Message text (supports HTML formatting).
            chat_id: Override default chat_id.
            parse_mode: Message parse mode (HTML or Markdown).

        Returns:
            API response dict or None if not configured.
        """
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping send_message")
            return None

        target = chat_id or self.chat_id
        payload = {
            "chat_id": target,
            "text": text,
            "parse_mode": parse_mode,
        }

        return await self._post("sendMessage", json=payload)

    async def send_message_with_inline_keyboard(
        self,
        text: str,
        buttons: list[list[dict[str, str]]],
        chat_id: str | None = None,
        parse_mode: str = "HTML",
    ) -> dict[str, Any] | None:
        """Send a text message with an inline keyboard.

        Args:
            text: Message text (supports HTML formatting).
            buttons: Nested list of button dicts with 'text' and 'callback_data'.
            chat_id: Override default chat_id.
            parse_mode: Message parse mode.

        Returns:
            API response dict or None if not configured.
        """
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping send with keyboard")
            return None

        target = chat_id or self.chat_id
        payload: dict[str, Any] = {
            "chat_id": target,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": {"inline_keyboard": buttons},
        }

        return await self._post("sendMessage", json=payload)

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
    ) -> dict[str, Any] | None:
        """Acknowledge a callback query (inline button press).

        Args:
            callback_query_id: ID of the callback query to answer.
            text: Optional notification text.

        Returns:
            API response dict or None.
        """
        if not self.is_configured:
            return None

        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text

        return await self._post("answerCallbackQuery", json=payload)

    async def edit_message_reply_markup(
        self,
        chat_id: str | int,
        message_id: int,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Edit inline keyboard of an existing message.

        Pass reply_markup=None or empty dict to remove the keyboard.

        Args:
            chat_id: Chat identifier.
            message_id: Message to edit.
            reply_markup: New markup (None to remove).

        Returns:
            API response dict or None.
        """
        if not self.is_configured:
            return None

        payload: dict[str, Any] = {
            "chat_id": str(chat_id),
            "message_id": message_id,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        return await self._post("editMessageReplyMarkup", json=payload)

    async def send_document(
        self,
        file_bytes: bytes,
        filename: str,
        chat_id: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any] | None:
        """Send a document/file via Telegram Bot API.

        Args:
            file_bytes: Raw file content bytes.
            filename: Name for the uploaded file.
            chat_id: Override default chat_id.
            caption: Optional caption for the document.

        Returns:
            API response dict or None if not configured.
        """
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping send_document")
            return None

        target = chat_id or self.chat_id
        files = {"document": (filename, file_bytes)}
        data: dict[str, str] = {"chat_id": target}
        if caption:
            data["caption"] = caption

        return await self._post("sendDocument", data=data, files=files)

    async def get_webhook_info(self) -> dict[str, Any] | None:
        """Fetch the currently registered Telegram webhook state."""
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping get_webhook_info")
            return None

        return await self._post("getWebhookInfo", json={})

    async def set_webhook(
        self,
        webhook_url: str,
        *,
        secret_token: str,
        allowed_updates: list[str] | None = None,
    ) -> dict[str, Any] | None:
        """Register the Telegram webhook with the desired runtime secret."""
        if not self.is_configured:
            logger.debug("Telegram not configured, skipping set_webhook")
            return None

        payload: dict[str, Any] = {
            "url": webhook_url,
            "secret_token": secret_token,
        }
        if allowed_updates is not None:
            payload["allowed_updates"] = allowed_updates

        return await self._post("setWebhook", json=payload)

    async def aclose(self) -> None:
        """Close the underlying httpx client if it was opened."""
        if self._http is None or self._http.is_closed:
            return
        await self._http.aclose()

    async def _post(
        self,
        method: str,
        json: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes]] | None = None,
    ) -> dict[str, Any] | None:
        """Send POST request to Telegram API with retries."""
        import asyncio

        url = f"{self._base_url}/{method}"
        client = self._get_http()

        for attempt in range(MAX_RETRIES):
            try:
                if json is not None:
                    resp = await client.post(url, json=json)
                else:
                    resp = await client.post(url, data=data, files=files)

                resp.raise_for_status()
                result: dict[str, Any] = resp.json()

                if not result.get("ok"):
                    logger.warning("Telegram API returned ok=false: %s", result)
                return result

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited — extract retry_after
                    retry_after = (
                        e.response.json()
                        .get("parameters", {})
                        .get("retry_after", RETRY_DELAYS[attempt])
                    )
                    logger.warning(
                        "Telegram rate limit hit, retrying in %ss", retry_after
                    )
                    await asyncio.sleep(float(retry_after))
                    continue

                logger.error(
                    "Telegram API error (attempt %d/%d): %s",
                    attempt + 1,
                    MAX_RETRIES,
                    e,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                return None

            except Exception:
                logger.exception(
                    "Telegram request failed (attempt %d/%d)",
                    attempt + 1,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                return None

        return None
