"""Regressions from the 2026-09-23 tester-feedback live replay.

Receipt: docs/reports/2026-09-23-tester-feedback-replay.json. Each test states
the structural rule the fix introduced, never the replayed wording.
"""

from __future__ import annotations

import datetime
import json
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel

import src.llm.message_processor as processor
from src.dialogue.claim_contract import RetrievedRow, row_from_catalog_product
from src.dialogue.decision_state import decision_state_directives
from src.dialogue.order_state import QuoteConsent, QuoteLifecycle
from src.dialogue.state import DialogueState
from src.llm import engine
from src.llm.catalog_planning import (
    SalesDeps,
    StockSnapshot,
    _enforce_claim_contract,
    _verify_volunteered_claims,
)
from src.llm.message_processor import (
    _limited_stock_product_references,
    _sales_agent_route,
    _Turn,
)
from src.llm.outbound_reply_guard import (
    finalize_customer_reply_text,
    looks_like_structured_payload,
)
from src.llm.response_runtime import ProductMediaPayload, dedupe_product_media
from src.llm.verified_answers import classify_product_match
from src.models.conversation import Conversation

# A claim-contract envelope cut at the completion limit, as in scenario A turn 2.
_TRUNCATED_ENVELOPE = (
    '{"claims":[{"claim_type":"catalog_fact","sku":"OF-HAI-Luma-Workstation-RJ '
    '9719-4-Walnut","field_path":"catalog description","value":"Screen dividers '
    'and three-drawer mobile pedestals for each user","source_value":"SKYLAND LUMA'
)


class _FakeResult:
    def __init__(self, output: str) -> None:
        self.output = output

    def usage(self) -> None:
        return None


def _conversation(metadata: dict[str, Any] | None = None) -> Conversation:
    return Conversation(
        id=uuid4(),
        phone="local",
        customer_name="Nadia",
        language="en",
        sales_stage="qualifying",
        metadata_=metadata or {},
    )


def _deps(conversation: Conversation | None = None, **kwargs: Any) -> SalesDeps:
    return SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=conversation or _conversation(),
        embedding_engine=None,
        zoho_inventory=None,
        zoho_crm=None,
        messaging_client=None,
        pii_map={},
        **kwargs,
    )


def _claim_deps() -> SalesDeps:
    deps = _deps(runtime_directives=("prior directive", "claim contract directive"))
    deps.claim_rows["AX-E1"] = row_from_catalog_product(
        sku="AX-E1",
        attributes={"specifications": {"Mechanism": "synchronised tilt"}},
        extras={"price": 800, "currency": "AED"},
    )
    return deps


# --- 1. An unreadable repair envelope never becomes customer text ------------


def test_structured_payload_detection_is_structural() -> None:
    assert looks_like_structured_payload(_TRUNCATED_ENVELOPE)
    assert looks_like_structured_payload('  ```json\n{"answer": "x"}\n```')
    assert looks_like_structured_payload("[1, 2]")
    assert not looks_like_structured_payload("The LUMA costs AED 1,883.")
    assert not looks_like_structured_payload("")


@pytest.mark.asyncio
async def test_truncated_repair_falls_back_to_the_pre_repair_draft() -> None:
    draft = _FakeResult("AX-E1 uses a synchronised tilt and costs AED 800.")

    async def _never(_deps: SalesDeps) -> None:
        raise AssertionError("an unreadable payload has no claims to retry")

    result, contract = await _enforce_claim_contract(
        _FakeResult(_TRUNCATED_ENVELOPE),
        repair_deps=_claim_deps(),
        repair_payload="{}",
        run_agent=_never,
        fallback_result=draft,
    )

    assert result.output == draft.output
    assert result.fell_back is True
    assert contract is None


@pytest.mark.asyncio
async def test_plain_text_repair_keeps_the_previous_behaviour() -> None:
    repaired = _FakeResult("A plain answer that ignored the envelope.")

    async def _never(_deps: SalesDeps) -> None:
        raise AssertionError("no retry for plain text")

    result, contract = await _enforce_claim_contract(
        repaired,
        repair_deps=_claim_deps(),
        repair_payload="{}",
        run_agent=_never,
        fallback_result=_FakeResult("draft"),
    )

    assert result is repaired
    assert contract is None


@pytest.mark.asyncio
async def test_truncated_retry_falls_back_to_the_pre_repair_draft() -> None:
    refuted = json.dumps(
        {
            "claims": [
                {
                    "claim_type": "catalog_fact",
                    "sku": "AX-E1",
                    "field_path": "attributes.specifications.Mechanism",
                    "value": "knee tilt",
                }
            ],
            "answer": "AX-E1 uses a knee tilt.",
        }
    )
    draft = _FakeResult("AX-E1 costs AED 800.")

    async def _retry(_deps: SalesDeps) -> _FakeResult:
        return _FakeResult(_TRUNCATED_ENVELOPE)

    result, contract = await _enforce_claim_contract(
        _FakeResult(refuted),
        repair_deps=_claim_deps(),
        repair_payload="{}",
        run_agent=_retry,
        fallback_result=draft,
    )

    assert result.output == draft.output
    assert not looks_like_structured_payload(result.output)
    assert contract is not None and contract.withheld


@pytest.mark.asyncio
async def test_truncated_volunteered_retry_leaves_the_turn_as_it_was() -> None:
    original = _FakeResult("AX-E1 uses a knee tilt and costs AED 800.")
    outputs = iter(
        [
            json.dumps(
                {
                    "claims": [
                        {
                            "claim_type": "catalog_fact",
                            "sku": "AX-E1",
                            "field_path": "attributes.specifications.Mechanism",
                            "value": "knee tilt",
                        }
                    ],
                    "answer": "rewrite",
                }
            ),
            _TRUNCATED_ENVELOPE,
        ]
    )

    async def _run(_deps: SalesDeps) -> _FakeResult:
        return _FakeResult(next(outputs))

    result, _contract = await _verify_volunteered_claims(
        original, run_deps=_claim_deps(), run_agent=_run
    )

    assert result is original


@pytest.mark.parametrize("language", ["en", "ar"])
def test_outbound_guard_never_sends_a_json_payload(language: str) -> None:
    guarded = finalize_customer_reply_text(_TRUNCATED_ENVELOPE, language=language)

    assert not looks_like_structured_payload(guarded)
    assert "claim_type" not in guarded
    assert guarded.strip()


def test_outbound_guard_unwraps_a_readable_claims_envelope() -> None:
    envelope = json.dumps(
        {"claims": [], "answer": "The LUMA 9719-4 is AED 1,883 per four-seat unit."}
    )

    assert (
        finalize_customer_reply_text(envelope, language="en")
        == "The LUMA 9719-4 is AED 1,883 per four-seat unit."
    )


def test_outbound_guard_leaves_prose_untouched() -> None:
    text = "The LUMA 9719-4 is AED 1,883. Shall I prepare a quotation?"

    assert finalize_customer_reply_text(text, language="en") == text


@pytest.mark.asyncio
async def test_catalog_repair_route_sends_the_draft_when_the_repair_is_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conv = _conversation()
    deps = _deps(
        conv,
        user_query="Compare LUMA and NOVO",
        recent_history=["assistant: Shall I compare them?"],
    )
    snapshot = "LUMA 9719-4: catalog price AED 1000. NOVO: catalog price AED 800."
    calls: list[int] = []

    async def search_products(ctx: RunContext[SalesDeps], query: str) -> str:
        ctx.deps.claim_rows["LUMA"] = RetrievedRow(
            sku="LUMA", fields={"price": "1000", "name": "LUMA 9719-4"}
        )
        return snapshot

    def model_request(messages: Any, info: Any) -> ModelResponse:
        calls.append(1)
        if len(calls) == 1:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        "search_products", {"query": "LUMA NOVO"}, tool_call_id="c1"
                    )
                ]
            )
        if len(calls) == 2:
            return ModelResponse(parts=[TextPart("LUMA is AED 1000; NOVO is AED 800.")])
        return ModelResponse(parts=[TextPart(_TRUNCATED_ENVELOPE)])

    model = FunctionModel(model_request)
    turn = _Turn(
        pending_reference_route=None,
        order_quote_route=None,
        db=deps.db,
        redis=deps.redis,
        conversation_id=conv.id,
        embedding_engine=None,
        zoho_client=None,
        messaging_client=None,
        crm_client=None,
        source_message_id=None,
        latency_trace=None,
        context_started=None,
        conv=conv,
        crm_context=None,
        pii_map={},
        history=[
            ModelRequest(parts=[UserPromptPart("Furniture for our team")]),
            ModelResponse(parts=[TextPart("Shall I compare them?")]),
        ],
        is_first_turn=False,
        model_runtime=SimpleNamespace(
            get=AsyncMock(return_value=("local-function-model", model))
        ),
        current_message_quote_customer_details={},
        combined_text=deps.user_query,
        masked_text=deps.user_query,
        recent_history=deps.recent_history,
        deps=deps,
    )
    monkeypatch.setattr(
        engine, "build_system_prompt", AsyncMock(return_value="NOOR BASE PERSONA")
    )
    monkeypatch.setattr(
        processor, "_materialize_verified_catalog_facts", lambda _deps: snapshot
    )
    with engine.sales_agent.override(model=model, tools=[search_products]):
        response = await _sales_agent_route(
            turn,
            db_model_main="local-function-model",
            dynamic_model=model,
            claim_contract_every_catalog_turn=False,
        )

    assert len(calls) == 3
    assert response.model.endswith("catalog-fact-repair-fallback")
    assert "LUMA is AED 1000" in response.text
    assert not looks_like_structured_payload(response.text)


# --- 2. A need description is "generic" when its families are covered -------

_NOVO_ROW = (
    "4 Person Face to Face Table SKYLAND NOVO 2400\n"
    "SKYLAND NOVO 2400 - 4-Person Workstation for open-plan offices.\n"
    "Workstations"
)
_LUMA_ROW = (
    "Four person workstation SKYLAND LUMA 9719-4\n"
    "Four-person workstation with screen dividers and mobile pedestals.\n"
    "Workstations"
)
_CHAIR_ROW = "Operative Office Chair CH 145 M grey NEW\nOffice chair.\nChairs"


def test_replayed_need_description_is_generic() -> None:
    query = (
        "Furniture for a new Dubai office for four people; suitable "
        "desks/workstations and ergonomic seating"
    )

    assert classify_product_match(query, [_NOVO_ROW, _LUMA_ROW, _CHAIR_ROW]) == (
        "generic"
    )
    assert classify_product_match(query, [_NOVO_ROW]) == "generic"


@pytest.mark.parametrize(
    "query",
    [
        "ergonomic desks for our new team",
        "office tables and chairs for six staff",
        "modern desks for our office in Dubai",
    ],
)
def test_family_covered_type_words_do_not_demote_a_need(query: str) -> None:
    assert classify_product_match(query, [_LUMA_ROW, _CHAIR_ROW]) == "generic"


def test_a_family_not_returned_still_demotes() -> None:
    assert classify_product_match("desks and chairs", [_LUMA_ROW]) != "generic"


def test_distinct_nearby_types_stay_nearby() -> None:
    assert (
        classify_product_match(
            "Tell me about your acoustic pods",
            ["Solo Privacy Booth Compact acoustic booth for calls"],
        )
        == "nearby"
    )
    pedestal = "Mobile Storage Pedestal. Compact office storage cabinet."
    assert classify_product_match("office accessories", [pedestal]) == "nearby"
    assert classify_product_match("office lighting add-on", [pedestal]) == "missing"


# --- 3. Limited stock is disclosed only when the ask exceeds the stock -------


def _stock_deps(selected: list[dict[str, Any]] | None) -> SalesDeps:
    metadata: dict[str, Any] = {}
    if selected is not None:
        state = DialogueState()
        state.slots.selected_items = selected
        metadata = state.to_metadata()
    deps = _deps(_conversation(metadata))
    deps.claim_rows["CH 616 NEW black"] = RetrievedRow(
        sku="CH 616 NEW black",
        fields={"name": "Operative Office Chair CH 616 NEW black"},
    )
    deps.stock_snapshots["ch 616 new black"] = StockSnapshot(
        sku="CH 616 NEW black",
        available=1,
        source="zoho",
        as_of=datetime.datetime(2026, 9, 23, tzinfo=datetime.UTC),
    )
    return deps


def test_limited_stock_is_disclosed_when_the_ask_exceeds_stock() -> None:
    references = _limited_stock_product_references(
        _stock_deps([{"sku": "CH 616 NEW black", "quantity": 4}])
    )

    assert "CH 616 NEW black" in references


def test_limited_stock_is_silent_when_stock_covers_the_ask() -> None:
    references = _limited_stock_product_references(
        _stock_deps(
            [
                {"sku": "CH 616 NEW black", "quantity": 1},
                {"sku": "CH 460 black", "quantity": 3},
            ]
        )
    )

    assert references == ()


def test_limited_stock_is_disclosed_when_no_quantity_is_recorded() -> None:
    assert "CH 616 NEW black" in _limited_stock_product_references(_stock_deps(None))


# --- 4. The details the model asks for are the gate's own list ---------------


def _consented_conversation(details: dict[str, str]) -> Conversation:
    state = DialogueState()
    state.slots.selected_items = [{"sku": "LUMA-4", "quantity": 1}]
    metadata = state.to_metadata()
    metadata["order_runtime"] = {
        "quote_workflow": {
            "consent": QuoteConsent.GRANTED.value,
            "lifecycle": QuoteLifecycle.COLLECTING_DETAILS.value,
        }
    }
    metadata["quote_customer_details"] = details
    return _conversation(metadata)


def test_gate_missing_details_include_email() -> None:
    conv = _conversation({"quote_customer_details": {"name": "Nadia"}})

    missing = engine._quote_missing_customer_details(_deps(conv))

    assert "customer email" in missing
    assert "specific delivery address" in missing
    assert any(item.startswith("company name") for item in missing)


def test_directive_names_every_gate_required_detail_together() -> None:
    conv = _consented_conversation({"name": "Nadia"})
    gate_missing = engine._quote_missing_customer_details(_deps(conv))

    directives = decision_state_directives(
        conv, customer_text="yes", missing_quote_details=gate_missing
    )
    closed = next(d for d in directives if d.startswith("CLOSED DECISION"))

    for detail in gate_missing:
        assert detail in closed
    assert "together" in closed
    assert "call create_quotation now" not in closed


def test_directive_proceeds_only_when_the_gate_has_nothing_missing() -> None:
    conv = _consented_conversation(
        {
            "name": "Nadia",
            "company": "Studio N",
            "email": "nadia@studio.ae",
            "address": "Office 12, Building 3, Dubai Design District",
        }
    )

    directives = decision_state_directives(
        conv,
        customer_text="ok",
        missing_quote_details=engine._quote_missing_customer_details(_deps(conv)),
    )

    assert any("call create_quotation now" in d for d in directives)


# --- 5. One image per product per turn ----------------------------------------


def test_deferred_media_is_deduplicated_by_product_in_order() -> None:
    luma = ProductMediaPayload(url="https://x/luma.jpg", caption="L", product_key="k1")
    luma_again = ProductMediaPayload(
        url="https://x/luma-2.jpg", caption="L2", product_key="k1"
    )
    novo = ProductMediaPayload(url="https://x/novo.jpg", caption="N", product_key="k2")

    assert dedupe_product_media([luma, novo, luma_again]) == (luma, novo)
