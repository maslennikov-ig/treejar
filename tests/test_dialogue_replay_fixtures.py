import json
import uuid
from pathlib import Path

import pytest

from src.dialogue.runner import run_dialogue_kernel
from src.models.conversation import Conversation
from src.schemas.common import SalesStage

FIXTURE_PATH = Path("tests/fixtures/dialogue/dialogue_state_kernel_replay.json")


def test_dialogue_replay_fixture_contract() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    cases = payload["cases"]
    assert {case["id"] for case in cases} >= {
        "gh36_name_gate_resume_bare_name",
        "gh37_product_quantity_without_fulfillment_no_handoff",
        "gh39_ch616_selection_after_product_choice",
        "gh40_terse_quote_details_preserve_context",
        "gh11_post_quotation_bulk_sample_discount_hold",
        "long_dialog_quote_memory_stress",
        "multilingual_mixed_latin_cyrillic_sku_variants",
    }

    issue_refs = {ref for case in cases for ref in case["issue_refs"]}
    assert {"gh-11", "gh-36", "gh-37", "gh-39", "gh-40"}.issubset(issue_refs)

    for case in cases:
        assert case["mode"] in {"shadow", "enforce", "legacy"}
        assert case["messages"]
        assert "dialogue_kernel" in case["initial_metadata"]
        expected = case["expected"]
        assert expected["route"]
        assert expected["flow"]
        if case["mode"] == "shadow":
            assert expected["side_effects_allowed"] is False
            assert expected["allowed_side_effects"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case_id", "expected_kernel_route", "expected_should_use_kernel"),
    [
        ("gh11_post_quotation_bulk_sample_discount_hold", "post_quotation_hold", False),
        ("gh40_terse_quote_details_preserve_context", "quote_details", False),
        ("gh39_ch616_selection_after_product_choice", "product_selection", False),
        ("multilingual_mixed_latin_cyrillic_sku_variants", "product_selection", False),
    ],
)
async def test_dialogue_replay_cases_run_through_kernel(
    case_id: str,
    expected_kernel_route: str,
    expected_should_use_kernel: bool,
) -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    case = next(item for item in payload["cases"] if item["id"] == case_id)
    metadata = dict(case["initial_metadata"])
    conversation = Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        customer_name=metadata.pop("customer_name", None),
        sales_stage=SalesStage.GREETING.value,
        language="en",
        escalation_status="none",
        metadata_=metadata,
    )
    history = [
        f"{message['role']}: {message['content']}" for message in case["messages"][:-1]
    ]
    user_message = str(case["messages"][-1]["content"])

    result = await run_dialogue_kernel(
        conversation=conversation,
        text=user_message,
        recent_history=[*history, f"user: {user_message}"],
        is_first_turn=False,
        mode="shadow",
        enforced_flows=(
            "name_gate",
            "product_selection",
            "quote_details",
            "post_quotation_hold",
        ),
        trace_enabled=True,
    )

    trace = conversation.metadata_["dialogue_kernel"]["traces"][-1]
    assert result.decision.flow == expected_kernel_route
    assert result.should_use_kernel is expected_should_use_kernel
    assert trace["kernel_route"] == expected_kernel_route
    assert trace["decision"]["side_effects_allowed"] is False
