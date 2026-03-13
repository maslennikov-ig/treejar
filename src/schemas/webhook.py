from __future__ import annotations

from pydantic import BaseModel


class WazzupMedia(BaseModel):
    url: str
    mimeType: str | None = None
    caption: str | None = None


class WazzupIncomingMessage(BaseModel):
    messageId: str
    chatId: str
    chatType: str
    text: str | None = None
    type: str  # "text" | "image" | "audio" | "document"
    channelId: str
    timestamp: int
    status: str | None = None
    media: WazzupMedia | None = None


class WazzupWebhookPayload(BaseModel):
    # `test: true` is sent by Wazzup during webhook registration verification
    test: bool | None = None
    messages: list[WazzupIncomingMessage] = []


class WazzupWebhookResponse(BaseModel):
    ok: bool = True
