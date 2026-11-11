"""Regression suite for tj-r62i.12 (tj-x8d8): Nikita Nov 10 / Noor Nov 11 mirror audit fixes.

Covers four structural classes uncovered by auditing Nikita's Nov 10 shift and
Noor's Nov 11 live production logs:
1. Local .xlsx / .docx / .csv BOQ extraction (with zip-bomb & DTD safety) and
   truthful >MAX_MEDIA_PER_BATCH overflow notes (*2157 BOQ, *4283 12-photo burst).
2. Made-to-order / zero-stock catalog fallback in RAG + truthful availability
   framing for Sofas & Custom Furniture (all 28 SOFA-* items have stock=0).
3. Preventing _reply_may_be_superseded from discarding turns that triggered a
   runtime escalation/manager alert, plus seeding escalation_repeat:{conv.id}
   after delivering a pausing handoff reply (*6892 race condition).
4. Keeping compound/additive bulk quantity detection while avoiding false sums
   across mutually exclusive ``or`` / ``/`` alternatives (*1456 refinement).
"""

from __future__ import annotations

import datetime
import io
import uuid
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import ToolReturn

import src.llm.engine as engine_module
from src.integrations.vision.media_reader import (
    CSV_MIME,
    DOCX_MIME,
    XLSX_MIME,
    describe_customer_media,
    detect_media_mime,
    extract_local_document_text,
)
from src.llm import LLMResponse
from src.llm.engine import _MADE_TO_ORDER_STOCK_LINE, SalesDeps, search_products
from src.llm.escalation_policy import b2b_handoff_decision, wholesale_quantity
from src.models.conversation import Conversation
from src.models.message import Message
from src.rag.pipeline import search_products as rag_pipeline_search_products
from src.schemas.product import ProductSearchQuery
from src.schemas.webhook import WazzupIncomingMessage, WazzupMedia
from src.services import chat, inbound_media
from src.services.chat import (
    _build_escalation_repeat_key,
    _reply_may_be_superseded,
    process_incoming_batch,
)
from src.services.customer_language import is_strongly_arabic_customer_text
from src.services.inbound_batch import inbound_chat_reference, inbound_queue_key
from src.services.inbound_media import (
    MAX_MEDIA_PER_BATCH,
    format_media_note,
    read_customer_media,
)
from src.services.runtime_execution_evidence import RuntimeToolTrace

CHAT_ID = "971509998877"
CHANNEL_ID = "chan-mirror-audit"


@pytest.fixture(autouse=True)
def _authorized_outbound_unit_fixture() -> Iterator[None]:
    with patch("src.services.outbound_safety._SendScope.check", new_callable=AsyncMock):
        yield


def _build_sample_boq_xlsx() -> bytes:
    """Build an in-memory .xlsx matching live chat *2157 (rich-text sst + NO/SET qty)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Furniture BOQ" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="6" uniqueCount="6">'
            "<si><t>L. FURNITURE WORKS</t></si>"
            "<si><t>L1</t></si>"
            "<si><r><t>Open Office </t></r><r><t>(GF) Workstation Chairs</t></r></si>"
            "<si><t>NO</t></si>"
            "<si><t>L2</t></si>"
            "<si><t>Break Area - L shaped sectional Sofa</t></si>"
            "</sst>",
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheetData>"
            '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
            '<row r="2">'
            '<c r="A2" t="s"><v>1</v></c>'
            '<c r="B2" t="s"><v>2</v></c>'
            '<c r="C2" t="s"><v>3</v></c>'
            '<c r="D2"><v>24</v></c>'
            "</row>"
            '<row r="3">'
            '<c r="A3" t="s"><v>4</v></c>'
            '<c r="B3" t="s"><v>5</v></c>'
            '<c r="C3" t="inlineStr"><is><t>SET</t></is></c>'
            '<c r="D3"><v>2</v></c>'
            "</row>"
            "</sheetData>"
            "</worksheet>",
        )
    return buf.getvalue()


def _build_sample_docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>"
            "</w:document>",
        )
    return buf.getvalue()


@pytest.mark.asyncio
async def test_xlsx_boq_attachment_is_read_locally_and_triggers_wholesale_handoff() -> (
    None
):
    xlsx_bytes = _build_sample_boq_xlsx()
    assert detect_media_mime(xlsx_bytes, None) == XLSX_MIME
    assert detect_media_mime(xlsx_bytes, "application/octet-stream") == XLSX_MIME

    downloader = AsyncMock()
    downloader.download_media = AsyncMock(return_value=xlsx_bytes)

    def _forbid_http(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Unexpected OpenRouter call for local xlsx: {request.url}"
        )

    real_async_client = httpx.AsyncClient

    def _mock_client_factory(*_args: Any, **_kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(_forbid_http))

    msg = WazzupIncomingMessage(
        messageId="boq-1",
        chatId=CHAT_ID,
        type="document",
        text="for sc rate.xlsx",
        channelId=CHANNEL_ID,
        contentUri="https://store.wazzup24.com/d79005de518426f41e82515ca8d05471",
        media=WazzupMedia(
            url="https://store.wazzup24.com/d79005de518426f41e82515ca8d05471",
            mimeType=None,
        ),
    )

    with (
        patch.object(inbound_media, "WazzupProvider") as provider_cls,
        patch.object(
            inbound_media.httpx, "AsyncClient", side_effect=_mock_client_factory
        ),
    ):
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=downloader)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        notes = await read_customer_media(
            [msg], channel_id=CHANNEL_ID, batch_ref="ib1_boq"
        )

    note = notes["boq-1"]
    assert note.read is True
    assert note.cost == 0.0
    assert note.model == "local/document_reader"
    assert '"for sc rate.xlsx"' in note.content
    assert "Open Office (GF) Workstation Chairs" in note.content
    assert "Qty: 24 pcs" in note.content
    assert "Qty: 2 sets" in note.content
    assert "\n" not in note.content
    assert wholesale_quantity(note.content) >= 24
    assert b2b_handoff_decision(note.content).allowed is True


@pytest.mark.asyncio
async def test_docx_and_csv_attachments_extract_locally_without_paid_api() -> None:
    docx_bytes = _build_sample_docx("Fit-out inquiry: 15 executive desks and 10 chairs")
    csv_bytes = b"Item,Unit,Qty\nErgonomic Mesh Chair,NO,30\nMeeting Table,SET,2\n"

    assert detect_media_mime(docx_bytes, "application/octet-stream") == DOCX_MIME
    assert detect_media_mime(csv_bytes, None, filename="schedule.csv") == CSV_MIME

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(AssertionError(req.url))
        )
    ) as client:
        docx_res = await describe_customer_media(
            docx_bytes, mime_type=DOCX_MIME, client=client, filename="inquiry.docx"
        )
        csv_res = await describe_customer_media(
            csv_bytes, mime_type=CSV_MIME, client=client, filename="schedule.csv"
        )

    assert "15 executive desks and 10 chairs" in docx_res.text
    assert docx_res.cost == 0.0
    assert "Ergonomic Mesh Chair | Qty: 30 pcs" in csv_res.text
    assert wholesale_quantity(csv_res.text) >= 30


def test_local_office_extractor_rejects_xxe_dtd_and_oversized_zip_entries() -> None:
    xxe_buf = io.BytesIO()
    with zipfile.ZipFile(xxe_buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe "boom">]>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:t>&xxe;</w:t></w:p></w:body></w:document>",
        )
    with pytest.raises(ValueError, match="DTD|entity"):
        extract_local_document_text(xxe_buf.getvalue(), mime_type=DOCX_MIME)

    bomb_buf = io.BytesIO()
    with zipfile.ZipFile(bomb_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "word/document.xml",
            b"<w:document>" + (b"A" * (9 * 1024 * 1024)) + b"</w:document>",
        )
    with pytest.raises(ValueError, match="uncompressed size limit"):
        extract_local_document_text(bomb_buf.getvalue(), mime_type=DOCX_MIME)


@pytest.mark.asyncio
async def test_media_burst_over_limit_emits_truthful_overflow_note_and_skips_language_detector() -> (
    None
):
    downloader = AsyncMock()
    downloader.download_media = AsyncMock(return_value=b"\xff\xd8\xffjpeg")
    describe = AsyncMock(
        return_value=SimpleNamespace(
            text="An office workstation.",
            model="test-vision",
            tokens_in=10,
            tokens_out=5,
            cost=0.0005,
        )
    )
    messages = [
        WazzupIncomingMessage(
            messageId=f"img-{i}",
            chatId=CHAT_ID,
            type="image",
            channelId=CHANNEL_ID,
            contentUri=f"https://cdn.wazzup24.com/{i}.jpg",
            media=WazzupMedia(
                url=f"https://cdn.wazzup24.com/{i}.jpg", mimeType="image/jpeg"
            ),
        )
        for i in range(1, 9)
    ]
    with (
        patch.object(inbound_media, "WazzupProvider") as provider_cls,
        patch.object(inbound_media, "describe_customer_media", describe),
    ):
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=downloader)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        notes = await read_customer_media(
            messages, channel_id=CHANNEL_ID, batch_ref="ib1_burst"
        )

    assert describe.await_count == MAX_MEDIA_PER_BATCH
    for idx in range(1, MAX_MEDIA_PER_BATCH + 1):
        assert notes[f"img-{idx}"].read is True
    for idx in range(MAX_MEDIA_PER_BATCH + 1, 9):
        overflow = notes[f"img-{idx}"].content
        assert notes[f"img-{idx}"].read is False
        assert "could not be opened" not in overflow
        assert f"only the first {MAX_MEDIA_PER_BATCH} attachments" in overflow
        assert "\n" not in overflow
        # Arabic customer text accompanied by overflow notes must still detect as Arabic.
        assert is_strongly_arabic_customer_text(f"أريد مكتب استقبال\n{overflow}")

    doc_overflow = format_media_note(
        message_type="document",
        caption="extra.pdf",
        description=None,
        mime_type="application/pdf",
        skipped_due_to_batch_limit=True,
    )
    assert "could not be opened" not in doc_overflow
    assert 'additional document "extra.pdf"' in doc_overflow


def _catalog_orm_row(
    sku: str,
    name_en: str,
    *,
    category: str,
    stock: int,
    price: float,
    zoho_item_id: str | None = None,
) -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name_en,
        name_ar=None,
        description_en="",
        category=category,
        subcategory=None,
        price=price,
        currency="AED",
        stock=stock,
        image_url="https://cdn.example.com/item.jpg",
        zoho_item_id=zoho_item_id,
        attributes=None,
        is_active=True,
        created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
        updated_at=None,
    )


@pytest.mark.asyncio
async def test_rag_search_products_falls_back_to_zero_stock_sofas_without_extra_embedding() -> (
    None
):
    in_stock_reception = _catalog_orm_row(
        "OF-HAI-Luma-Reception-RJ 9788-8-1800-Walnut",
        "Reception desk 1800 SKYLAND LUMA 9788-8",
        category="Desks & Tables",
        stock=2,
        price=1450.0,
        zoho_item_id="zoho-rec-1",
    )
    sofa_cosima = _catalog_orm_row(
        "SOFA-COSIMA",
        "Cosima Office Sofa",
        category="Sofas",
        stock=0,
        price=2000.0,
        zoho_item_id=None,
    )
    sofa_cloud = _catalog_orm_row(
        "SOFA-CLOUD",
        "Cloud Office Sofa",
        category="Sofas",
        stock=0,
        price=1850.0,
        zoho_item_id=None,
    )

    first_res = MagicMock()
    first_res.scalars.return_value.all.return_value = [in_stock_reception]
    second_res = MagicMock()
    second_res.scalars.return_value.all.return_value = [sofa_cosima, sofa_cloud]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[first_res, second_res])
    embedder = AsyncMock()
    embedder.embed_async = AsyncMock(return_value=[0.1, 0.2, 0.3])

    for sofa_query in ("3-seater reception sofa", "office couch", "كنب مكتبي"):
        db.execute.reset_mock()
        db.execute.side_effect = [first_res, second_res]
        embedder.embed_async.reset_mock()

        result = await rag_pipeline_search_products(
            db,
            ProductSearchQuery(
                query=sofa_query,
                in_stock_only=True,
                include_made_to_order_fallback=True,
                limit=3,
            ),
            embedder,
        )
        assert embedder.embed_async.await_count == 1
        assert db.execute.await_count == 2
        assert [p.sku for p in result.products] == ["SOFA-COSIMA", "SOFA-CLOUD"]


@pytest.mark.asyncio
async def test_rag_search_products_skips_fallback_when_in_stock_matches_or_item_missing() -> (
    None
):
    in_stock_chair = _catalog_orm_row(
        "CH 460 black",
        "Operative Office Chair CH 460 black",
        category="Chairs",
        stock=8,
        price=180.0,
        zoho_item_id="zoho-ch-460",
    )
    zero_stock_chair = _catalog_orm_row(
        "CH 999 black",
        "Operative Office Chair CH 999 black",
        category="Chairs",
        stock=0,
        price=220.0,
        zoho_item_id="zoho-ch-999",
    )

    primary_res = MagicMock()
    primary_res.scalars.return_value.all.return_value = [in_stock_chair]
    fallback_res = MagicMock()
    fallback_res.scalars.return_value.all.return_value = [zero_stock_chair]

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[primary_res, fallback_res])
    embedder = AsyncMock()
    embedder.embed_async = AsyncMock(return_value=[0.1, 0.2, 0.3])

    # 1. Ordinary in-stock match does not even run the second SQL query.
    exact_res = await rag_pipeline_search_products(
        db,
        ProductSearchQuery(
            query="office chair",
            in_stock_only=True,
            include_made_to_order_fallback=True,
            limit=3,
        ),
        embedder,
    )
    assert db.execute.await_count == 1
    assert [p.sku for p in exact_res.products] == ["CH 460 black"]

    # 2. Non-existent product ("water dispenser") does not adopt unrelated zero-stock rows.
    db.execute.reset_mock()
    db.execute.side_effect = [primary_res, fallback_res]
    missing_res = await rag_pipeline_search_products(
        db,
        ProductSearchQuery(
            query="water dispenser",
            in_stock_only=True,
            include_made_to_order_fallback=True,
            limit=3,
        ),
        embedder,
    )
    assert [p.sku for p in missing_res.products] == ["CH 460 black"]


@dataclass
class _DummyCtx:
    deps: SalesDeps


@pytest.mark.asyncio
async def test_engine_search_products_marks_made_to_order_sofas_without_ready_stock_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sofa_row = _catalog_orm_row(
        "SOFA-COSIMA",
        "Cosima Office Sofa",
        category="Sofas",
        stock=0,
        price=2000.0,
        zoho_item_id=None,
    )
    captured_queries: list[ProductSearchQuery] = []

    async def _fake_rag(
        db: Any, query: ProductSearchQuery, embedding_engine: Any
    ) -> Any:
        captured_queries.append(query)
        from src.schemas.product import ProductRead, ProductSearchResult

        return ProductSearchResult(
            products=[ProductRead.model_validate(sofa_row)],
            query_interpreted=query.query,
            total_found=1,
        )

    monkeypatch.setattr(engine_module, "rag_search_products", _fake_rag)
    db = AsyncMock()
    empty_res = MagicMock()
    empty_res.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=empty_res)
    zoho = AsyncMock()
    zoho.get_stock_bulk = AsyncMock(return_value=[])

    ctx = _DummyCtx(
        deps=SalesDeps(
            db=db,
            redis=AsyncMock(),
            conversation=Conversation(
                id=uuid.uuid4(),
                phone=CHAT_ID,
                sales_stage="discovery",
                language="en",
            ),
            embedding_engine=AsyncMock(),
            zoho_inventory=zoho,
            zoho_crm=AsyncMock(),
            messaging_client=MagicMock(),
            pii_map={},
            crm_context={"Segment": "Unknown"},
            defer_product_media=True,
        )
    )

    result = await search_products(ctx, "Cosima Office Sofa")  # type: ignore[arg-type]
    assert (
        captured_queries and captured_queries[0].include_made_to_order_fallback is True
    )
    assert isinstance(result, ToolReturn)
    text = str(result.return_value)
    assert "Name: Cosima Office Sofa" in text
    assert "2000.00 AED" in text
    assert _MADE_TO_ORDER_STOCK_LINE in text


class _BatchFakeRedis:
    def __init__(self) -> None:
        self.lists: defaultdict[str, list[str]] = defaultdict(list)
        self.values: dict[str, Any] = {}

    async def set(
        self, key: str, value: Any, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def setex(self, key: str, _ttl: int, value: Any) -> bool:
        self.values[key] = value
        return True

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def lrange(self, key: str, _start: int, _end: int) -> list[str]:
        return list(self.lists[key])

    async def lmove(self, source: str, target: str, *_where: str) -> str | None:
        if not self.lists[source]:
            return None
        value = self.lists[source].pop(0)
        self.lists[target].append(value)
        return value

    async def llen(self, key: str) -> int:
        return len(self.lists[key])

    async def lpush(self, key: str, *values: str) -> int:
        for value in values:
            self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def rpush(self, key: str, *values: str) -> int:
        self.lists[key].extend(values)
        return len(self.lists[key])

    async def eval(self, script: str, key_count: int, *args: str) -> int:
        keys, argv = args[:key_count], args[key_count:]
        if script == chat._RELEASE_OR_CONTINUE_INBOUND_SCRIPT:
            if self.values.get(keys[0]) != argv[0]:
                return -1
            if self.lists[keys[1]]:
                return 1
            self.values.pop(keys[0], None)
            return 0
        if script == chat._RELEASE_INBOUND_LOCK_SCRIPT:
            if self.values.get(keys[0]) == argv[0]:
                self.values.pop(keys[0], None)
                return 1
            return 0
        if script == chat._FINALIZE_INBOUND_BATCH_SCRIPT:
            self.lists.pop(keys[0], None)
            return 1
        raise AssertionError("unexpected script")

    def __getattr__(self, name: str) -> AsyncMock:
        return AsyncMock(return_value=None)


@pytest.mark.asyncio
async def test_handoff_turn_is_never_superseded_and_suppresses_immediate_duplicate_ack() -> (
    None
):
    """Reproduces *6892: wholesale handoff + queued '?' must keep consultative reply."""
    search_only_response = LLMResponse(
        text=(
            "Here are 4-table workstation sets with 5 chairs each. "
            "A Treejar manager has been notified about your project order and "
            "will contact you shortly with project pricing."
        ),
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
        model="anthropic/claude-sonnet-5.5",
        tool_traces=(
            RuntimeToolTrace(
                call_id="c-1",
                tool_name="search_products",
                arguments_digest="0" * 64,
                outcome_digest="1" * 64,
                state="returned",
            ),
        ),
    )
    assert _reply_may_be_superseded(search_only_response, 1) is True
    assert (
        _reply_may_be_superseded(search_only_response, 1, escalation_mutated=True)
        is False
    )

    redis = _BatchFakeRedis()
    batch_ref = inbound_chat_reference(CHAT_ID)
    queue_key = inbound_queue_key(batch_ref)
    redis.lists[queue_key].append(
        WazzupIncomingMessage(
            messageId="m-bulk-1",
            chatId=CHAT_ID,
            chatType="whatsapp",
            type="text",
            text="I need 4 table with 5 chairs like 4 set",
            channelId=CHANNEL_ID,
            timestamp=1790179140,
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
    session.scalar = AsyncMock(return_value="none")

    def _execute(statement: Any) -> MagicMock:
        result = MagicMock()
        stmt_str = str(statement)
        if "count(" in stmt_str.lower():
            result.scalar_one.return_value = 2
            return result
        if "conversation_summaries" in stmt_str:
            result.scalar_one_or_none.return_value = None
            return result
        result.scalars.return_value.first.return_value = None
        if "wazzup_message_id" in stmt_str:
            result.scalars.return_value.all.return_value = [
                item.wazzup_message_id for item in added if isinstance(item, Message)
            ]
        else:
            result.scalars.return_value.all.return_value = [conversation]
        return result

    session.execute.side_effect = _execute

    async def _fake_process_message(**_kwargs: Any) -> LLMResponse:
        # Deterministic wholesale handoff mutated escalation_status without tool_traces.
        conversation.escalation_status = "pending"
        conversation.metadata_ = {
            **(conversation.metadata_ or {}),
            "wholesale_handoff_notified_at": "2026-11-11T09:51:16+00:00",
        }
        # Customer sends "?" while LLM turn is still running.
        await redis.rpush(
            queue_key,
            WazzupIncomingMessage(
                messageId="m-followup-q",
                chatId=CHAT_ID,
                chatType="whatsapp",
                type="text",
                text="?",
                channelId=CHANNEL_ID,
                timestamp=1790179145,
            ).model_dump_json(),
        )
        return search_only_response

    wazzup = AsyncMock()
    wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")
    send_text = AsyncMock()
    renotify_mgr = AsyncMock()

    with (
        patch("src.services.chat.settings.wazzup_channel_id", CHANNEL_ID),
        patch("src.services.chat.async_session_factory") as session_factory,
        patch("src.services.chat.process_message", side_effect=_fake_process_message),
        patch("src.services.chat.WazzupProvider") as provider_cls,
        patch("src.services.chat.ZohoInventoryClient") as inventory_cls,
        patch("src.services.chat.ZohoCRMClient") as crm_cls,
        patch("src.services.chat.EmbeddingEngine"),
        patch("src.services.chat.send_wazzup_text_with_audit", send_text),
        patch(
            "src.services.chat.wait_for_inbound_quiet", new=AsyncMock(return_value=0.0)
        ),
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            renotify_mgr,
        ),
    ):
        session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        session_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=wazzup)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        inventory_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        inventory_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        crm_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        crm_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        await process_incoming_batch({"redis": redis, "job_try": 1}, batch_ref)

    # Consultative handoff reply WAS delivered, and "?" did NOT trigger duplicate canned ack!
    sent_texts = [call.kwargs["text"] for call in send_text.await_args_list]
    assert len(sent_texts) == 1
    assert "4-table workstation sets" in sent_texts[0]
    assert "Thank you for your message!" not in sent_texts[0]
    assert await redis.get(_build_escalation_repeat_key(conversation.id)) == "1"


@pytest.mark.parametrize(
    ("customer_text", "expected_qty", "expected_allowed"),
    [
        ("I need 12 desks and 12 chairs for our new office", 24, True),
        ("I need 4 table with 5 chairs like 4 set", 20, True),
        ("4 sets of 5 chairs", 20, True),
        ("12 black chairs or 12 grey chairs", 12, False),
        ("12 chairs in black / 12 chairs in grey", 12, False),
        ("12 كراسي أسود أو 12 كراسي رمادي", 12, False),
        ("8 desks, and 6 black chairs or 6 grey chairs", 14, False),
        ("10 desks, and 12 black chairs or 12 grey chairs", 22, True),
        ("We're furnishing a new office for 25 people.", 0, False),
    ],
)
def test_bulk_quantity_distinguishes_additive_orders_from_or_alternatives(
    customer_text: str,
    expected_qty: int,
    expected_allowed: bool,
) -> None:
    assert wholesale_quantity(customer_text) == expected_qty
    assert b2b_handoff_decision(customer_text).allowed is expected_allowed
