"""Which conversations may raise a manager alert (tj-zyxz).

Verified against production on 2026-08-06: no `telegram_test_mode_enabled` row
exists and `TELEGRAM_ALLOWED_INBOUND_PHONE` is unset on the runtime, so the gate
ran on the hardcoded default in `src/core/config.py`. It happened to be
Treejar's live WhatsApp line, so all 15 escalations of the previous 30 days did
alert — the rule was right by luck, not by construction. A second line, a number
change, or a conversation without channel metadata was silently dropped, and 11
of the 84 escalations on record already carried no channel metadata.

The rule now takes a list and fails open. A spurious alert costs the internal
group one message; a dropped one costs a customer who asked for a human.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.inbound_channels import (
    allowed_inbound_channel_phones,
    should_send_manager_alert_for_conversation,
    should_send_telegram_alert_for_conversation,
)

_LIVE_LINE = "+971551220665"
_SECOND_LINE = "+971509998877"


def _conversation(inbound_phone: str | None) -> SimpleNamespace:
    metadata = {"inbound_channel_phone": inbound_phone} if inbound_phone else {}
    return SimpleNamespace(metadata_=metadata)


@pytest.fixture
def allowlist(monkeypatch: pytest.MonkeyPatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(
            "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
            value,
            raising=False,
        )

    return _set


def test_a_second_line_alerts_once_it_is_configured(allowlist) -> None:
    """The acceptance criterion: adding a line does not need a code change."""
    allowlist(f"{_LIVE_LINE}, {_SECOND_LINE}")

    assert should_send_manager_alert_for_conversation(_conversation(_SECOND_LINE))
    assert should_send_manager_alert_for_conversation(_conversation(_LIVE_LINE))


@pytest.mark.parametrize(
    "raw",
    [
        f" {_LIVE_LINE} ,{_SECOND_LINE}",
        f"971551220665,{_SECOND_LINE}",
        f"{_LIVE_LINE},,{_SECOND_LINE},",
    ],
)
def test_the_list_survives_ordinary_configuration_sloppiness(
    raw: str, allowlist
) -> None:
    allowlist(raw)

    assert allowed_inbound_channel_phones() == frozenset({_LIVE_LINE, _SECOND_LINE})


def test_a_conversation_on_a_known_other_line_still_does_not_alert(allowlist) -> None:
    """Failing open is not the same as having no rule."""
    allowlist(_LIVE_LINE)

    assert not should_send_manager_alert_for_conversation(_conversation(_SECOND_LINE))


def test_a_conversation_with_no_channel_metadata_alerts(allowlist) -> None:
    """11 of 84 production escalations looked like this and were dropped."""
    allowlist(_LIVE_LINE)

    assert should_send_manager_alert_for_conversation(_conversation(None))


@pytest.mark.parametrize("empty", ["", "   ", ",", " , "])
def test_an_empty_allowlist_alerts_rather_than_silencing_everything(
    empty: str, allowlist
) -> None:
    """The old rule returned False here, which is total silent failure."""
    allowlist(empty)

    assert allowed_inbound_channel_phones() == frozenset()
    assert should_send_manager_alert_for_conversation(_conversation(_LIVE_LINE))
    assert should_send_manager_alert_for_conversation(_conversation(None))


def test_the_routine_alert_rule_stays_strict(allowlist) -> None:
    """The two families are gated separately on purpose.

    A quality or review alert is periodic and its cost of being wrong is noise,
    so an unattributable conversation still produces none. Only the escalation
    fails open, because only it can strand a customer.
    """
    allowlist(_LIVE_LINE)

    assert not should_send_telegram_alert_for_conversation(_conversation(None))
    assert should_send_manager_alert_for_conversation(_conversation(None))
