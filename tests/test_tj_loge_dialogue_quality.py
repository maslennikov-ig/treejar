"""Live dialogue quality fixes from the 2026-11-05 pilot review (tj-loge).

- tj-loge.1: customer photos and documents reach the sales turn as text.
- tj-loge.2: a burst of customer messages is answered once, after a pause.
- tj-loge.3: a job application or supplier pitch alerts a manager.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.config import settings
from src.integrations.vision import media_reader
from src.integrations.vision.media_reader import (
    describe_customer_media,
    detect_media_mime,
)
from src.llm import LLMResponse, message_processor
from src.llm.non_sales_intent import non_sales_intent
from src.models.conversation import Conversation
from src.models.message import Message
from src.schemas.webhook import WazzupIncomingMessage, WazzupMedia
from src.services import inbound_media
from src.services.chat import process_incoming_batch
from src.services.customer_language import is_strongly_arabic_customer_text
from src.services.inbound_batch import (
    inbound_chat_reference,
    inbound_queue_key,
    inbound_quiet_wait_seconds,
    serialize_inbound_message,
    wait_for_inbound_quiet,
)
from src.services.inbound_media import (
    CustomerMediaNote,
    format_media_note,
    read_customer_media,
)
from tests.test_chat_reply_supersession import CHANNEL_ID, CHAT_ID, _FakeRedis

# --- tj-loge.2: quiet window -------------------------------------------------


def test_quiet_window_waits_for_the_newest_message() -> None:
    assert (
        inbound_quiet_wait_seconds(
            [100.0, 110.0], now=112.0, quiet_seconds=15.0, max_wait_seconds=60.0
        )
        == 13.0
    )


def test_quiet_window_is_capped_from_the_oldest_message() -> None:
    assert (
        inbound_quiet_wait_seconds(
            [100.0, 158.0], now=159.0, quiet_seconds=15.0, max_wait_seconds=60.0
        )
        == 1.0
    )
    assert (
        inbound_quiet_wait_seconds(
            [100.0, 170.0], now=171.0, quiet_seconds=15.0, max_wait_seconds=60.0
        )
        == 0.0
    )


def test_quiet_window_disabled_or_empty_does_not_wait() -> None:
    assert (
        inbound_quiet_wait_seconds(
            [], now=1.0, quiet_seconds=15.0, max_wait_seconds=60.0
        )
        == 0.0
    )
    assert (
        inbound_quiet_wait_seconds(
            [1.0], now=1.0, quiet_seconds=0.0, max_wait_seconds=60.0
        )
        == 0.0
    )


def _queued(text: str, received_at: float, **extra: Any) -> str:
    return serialize_inbound_message(
        WazzupIncomingMessage(
            messageId=str(uuid.uuid4()),
            chatId=CHAT_ID,
            text=text,
            channelId=CHANNEL_ID,
            **extra,
        ),
        received_at=received_at,
    )


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.mark.asyncio
async def test_wait_for_quiet_sleeps_until_the_customer_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "inbound_quiet_seconds", 15.0)
    monkeypatch.setattr(settings, "inbound_quiet_max_wait_seconds", 60.0)
    redis = _FakeRedis()
    clock = _Clock(1000.0)
    redis.lists["q"].append(_queued("Wholesale only?", 997.0))

    waited = await wait_for_inbound_quiet(redis, "q", sleep=clock.sleep, clock=clock)

    assert waited == pytest.approx(12.0)
    assert clock.now == pytest.approx(1012.0)


@pytest.mark.asyncio
async def test_wait_for_quiet_extends_when_another_message_arrives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "inbound_quiet_seconds", 15.0)
    monkeypatch.setattr(settings, "inbound_quiet_max_wait_seconds", 60.0)
    redis = _FakeRedis()
    clock = _Clock(1000.0)
    redis.lists["q"].append(_queued("Two only", 1000.0))

    async def sleep(seconds: float) -> None:
        await clock.sleep(seconds)
        if len(clock.sleeps) == 1:
            redis.lists["q"].append(
                _queued("The one we are using lock damaged", clock.now)
            )

    await wait_for_inbound_quiet(redis, "q", sleep=sleep, clock=clock)

    assert clock.now == pytest.approx(1020.0)


@pytest.mark.asyncio
async def test_wait_for_quiet_skips_when_a_manager_wrote(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "inbound_quiet_seconds", 15.0)
    redis = _FakeRedis()
    clock = _Clock(1000.0)
    redis.lists["q"].append(_queued("Hi", 999.0))
    redis.lists["q"].append(_queued("Manager here", 999.5, isEcho=True, status="sent"))

    assert (
        await wait_for_inbound_quiet(redis, "q", sleep=clock.sleep, clock=clock) == 0.0
    )


@pytest.mark.asyncio
async def test_wait_for_quiet_is_off_by_default_in_tests() -> None:
    redis = _FakeRedis()
    redis.lists["q"].append(_queued("Hi", 10**10))
    assert await wait_for_inbound_quiet(redis, "q") == 0.0


# --- tj-loge.1: attachments ---------------------------------------------------


def test_media_notes_name_what_the_customer_sent() -> None:
    photo = format_media_note(
        message_type="image", caption="", description="A grey cabinet\nlock, round."
    )
    assert (
        photo
        == "[The customer sent a photo. The photo shows: A grey cabinet lock, round.]"
    )
    captioned = format_media_note(
        message_type="image", caption="This one", description=None
    )
    assert captioned == (
        "[The customer sent a photo with the caption: 'This one'. It could not be opened.]"
    )
    document = format_media_note(
        message_type="document",
        caption="Touhid Furniture Technician.pdf",
        description="A CV of a furniture technician.",
        mime_type="application/pdf",
    )
    assert document == (
        '[The customer sent a document "Touhid Furniture Technician.pdf". '
        "It contains: A CV of a furniture technician.]"
    )
    assert "cannot view videos" in format_media_note(
        message_type="video", caption="", description=None
    )


def test_detect_media_mime_uses_declared_type_then_magic_bytes() -> None:
    assert detect_media_mime(b"", "image/jpg") == "image/jpeg"
    assert detect_media_mime(b"\x89PNG\r\n\x1a\nrest", None) == "image/png"
    assert (
        detect_media_mime(b"%PDF-1.7", "application/octet-stream") == "application/pdf"
    )
    assert detect_media_mime(b"plain", "text/plain") is None


@pytest.mark.asyncio
async def test_describe_customer_media_sends_image_and_parses_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "media_description_model", "anthropic/claude-haiku-5.5"
    )
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "anthropic/claude-haiku-5.5",
                "choices": [{"message": {"content": " A 2-seat workstation. "}}],
                "usage": {
                    "prompt_tokens": 900,
                    "completion_tokens": 40,
                    "cost": 0.0011,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await describe_customer_media(
            b"\xff\xd8\xffdata",
            mime_type="image/jpeg",
            client=client,
            caption="Size as same",
        )

    assert seen["url"].endswith("/chat/completions")
    parts = seen["body"]["messages"][1]["content"]
    assert "Size as same" in parts[0]["text"]
    assert parts[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert seen["body"]["temperature"] == 0.0
    assert result.text == "A 2-seat workstation."
    assert (result.tokens_in, result.tokens_out, result.cost) == (900, 40, 0.0011)


@pytest.mark.asyncio
async def test_describe_customer_media_sends_pdf_as_file() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "A CV."}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await describe_customer_media(
            b"%PDF-1.7", mime_type="application/pdf", client=client, filename="cv.pdf"
        )

    part = seen["body"]["messages"][1]["content"][1]
    assert part["type"] == "file"
    assert part["file"]["filename"] == "cv.pdf"
    assert part["file"]["file_data"].startswith("data:application/pdf;base64,")


def test_media_reader_limits_are_bounded() -> None:
    assert media_reader.media_size_limit("image/png") == media_reader.MAX_IMAGE_BYTES
    assert (
        media_reader.media_size_limit("application/pdf")
        == media_reader.MAX_DOCUMENT_BYTES
    )


def _image_message(message_id: str, *, url: str | None, text: str | None = None) -> Any:
    return WazzupIncomingMessage(
        messageId=message_id,
        chatId=CHAT_ID,
        type="image",
        text=text,
        channelId=CHANNEL_ID,
        contentUri=url,
        media=WazzupMedia(url=url, mimeType="image/jpeg") if url else None,
    )


@pytest.mark.asyncio
async def test_read_customer_media_describes_photos_and_survives_failures() -> None:
    downloader = AsyncMock()
    downloader.download_media = AsyncMock(return_value=b"\xff\xd8\xffdata")
    describe = AsyncMock(
        return_value=media_reader.MediaDescriptionResult(
            text="A cabinet lock with a round key barrel.", model="m", cost=0.001
        )
    )
    with (
        patch.object(inbound_media, "WazzupProvider") as provider_cls,
        patch.object(inbound_media, "describe_customer_media", describe),
    ):
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=downloader)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        notes = await read_customer_media(
            [
                _image_message("img-1", url="https://cdn.wazzup24.com/a.jpg"),
                _image_message("img-2", url=None),
            ],
            channel_id=CHANNEL_ID,
            batch_ref="ib1_test",
        )

    assert notes["img-1"].read is True
    assert notes["img-1"].content == (
        "[The customer sent a photo. The photo shows: A cabinet lock with a round key barrel.]"
    )
    assert notes["img-1"].cost == 0.001
    assert notes["img-2"].read is False
    assert "could not be opened" in notes["img-2"].content


@pytest.mark.asyncio
async def test_read_customer_media_reports_a_failed_read() -> None:
    downloader = AsyncMock()
    downloader.download_media = AsyncMock(side_effect=httpx.ConnectError("boom"))
    with patch.object(inbound_media, "WazzupProvider") as provider_cls:
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=downloader)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        notes = await read_customer_media(
            [
                _image_message(
                    "img-1", url="https://cdn.wazzup24.com/a.jpg", text="This one"
                )
            ],
            channel_id=CHANNEL_ID,
            batch_ref="ib1_test",
        )
    assert notes["img-1"].content == (
        "[The customer sent a photo with the caption: 'This one'. It could not be opened.]"
    )


@pytest.mark.asyncio
async def test_photo_only_batch_reaches_the_turn_and_is_stored() -> None:
    """*2588 / *5868: a photo with no text used to be dropped before the LLM."""

    redis = _FakeRedis()
    queue_key = inbound_queue_key(inbound_chat_reference(CHAT_ID))
    redis.lists[queue_key].append(
        _image_message("img-1", url="https://cdn.wazzup24.com/a.jpg").model_dump_json()
    )
    redis.lists[queue_key].append(
        WazzupIncomingMessage(
            messageId="txt-1",
            chatId=CHAT_ID,
            text="This type of lock available with you?",
            channelId=CHANNEL_ID,
        ).model_dump_json()
    )
    conversation = Conversation(
        id=uuid.uuid4(),
        phone=CHAT_ID,
        language="en",
        escalation_status="none",
        metadata_={"inbound_channel_id": CHANNEL_ID},
    )
    session = AsyncMock()
    added: list[object] = []
    session.add = MagicMock(side_effect=added.append)

    def execute(statement: Any) -> MagicMock:
        result = MagicMock()
        result.scalars.return_value.first.return_value = None
        if "wazzup_message_id" in str(statement):
            result.scalars.return_value.all.return_value = []
        else:
            result.scalars.return_value.all.return_value = [conversation]
        return result

    session.execute.side_effect = execute
    note = CustomerMediaNote(
        content="[The customer sent a photo. The photo shows: A round cabinet lock.]",
        read=True,
        tokens_in=900,
        tokens_out=20,
        cost=0.001,
        model="anthropic/claude-haiku-5.5",
    )
    read_media = AsyncMock(return_value={"img-1": note})
    process_message = AsyncMock(
        return_value=LLMResponse(
            text="That is a round cabinet lock.",
            tokens_in=1,
            tokens_out=1,
            cost=0.0,
            model="t",
        )
    )
    wazzup = AsyncMock()
    wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")
    with (
        patch("src.services.outbound_safety._SendScope.check", new_callable=AsyncMock),
        patch("src.services.chat.settings.wazzup_channel_id", CHANNEL_ID),
        patch("src.services.chat.async_session_factory") as session_factory,
        patch("src.services.chat.process_message", process_message),
        patch("src.services.chat.read_customer_media", read_media),
        patch("src.services.chat.WazzupProvider") as provider_cls,
        patch("src.services.chat.ZohoInventoryClient") as inventory_cls,
        patch("src.services.chat.ZohoCRMClient") as crm_cls,
        patch("src.services.chat.EmbeddingEngine"),
        patch("src.services.chat.send_wazzup_text_with_audit", AsyncMock()),
        patch(
            "src.services.chat._enqueue_summary_refresh_if_needed",
            new_callable=AsyncMock,
        ),
    ):
        session_factory.return_value.__aenter__.return_value = session
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=wazzup)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        for client_cls in (inventory_cls, crm_cls):
            client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await process_incoming_batch({"redis": redis}, inbound_chat_reference(CHAT_ID))

    read_media.assert_awaited_once()
    combined = process_message.await_args.kwargs["combined_text"]
    assert combined.startswith(
        "[The customer sent a photo. The photo shows: A round cabinet lock.]"
    )
    assert combined.endswith("This type of lock available with you?")
    stored = {
        item.wazzup_message_id: item
        for item in added
        if isinstance(item, Message) and item.role == "user"
    }
    assert stored["img-1"].content == note.content
    assert stored["img-1"].message_type == "image"
    assert (stored["img-1"].cost, stored["img-1"].model) == (
        0.001,
        "anthropic/claude-haiku-5.5",
    )


def test_media_note_does_not_hide_an_arabic_caption() -> None:
    text = (
        "هل يتوفر هذا القفل لديكم\n"
        "[The customer sent a photo. The photo shows: A grey metal cabinet with a "
        "round lock on the top drawer and two keys.]"
    )
    assert is_strongly_arabic_customer_text(text)


# --- tj-loge.3: non-sales messages --------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Dear Sir, I am seeking furniture technician tasks  having 7years of experience",
        '[The customer sent a document "a.pdf". It contains: A CV of a technician.]',
        "Any vacancy for a sales executive?",
        "أبحث عن عمل في شركتكم",
    ],
)
def test_job_applications_are_recognised(text: str) -> None:
    assert non_sales_intent(text) == "recruitment"


@pytest.mark.parametrize(
    "text",
    [
        "We are a leading manufacturer of office chairs in China",
        "We would like to become your supplier for office chairs",
    ],
)
def test_supplier_pitches_are_recognised(text: str) -> None:
    assert non_sales_intent(text) == "supplier_pitch"


@pytest.mark.parametrize(
    "text",
    [
        "manager desk required",
        "Qty.350Nos",
        "Work station  with cabinet",
        "Hi. I am interested in purchasing office furniture. Could you assist me?",
        "We need 20 chairs for our new office, the supplier we used closed",
        "Please include net 30 payment terms in the business proposal.",
        "",
    ],
)
def test_sales_messages_are_not_flagged(text: str) -> None:
    assert non_sales_intent(text) is None


def _turn(text: str, *, metadata: dict[str, Any] | None = None) -> Any:
    conversation = Conversation(
        id=uuid.uuid4(),
        phone=CHAT_ID,
        language="en",
        escalation_status="none",
        metadata_=metadata or {},
    )
    return SimpleNamespace(
        combined_text=text,
        db=AsyncMock(),
        deps=SimpleNamespace(conversation=conversation, recent_history=["Hi"]),
    )


@pytest.mark.asyncio
async def test_job_application_alerts_a_manager_once_without_pausing() -> None:
    turn = _turn("I am seeking furniture technician tasks having 7years of experience")
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        assert await message_processor._non_sales_team_notice(turn) == "recruitment"
        assert await message_processor._non_sales_team_notice(turn) is None

    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["pause_bot"] is False
    assert "job application" in kwargs["reason"]
    assert turn.deps.conversation.escalation_status == "none"


@pytest.mark.asyncio
async def test_paused_conversation_gets_no_non_sales_alert() -> None:
    turn = _turn("Any vacancy?")
    turn.deps.conversation.escalation_status = "pending"
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        assert await message_processor._non_sales_team_notice(turn) is None
    notify.assert_not_awaited()


def test_supplier_pitch_reply_says_it_was_passed_on() -> None:
    response = LLMResponse(
        text="Thank you for reaching out.",
        tokens_in=0,
        tokens_out=0,
        cost=0.0,
        model="t",
    )
    message_processor._ensure_supplier_pitch_notice(response, "en")
    assert response.text.endswith(
        "I have passed your message to Treejar's commercial team."
    )
    before = response.text
    message_processor._ensure_supplier_pitch_notice(response, "en")
    assert response.text == before
