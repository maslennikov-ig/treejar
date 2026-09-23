"""Closed decisions and the last proposal (tj-uz6j.3, tj-uz6j.7).

Replays the shapes of production conversations 207f7c10 and fa224cab
(2026-09-23, gpt-6-luna) through the durable state with stubbed model output:
the assistant's closing question is recorded with the catalog rows it names, a
short customer "yes" is tied to that question, and a validated selection is
rendered as a closed decision that switches the turn to proceed mode.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.dialogue.claim_contract import RetrievedRow
from src.dialogue.decision_state import (
    classify_short_reply,
    clear_assistant_proposal,
    closing_question,
    decision_state_directives,
    keyboard_layout_reading,
    proposal_items,
    record_assistant_proposal,
    referenced_catalog_items,
)
from src.dialogue.state import DialogueState
from src.llm import engine
from src.models.conversation import Conversation

LUMA_4 = "SKY-LUMA-9719-4-WAL"
LUMA_2 = "SKY-LUMA-9719-2-WAL"
LUMA_1 = "SKY-LUMA-9719-1-WAL"
NOVO_4 = "SKY-NOVO-2400-4P"
NOVO_2 = "SKY-NOVO-2400-2P"

CATALOG: dict[str, tuple[str, str]] = {
    LUMA_4: ("Workstation SKYLAND LUMA 9719-4 walnut", "1883.0"),
    LUMA_2: ("Workstation SKYLAND LUMA 9719-2 walnut", "990.0"),
    LUMA_1: ("Workstation SKYLAND LUMA 9719-1 walnut", "560.0"),
    NOVO_4: ("4 Person Face to Face Table SKYLAND NOVO 2400", "1813.0"),
    NOVO_2: ("2 Person Table SKYLAND NOVO 2400", "1120.0"),
}


def _rows(*skus: str) -> dict[str, RetrievedRow]:
    return {
        sku: RetrievedRow(
            sku=sku, fields={"name": CATALOG[sku][0], "price": CATALOG[sku][1]}
        )
        for sku in skus
    }


def _conversation(metadata: dict[str, Any] | None = None) -> Conversation:
    return Conversation(
        phone="+971500000000",
        language="en",
        customer_name="Nadia",
        metadata_=metadata or {},
    )


def _assistant_turn(
    conversation: Conversation, reply: str, rows: dict[str, RetrievedRow]
) -> None:
    """What `_finalize_turn_response` does with the reply it actually sent."""

    conversation.metadata_ = record_assistant_proposal(
        conversation.metadata_, reply, rows
    )


def _tool_context(conversation: Conversation, text: str) -> Any:
    return SimpleNamespace(
        deps=SimpleNamespace(
            user_query=text,
            pii_map={},
            source_message_id="source-1",
            recent_history=[],
            conversation=conversation,
            db=SimpleNamespace(flush=AsyncMock()),
            executed_tool_names=[],
            tool_mode="full",
            product_search_calls=0,
        )
    )


async def _find_product(_db: object, sku: str) -> SimpleNamespace | None:
    if sku not in CATALOG:
        return None
    return SimpleNamespace(sku=sku, name_en=CATALOG[sku][0])


# --- Form of the customer message ---------------------------------------------


@pytest.mark.parametrize(
    ("text", "kind", "bare"),
    [
        ("yes", "assent", True),
        ("Yes please!", "assent", True),
        ("sure", "assent", True),
        ("of course", "assent", True),
        ("keep it", "assent", True),
        ("نعم", "assent", True),
        ("yes, LUMA would be perfect", "assent", False),
        ("no thanks", "decline", True),
        ("لا", "decline", True),
    ],
)
def test_short_replies_are_classified_by_form(text: str, kind: str, bare: bool) -> None:
    reply = classify_short_reply(text)
    assert reply is not None
    assert (reply.kind, reply.bare) == (kind, bare)


@pytest.mark.parametrize(
    "text",
    [
        "4",
        "good morning",
        "ok, and what about delivery?",
        "I need 2 workstations. nadia@example.com",
        "We're a design team. We collaborate often.",
        "مرحبا",
    ],
)
def test_content_messages_are_not_short_answers(text: str) -> None:
    assert classify_short_reply(text) is None


def test_wrong_keyboard_layout_reads_as_the_intended_answer() -> None:
    reply = classify_short_reply("ыгку")
    assert reply is not None
    assert reply.kind == "assent" and reply.bare
    assert reply.layout_reading == "sure"
    assert keyboard_layout_reading("ыгку") == ("Russian", "sure")
    # Arabic is a customer language: only a reading that is itself an answer
    # is offered, never a transliteration of ordinary Arabic.
    assert keyboard_layout_reading("غثس") == ("Arabic", "yes")
    assert keyboard_layout_reading("مرحبا") is None


# --- The last proposal ---------------------------------------------------------


def test_closing_question_is_the_question_the_reply_ends_on() -> None:
    assert (
        closing_question(
            "SKYLAND LUMA 9719-4 is 1,883.00 AED.\n\n"
            "Shall I carry *LUMA* forward as your preferred option?"
        )
        == "Shall I carry *LUMA* forward as your preferred option?"
    )
    assert (
        closing_question(
            "Would you like me to prepare a quotation for these workstations?\n"
            "Thank you!"
        )
        == "Would you like me to prepare a quotation for these workstations?"
    )
    assert (
        closing_question(
            "Which layout do you prefer? Meanwhile, the walnut finish is in stock "
            "for both layouts and delivery is included within Dubai."
        )
        is None
    )
    assert closing_question("Noted: 1 x LUMA 9719-4.") is None


def test_proposal_items_follow_the_question_not_the_whole_comparison() -> None:
    reply = (
        "SKYLAND LUMA 9719-4 (1,883 AED) gives each person privacy; SKYLAND NOVO "
        "2400 (1,813 AED) is more open.\n\nShall I carry LUMA forward?"
    )
    question = closing_question(reply)
    assert question == "Shall I carry LUMA forward?"
    items = proposal_items(question, reply, _rows(LUMA_4, NOVO_4))
    assert [item.sku for item in items] == [LUMA_4]


def test_referenced_items_tell_model_siblings_apart_by_stated_price() -> None:
    reply = (
        "For four people facing each other I recommend the SKYLAND NOVO 2400 "
        "at 1,813 AED, 21 in stock. Shall I carry it forward?"
    )
    items = referenced_catalog_items(reply, _rows(NOVO_4, NOVO_2, LUMA_4))
    assert [item.sku for item in items] == [NOVO_4]


def test_record_proposal_preserves_state_and_clears_on_a_reply_without_question() -> (
    None
):
    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA_4, "quantity": 1}]
    metadata = state.to_metadata({"unrelated": "kept"})

    metadata = record_assistant_proposal(
        metadata, "LUMA 9719-4 is 1883 AED. Shall I prepare it?", _rows(LUMA_4)
    )
    loaded = DialogueState.load(metadata)
    assert loaded.last_proposal is not None
    assert [item.sku for item in loaded.last_proposal.items] == [LUMA_4]
    assert loaded.slots.selected_items == [{"sku": LUMA_4, "quantity": 1}]
    assert metadata["unrelated"] == "kept"

    metadata = record_assistant_proposal(metadata, "Noted, thank you.", {})
    assert DialogueState.load(metadata).last_proposal is None
    assert DialogueState.load(metadata).slots.selected_items == [
        {"sku": LUMA_4, "quantity": 1}
    ]


def test_damaged_proposal_costs_only_the_proposal() -> None:
    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA_4, "quantity": 1}]
    metadata = state.to_metadata()
    metadata["dialogue_kernel"]["state"]["last_proposal"] = {"items": "garbage"}
    loaded = DialogueState.load(metadata)
    assert loaded.last_proposal is None
    assert loaded.slots.selected_items == [{"sku": LUMA_4, "quantity": 1}]


# --- Replay: conversation 207f7c10 ---------------------------------------------


@pytest.mark.asyncio
async def test_replay_207f7c10_selection_closes_comparison_and_owns_quantity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_find_catalog_product_by_sku", _find_product)
    conversation = _conversation()

    # 14:51 The assistant compares both and asks to carry LUMA forward.
    _assistant_turn(
        conversation,
        "For privacy with collaboration, SKYLAND LUMA 9719-4 (1,883 AED, 30 in "
        "stock) suits you better than the SKYLAND NOVO 2400 (1,813 AED).\n\n"
        "Shall I carry LUMA 9719-4 forward as your preferred option?",
        _rows(LUMA_4, NOVO_4),
    )

    # "yes, LUMA would be perfect" is tied to that question and its item.
    directives = decision_state_directives(
        conversation, customer_text="yes, LUMA would be perfect"
    )
    assert len(directives) == 1
    assent = directives[0]
    assert "a yes to your last question" in assent
    assert "Shall I carry LUMA 9719-4 forward" in assent
    assert LUMA_4 in assent and NOVO_4 not in assent
    assert "do not list the options again" in assent
    assert "adjusts that proposal" in assent
    assert "LUMA would be perfect" not in assent  # customer text stays data

    # The model records the choice with the validated tool.
    ctx = _tool_context(conversation, "yes, LUMA would be perfect")
    result = await engine.record_customer_requirements(
        ctx, items=[engine.RecordedItem(sku=LUMA_4, quantity=1)]
    )
    assert "Recorded: 1 x " + LUMA_4 in result
    _assistant_turn(
        conversation, "Noted: 1 x SKYLAND LUMA 9719-4. When do you need it?", {}
    )

    # 14:55-14:57 Later answers must not reopen the comparison.
    for customer_text in (
        "next week",
        "I'm the owner",
        "We're a design team. We collaborate often, but each person needs "
        "some privacy.",
    ):
        directives = decision_state_directives(
            conversation, customer_text=customer_text
        )
        closed = directives[0]
        assert closed.startswith("CLOSED DECISION")
        assert "1 x Workstation SKYLAND LUMA 9719-4 walnut" in closed
        assert NOVO_4 not in closed
        assert "do not re-ask a preference" in closed
        assert "offer to prepare the quotation" in closed

    # 15:05 "I need 2 workstations" updates the chosen line, not the variant.
    directives = decision_state_directives(
        conversation, customer_text="I need 2 workstations. nadia@example.com"
    )
    quantity = directives[1]
    assert f"record_customer_requirements with SKU {LUMA_4}" in quantity
    assert "Do not ask which variant" in quantity
    result = await engine.record_customer_requirements(
        _tool_context(conversation, "I need 2 workstations"),
        items=[engine.RecordedItem(sku=LUMA_4, quantity=2)],
    )
    slots = DialogueState.from_conversation(conversation).slots
    assert slots.selected_items == [
        {"sku": LUMA_4, "quantity": 2, "name": CATALOG[LUMA_4][0]}
    ]


@pytest.mark.asyncio
async def test_consented_selection_switches_to_proceed_mode() -> None:
    conversation = _conversation()
    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA_4, "quantity": 2}]
    conversation.metadata_ = state.to_metadata()
    _assistant_turn(
        conversation,
        "Shall I prepare a formal quote for the LUMA 9719-4 you selected?",
        _rows(LUMA_4),
    )

    ctx = _tool_context(conversation, "sure")
    await engine.record_customer_intent(
        ctx, evidence="sure", quotation_consent="granted"
    )
    directives = decision_state_directives(conversation, customer_text="Treejar LLC")
    closed = directives[0]
    assert "the quotation is agreed" in closed
    assert "specific delivery address" in closed
    assert "create_quotation" in closed

    conversation.metadata_ = {
        **conversation.metadata_,
        "quote_customer_details": {
            "name": "Nadia",
            "company": "Studio N",
            "address": "Office 12, Building 3, Dubai Design District",
        },
    }
    closed = decision_state_directives(conversation, customer_text="ok")[0]
    assert "call create_quotation now" in closed


# --- Replay: conversation fa224cab ---------------------------------------------


def test_replay_fa224cab_bare_yes_accepts_the_proposed_item_only() -> None:
    conversation = _conversation()
    _assistant_turn(
        conversation,
        "For your four-person team, the 4 Person Face to Face Table SKYLAND NOVO "
        "2400 at 1,813 AED keeps everyone together. Shall I carry it forward?",
        _rows(NOVO_4, NOVO_2),
    )
    directives = decision_state_directives(conversation, customer_text="yes")
    assert len(directives) == 1
    assert NOVO_4 in directives[0] and NOVO_2 not in directives[0]
    assert "do not reinterpret it as a different quantity or variant" in directives[0]
    assert "Do not ask them to confirm it again" in directives[0]


def test_replay_fa224cab_layout_typo_and_keep_it_accept_the_quote_offer() -> None:
    conversation = _conversation()
    state = DialogueState()
    state.slots.selected_items = [
        {"sku": LUMA_4, "quantity": 3, "name": CATALOG[LUMA_4][0]}
    ]
    conversation.metadata_ = state.to_metadata()
    _assistant_turn(
        conversation,
        "3 x SKYLAND LUMA 9719-4 walnut at 1,883 AED each.",
        _rows(LUMA_4, LUMA_2, NOVO_4),
    )
    # The quote offer names no product again; the earlier rows stay resolvable.
    _assistant_turn(
        conversation,
        "LUMA 9719-4 in walnut is in stock.\n"
        "Would you like me to prepare a quotation for these three workstations?",
        {},
    )

    for customer_text in ("ыгку", "ыгку\nsure", "keep it"):
        directives = decision_state_directives(
            conversation, customer_text=customer_text
        )
        joined = "\n".join(directives)
        assert "CLOSED DECISION" in joined
        assert "a yes to your last question" in joined
        assert "prepare a quotation for these three workstations" in joined
        assert "record consent with record_customer_intent" in joined
        assert NOVO_4 not in joined
    typo = decision_state_directives(conversation, customer_text="ыгку")
    assert any('it reads "sure"' in directive for directive in typo)


def test_a_withdrawn_reply_leaves_no_question_to_answer() -> None:
    conversation = _conversation()
    _assistant_turn(
        conversation, "Which layout do you prefer: 2 x 9719-4 or 4 x 9719-2?", {}
    )
    conversation.metadata_ = clear_assistant_proposal(conversation.metadata_)
    assert decision_state_directives(conversation, customer_text="yes") == ()


# --- Prompt wiring ---------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_system_prompt_renders_decision_state_as_binding(
    mock_prompt: AsyncMock,
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    conversation = _conversation()
    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA_4, "quantity": 1}]
    conversation.metadata_ = state.to_metadata()
    ctx = SimpleNamespace(
        deps=SimpleNamespace(
            db=AsyncMock(),
            redis=AsyncMock(),
            conversation=conversation,
            user_query="I need 2 workstations",
            behavior_rules=None,
            faq_context=None,
            crm_context=None,
            customer_facts_context=None,
            runtime_directives=(),
            permitted_asks=None,
            tool_mode="full",
        )
    )
    with patch.object(engine, "_format_captured_sales_context", return_value=""):
        prompt = await engine.inject_system_prompt(ctx)
    assert "[DECISION STATE: recorded by validated tools; binding]" in prompt
    assert f"- CLOSED DECISION -- the customer has chosen: 1 x SKU {LUMA_4}" in prompt
    assert f"record_customer_requirements with SKU {LUMA_4}" in prompt


@pytest.mark.asyncio
@patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
async def test_system_prompt_has_no_decision_block_without_decisions(
    mock_prompt: AsyncMock,
) -> None:
    mock_prompt.return_value = "BASE PROMPT"
    ctx = SimpleNamespace(
        deps=SimpleNamespace(
            db=AsyncMock(),
            redis=AsyncMock(),
            conversation=_conversation(),
            user_query="I need office desks",
            behavior_rules=None,
            faq_context=None,
            crm_context=None,
            customer_facts_context=None,
            runtime_directives=(),
            permitted_asks=None,
            tool_mode="full",
        )
    )
    with patch.object(engine, "_format_captured_sales_context", return_value=""):
        prompt = await engine.inject_system_prompt(ctx)
    assert "[DECISION STATE" not in prompt


# --- Turn wiring -----------------------------------------------------------------


class _AgentResult:
    def __init__(self, output: str) -> None:
        self.output = output

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=5, output_tokens=5, cost=None)


@pytest.mark.asyncio
@patch("src.rag.pipeline.search_knowledge", new_callable=AsyncMock)
@patch("src.core.config.get_system_config", new_callable=AsyncMock)
@patch("src.llm.engine.build_message_history", new_callable=AsyncMock)
@patch("src.llm.engine.sales_agent.run", new_callable=AsyncMock)
async def test_sent_reply_records_the_question_a_following_yes_answers(
    mock_run: AsyncMock,
    mock_build_history: AsyncMock,
    mock_get_system_config: AsyncMock,
    mock_search_knowledge: AsyncMock,
) -> None:
    import uuid
    from unittest.mock import MagicMock

    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    conversation = _conversation()
    conversation.id = uuid.uuid4()
    conversation.sales_stage = "solution"
    conversation.escalation_status = "none"
    db = AsyncMock()
    db.get.return_value = conversation
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    result.scalar_one_or_none.return_value = None
    db.execute.return_value = result
    redis = AsyncMock()
    redis.get.return_value = None

    async def config(_db: object, _key: str, default: str) -> str:
        return default

    mock_get_system_config.side_effect = config
    mock_search_knowledge.return_value = []
    mock_build_history.return_value = [
        ModelRequest(parts=[UserPromptPart(content="Compare LUMA and NOVO")]),
        ModelResponse(parts=[TextPart(content="Here are both options.")]),
        ModelRequest(parts=[UserPromptPart(content="Which suits privacy?")]),
    ]
    reply = (
        "SKYLAND LUMA 9719-4 at 1,883 AED gives each person a screened desk.\n\n"
        "Shall I carry LUMA 9719-4 forward as your preferred option?"
    )

    async def run(*_args: object, **kwargs: Any) -> _AgentResult:
        kwargs["deps"].claim_rows.update(_rows(LUMA_4, NOVO_4))
        return _AgentResult(reply)

    mock_run.side_effect = run
    await engine.process_message(
        conversation_id=conversation.id,
        combined_text="Which suits privacy?",
        db=db,
        redis=redis,
        embedding_engine=AsyncMock(),
        zoho_client=AsyncMock(),
        messaging_client=AsyncMock(),
    )

    proposal = DialogueState.load(conversation.metadata_).last_proposal
    assert proposal is not None
    assert proposal.question.endswith("as your preferred option?")
    assert [item.sku for item in proposal.items] == [LUMA_4]
    directives = decision_state_directives(conversation, customer_text="yes")
    assert "Shall I carry LUMA 9719-4 forward" in directives[0]


def test_closed_selection_skus_feed_tool_contracts() -> None:
    from src.dialogue.decision_state import closed_selection_skus

    conversation = _conversation()
    assert closed_selection_skus(conversation) == ()
    state = DialogueState()
    state.slots.selected_items = [{"sku": LUMA_4, "quantity": 2}]
    conversation.metadata_ = state.to_metadata()
    assert closed_selection_skus(conversation) == (LUMA_4,)
    state.slots.quote_sent = True
    conversation.metadata_ = state.to_metadata()
    assert closed_selection_skus(conversation) == ()


def test_search_and_stock_contracts_switch_to_proceed_mode_after_selection() -> None:
    from src.llm.catalog_planning import (
        _product_search_response_contract,
        _stock_follow_up_contract,
    )

    for kind in ("exact", "generic", "nearby"):
        contract = _product_search_response_contract(
            match_kind=kind,  # type: ignore[arg-type]
            closed_selection_skus=("OF-HAI-Luma-Workstation-RJ 9719-4-Walnut",),
        )
        assert "already chosen" in contract
        assert "lead with up to 3" not in contract.lower()
        assert "not confirmed" not in contract

    open_contract = _product_search_response_contract(match_kind="exact")
    assert "lead with up to 3" in open_contract.lower()
    empty = _product_search_response_contract(
        match_kind="empty", closed_selection_skus=("X-1",)
    )
    assert "already chosen" not in empty

    assert "listing options" in _stock_follow_up_contract(selection_closed=True)
    assert "option-first" in _stock_follow_up_contract()
