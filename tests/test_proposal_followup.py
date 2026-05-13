import datetime
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from src.models.conversation import Conversation
from src.services.outbound_audit import deterministic_crm_message_id
from src.services.proposal_followup import (
    ProposalFollowupSendControls,
    build_followup_send_plan,
    next_due_followup_step,
    process_due_proposal_followup,
    record_customer_reply,
    record_followup_step_sent,
    record_proposal_read,
    record_proposal_sent,
)


def _dt(value: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))


def _conversation() -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        phone="+971501234567",
        status="active",
        deal_status="pending",
        metadata_={},
    )


def _proposal_state(conv: Conversation) -> dict[str, object]:
    metadata = conv.metadata_ or {}
    state = metadata["proposal_followup"]
    assert isinstance(state, dict)
    return state


def test_record_proposal_sent_initializes_followup_metadata_and_schedule() -> None:
    conv = _conversation()

    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    state = _proposal_state(conv)
    assert state["sent_at"] == "2026-05-04T08:00:00+00:00"
    assert state["kp_message_id"] == "kp-msg-1"
    assert state["kp_read"] is False
    assert state["chain_stopped"] is False
    assert state["pause_until"] is None
    assert set(state["steps"]) == {"1", "2", "3", "4"}
    assert state["steps"]["1"]["scheduled_at"] == "2026-05-05T08:00:00+00:00"
    assert state["steps"]["2"]["scheduled_at"] == "2026-05-06T08:00:00+00:00"
    assert state["steps"]["3"]["scheduled_at"] == "2026-05-11T06:00:00+00:00"
    assert state["steps"]["4"]["scheduled_at"] == "2026-05-18T06:00:00+00:00"


def test_record_proposal_read_moves_fu1_to_two_hours_after_read() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    record_proposal_read(conv, read_at=_dt("2026-05-04T09:00:00Z"))

    state = _proposal_state(conv)
    assert state["kp_read"] is True
    assert state["kp_read_at"] == "2026-05-04T09:00:00+00:00"
    assert state["steps"]["1"]["scheduled_at"] == "2026-05-04T11:00:00+00:00"
    assert state["steps"]["2"]["scheduled_at"] == "2026-05-05T11:00:00+00:00"


def test_business_window_shifts_weekend_and_after_hours_to_monday_morning() -> None:
    conv = _conversation()

    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-08T16:30:00Z"),
        kp_message_id="kp-msg-friday",
    )

    state = _proposal_state(conv)
    assert state["steps"]["1"]["scheduled_at"] == "2026-05-11T06:00:00+00:00"


def test_record_followup_sent_reschedules_subsequent_steps_from_actual_sent_time() -> (
    None
):
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    record_followup_step_sent(conv, step=1, sent_at=_dt("2026-05-05T13:30:00Z"))

    state = _proposal_state(conv)
    assert state["steps"]["1"]["sent_at"] == "2026-05-05T13:30:00+00:00"
    assert state["steps"]["1"]["status"] == "sent"
    assert state["steps"]["2"]["scheduled_at"] == "2026-05-06T13:30:00+00:00"
    assert state["steps"]["3"]["scheduled_at"] == "2026-05-11T06:00:00+00:00"
    assert state["steps"]["4"]["scheduled_at"] == "2026-05-18T06:00:00+00:00"


def test_next_due_followup_respects_pause_and_stop_state() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )
    due_at = _dt("2026-05-05T08:00:00Z")

    assert next_due_followup_step(conv, now=due_at).step == 1

    state = _proposal_state(conv)
    state["pause_until"] = "2026-05-06T08:00:00+00:00"
    assert next_due_followup_step(conv, now=due_at) is None

    state["pause_until"] = None
    state["chain_stopped"] = True
    assert next_due_followup_step(conv, now=due_at) is None


def test_meaningful_customer_reply_stops_chain() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    decision = record_customer_reply(
        conv,
        text="Please update the proposal for five desks instead.",
        received_at=_dt("2026-05-04T12:00:00Z"),
    )

    state = _proposal_state(conv)
    assert decision.action == "stop"
    assert decision.recommended_deal_status is None
    assert state["chain_stopped"] is True
    assert state["stop_reason"] == "customer_reply"


def test_short_customer_reply_stops_chain() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    decision = record_customer_reply(
        conv,
        text="ok",
        received_at=_dt("2026-05-04T12:00:00Z"),
    )

    state = _proposal_state(conv)
    assert decision.action == "stop"
    assert decision.reason == "customer_reply"
    assert state["chain_stopped"] is True
    assert state["stop_reason"] == "customer_reply"


def test_explicit_rejection_stops_chain_and_recommends_rejected_status() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    decision = record_customer_reply(
        conv,
        text="Thanks, but we are not interested anymore.",
        received_at=_dt("2026-05-04T12:00:00Z"),
    )

    state = _proposal_state(conv)
    assert decision.action == "stop"
    assert decision.recommended_deal_status == "rejected"
    assert state["chain_stopped"] is True
    assert state["stop_reason"] == "explicit_rejection"


def test_autoreply_with_date_pauses_until_next_day_without_stopping_chain() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    decision = record_customer_reply(
        conv,
        text="Automatic reply: I am out of office until 2026-05-20.",
        received_at=_dt("2026-05-04T12:00:00Z"),
    )

    state = _proposal_state(conv)
    assert decision.action == "pause"
    assert decision.pause_until == _dt("2026-05-20T20:00:00Z")
    assert state["pause_until"] == "2026-05-20T20:00:00+00:00"
    assert state["chain_stopped"] is False


def test_autoreply_without_date_pauses_for_three_days() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )

    decision = record_customer_reply(
        conv,
        text="Auto-reply: I am away from office.",
        received_at=_dt("2026-05-04T12:00:00Z"),
    )

    state = _proposal_state(conv)
    assert decision.action == "pause"
    assert decision.pause_until == _dt("2026-05-07T12:00:00Z")
    assert state["pause_until"] == "2026-05-07T12:00:00+00:00"
    assert state["chain_stopped"] is False


def test_send_plan_is_disabled_by_default_and_requires_safe_message_mode() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )
    due = next_due_followup_step(conv, now=_dt("2026-05-05T08:00:00Z"))

    assert due is not None
    default_plan = build_followup_send_plan(due)
    assert default_plan.can_send is False
    assert default_plan.reason == "proposal_followup_disabled"

    no_template = build_followup_send_plan(
        due,
        controls=ProposalFollowupSendControls(enabled=True),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
    )
    assert no_template.can_send is False
    assert no_template.reason == "template_required_outside_24h"

    unconfirmed_template_plan = build_followup_send_plan(
        due,
        controls=ProposalFollowupSendControls(
            enabled=True,
            template_name="proposal_followup_fu1_v1",
        ),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
    )
    assert unconfirmed_template_plan.can_send is False
    assert unconfirmed_template_plan.reason == "template_transport_unconfirmed"

    template_plan = build_followup_send_plan(
        due,
        controls=ProposalFollowupSendControls(
            enabled=True,
            template_name="proposal_followup_fu1_v1",
            template_transport_confirmed=True,
        ),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
    )
    assert template_plan.can_send is True
    assert template_plan.mode == "template"
    assert template_plan.template_name == "proposal_followup_fu1_v1"

    no_freeform = build_followup_send_plan(
        due,
        controls=ProposalFollowupSendControls(enabled=True),
        last_customer_inbound_at=_dt("2026-05-05T07:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
    )
    assert no_freeform.can_send is False
    assert no_freeform.reason == "freeform_text_required_within_24h"

    freeform_plan = build_followup_send_plan(
        due,
        controls=ProposalFollowupSendControls(
            enabled=True,
            freeform_text_by_step={1: "Checking whether you had a chance to review."},
        ),
        last_customer_inbound_at=_dt("2026-05-05T07:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
    )
    assert freeform_plan.can_send is True
    assert freeform_plan.mode == "freeform"
    assert freeform_plan.text == "Checking whether you had a chance to review."


class _NoExistingAuditResult:
    def scalar_one_or_none(self) -> object | None:
        return None


def _mock_db() -> AsyncMock:
    db = AsyncMock()
    db.execute.return_value = _NoExistingAuditResult()
    db.add = Mock()
    return db


@pytest.mark.asyncio
async def test_process_due_proposal_followup_disabled_default_sends_nothing() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )
    provider = AsyncMock()
    db = _mock_db()

    result = await process_due_proposal_followup(
        db,
        conv,
        controls=ProposalFollowupSendControls(),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
        provider=provider,
    )

    assert result.sent is False
    assert result.reason == "proposal_followup_disabled"
    provider.send_template.assert_not_awaited()
    provider.send_text.assert_not_awaited()
    db.commit.assert_not_awaited()
    state = _proposal_state(conv)
    assert state["steps"]["1"]["status"] == "pending"


@pytest.mark.asyncio
async def test_process_due_proposal_followup_template_send_records_step() -> None:
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )
    provider = AsyncMock()
    provider.outbound_chat_id.return_value = conv.phone
    provider.send_template.return_value = "fu-provider-1"
    db = _mock_db()
    scheduled_at = _dt("2026-05-05T08:00:00Z")
    crm_message_id = deterministic_crm_message_id(
        "proposal_followup",
        conv.id,
        "fu1",
        scheduled_at.isoformat(),
    )

    result = await process_due_proposal_followup(
        db,
        conv,
        controls=ProposalFollowupSendControls(
            enabled=True,
            template_name_by_step={1: "proposal_followup_fu1_v1"},
            template_transport_confirmed=True,
        ),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=scheduled_at,
        provider=provider,
    )

    assert result.sent is True
    assert result.reason is None
    assert result.crm_message_id == crm_message_id
    assert result.provider_message_id == "fu-provider-1"
    provider.send_template.assert_awaited_once_with(
        conv.phone,
        "proposal_followup_fu1_v1",
        {},
        crm_message_id=crm_message_id,
    )
    provider.send_text.assert_not_awaited()
    db.commit.assert_awaited_once()
    state = _proposal_state(conv)
    assert state["steps"]["1"]["status"] == "sent"
    assert state["steps"]["1"]["provider_message_id"] == "fu-provider-1"


@pytest.mark.asyncio
async def test_process_due_proposal_followup_missing_template_does_not_mark_sent() -> (
    None
):
    conv = _conversation()
    record_proposal_sent(
        conv,
        sent_at=_dt("2026-05-04T08:00:00Z"),
        kp_message_id="kp-msg-1",
    )
    provider = AsyncMock()
    db = _mock_db()

    result = await process_due_proposal_followup(
        db,
        conv,
        controls=ProposalFollowupSendControls(enabled=True),
        last_customer_inbound_at=_dt("2026-05-03T08:00:00Z"),
        now=_dt("2026-05-05T08:00:00Z"),
        provider=provider,
    )

    assert result.sent is False
    assert result.reason == "template_required_outside_24h"
    provider.send_template.assert_not_awaited()
    provider.send_text.assert_not_awaited()
    db.commit.assert_not_awaited()
    state = _proposal_state(conv)
    assert state["steps"]["1"]["status"] == "pending"
