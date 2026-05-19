import uuid
from types import SimpleNamespace

import pytest

from src.models.conversation import Conversation
from src.schemas.common import SalesStage


def _conversation(*, customer_name: str | None = None) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        customer_name=customer_name,
        sales_stage=SalesStage.GREETING.value,
        language="en",
        escalation_status="none",
        metadata_=None,
    )


@pytest.mark.asyncio
async def test_dialogue_kernel_legacy_mode_is_noop() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation()

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="legacy",
        enforced_flows=(),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.handled is False
    assert conv.metadata_ is None


@pytest.mark.asyncio
async def test_dialogue_kernel_legacy_mode_does_not_invoke_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    async def fail_graph(_input: object) -> object:
        raise RuntimeError("graph invoked")

    monkeypatch.setattr(runner, "_COMPILED_GRAPH", SimpleNamespace(ainvoke=fail_graph))
    conv = _conversation()

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="legacy",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "legacy_fallback"
    assert conv.metadata_ is None


@pytest.mark.asyncio
async def test_dialogue_kernel_hydrates_known_customer_name_from_conversation() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lili")

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "product_selection"
    assert result.state.slots.customer_name == "Lili"


@pytest.mark.asyncio
async def test_dialogue_kernel_shadow_records_bounded_trace_without_handling() -> None:
    from src.dialogue.runner import record_legacy_route, run_dialogue_kernel

    conv = _conversation()

    result = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need SKYLAND NOVO 2400 and CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="shadow",
        enforced_flows=("name_gate", "product_selection"),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "name_gate"
    assert result.decision.side_effects_allowed is False

    record_legacy_route(conv, result, legacy_route="mock-model|name-gate")

    traces = conv.metadata_["dialogue_kernel"]["traces"]
    assert len(traces) == 1
    assert traces[0]["mode"] == "shadow"
    assert traces[0]["kernel_route"] == "name_gate"
    assert traces[0]["legacy_route"] == "mock-model|name-gate"
    assert traces[0]["decision"]["side_effects_allowed"] is False


@pytest.mark.asyncio
async def test_dialogue_kernel_enforce_handles_only_allowlisted_flow() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation()

    blocked = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("quote_details",),
        trace_enabled=True,
    )
    assert blocked.should_use_kernel is False
    assert blocked.decision.flow == "name_gate"

    allowed = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert allowed.should_use_kernel is True
    assert allowed.decision.flow == "name_gate"
    assert allowed.decision.response_text == "Hello"
    assert allowed.decision.side_effects_allowed is True


@pytest.mark.asyncio
async def test_dialogue_kernel_quantity_selection_delegates_to_legacy_when_allowlisted() -> (
    None
):
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lil")

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need 6 CH 616",
        recent_history=[
            "assistant: For ergonomic chairs, choose CH 616, CH-190, or CH 620."
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.decision.flow == "product_selection"
    assert result.decision.handled is False
    assert result.should_use_kernel is False
    assert result.decision.metadata["refs"][0]["quantity"] == 6


@pytest.mark.asyncio
async def test_dialogue_kernel_post_quotation_hold_preserves_context() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {
        "dialogue_kernel": {
            "state": {
                "version": 1,
                "active_flow": "post_quotation_hold",
                "slots": {
                    "customer_name": "Lili",
                    "selected_items": [{"sku": "CH-616", "quantity": 1}],
                    "quote_sent": True,
                    "post_quotation_status": "awaiting_customer_decision",
                },
                "last_question": {
                    "flow": "post_quotation_hold",
                    "prompt_key": "quote_sent_check",
                    "expected_slots": ["post_quotation_status"],
                },
            }
        }
    }

    result = await run_dialogue_kernel(
        conversation=conv,
        text="ok",
        recent_history=[
            "assistant: I sent the quotation PDF. Please let me know if it works for you."
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("post_quotation_hold",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.flow == "post_quotation_hold"
    assert "quotation" in (result.decision.response_text or "").lower()
    assert conv.metadata_["dialogue_kernel"]["state"]["slots"]["quote_sent"] is True


@pytest.mark.asyncio
async def test_dialogue_kernel_post_quotation_hold_loads_legacy_quote_metadata() -> (
    None
):
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Vituzone Buyer")
    conv.metadata_ = {
        "last_quote_status": "sent",
        "pending_quote_selection": {
            "source": "quotation_sent",
            "items": [{"sku": "CH 616", "quantity": 12}],
        },
    }

    result = await run_dialogue_kernel(
        conversation=conv,
        text="Can you send a sample first and give a better discount?",
        recent_history=[
            "assistant: I have shared the quotation for 12 chairs. Please let me know if you would like to proceed.",
            "user: Can you send a sample first and give a better discount?",
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("post_quotation_hold",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.flow == "post_quotation_hold"
    assert result.state.slots.quote_sent is True
    assert result.state.slots.selected_items == [{"sku": "CH 616", "quantity": 12}]
