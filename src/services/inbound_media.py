"""Turn customer photos, documents and other attachments into message text.

Wazzup delivers an image or a PDF with no text, so the stored message was
empty and the model never learned an attachment existed. Each customer
attachment now becomes a bracketed note: what the photo shows (read by a
vision model), what the document contains, or that a file could not be
opened. The note is the message content, so history and every text guard see
it on later turns too.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any

import httpx

from src.integrations.messaging.wazzup import MediaDownloadTooLarge, WazzupProvider
from src.integrations.vision.media_reader import (
    DOCUMENT_MIME_TYPES,
    LOCAL_DOCUMENT_MIME_TYPES,
    MAX_DOCUMENT_BYTES,
    describe_customer_media,
    detect_media_mime,
    media_size_limit,
    normalize_mime,
)

logger = logging.getLogger(__name__)

READABLE_MEDIA_TYPES = frozenset({"image", "document", "file", "sticker"})
UNREADABLE_MEDIA_TYPES = frozenset({"video", "gif", "unsupported"})
MAX_MEDIA_PER_BATCH = 6


@dataclass(frozen=True, slots=True)
class CustomerMediaNote:
    content: str
    read: bool
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost: float | None = None
    model: str | None = None


def _media_url(message: Any) -> str | None:
    url = getattr(message, "contentUri", None)
    media = getattr(message, "media", None)
    if not url and media is not None:
        url = getattr(media, "url", None)
    return url if isinstance(url, str) and url.startswith("https://") else None


def _declared_mime(message: Any) -> str:
    media = getattr(message, "media", None)
    return normalize_mime(getattr(media, "mimeType", None) if media else None)


def _caption(message: Any) -> str:
    media = getattr(message, "media", None)
    caption = getattr(media, "caption", None) if media else None
    text = getattr(message, "text", None)
    for value in (caption, text):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _filename_hint(message: Any, url: str | None, caption: str) -> str | None:
    media = getattr(message, "media", None)
    for candidate in (
        getattr(media, "fileName", None) if media else None,
        getattr(media, "filename", None) if media else None,
        caption,
    ):
        if isinstance(candidate, str) and "." in candidate.strip():
            return candidate.strip()
    if url:
        parsed = urllib.parse.urlparse(url)
        tail = urllib.parse.unquote(parsed.path.rsplit("/", 1)[-1])
        if "." in tail:
            return tail
        for query_name in urllib.parse.parse_qs(parsed.query).get("filename", ()):
            cleaned = query_name.strip()
            if "." in cleaned:
                return cleaned
    return None


def _kind_label(message_type: str, mime_type: str | None) -> str:
    if (
        mime_type in DOCUMENT_MIME_TYPES
        or mime_type in LOCAL_DOCUMENT_MIME_TYPES
        or message_type in {"document", "file"}
    ):
        return "document"
    return "photo"


def format_media_note(
    *,
    message_type: str,
    caption: str,
    description: str | None,
    mime_type: str | None = None,
    skipped_due_to_batch_limit: bool = False,
    size_limit_bytes: int | None = None,
) -> str:
    """Return the stored text for one customer attachment.

    The note stays on one line so the language check can skip it
    (``_MEDIA_NOTE_RE`` in ``src/services/customer_language.py``).
    """
    caption = " ".join(caption.split())
    description = " ".join(description.split()) if description else None
    if message_type == "unsupported":
        return (
            "[The customer sent an attachment in a format WhatsApp could not deliver.]"
        )
    if message_type in UNREADABLE_MEDIA_TYPES:
        note = f"[The customer sent a {message_type}; Noor cannot view videos.]"
        return f"{caption}\n{note}" if caption else note
    kind = _kind_label(message_type, mime_type)
    if size_limit_bytes is not None:
        name = f' "{caption}"' if caption else ""
        limit_mib = size_limit_bytes // (1024 * 1024)
        return (
            f"[The customer sent a {kind}{name}, but it could not be opened "
            f"because it exceeds the {limit_mib} MiB attachment limit.]"
        )
    if skipped_due_to_batch_limit:
        if kind == "document":
            name = f' "{caption}"' if caption else ""
            return (
                f"[The customer sent an additional document{name}; only the first "
                f"{MAX_MEDIA_PER_BATCH} attachments in one message burst are "
                "inspected automatically.]"
            )
        caption_part = f" with the caption: {caption!r}" if caption else ""
        return (
            f"[The customer sent an additional photo{caption_part}; only the first "
            f"{MAX_MEDIA_PER_BATCH} attachments in one message burst are "
            "inspected automatically.]"
        )
    if kind == "document":
        name = f' "{caption}"' if caption else ""
        if description:
            return f"[The customer sent a document{name}. It contains: {description}]"
        return f"[The customer sent a document{name}, but it could not be opened.]"
    head = (
        f"[The customer sent a photo with the caption: {caption!r}."
        if caption
        else ("[The customer sent a photo.")
    )
    if description:
        return f"{head} The photo shows: {description}]"
    return f"{head} It could not be opened.]"


def is_customer_media(message: Any) -> bool:
    message_type = str(getattr(message, "type", "") or "")
    return (
        message_type in READABLE_MEDIA_TYPES or message_type in UNREADABLE_MEDIA_TYPES
    )


async def _read_one(
    message: Any,
    *,
    downloader: WazzupProvider,
    client: httpx.AsyncClient,
    batch_ref: str,
) -> CustomerMediaNote:
    message_type = str(getattr(message, "type", "") or "")
    caption = _caption(message)
    declared = _declared_mime(message)
    url = _media_url(message)
    if url is None:
        logger.warning(
            "Customer attachment has no downloadable URL: batch_ref=%s type=%s",
            batch_ref,
            message_type,
        )
        return CustomerMediaNote(
            content=format_media_note(
                message_type=message_type,
                caption=caption,
                description=None,
                mime_type=declared or None,
            ),
            read=False,
        )
    mime_type: str | None = declared or None
    filename_hint = _filename_hint(message, url, caption)
    try:
        data = await downloader.download_media(
            url, max_retries=2, client=client, max_bytes=MAX_DOCUMENT_BYTES
        )
        mime_type = detect_media_mime(data, declared, filename=filename_hint)
        if mime_type is None:
            raise ValueError("Unsupported attachment type")
        is_doc_mime = (
            mime_type in DOCUMENT_MIME_TYPES or mime_type in LOCAL_DOCUMENT_MIME_TYPES
        )
        filename = (caption or filename_hint) if is_doc_mime else None
        size_limit = media_size_limit(mime_type)
        if len(data) > size_limit:
            logger.warning(
                "Customer attachment exceeds size limit: batch_ref=%s size=%d limit=%d",
                batch_ref,
                len(data),
                size_limit,
            )
            return CustomerMediaNote(
                content=format_media_note(
                    message_type=message_type,
                    caption=filename or caption,
                    description=None,
                    mime_type=mime_type,
                    size_limit_bytes=size_limit,
                ),
                read=False,
            )
        result = await describe_customer_media(
            data,
            mime_type=mime_type,
            client=client,
            filename=filename,
            caption=None if filename == caption else caption,
        )
    except MediaDownloadTooLarge:
        is_document = _kind_label(message_type, declared) == "document"
        return CustomerMediaNote(
            content=format_media_note(
                message_type=message_type,
                caption=caption or filename_hint or "",
                description=None,
                mime_type=declared,
                size_limit_bytes=MAX_DOCUMENT_BYTES
                if is_document
                else media_size_limit(declared),
            ),
            read=False,
        )
    except Exception as exc:
        logger.warning(
            "Could not read customer attachment: batch_ref=%s type=%s error_type=%s",
            batch_ref,
            message_type,
            type(exc).__name__,
        )
        return CustomerMediaNote(
            content=format_media_note(
                message_type=message_type,
                caption=caption,
                description=None,
                mime_type=mime_type,
            ),
            read=False,
        )
    return CustomerMediaNote(
        content=format_media_note(
            message_type=message_type,
            caption=caption,
            description=result.text,
            mime_type=mime_type,
        ),
        read=True,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        cost=result.cost,
        model=result.model,
    )


async def read_customer_media(
    messages: list[Any],
    *,
    channel_id: str,
    batch_ref: str,
) -> dict[str, CustomerMediaNote]:
    """Return a note per customer attachment, keyed by Wazzup message id."""
    targets = [m for m in messages if m.messageId and is_customer_media(m)]
    if not targets:
        return {}
    notes: dict[str, CustomerMediaNote] = {}
    readable: list[Any] = []
    for message in targets:
        if message.type in READABLE_MEDIA_TYPES and len(readable) < MAX_MEDIA_PER_BATCH:
            readable.append(message)
            continue
        notes[message.messageId] = CustomerMediaNote(
            content=format_media_note(
                message_type=str(message.type),
                caption=_caption(message),
                description=None,
                mime_type=_declared_mime(message) or None,
                skipped_due_to_batch_limit=True,
            ),
            read=False,
        )
    if not readable:
        return notes
    try:
        async with (
            WazzupProvider(channel_id=channel_id) as downloader,
            httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client,
        ):
            results = await asyncio.gather(
                *(
                    _read_one(
                        m, downloader=downloader, client=client, batch_ref=batch_ref
                    )
                    for m in readable
                )
            )
    except Exception as exc:
        logger.warning(
            "Customer attachment reading failed: batch_ref=%s error_type=%s",
            batch_ref,
            type(exc).__name__,
        )
        results = [
            CustomerMediaNote(
                content=format_media_note(
                    message_type=str(m.type), caption=_caption(m), description=None
                ),
                read=False,
            )
            for m in readable
        ]
    for message, note in zip(readable, results, strict=True):
        notes[message.messageId] = note
    return notes
