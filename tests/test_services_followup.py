import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus
from src.services.followup import (
    PaymentReminderControlsConfig,
    _naive_utc_now,
    _run_payment_reminders_with_db,
    build_payment_reminder_candidate,
    run_automatic_followups,
)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock the async DB session."""
    session = AsyncMock(spec=AsyncSession)

    # We mock the return value for db.execute().scalars().all()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    session.execute.return_value = mock_result
    return session


@pytest.mark.asyncio
async def test_run_automatic_followups_queries_db(mock_db_session: AsyncMock) -> None:
    # We patch the database session context manager
    with patch("src.services.followup.async_session_factory") as mock_session_maker:
        mock_session_maker.return_value.__aenter__.return_value = mock_db_session

        # Also mock _process_followup_for_conversation to ensure it's called
        with patch(
            "src.services.followup._process_followup_for_conversation"
        ) as mock_process:
            # Provide some mock conversations to return
            now = datetime.datetime.now(datetime.UTC)
            conv_24h = Conversation(
                id=uuid.uuid4(),
                phone="1",
                updated_at=now - datetime.timedelta(hours=24, minutes=30),
                escalation_status=EscalationStatus.NONE.value,
            )

            # Setup db execute to return different conversations for different queries
            # For simplicity, we just return one conv on the first query and [] for others
            mock_result = MagicMock()
            mock_scalars = MagicMock()

            # The order of execution: 24h, 72h, 168h
            mock_scalars.all.side_effect = [
                [conv_24h],  # 24h
                [],  # 72h
                [],  # 168h
            ]
            mock_result.scalars.return_value = mock_scalars
            mock_db_session.execute.return_value = mock_result

            await run_automatic_followups(
                {
                    "payment_reminder_controls": {"mode": "disabled"},
                    "legacy_automatic_followup_enabled": True,
                }
            )

            assert mock_db_session.execute.call_count == 3
            mock_process.assert_called_once_with(mock_db_session, conv_24h)


@pytest.mark.asyncio
async def test_run_automatic_followups_default_does_not_send_llm_free_text(
    mock_db_session: AsyncMock,
) -> None:
    """Generic inactive LLM follow-ups must be opt-in, not the default cron behavior."""
    with patch("src.services.followup.async_session_factory") as mock_session_maker:
        mock_session_maker.return_value.__aenter__.return_value = mock_db_session
        with (
            patch(
                "src.services.followup._process_payment_reminder_for_conversation"
            ) as mock_payment,
            patch(
                "src.services.followup._process_followup_for_conversation"
            ) as mock_legacy,
        ):
            await run_automatic_followups({})

    mock_payment.assert_not_called()
    mock_legacy.assert_not_called()


def _approved_conversation(**overrides: object) -> Conversation:
    now = _naive_utc_now()
    metadata = {
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
    }
    data = {
        "id": uuid.uuid4(),
        "phone": "+971501234567",
        "status": "active",
        "deal_status": "pending",
        "updated_at": now - datetime.timedelta(hours=26),
        "escalation_status": EscalationStatus.NONE.value,
        "metadata_": metadata,
    }
    data.update(overrides)
    return Conversation(**data)


def test_approved_active_order_becomes_payment_reminder_candidate() -> None:
    now = _naive_utc_now()
    conv = _approved_conversation()
    candidate = build_payment_reminder_candidate(
        conv,
        controls=PaymentReminderControlsConfig(mode="scheduled"),
        last_customer_inbound_at=now - datetime.timedelta(hours=25),
        now=now,
    )

    assert candidate is not None
    assert candidate.order_key == "so-001"
    assert candidate.crm_message_id.startswith(f"payment_reminder:{conv.id}:so-001:")


@pytest.mark.parametrize(
    ("overrides", "metadata_updates"),
    [
        ({"status": "closed"}, {}),
        ({"deal_status": "delivered"}, {}),
        ({"deal_status": "paid"}, {}),
        ({"escalation_status": EscalationStatus.MANUAL_TAKEOVER.value}, {}),
        ({"escalation_status": EscalationStatus.PENDING.value}, {}),
        ({}, {"quotation_decision_status": "rejected"}),
        ({}, {"zoho_sale_order_active": False}),
        ({}, {"order_active": False}),
        ({}, {"payment_status": "paid"}),
        ({}, {"order_status": "delivered"}),
    ],
)
def test_payment_reminder_candidate_excludes_stop_conditions(
    overrides: dict[str, object],
    metadata_updates: dict[str, object],
) -> None:
    now = _naive_utc_now()
    conv = _approved_conversation(**overrides)
    metadata = dict(conv.metadata_ or {})
    metadata.update(metadata_updates)
    if "quotation_decision_status" in metadata_updates:
        decision = dict(metadata["quotation_decision"])
        decision["status"] = metadata_updates["quotation_decision_status"]
        metadata["quotation_decision"] = decision
    conv.metadata_ = metadata

    candidate = build_payment_reminder_candidate(
        conv,
        controls=PaymentReminderControlsConfig(mode="scheduled"),
        last_customer_inbound_at=now - datetime.timedelta(hours=25),
        now=now,
    )

    assert candidate is None


@pytest.mark.asyncio
async def test_run_payment_reminders_scans_past_first_page_non_candidates() -> None:
    """Scheduled reminders must not miss valid orders behind active non-orders."""
    now = _naive_utc_now()
    non_candidates = [
        Conversation(
            id=uuid.uuid4(),
            phone=f"+971500000{i:03d}",
            status="active",
            deal_status="pending",
            updated_at=now - datetime.timedelta(hours=30),
            escalation_status=EscalationStatus.NONE.value,
            metadata_={},
        )
        for i in range(50)
    ]
    eligible = _approved_conversation()

    class _CountResult:
        def scalar(self) -> int:
            return 0

    class _RowsResult:
        def __init__(self, rows: list[tuple[Conversation, datetime.datetime]]) -> None:
            self._rows = rows

        def all(self) -> list[tuple[Conversation, datetime.datetime]]:
            return self._rows

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [
        _CountResult(),
        _RowsResult(
            [(conv, now - datetime.timedelta(hours=25)) for conv in non_candidates]
        ),
        _RowsResult([(eligible, now - datetime.timedelta(hours=25))]),
    ]

    with patch(
        "src.services.followup._process_payment_reminder_for_conversation",
        new=AsyncMock(return_value=MagicMock(sent=True)),
    ) as mock_process:
        await _run_payment_reminders_with_db(
            mock_db,
            controls=PaymentReminderControlsConfig(
                mode="scheduled",
                max_per_run=1,
                daily_limit=1,
                template_name="payment_reminder_approved_order_v1",
            ),
            now=now,
            trigger="scheduled",
        )

    mock_process.assert_awaited_once()
    assert mock_process.await_args.args[1].id == eligible.id


def test_naive_utc_now_returns_naive_datetime() -> None:
    now = _naive_utc_now()

    assert now.tzinfo is None
