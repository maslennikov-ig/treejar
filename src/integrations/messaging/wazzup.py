from __future__ import annotations

import asyncio
from typing import Any

import httpx

from src.core.config import settings
from src.integrations.messaging.base import MessagingProvider


class WazzupProvider(MessagingProvider):
    """Wazzup API client implementing MessagingProvider protocol."""

    def __init__(self, channel_id: str | None = None) -> None:
        """Initialize the Wazzup API client.

        Args:
            channel_id: Default channelId for messages. Can be overridden per request.
        """
        self.base_url = settings.wazzup_api_url
        self.api_key = settings.wazzup_api_key
        self.channel_id = channel_id

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=httpx.Timeout(30.0),
        )

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        """Make an authenticated request to Wazzup API with retries and backoff."""
        max_retries = 3

        for attempt in range(1, max_retries + 1):
            try:
                response = await self.client.request(
                    method=method,
                    url=path,
                    json=json,
                )
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                # 429 Too Many Requests
                if e.response.status_code == 429 and attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise

            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise

        raise RuntimeError("Unreachable")

    async def send_text(self, chat_id: str, text: str) -> str:
        """Send a text message. Returns message ID.

        Wazzup returns a message ID if successful, or an empty response body
        sometimes, so we return a placeholder if not present.
        """
        payload: dict[str, Any] = {
            "chatId": chat_id,
            "chatType": "whatsapp",
            "text": text,
        }
        if self.channel_id:
            payload["channelId"] = self.channel_id

        response = await self._request("POST", "/message", json=payload)
        data = response.json()

        if isinstance(data, dict):
            return str(data.get("messageId", "unknown"))
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
             return str(data[0].get("messageId", "unknown"))
        return "unknown"

    async def send_media(
        self, chat_id: str, url: str, caption: str | None = None
    ) -> str:
        """Send media (image/document/audio). Returns message ID."""
        payload: dict[str, Any] = {
            "chatId": chat_id,
            "chatType": "whatsapp",
            "contentUri": url,  # Wazzup v3 uses contentUri instead of media.url
        }
        if caption:
            payload["text"] = caption
        if self.channel_id:
            payload["channelId"] = self.channel_id

        response = await self._request("POST", "/message", json=payload)
        data = response.json()

        if isinstance(data, dict):
            return str(data.get("messageId", "unknown"))
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
             return str(data[0].get("messageId", "unknown"))
        return "unknown"

    async def send_template(
        self, chat_id: str, template_name: str, params: dict[str, str] | None = None
    ) -> str:
        """Send a pre-approved template message (for >24h follow-ups). Returns message ID."""
        if params is not None:
             # Just an example mapping, exact schema depends on Wazzup
             # For simpler templates, content could be just a string
             pass

        payload: dict[str, Any] = {
            "chatId": chat_id,
            "chatType": "whatsapp",
            "template": True,
            # For simplicity, assuming Wazzup format accepts a text mapped to template
            # Real Wazzup HSM format differs but keeping the interface intact.
            "text": template_name,
        }
        if self.channel_id:
            payload["channelId"] = self.channel_id

        response = await self._request("POST", "/message", json=payload)
        data = response.json()

        if isinstance(data, dict):
            return str(data.get("messageId", "unknown"))
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
             return str(data[0].get("messageId", "unknown"))
        return "unknown"

    async def __aenter__(self) -> WazzupProvider:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
