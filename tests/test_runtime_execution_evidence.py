from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)


def test_tool_trace_comes_from_model_messages_and_keeps_unknown_calls() -> None:
    from src.services.runtime_execution_evidence import extract_runtime_tool_traces

    returned_id = "tool-returned"
    unknown_id = "tool-unknown"
    result = SimpleNamespace(
        all_messages=lambda: [
            ModelResponse(
                parts=[
                    ToolCallPart(
                        "search_products",
                        {"query": "generic furniture"},
                        tool_call_id=returned_id,
                    ),
                    ToolCallPart(
                        "get_stock",
                        {"sku": "GENERIC-01"},
                        tool_call_id=unknown_id,
                    ),
                ]
            ),
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        "search_products",
                        {"count": 1},
                        tool_call_id=returned_id,
                    )
                ]
            ),
        ]
    )

    traces = extract_runtime_tool_traces(result)

    assert [item.tool_name for item in traces] == [
        "search_products",
        "get_stock",
    ]
    assert [item.state for item in traces] == ["returned", "unknown"]
    assert traces[0].arguments_digest != traces[0].outcome_digest
    assert traces[1].outcome_digest is None


def test_runtime_turn_evidence_is_versioned_replaced_and_bounded() -> None:
    from src.services.runtime_execution_evidence import (
        RUNTIME_EXECUTION_EVIDENCE_KEY,
        RuntimeToolTrace,
        record_runtime_turn_evidence,
    )

    conversation = SimpleNamespace(metadata_={"unrelated": {"kept": True}})
    trace = RuntimeToolTrace(
        call_id="call-1",
        tool_name="search_products",
        arguments_digest="a" * 64,
        outcome_digest="b" * 64,
        state="returned",
    )
    now = datetime.now(UTC)

    for index in range(25):
        record_runtime_turn_evidence(
            conversation,
            source_message_id=f"message-{index}",
            assistant_message_id=f"assistant-{index}",
            received_at=now,
            recorded_at=now,
            usage_provenance="provider_reported",
            text_provenance="model",
            tool_traces=(trace,),
        )
    record_runtime_turn_evidence(
        conversation,
        source_message_id="message-24",
        assistant_message_id="assistant-replaced",
        received_at=now,
        recorded_at=now,
        usage_provenance="deterministic_static",
        text_provenance="deterministic_static",
        tool_traces=(),
    )

    evidence = conversation.metadata_[RUNTIME_EXECUTION_EVIDENCE_KEY]
    assert conversation.metadata_["unrelated"] == {"kept": True}
    assert evidence["schema_version"] == "noor-runtime-execution-evidence/v3"
    assert len(evidence["turns"]) == 20
    assert evidence["turns"][-1]["assistant_message_id"] == "assistant-replaced"
    assert evidence["turns"][-1]["schema_version"] == ("noor-runtime-turn-evidence/v4")
    assert evidence["turns"][-1]["text_provenance"] == "deterministic_static"
    assert [item["source_message_id"] for item in evidence["turns"]].count(
        "message-24"
    ) == 1


def test_runtime_turn_evidence_reads_v3_without_text_provenance() -> None:
    from src.services.runtime_execution_evidence import RuntimeTurnEvidence

    now = datetime.now(UTC)
    legacy = RuntimeTurnEvidence.model_validate(
        {
            "schema_version": "noor-runtime-turn-evidence/v3",
            "source_message_id": "message-legacy",
            "assistant_message_id": "assistant-legacy",
            "received_at": now,
            "recorded_at": now,
            "usage_provenance": "provider_reported",
            "tool_traces": [],
        }
    )

    assert legacy.text_provenance is None


def test_runtime_inventory_projects_business_effects_without_customer_content() -> None:
    from src.services.runtime_execution_evidence import snapshot_runtime_inventory

    conversation = SimpleNamespace(
        id="conversation-1",
        zoho_contact_id="contact-1",
        zoho_deal_id="deal-1",
        deal_status="New Lead",
        escalation_status="pending",
        metadata_={
            "quotation_effect_journal": {
                "entries": [
                    {
                        "sale_order_id": "order-1",
                        "status": "pdf_sent",
                        "source_message_id": "provider-message-1",
                        "media_crm_message_id": "quotation:media",
                        "caption_crm_message_id": "quotation:caption",
                    }
                ]
            },
            "customer_free_text": "must not leak",
        },
    )

    inventory = snapshot_runtime_inventory(conversation)

    assert inventory == {
        "crm:contact:contact-1": {"state": "active"},
        "crm:deal:deal-1": {"state": "active", "status": "New Lead"},
        "quotation:sale_order:order-1": {
            "state": "active",
            "status": "pdf_sent",
            "source_message_id": "provider-message-1",
            "media_crm_message_id": "quotation:media",
            "caption_crm_message_id": "quotation:caption",
        },
        "escalation:conversation:conversation-1": {
            "state": "active",
            "status": "pending",
        },
    }
    assert "customer_free_text" not in repr(inventory)
