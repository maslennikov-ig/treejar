import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus, SalesStage
from src.services.followup import (
    PaymentReminderControlsConfig,
    _process_followup_for_conversation,
    _process_payment_reminder_for_conversation,
)


class _FakeAgentResult:
    output = "Just checking in, anything I can help with?"

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=12, output_tokens=8)


def _approved_payment_conversation() -> Conversation:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    return Conversation(
        id=uuid.uuid4(),
        phone="+971501234567",
        status="active",
        deal_status="pending",
        updated_at=now - datetime.timedelta(hours=26),
        escalation_status=EscalationStatus.NONE.value,
        metadata_={
            "quotation_decision": {
                "status": "approved",
                "active": True,
                "quote_number": "SO-001",
                "zoho_sale_order_id": "so-001",
                "decided_at": (now - datetime.timedelta(hours=26)).isoformat(),
            },
            "quotation_decision_status": "approved",
            "zoho_sale_order_id": "so-001",
            "zoho_sale_order_active": True,
            "order_active": True,
        },
    )


@pytest.mark.asyncio
async def test_process_followup_for_conversation() -> None:
    # Setup mock conversation
    now = datetime.datetime.now(datetime.UTC)
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        updated_at=now - datetime.timedelta(hours=24, minutes=30),
        escalation_status=EscalationStatus.NONE.value,
        sales_stage=SalesStage.GREETING.value,
    )

    mock_db = AsyncMock()

    import src.llm.engine as engine

    test_model = TestModel(
        custom_output_text="Just checking in, anything I can help with?", call_tools=[]
    )

    with (
        patch("src.services.followup.get_redis_client", return_value=AsyncMock()),
        patch("src.services.followup.EmbeddingEngine", return_value=AsyncMock()),
        patch("src.services.followup.ZohoCRMClient", return_value=AsyncMock()),
        patch(
            "src.services.followup.WazzupProvider", return_value=AsyncMock()
        ) as mock_wazzup_cls,
        patch(
            "src.integrations.inventory.zoho_inventory.ZohoInventoryClient",
            return_value=AsyncMock(),
        ),
        patch("src.llm.context.build_message_history", return_value=[]),
        patch("src.core.cache.get_cached_crm_profile", return_value=None),
    ):
        mock_wazzup = mock_wazzup_cls.return_value

        with engine.sales_agent.override(model=test_model):
            await _process_followup_for_conversation(mock_db, conv)

        # Verify message was sent
        mock_wazzup.send_text.assert_called_once_with(
            "12345",
            "Just checking in, anything I can help with?",
            crm_message_id=f"followup:{conv.id}:inactive",
        )

        # Verify db.add and commit cover the AI message plus outbound audit row.
        assert mock_db.add.call_count == 2
        assert mock_db.add.call_args_list[0].args[0].role == "assistant"
        assert mock_db.commit.await_count == 2


@pytest.mark.asyncio
async def test_process_followup_for_conversation_passes_expected_llm_safety_kwargs() -> (
    None
):
    now = datetime.datetime.now(datetime.UTC)
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        updated_at=now - datetime.timedelta(hours=24, minutes=30),
        escalation_status=EscalationStatus.NONE.value,
        sales_stage=SalesStage.GREETING.value,
    )

    mock_db = AsyncMock()

    with (
        patch("src.services.followup.get_redis_client", return_value=AsyncMock()),
        patch("src.services.followup.EmbeddingEngine", return_value=AsyncMock()),
        patch("src.services.followup.ZohoCRMClient", return_value=AsyncMock()),
        patch("src.services.followup.WazzupProvider", return_value=AsyncMock()),
        patch(
            "src.integrations.inventory.zoho_inventory.ZohoInventoryClient",
            return_value=AsyncMock(),
        ),
        patch("src.llm.context.build_message_history", return_value=[]),
        patch("src.core.cache.get_cached_crm_profile", return_value=None),
        patch(
            "src.llm.engine.sales_agent.run",
            new=AsyncMock(return_value=_FakeAgentResult()),
        ) as mock_run,
    ):
        await _process_followup_for_conversation(mock_db, conv)

    call_kwargs = mock_run.await_args.kwargs
    assert call_kwargs["model_settings"]["max_tokens"] == 500
    assert "usage_limits" not in call_kwargs


@pytest.mark.asyncio
async def test_payment_reminder_over_24h_without_template_blocks() -> None:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    conv = _approved_payment_conversation()
    provider = AsyncMock()
    mock_db = AsyncMock()

    result = await _process_payment_reminder_for_conversation(
        mock_db,
        conv,
        controls=PaymentReminderControlsConfig(mode="scheduled", template_name=None),
        last_customer_inbound_at=now - datetime.timedelta(hours=25),
        now=now,
        provider=provider,
    )

    assert result.sent is False
    assert result.reason == "template_missing"
    provider.send_template.assert_not_called()
    provider.send_text.assert_not_called()
    assert (
        conv.metadata_["payment_reminders"]["so-001"]["initial-24h"]["status"]
        == "blocked"
    )


@pytest.mark.asyncio
async def test_payment_reminder_over_24h_with_template_uses_crm_message_id() -> None:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    conv = _approved_payment_conversation()
    provider = AsyncMock()
    provider.send_template.return_value = "msg-template-1"
    provider.outbound_chat_id.return_value = "+971501234567"
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    result = await _process_payment_reminder_for_conversation(
        mock_db,
        conv,
        controls=PaymentReminderControlsConfig(
            mode="scheduled",
            template_name="payment_reminder_approved_order_v1",
        ),
        last_customer_inbound_at=now - datetime.timedelta(hours=25),
        now=now,
        provider=provider,
    )

    assert result.sent is True
    assert result.crm_message_id == f"payment_reminder:{conv.id}:so-001:initial-24h"
    provider.send_template.assert_awaited_once_with(
        "+971501234567",
        "payment_reminder_approved_order_v1",
        {},
        crm_message_id=f"payment_reminder:{conv.id}:so-001:initial-24h",
    )
    provider.send_text.assert_not_called()
    assert (
        conv.metadata_["payment_reminders"]["so-001"]["initial-24h"]["status"] == "sent"
    )


@pytest.mark.asyncio
async def test_payment_reminder_closes_locally_created_wazzup_provider() -> None:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    conv = _approved_payment_conversation()
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    provider = AsyncMock()
    provider.send_template.return_value = "msg-template-1"
    provider.outbound_chat_id.return_value = "+971501234567"

    with patch("src.services.followup.WazzupProvider", return_value=provider):
        result = await _process_payment_reminder_for_conversation(
            mock_db,
            conv,
            controls=PaymentReminderControlsConfig(
                mode="scheduled",
                template_name="payment_reminder_approved_order_v1",
            ),
            last_customer_inbound_at=now - datetime.timedelta(hours=25),
            now=now,
        )

    assert result.sent is True
    provider.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_payment_reminder_duplicate_state_prevents_repeat_send() -> None:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    conv = _approved_payment_conversation()
    conv.metadata_["payment_reminders"] = {
        "so-001": {
            "initial-24h": {
                "status": "sent",
                "crm_message_id": f"payment_reminder:{conv.id}:so-001:initial-24h",
            }
        }
    }
    provider = AsyncMock()

    result = await _process_payment_reminder_for_conversation(
        AsyncMock(),
        conv,
        controls=PaymentReminderControlsConfig(
            mode="scheduled",
            template_name="payment_reminder_approved_order_v1",
        ),
        last_customer_inbound_at=now - datetime.timedelta(hours=25),
        now=now,
        provider=provider,
    )

    assert result.sent is False
    assert result.reason == "duplicate"
    provider.send_template.assert_not_called()
    provider.send_text.assert_not_called()


@pytest.mark.asyncio
async def test_payment_reminder_within_24h_requires_explicit_configured_text() -> None:
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    conv = _approved_payment_conversation()
    provider = AsyncMock()
    provider.send_text.return_value = "msg-text-1"
    provider.outbound_chat_id.return_value = "+971501234567"
    mock_db = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none.return_value = None

    disabled = await _process_payment_reminder_for_conversation(
        mock_db,
        conv,
        controls=PaymentReminderControlsConfig(
            mode="scheduled",
            template_name="payment_reminder_approved_order_v1",
            min_hours_after_approval=1,
        ),
        last_customer_inbound_at=now - datetime.timedelta(hours=2),
        now=now,
        provider=provider,
    )
    assert disabled.sent is False
    assert disabled.reason == "within_24h_text_disabled"
    provider.send_text.assert_not_called()

    conv.metadata_.pop("payment_reminders", None)
    enabled = await _process_payment_reminder_for_conversation(
        mock_db,
        conv,
        controls=PaymentReminderControlsConfig(
            mode="scheduled",
            min_hours_after_approval=1,
            within_24h_text_enabled=True,
            within_24h_text="Your approved order is awaiting payment.",
        ),
        last_customer_inbound_at=now - datetime.timedelta(hours=2),
        now=now,
        provider=provider,
    )

    assert enabled.sent is True
    provider.send_text.assert_awaited_once_with(
        "+971501234567",
        "Your approved order is awaiting payment.",
        crm_message_id=f"payment_reminder:{conv.id}:so-001:initial-1h",
    )
