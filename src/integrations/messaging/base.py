from __future__ import annotations

from typing import Protocol


class MessagingProvider(Protocol):
    """Abstract messaging provider interface.

    Implement this protocol to add new messaging channels
    (Wazzup, Meta Cloud API, Telegram, etc.)
    """

    async def send_text(
        self,
        chat_id: str,
        text: str,
        crm_message_id: str | None = None,
    ) -> str:
        """Send a text message. Returns message ID."""
        ...

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
        """Send media (image/document/audio). Returns message ID."""
        ...

    async def send_template(
        self,
        chat_id: str,
        template_name: str,
        params: dict[str, str],
        crm_message_id: str | None = None,
    ) -> str:
        """Send a pre-approved template message (for >24h follow-ups). Returns message ID."""
        ...
