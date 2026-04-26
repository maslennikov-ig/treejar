from __future__ import annotations

import asyncio
import logging
import mimetypes
from dataclasses import dataclass
from typing import Any

import httpx

from src.core.config import settings
from src.integrations.messaging.base import MessagingProvider
from src.services.inbound_channels import normalize_channel_phone

logger = logging.getLogger(__name__)

# Temporary file hosting for Wazzup contentUri (files expire after ~1h).
# Wazzup v3 API requires a *public URL* for media — base64 is NOT supported.
_TMPFILES_UPLOAD_URL = "https://tmpfiles.org/api/v1/upload"


@dataclass(frozen=True)
class WazzupMediaSendResult:
    message_id: str
    caption_message_id: str | None
    content_uri: str
    outbound_chat_id: str


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
                logger.error(
                    "Wazzup HTTP error %s: %s", e.response.status_code, e.response.text
                )
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

    @staticmethod
    async def _upload_to_tmpfiles(
        content: bytes,
        content_type: str | None = None,
    ) -> str:
        """Upload bytes to tmpfiles.org and return a direct-download URL.

        Wazzup v3 requires ``contentUri`` — a publicly accessible URL.
        tmpfiles.org provides free temporary hosting (files expire ~1 h),
        which is sufficient because WhatsApp caches media on delivery.

        Returns:
            Public direct-download URL (https://tmpfiles.org/dl/…).

        Raises:
            RuntimeError: If upload fails or the service is unavailable.
        """
        ext = (
            mimetypes.guess_extension(content_type or "application/octet-stream") or ""
        )
        filename = f"file{ext}"

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            resp = await http.post(
                _TMPFILES_UPLOAD_URL,
                files={
                    "file": (
                        filename,
                        content,
                        content_type or "application/octet-stream",
                    )
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "success":
            raise RuntimeError(f"tmpfiles.org upload failed: {data}")

        # tmpfiles.org URL: https://tmpfiles.org/12345/file.pdf
        # Direct-download:  https://tmpfiles.org/dl/12345/file.pdf
        page_url: str = data["data"]["url"]
        dl_url = page_url.replace("tmpfiles.org/", "tmpfiles.org/dl/", 1)
        logger.info("Uploaded %d bytes to %s", len(content), dl_url)
        return dl_url

    async def download_media(
        self, url: str, max_retries: int = 2, client: httpx.AsyncClient | None = None
    ) -> bytes:
        """Download media content (audio, images, etc.) from a URL.

        Uses a separate httpx.AsyncClient because media URLs are absolute
        CDN URLs (e.g. https://cdn.wazzup24.com/...), while self.client
        is configured with base_url=wazzup_api_url for API calls.

        Args:
            url: Full URL to the media file (typically from Wazzup CDN).
            max_retries: Number of retry attempts for transient failures.
            client: Optional shared httpx.AsyncClient to reuse connection.

        Returns:
            Raw bytes of the media file.
        """
        for attempt in range(1, max_retries + 1):
            try:
                if client is not None:
                    response = await client.get(url, timeout=httpx.Timeout(30.0))
                    response.raise_for_status()
                    return response.content
                else:
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(30.0)
                    ) as dl_client:
                        response = await dl_client.get(url)
                        response.raise_for_status()
                        return response.content
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt < max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise
        raise RuntimeError("Unreachable")

    @staticmethod
    def _extract_message_id(data: Any) -> str:
        """Extract messageId from Wazzup response (dict or list)."""
        if isinstance(data, dict):
            return str(data.get("messageId", "unknown"))
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            return str(data[0].get("messageId", "unknown"))
        return "unknown"

    @staticmethod
    def _outbound_chat_id(chat_id: str) -> str:
        """Strip repo-owned smoke suffixes before calling Wazzup.

        Our live smoke tooling may decorate the inbound chatId as
        ``+7999...#smoke-tag`` to keep the test conversation isolated in app
        storage. Wazzup only accepts the real WhatsApp chat id, so outbound
        delivery must use the base part before ``#``.
        """
        base_chat_id, _, suffix = chat_id.partition("#")
        if suffix and base_chat_id:
            logger.info(
                "Using base Wazzup chatId %s for synthetic profile suffix %s",
                base_chat_id,
                suffix,
            )
            return base_chat_id
        return chat_id

    def outbound_chat_id(self, chat_id: str) -> str:
        return self._outbound_chat_id(chat_id)

    async def send_text(
        self,
        chat_id: str,
        text: str,
        crm_message_id: str | None = None,
    ) -> str:
        """Send a text message. Returns message ID."""
        outbound_chat_id = self._outbound_chat_id(chat_id)
        payload: dict[str, Any] = {
            "chatId": outbound_chat_id,
            "chatType": "whatsapp",
            "text": text,
        }
        if self.channel_id:
            payload["channelId"] = self.channel_id
        if crm_message_id:
            payload["crmMessageId"] = crm_message_id

        response = await self._request("POST", "/message", json=payload)
        return self._extract_message_id(response.json())

    async def send_media_detailed(
        self,
        chat_id: str,
        url: str | None = None,
        caption: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
        crm_message_id: str | None = None,
        caption_crm_message_id: str | None = None,
    ) -> WazzupMediaSendResult:
        """Send media and return both media and optional caption message IDs.

        Wazzup v3 constraints:
        - Files must be sent via ``contentUri`` (publicly accessible URL).
        - ``text`` and ``contentUri`` **cannot** coexist in the same request.

        When ``content`` (raw bytes) is provided, the file is first uploaded
        to a temporary hosting service to obtain a public URL.

        If both a file and a caption are provided, two messages are sent:
        first the file, then the caption text.
        """
        # Resolve the public URL for the file
        content_uri: str | None = url
        if content and not content_uri:
            content_uri = await self._upload_to_tmpfiles(content, content_type)

        if not content_uri:
            raise ValueError("send_media requires either url or content")

        outbound_chat_id = self._outbound_chat_id(chat_id)

        # --- Send the file (contentUri only, no text) ---
        payload: dict[str, Any] = {
            "chatId": outbound_chat_id,
            "chatType": "whatsapp",
            "contentUri": content_uri,
        }
        if self.channel_id:
            payload["channelId"] = self.channel_id
        if crm_message_id:
            payload["crmMessageId"] = crm_message_id

        response = await self._request("POST", "/message", json=payload)
        msg_id = self._extract_message_id(response.json())

        # --- Send caption as a separate text message (if provided) ---
        caption_msg_id: str | None = None
        if caption:
            try:
                caption_msg_id = await self.send_text(
                    outbound_chat_id,
                    caption,
                    crm_message_id=caption_crm_message_id,
                )
            except Exception:
                logger.warning(
                    "File sent (msg_id=%s) but caption failed", msg_id, exc_info=True
                )

        return WazzupMediaSendResult(
            message_id=msg_id,
            caption_message_id=caption_msg_id,
            content_uri=content_uri,
            outbound_chat_id=outbound_chat_id,
        )

    async def send_media(
        self,
        chat_id: str,
        url: str | None = None,
        caption: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
        crm_message_id: str | None = None,
        caption_crm_message_id: str | None = None,
    ) -> str:
        """Send media (image/document/audio). Returns media message ID."""
        result = await self.send_media_detailed(
            chat_id=chat_id,
            url=url,
            caption=caption,
            content=content,
            content_type=content_type,
            crm_message_id=crm_message_id,
            caption_crm_message_id=caption_crm_message_id,
        )
        msg_id = result.message_id
        return msg_id

    async def send_template(
        self,
        chat_id: str,
        template_name: str,
        params: dict[str, str] | None = None,
        crm_message_id: str | None = None,
    ) -> str:
        """Send a pre-approved template message (for >24h follow-ups). Returns message ID."""
        if params is not None:
            # Just an example mapping, exact schema depends on Wazzup
            # For simpler templates, content could be just a string
            pass

        outbound_chat_id = self._outbound_chat_id(chat_id)
        payload: dict[str, Any] = {
            "chatId": outbound_chat_id,
            "chatType": "whatsapp",
            "template": True,
            # For simplicity, assuming Wazzup format accepts a text mapped to template
            # Real Wazzup HSM format differs but keeping the interface intact.
            "text": template_name,
        }
        if self.channel_id:
            payload["channelId"] = self.channel_id
        if crm_message_id:
            payload["crmMessageId"] = crm_message_id

        response = await self._request("POST", "/message", json=payload)
        return self._extract_message_id(response.json())

    async def resolve_channel_phone(self, channel_id: str) -> str | None:
        """Resolve a Wazzup channelId into a normalized plainId phone."""
        response = await self._request("GET", "/channels")
        payload = response.json()
        channels = payload if isinstance(payload, list) else []

        for channel in channels:
            if not isinstance(channel, dict):
                continue
            if channel.get("channelId") != channel_id:
                continue
            plain_id = channel.get("plainId")
            if not isinstance(plain_id, str):
                return None
            return normalize_channel_phone(plain_id)

        return None

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
