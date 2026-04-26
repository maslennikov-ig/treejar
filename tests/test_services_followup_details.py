import datetime
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus, SalesStage
from src.services.followup import _process_followup_for_conversation


class _FakeAgentResult:
    output = "Just checking in, anything I can help with?"

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=12, output_tokens=8)


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
