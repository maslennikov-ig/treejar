"""The company-activity cooldown, joined end to end rather than at each end.

`tj-f6yp` shipped two tests and neither could see the wire between them. One
handed `company_activity_asked_previous_turn=True` straight to `render_reply`;
the other handed `_finalize_turn_response` a hardcoded `emitted_asks`. The slot
name never appeared in both, so renaming the metadata key, or dropping one of
the two call sites in `src/llm/message_processor.py`, left both green.

Everything here drives one `Conversation` through the real reader
(`_Turn.permitted_asks`), the real renderer (`_Turn.render_reply`) and the real
writer (`_finalize_turn_response`), in that order, turn after turn. `tj-d651`.
"""

from __future__ import annotations

import datetime
from typing import Any, cast
from uuid import uuid4

import pytest

from src.dialogue.claim_contract import RetrievedRow
from src.llm.catalog_planning import SalesDeps, StockSnapshot
from src.llm.message_processor import _finalize_turn_response, _Turn
from src.llm.response_policy import AskKind
from src.llm.response_runtime import LLMResponse
from src.models.conversation import Conversation

# Nothing on the path under test touches the database, Redis, the embedding
# engine or either vendor client, so they are absent rather than mocked: a
# stand-in that answers is a stand-in that can hide a call.
UNUSED: Any = cast("Any", None)

# Rule 13 applies to a fit-out and not to a shopping trip, so the turn has to
# look like one: a known company, no recorded activity, and a customer message
# that reads as a project. `_turn_owes_the_company_question` wants all three.
PROJECT_MESSAGE = "We're fitting out a new office for 40 people next month."
SELLING_REPLY = "We can plan the workstations around your team."


def _conversation() -> Conversation:
    return Conversation(
        phone="+971500000000",
        language="en",
        metadata_={
            "quote_customer_details": {"company": "Cedarline Test Offices"},
        },
    )


def _deps(conversation: Conversation) -> SalesDeps:
    return SalesDeps(
        db=UNUSED,
        redis=UNUSED,
        conversation=conversation,
        embedding_engine=UNUSED,
        zoho_inventory=UNUSED,
        zoho_crm=None,
        messaging_client=UNUSED,
        pii_map={},
        user_query=PROJECT_MESSAGE,
        recent_history=[f"user:{PROJECT_MESSAGE}"],
    )


def _turn(conversation: Conversation, *, is_first_turn: bool = False) -> _Turn:
    """A real `_Turn` over a real `Conversation`, with the plumbing left out.

    The infrastructure fields are `None` on purpose: nothing on the path under
    test touches the database, Redis, the embedding engine or either vendor
    client, and a real `_Turn` is what makes a renamed field or a moved call
    site fail here instead of passing against a stand-in.
    """

    deps = _deps(conversation)
    return _Turn(
        pending_reference_route=UNUSED,
        order_quote_route=UNUSED,
        db=UNUSED,
        redis=UNUSED,
        conversation_id=uuid4(),
        embedding_engine=UNUSED,
        zoho_client=UNUSED,
        messaging_client=UNUSED,
        crm_client=None,
        source_message_id=None,
        latency_trace=None,
        context_started=None,
        conv=conversation,
        crm_context=None,
        pii_map={},
        history=[],
        is_first_turn=is_first_turn,
        model_runtime=UNUSED,
        current_message_quote_customer_details={},
        combined_text=PROJECT_MESSAGE,
        masked_text=PROJECT_MESSAGE,
        recent_history=[f"user:{PROJECT_MESSAGE}"],
        deps=deps,
    )


async def _take_one_turn(
    conversation: Conversation,
    reply: str,
    *,
    is_first_turn: bool = False,
) -> tuple[frozenset[AskKind], str, frozenset[AskKind]]:
    """Read the slot, render the reply, write the slot. One production turn."""

    turn = _turn(conversation, is_first_turn=is_first_turn)
    permitted = turn.permitted_asks()
    rendered = turn.render_reply(
        reply,
        response_deps=turn.deps,
        provenance="model",
        model_name="test-model",
    )
    response = LLMResponse(
        text=rendered.text,
        tokens_in=0,
        tokens_out=0,
        cost=0.0,
        model="test-model",
        emitted_asks=rendered.emitted_asks,
    )
    await _finalize_turn_response(turn, response)
    return permitted, rendered.text, rendered.emitted_asks


def test_the_turn_carries_low_stock_anchor_state_into_the_shipped_renderer() -> None:
    turn = _turn(_conversation(), is_first_turn=True)
    turn.opening_anchor_line = (
        "Chairs from AED 139, desks and workstations from AED 58."
    )
    turn.opening_anchor_has_limited_stock = True

    rendered = turn.render_reply(
        "What kind of office are you furnishing?",
        response_deps=turn.deps,
        provenance="model",
        model_name="test-model",
    )

    assert "limited stock" in rendered.text.casefold()
    assert "larger quantities" in rendered.text.casefold()


def test_the_turn_derives_low_stock_references_from_retrieved_state() -> None:
    turn = _turn(_conversation())
    turn.deps.claim_rows["CH-LOW"] = RetrievedRow(
        sku="CH-LOW",
        fields={"name": "Task chair CH-LOW"},
    )
    turn.deps.stock_snapshots["ch-low"] = StockSnapshot(
        sku="CH-LOW",
        available=1,
        source="zoho",
        as_of=datetime.datetime.now(datetime.UTC),
    )

    rendered = turn.render_reply(
        "Task chair CH-LOW is AED 139. Would one suit the reception desk?",
        response_deps=turn.deps,
        provenance="model",
        model_name="test-model",
    )

    assert "limited stock" in rendered.text.casefold()


@pytest.mark.asyncio
async def test_the_company_ask_is_made_skipped_and_then_made_again() -> None:
    """Turn N asks, N+1 must not, N+2 asks again.

    The sequence is the whole point. A cooldown that never lifts is the same
    defect as no cooldown at all, and neither shipped test could tell them
    apart because neither let the second turn read what the first one wrote.
    """

    conversation = _conversation()

    permitted_n, text_n, emitted_n = await _take_one_turn(conversation, SELLING_REPLY)

    assert AskKind.COMPANY_ACTIVITY in permitted_n
    assert "what does your company" in text_n.casefold()
    assert AskKind.COMPANY_ACTIVITY in emitted_n
    assert conversation.metadata_ is not None
    assert conversation.metadata_["company_activity_asked_previous_turn"] is True

    permitted_next, text_next, emitted_next = await _take_one_turn(
        conversation, SELLING_REPLY
    )

    assert AskKind.COMPANY_ACTIVITY not in permitted_next
    assert "what does your company" not in text_next.casefold()
    assert AskKind.COMPANY_ACTIVITY not in emitted_next
    assert "company_activity_asked_previous_turn" not in conversation.metadata_

    permitted_after, text_after, emitted_after = await _take_one_turn(
        conversation, SELLING_REPLY
    )

    assert AskKind.COMPANY_ACTIVITY in permitted_after
    assert "what does your company" in text_after.casefold()
    assert AskKind.COMPANY_ACTIVITY in emitted_after
    assert conversation.metadata_["company_activity_asked_previous_turn"] is True


@pytest.mark.asyncio
async def test_a_folded_away_company_ask_does_not_record_the_slot() -> None:
    """The trap `tj-f6yp` named and did not cover, for `COMPANY_ACTIVITY`.

    A first turn is where the ask can be permitted and still never reach the
    customer: `carry_the_company_question` is gated on later turns, so nothing
    puts the question back after `collapse_question_form` drops it as the
    second question of the reply. Recording the slot there would start a
    cooldown for a question nobody was asked.
    """

    conversation = _conversation()

    permitted, text, emitted = await _take_one_turn(
        conversation,
        "How many desks do you need? And what does your company do, day to day?",
        is_first_turn=True,
    )

    assert AskKind.COMPANY_ACTIVITY in permitted
    assert "what does your company" not in text.casefold()
    assert AskKind.COMPANY_ACTIVITY not in emitted
    assert conversation.metadata_ is not None
    assert "company_activity_asked_previous_turn" not in conversation.metadata_


@pytest.mark.asyncio
async def test_a_company_ask_the_customer_receives_records_the_slot() -> None:
    """The control for the fold: same turn shape, question kept, slot written."""

    conversation = _conversation()

    _, text, emitted = await _take_one_turn(
        conversation,
        "What does your company do, day to day?",
        is_first_turn=True,
    )

    assert "what does your company" in text.casefold()
    assert AskKind.COMPANY_ACTIVITY in emitted
    assert conversation.metadata_ is not None
    assert conversation.metadata_["company_activity_asked_previous_turn"] is True
