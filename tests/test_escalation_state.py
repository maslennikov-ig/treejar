from src.schemas.common import EscalationStatus
from src.services.escalation_state import (
    allows_automatic_followup,
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
