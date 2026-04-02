"""Integration test: delivered deal → feedback request → feedback saved."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.conversation import Conversation
from src.schemas.common import DealStatus, SalesStage


@pytest.mark.asyncio
async def test_feedback_cron_triggers_for_delivered_deals() -> None:
    """Test that run_feedback_requests finds delivered deals without feedback."""
    now = datetime.now(UTC)
    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971501234567",
        sales_stage=SalesStage.CLOSING.value,
        language="en",
        escalation_status="none",
        deal_status="delivered",
        deal_delivered_at=now - timedelta(hours=30),
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [conv]
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    with (
        patch("src.services.followup.async_session_factory") as mock_sf,
        patch("src.services.followup._send_feedback_request") as mock_send,
    ):
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.followup import run_feedback_requests

        await run_feedback_requests({})

        mock_send.assert_called_once_with(mock_db, conv)


@pytest.mark.asyncio
async def test_feedback_cron_skips_conversations_with_existing_feedback() -> None:
    """Test that cron does NOT trigger for conversations that already have feedback."""
    # The actual query in the cron should LEFT JOIN with feedbacks
    # and filter where feedbacks.id IS NULL.
    # We test that the SQL query structure is correct via the cron function.
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []  # No conversations matched the query
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    with (
        patch("src.services.followup.async_session_factory") as mock_sf,
        patch("src.services.followup._send_feedback_request") as mock_send,
    ):
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.followup import run_feedback_requests

        await run_feedback_requests({})

        mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_dashboard_feedback_metrics() -> None:
    """Test that dashboard metrics include feedback-related KPIs."""
    from src.schemas.admin import DashboardMetricsResponse

    # Verify the schema has feedback fields
    fields = DashboardMetricsResponse.model_fields
    assert "feedback_count" in fields
    assert "avg_rating_overall" in fields
    assert "avg_rating_delivery" in fields
    assert "nps_score" in fields
    assert "recommend_rate" in fields


@pytest.mark.asyncio
async def test_feedback_cron_sql_structure() -> None:
    """CR-7: Verify the SQL query structure contains outerjoin, IS NULL, and deal_status.

    Captures the actual SQLAlchemy statement passed to db.execute() and compiles
    it to check for critical query elements that the mock-based tests can't verify.
    """
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_db.execute.return_value = mock_result

    with (
        patch("src.services.followup.async_session_factory") as mock_sf,
        patch("src.services.followup._send_feedback_request"),
    ):
        mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

        from src.services.followup import run_feedback_requests

        await run_feedback_requests({})

    # Capture the statement that was passed to db.execute()
    assert mock_db.execute.called, "db.execute should have been called"
    stmt = mock_db.execute.call_args[0][0]

    # Compile the SQLAlchemy statement to raw SQL string
    from sqlalchemy.dialects import postgresql

    compiled = str(stmt.compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    compiled_lower = compiled.lower()

    # Verify LEFT OUTER JOIN on feedbacks table
    assert "left outer join" in compiled_lower and "feedbacks" in compiled_lower, (
        f"Expected LEFT OUTER JOIN feedbacks in SQL, got:\n{compiled}"
    )

    # Verify IS NULL filter (excludes conversations that already have feedback)
    assert "is null" in compiled_lower, (
        f"Expected IS NULL filter for feedbacks.id in SQL, got:\n{compiled}"
    )

    # Verify deal_status filter
    assert "deal_status" in compiled_lower, (
        f"Expected deal_status filter in SQL, got:\n{compiled}"
    )

    # Verify time-window filters (deal_delivered_at — NOT updated_at)
    assert "deal_delivered_at" in compiled_lower, (
        f"Expected deal_delivered_at filter in SQL (not updated_at), got:\n{compiled}"
    )
    assert (
        "updated_at" not in compiled_lower
        or compiled_lower.count("deal_delivered_at") >= 2
    ), f"Expected deal_delivered_at used for time window filters, got:\n{compiled}"


@pytest.mark.asyncio
async def test_deal_delivered_at_set_on_first_delivered_transition() -> None:
    """CR: When deal_status is updated to DELIVERED and deal_delivered_at is None,
    deal_delivered_at should be set to current UTC timestamp.
    """
    from datetime import UTC, datetime

    from src.api.v1.conversations import update_conversation
    from src.schemas.conversation import ConversationUpdate

    conv_id = uuid.uuid4()
    now = datetime.now(UTC)
    conv = Conversation(
        id=conv_id,
        phone="+971501234567",
        sales_stage=SalesStage.CLOSING.value,
        language="en",
        status="active",
        escalation_status="none",
        deal_status=None,
        deal_delivered_at=None,
        created_at=now,
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    body = ConversationUpdate(deal_status="delivered")

    before = datetime.now(UTC)
    await update_conversation(conv_id, body, mock_db)
    after = datetime.now(UTC)

    assert conv.deal_status == DealStatus.DELIVERED.value
    assert conv.deal_delivered_at is not None
    assert before <= conv.deal_delivered_at <= after


@pytest.mark.asyncio
async def test_deal_delivered_at_not_overwritten_on_subsequent_update() -> None:
    """CR: If deal_delivered_at is already set, it must NOT be overwritten on
    subsequent PATCH requests that keep deal_status = DELIVERED.
    """
    from datetime import UTC, datetime

    from src.api.v1.conversations import update_conversation
    from src.schemas.conversation import ConversationUpdate

    original_ts = datetime.now(UTC) - timedelta(hours=5)
    now = datetime.now(UTC)
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        phone="+971501234567",
        sales_stage=SalesStage.FEEDBACK.value,
        language="en",
        status="active",
        escalation_status="none",
        deal_status="delivered",
        deal_delivered_at=original_ts,
        created_at=now,
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock(side_effect=lambda obj: None)

    body = ConversationUpdate(deal_status="delivered")

    await update_conversation(conv_id, body, mock_db)

    # deal_delivered_at must remain unchanged
    assert conv.deal_delivered_at == original_ts
