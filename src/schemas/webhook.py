from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class WazzupMedia(BaseModel):
    url: str
    mimeType: str | None = None
    caption: str | None = None


class WazzupIncomingMessage(BaseModel):
    """Wazzup v3 webhook message.

    Real payload example from Wazzup:
    {
      "messageId": "uuid",
      "chatId": "971551220665",
      "chatType": "whatsapp",
      "channelId": "uuid",
      "text": "Hello",
      "type": "text",
      "status": "inbound",
      "dateTime": "2026-03-13T11:07:27.000",
      "authorType": "client"
    }
    """

    messageId: str
    chatId: str
    chatType: str = "whatsapp"
    text: str | None = None
    type: str = "text"
    channelId: str = ""
    status: str | None = None
    media: WazzupMedia | None = None

    # Wazzup v3 sends `dateTime` (string), not `timestamp` (int)
    dateTime: str | None = None
    timestamp: int | None = None

    # Additional Wazzup v3 fields
    authorType: str | None = None  # "client", "operator", "system"
    isEcho: bool | None = None

    model_config = {"extra": "allow"}


class WazzupWebhookPayload(BaseModel):
    # `test: true` is sent by Wazzup during webhook registration verification
    test: bool | None = None
    messages: list[WazzupIncomingMessage] = []
    # Wazzup also sends status updates in a separate array
    statuses: list[dict[str, Any]] = []

    model_config = {"extra": "allow"}
