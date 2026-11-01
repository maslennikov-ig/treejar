from __future__ import annotations

import pytest

from src.dialogue.runner import quote_consent_signal
from src.dialogue.state import QuoteConsent


@pytest.mark.parametrize(
    ("text", "history", "expected"),
    [
        ("I do not want the quotation.", [], QuoteConsent.DECLINED),
        ("No quote please, just share prices.", [], QuoteConsent.DECLINED),
        ("لا أريد عرض سعر", [], QuoteConsent.DECLINED),
        ("No quotation for now, maybe later.", [], QuoteConsent.DEFERRED),
        ("Hold the quote for now.", [], QuoteConsent.DEFERRED),
        ("عرض السعر لاحقاً", [], QuoteConsent.DEFERRED),
        ("Please prepare a quotation.", [], QuoteConsent.GRANTED),
        ("Send quotation please.", [], QuoteConsent.GRANTED),
        ("أرسل عرض السعر", [], QuoteConsent.GRANTED),
        (
            "Yes please!",
            ["assistant: Would you like a formal quotation?"],
            QuoteConsent.GRANTED,
        ),
        (
            "نعم",
            ["assistant: هل ترغب في عرض سعر رسمي؟"],
            QuoteConsent.GRANTED,
        ),
        (
            "Yes",
            ["assistant: Do you prefer mesh or leather?"],
            None,
        ),
        ("Please show me chair options.", [], None),
    ],
)
def test_quote_consent_signal_classifies_consent_defer_and_decline(
    text: str,
    history: list[str],
    expected: QuoteConsent | None,
) -> None:
    assert quote_consent_signal(text, history) is expected
