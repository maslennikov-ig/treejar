from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from src.models.conversation import Conversation
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit


def _observed_rows(
    *,
    status: str = "delivered",
    baseline_inventory: dict[str, dict[str, object]] | None = None,
    final_inventory: dict[str, dict[str, object]] | None = None,
    final_readback_inventory: dict[str, dict[str, object]] | None = None,
):
    from src.services.e2e_observation_producer import ObservedTurnRows

    sent_at = datetime(2026, 7, 29, 9, 0, tzinfo=UTC)
    conversation_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    audit_id = uuid.uuid4()
    conversation = Conversation(
        id=conversation_id,
        phone="protected-test-identity",
        metadata_={
            "runtime_e2e_follow_up_suppressed": True,
        },
    )
    inbound = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content="A generic catalog question",
        message_type="text",
        wazzup_message_id="provider-inbound-1",
        tokens_in=2,
        tokens_out=3,
        cost=Decimal("0.010000"),
        model="voice-model",
        created_at=sent_at.replace(tzinfo=None),
    )
    assistant = Message(
        id=assistant_id,
        conversation_id=conversation_id,
        role="assistant",
        content="A generic catalog answer",
        tokens_in=10,
        tokens_out=20,
        cost=Decimal("0.020000"),
        model="chat-model",
        created_at=(sent_at + timedelta(seconds=1)).replace(tzinfo=None),
    )
    audit = OutboundMessageAudit(
        id=audit_id,
        conversation_id=conversation_id,
        provider="wazzup",
        chat_id="protected-test-identity",
        message_type="text",
        content=assistant.content,
        source="bot_reply",
        status=status,
        provider_message_id="provider-outbound-1",
        details={
            "source_message_id": "provider-inbound-1",
            "follow_up_suppressed": True,
        },
        status_updated_at=(sent_at + timedelta(seconds=2)).replace(tzinfo=None),
        created_at=(sent_at + timedelta(seconds=1)).replace(tzinfo=None),
    )
    evidence = {
        "schema_version": "noor-runtime-turn-evidence/v3",
        "source_message_id": inbound.wazzup_message_id,
        "assistant_message_id": str(assistant_id),
        "received_at": (sent_at + timedelta(milliseconds=200)).isoformat(),
        "recorded_at": (sent_at + timedelta(seconds=1)).isoformat(),
        "usage_provenance": "provider_reported",
        "tool_traces": [
            {
                "call_id": "call-1",
                "tool_name": "search_products",
                "arguments_digest": "a" * 64,
                "outcome_digest": "b" * 64,
                "state": "returned",
            }
        ],
        "baseline_inventory": baseline_inventory or {},
        "final_inventory": final_inventory or {},
    }
    return ObservedTurnRows(
        conversation=conversation,
        inbound=inbound,
        assistant=assistant,
        outbound=(audit,),
        runtime_evidence=evidence,
        final_readback_inventory=final_readback_inventory or {},
    )


def test_execution_fact_uses_server_rows_for_text_trace_duration_and_cost() -> None:
    from src.services.e2e_observation_producer import build_turn_fact

    fact = build_turn_fact("turn-1", _observed_rows())

    assert fact.question == "A generic catalog question"
    assert fact.answer == "A generic catalog answer"
    assert fact.model == "chat-model"
    assert fact.tools == ("search_products",)
    assert fact.tool_outcomes == ("returned",)
    assert fact.tool_traces[0].call_id == "call-1"
    assert fact.tool_traces[0].arguments_digest == "a" * 64
    assert fact.tool_traces[0].outcome_digest == "b" * 64
    assert fact.duration_ms == 2000
    assert fact.token_count == 35
    assert fact.cost_usd == 0.03
    assert fact.provider_message_id == "provider-outbound-1"


@pytest.mark.parametrize(
    "field",
    ["model", "tokens_in", "tokens_out", "cost"],
)
def test_execution_fact_blocks_missing_provider_usage(field: str) -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationNotReady,
        build_turn_fact,
    )

    rows = _observed_rows()
    setattr(rows.assistant, field, None)

    with pytest.raises(ProductionObservationNotReady, match="usage"):
        build_turn_fact("turn-1", rows)


def test_execution_fact_accepts_explicit_deterministic_zero_cost_provenance() -> None:
    from src.services.e2e_observation_producer import build_turn_fact

    rows = _observed_rows()
    rows.runtime_evidence["usage_provenance"] = "deterministic_static"
    rows.assistant.model = "dialogue-kernel|deterministic"
    rows.assistant.tokens_in = 0
    rows.assistant.tokens_out = 0
    rows.assistant.cost = None
    rows.inbound.model = None
    rows.inbound.tokens_in = None
    rows.inbound.tokens_out = None
    rows.inbound.cost = None

    fact = build_turn_fact("turn-1", rows)

    assert fact.model == "dialogue-kernel|deterministic"
    assert fact.token_count == 0
    assert fact.cost_usd == 0


@pytest.mark.parametrize("status", ["pending", "sent", "unknown"])
def test_execution_fact_blocks_nonterminal_outbound_effect(status: str) -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationNotReady,
        build_turn_fact,
    )

    with pytest.raises(ProductionObservationNotReady, match="nonterminal"):
        build_turn_fact("turn-1", _observed_rows(status=status))


def test_execution_fact_blocks_incomplete_tool_trace() -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationNotReady,
        build_turn_fact,
    )

    rows = _observed_rows()
    rows.runtime_evidence["tool_traces"][0]["state"] = "unknown"
    rows.runtime_evidence["tool_traces"][0]["outcome_digest"] = None

    with pytest.raises(ProductionObservationNotReady, match="tool"):
        build_turn_fact("turn-1", rows)


def test_reconciliation_observation_contains_only_server_facts() -> None:
    from src.services.e2e_observation_producer import (
        build_reconciliation_observation,
    )

    observation = build_reconciliation_observation(
        rows=(_observed_rows(),),
        observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
    ).model_dump(mode="json")

    assert observation["schema_version"] == ("noor-e2e-wazzup-action-reconciliation/v2")
    assert observation["adapter_id"] == "wazzup-webhook-adapter"
    assert observation["capability"] == "webhook.inbound"
    assert observation["source_message_ids"] == ["provider-inbound-1"]
    assert observation["outbound_provider_message_ids"] == ["provider-outbound-1"]
    assert observation["resolved_state"] == "succeeded"
    assert observation["actual_cost_usd"] == 0.03
    assert observation["inventory"]
    assert "action_id" not in observation
    assert "reservation_digest" not in observation
    assert "causal_event_digest" not in observation


def test_execution_observation_covers_business_inventory_delta() -> None:
    from src.services.e2e_observation_producer import build_execution_observation

    artifact_id = "quotation:sale_order:order-1"
    rows = _observed_rows(
        final_inventory={
            artifact_id: {
                "state": "active",
                "status": "pdf_sent",
                "source_message_id": "provider-inbound-1",
            }
        },
        final_readback_inventory={
            artifact_id: {
                "state": "resolved",
                "status": "pdf_sent",
                "source_message_id": "provider-inbound-1",
            }
        },
    )

    observation = build_execution_observation(
        execution_id="SC-QUOTE",
        turns=(("turn-1", rows),),
        observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
    )

    business_fact = next(
        item
        for item in observation.side_effect_facts
        if item.artifact_id == artifact_id
    )
    assert business_fact.subsystem == "quotation"
    assert business_fact.artifact_type == "sale_order"
    assert business_fact.expected_effect["state"] == "active"
    assert business_fact.final_readback == {
        "state": "resolved",
        "status": "pdf_sent",
        "source_message_id": "provider-inbound-1",
    }
    assert business_fact.disposition == "resolved"


def test_execution_observation_preserves_unchanged_preexisting_inventory() -> None:
    from src.services.e2e_observation_producer import build_execution_observation

    artifact_id = "crm:contact:contact-existing"
    unchanged = {"state": "active", "status": "customer"}
    rows = _observed_rows(
        baseline_inventory={artifact_id: unchanged},
        final_inventory={artifact_id: unchanged},
    )

    observation = build_execution_observation(
        execution_id="SC-CRM",
        turns=(("turn-1", rows),),
        observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
    )

    assert observation.baseline_inventory[artifact_id] == unchanged
    assert observation.final_inventory[artifact_id] == unchanged
    assert all(
        item.artifact_id != artifact_id for item in observation.side_effect_facts
    )


@pytest.mark.parametrize("duplicate_kind", ["turn", "message", "provider"])
def test_execution_observation_rejects_duplicate_transcript_identities(
    duplicate_kind: str,
) -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationError,
        build_execution_observation,
    )

    first = _observed_rows()
    second = _observed_rows()
    second.inbound.wazzup_message_id = "provider-inbound-2"
    second.runtime_evidence["source_message_id"] = "provider-inbound-2"
    second.outbound[0].details["source_message_id"] = "provider-inbound-2"
    second.outbound[0].provider_message_id = "provider-outbound-2"
    turn_ids = ("turn-1", "turn-2")
    if duplicate_kind == "turn":
        turn_ids = ("turn-1", "turn-1")
    elif duplicate_kind == "message":
        second.inbound.id = first.inbound.id
    else:
        second.outbound[0].provider_message_id = first.outbound[0].provider_message_id

    with pytest.raises(ProductionObservationError, match="duplicate"):
        build_execution_observation(
            execution_id="SC-OPEN-EN",
            turns=((turn_ids[0], first), (turn_ids[1], second)),
            observed_at=datetime.now(UTC),
        )


def test_execution_observation_reports_active_delta_as_cleanup_pending() -> None:
    from src.services.e2e_observation_producer import build_execution_observation

    artifact_id = "crm:contact:contact-test"
    rows = _observed_rows(
        final_inventory={artifact_id: {"state": "active"}},
        final_readback_inventory={
            artifact_id: {"state": "active", "status": "customer"}
        },
    )

    observation = build_execution_observation(
        execution_id="SC-CRM",
        turns=(("turn-1", rows),),
        observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
    )
    fact = next(
        item
        for item in observation.side_effect_facts
        if item.artifact_id == artifact_id
    )

    assert fact.disposition == "cleanup_pending"
    assert observation.final_inventory[artifact_id] == {
        "state": "active",
        "status": "customer",
    }


def test_execution_observation_blocks_unlisted_business_effect() -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationNotReady,
        build_execution_observation,
    )

    rows = _observed_rows(
        final_inventory={"crm:contact:contact-1": {"state": "active"}}
    )

    with pytest.raises(ProductionObservationNotReady, match="disposition"):
        build_execution_observation(
            execution_id="SC-CRM",
            turns=(("turn-1", rows),),
            observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
        )


def test_execution_observation_blocks_unknown_terminal_readback() -> None:
    from src.services.e2e_observation_producer import (
        ProductionObservationNotReady,
        build_execution_observation,
    )

    artifact_id = "escalation:conversation:conversation-1"
    rows = _observed_rows(
        final_inventory={artifact_id: {"state": "unknown", "status": "pending"}},
        final_readback_inventory={
            artifact_id: {
                "state": "unknown",
                "status": "pending",
            }
        },
    )

    with pytest.raises(ProductionObservationNotReady, match="incomplete|terminal"):
        build_execution_observation(
            execution_id="SC-ESCALATE",
            turns=(("turn-1", rows),),
            observed_at=datetime(2026, 7, 29, 9, 0, 3, tzinfo=UTC),
        )


@pytest.mark.asyncio
async def test_business_readback_uses_exact_provider_identities_and_safe_fields() -> (
    None
):
    from src.services.e2e_observation_producer import collect_business_readbacks

    final_inventory = {
        "crm:contact:contact-1": {"state": "active"},
        "crm:deal:deal-1": {"state": "active", "status": "New Lead"},
        "quotation:sale_order:order-1": {
            "state": "active",
            "status": "pdf_sent",
        },
    }
    rows = _observed_rows(final_inventory=final_inventory)
    crm = AsyncMock()
    crm.get_contact.return_value = {
        "id": "contact-1",
        "status": "active",
        "Full_Name": "must not be copied",
    }
    crm.get_deal_status.return_value = {
        "id": "deal-1",
        "Stage": "New Lead",
        "Contact_Name": "must not be copied",
    }
    inventory = AsyncMock()
    inventory.get_sale_order.return_value = {
        "salesorder": {
            "salesorder_id": "order-1",
            "customer_id": "contact-1",
            "customer_name": "must not be copied",
            "status": "draft",
            "total": 200,
            "line_items": [
                {
                    "item_id": "item-1",
                    "sku": "SKU-1",
                    "name": "must not be copied",
                    "quantity": 2,
                    "rate": 100,
                    "item_total": 200,
                }
            ],
        }
    }

    readbacks = await collect_business_readbacks(
        rows,
        crm_client=crm,
        inventory_client=inventory,
    )

    crm.get_contact.assert_awaited_once_with("contact-1")
    crm.get_deal_status.assert_awaited_once_with("deal-1")
    inventory.get_sale_order.assert_awaited_once_with("order-1")
    assert readbacks["quotation:sale_order:order-1"] == {
        "state": "active",
        "status": "draft",
        "customer_id": "contact-1",
        "line_items": [
            {
                "item_id": "item-1",
                "sku": "SKU-1",
                "quantity": 2,
                "rate": 100,
                "item_total": 200,
            }
        ],
        "total": 200,
    }
    assert "must not be copied" not in repr(readbacks)


def test_ssh_transport_allows_only_exact_server_observer_command() -> None:
    from scripts.e2e_acceptance.live_transport import ReadOnlySshTransport
    from scripts.e2e_acceptance.production import ProductionAdapterError

    command = [
        "/usr/bin/docker",
        "compose",
        "--project-directory",
        "/opt/noor",
        "--project-name",
        "noor",
        "exec",
        "-T",
        "app",
        "/app/.venv/bin/noor-e2e-observe",
        "execution",
        "--execution-id",
        "SC-GENERIC",
        "--turn",
        "turn-1=provider-message-1",
    ]

    transport = ReadOnlySshTransport(
        host_alias="noor-production",
        source_commands={"execution:SC-GENERIC": command},
    )
    assert transport.source_commands["execution:SC-GENERIC"] == tuple(command)

    changed = list(command)
    changed[9] = "/app/.venv/bin/python"
    with pytest.raises(ProductionAdapterError, match="read-only"):
        ReadOnlySshTransport(
            host_alias="noor-production",
            source_commands={"execution:SC-GENERIC": changed},
        )
