from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from src.schemas.common import EscalationStatus
from src.services.escalation_state import (
    EscalationAction,
    EscalationValidity,
    allows_automatic_followup,
    classify_pending_escalation,
    classify_record_source,
    is_active_human_handoff,
    should_pause_bot_for_escalation,
    should_send_escalation_fallback,
)


def test_resolved_status_is_not_an_active_human_handoff() -> None:
    assert not is_active_human_handoff(EscalationStatus.RESOLVED.value)
    assert not should_pause_bot_for_escalation(EscalationStatus.RESOLVED.value)
    assert not should_send_escalation_fallback(EscalationStatus.RESOLVED.value)


def test_manual_takeover_pauses_bot_without_fallback() -> None:
    assert not is_active_human_handoff(EscalationStatus.MANUAL_TAKEOVER.value)
    assert should_pause_bot_for_escalation(EscalationStatus.MANUAL_TAKEOVER.value)
    assert not should_send_escalation_fallback(EscalationStatus.MANUAL_TAKEOVER.value)


def test_resolved_status_allows_automatic_followups() -> None:
    assert allows_automatic_followup(EscalationStatus.NONE.value)
    assert allows_automatic_followup(EscalationStatus.RESOLVED.value)
    assert not allows_automatic_followup(EscalationStatus.PENDING.value)


@pytest.mark.parametrize(
    (
        "conversation_status",
        "conversation_escalation_status",
        "age_days",
        "expected_validity",
        "expected_action",
    ),
    [
        ("active", "pending", 45, EscalationValidity.VALID, EscalationAction.REVIEW),
        ("active", "pending", 8, EscalationValidity.VALID, EscalationAction.REVIEW),
        ("active", "none", 45, EscalationValidity.STALE, EscalationAction.RESOLVE),
        ("active", "none", 8, EscalationValidity.AMBIGUOUS, EscalationAction.REVIEW),
        ("closed", "resolved", 8, EscalationValidity.STALE, EscalationAction.RESOLVE),
        (
            "active",
            "manual_takeover",
            45,
            EscalationValidity.VALID,
            EscalationAction.REVIEW,
        ),
    ],
)
def test_pending_escalation_classification_uses_repository_state_policy(
    conversation_status: str,
    conversation_escalation_status: str,
    age_days: int,
    expected_validity: EscalationValidity,
    expected_action: EscalationAction,
) -> None:
    now = datetime(2026, 7, 23, tzinfo=UTC)

    classification = classify_pending_escalation(
        escalation_id=uuid4(),
        conversation_id=uuid4(),
        phone="+971500000000",
        conversation_status=conversation_status,
        conversation_escalation_status=conversation_escalation_status,
        escalation_status="pending",
        escalation_created_at=now - timedelta(days=age_days),
        now=now,
        stale_after_days=30,
    )

    assert classification.validity is expected_validity
    assert classification.action is expected_action


@pytest.mark.parametrize(
    ("phone", "expected"),
    [
        ("+971500000000", "real"),
        ("+79262810921#tj-final27-quality-1", "synthetic"),
        ("+79262810921#smoke-tool-final", "synthetic"),
        ("+971500000000#archived-reset-abc", "real_archived"),
        ("+971500000000#unrecognized", "tagged_unknown"),
    ],
)
def test_record_source_classification_is_conservative(
    phone: str,
    expected: str,
) -> None:
    assert classify_record_source(phone).value == expected
