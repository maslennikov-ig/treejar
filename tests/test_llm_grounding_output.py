from __future__ import annotations

import pytest

from src.llm.grounding_output import (
    GroundingOutputAction,
    GroundingViolation,
    classify_grounding_output,
    enforce_grounding_output,
)

MEDICAL_ATTEMPT_3 = (
    "The Nova Task chair does have a seat-depth adjustment, but I can't "
    "confirm that it will reduce back pain. There is no medical or "
    "health-outcome evidence available for this product. For health concerns, "
    "I'd recommend consulting a qualified healthcare professional. If you'd "
    "like, you can visit our UAE showroom to experience the chair's build "
    "quality and features in person."
)

STOCK_ATTEMPT_3 = (
    "AX-E1 is a valid catalog SKU, but I'm unable to confirm its current stock "
    "status right now as no inventory result is available. Could you let me "
    "know the quantity you need and your delivery timeline? I can also arrange "
    "for our team to check and get back to you, or you're welcome to visit our "
    "UAE showroom to experience our product quality firsthand."
)


def test_classify_grounding_output_finds_exact_attempt_3_violations() -> None:
    assert classify_grounding_output(MEDICAL_ATTEMPT_3) == (
        GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL,
    )
    assert classify_grounding_output(STOCK_ATTEMPT_3) == (
        GroundingViolation.FUTURE_STOCK_CHECK,
    )


@pytest.mark.parametrize(
    "text",
    [
        "I can confirm availability: 7 units are currently in stock.",
        "I can confirm AX-E1 is currently in stock.",
        "I can confirm that 7 AX-E1 units are currently in stock.",
    ],
)
def test_present_stock_confirmation_requires_current_turn_inventory_evidence(
    text: str,
) -> None:
    assert classify_grounding_output(text) == (GroundingViolation.FUTURE_STOCK_CHECK,)
    assert classify_grounding_output(text, inventory_confirmed=True) == ()

    rejected = enforce_grounding_output(text, language="en")
    confirmed = enforce_grounding_output(
        text,
        language="en",
        inventory_confirmed=True,
    )
    assert rejected.action is GroundingOutputAction.REPLACED
    assert "unconfirmed" in rejected.text.casefold()
    assert confirmed.action is GroundingOutputAction.UNCHANGED
    assert confirmed.text == text


def test_confirmed_present_stock_does_not_authorize_later_future_check() -> None:
    text = (
        "I can confirm availability: 7 units are currently in stock, and I "
        "will check inventory again later."
    )

    assert classify_grounding_output(text, inventory_confirmed=True) == (
        GroundingViolation.FUTURE_STOCK_CHECK,
    )
    result = enforce_grounding_output(
        text,
        language="en",
        inventory_confirmed=True,
    )
    assert result.action is GroundingOutputAction.REPAIRED
    assert result.text == "I can confirm availability: 7 units are currently in stock"
    assert "will check" not in result.text.casefold()


def test_mixed_stock_and_delivery_check_is_unsafe_but_delivery_only_is_safe() -> None:
    mixed = "Our inventory team will check stock and delivery and get back to you."
    delivery_only = (
        "Current stock is unconfirmed. Our inventory team will check delivery "
        "and get back to you."
    )

    assert classify_grounding_output(mixed) == (GroundingViolation.FUTURE_STOCK_CHECK,)
    assert classify_grounding_output(delivery_only) == ()


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        (
            (
                "Current stock is unconfirmed. Our inventory team will check "
                "availability and get back to you."
            ),
            GroundingViolation.FUTURE_STOCK_CHECK,
        ),
        (
            (
                "I can't confirm it reduces back pain. Visit our showroom to "
                "experience the AX-E1 in person."
            ),
            GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL,
        ),
    ],
)
def test_classify_grounding_output_covers_review_regressions(
    text: str,
    violation: GroundingViolation,
) -> None:
    assert classify_grounding_output(text) == (violation,)


@pytest.mark.parametrize(
    "text",
    [
        ("You're welcome to visit our UAE showroom to experience our product quality."),
        "I can't confirm that a specific chair will be available to try.",
        "There is no evidence that this chair will reduce back pain.",
        "Samples may be arranged depending on your project requirements.",
        "Current AX-E1 stock is unconfirmed because no inventory result is available.",
        "Zoho confirmed that 7 AX-E1 units are currently in stock.",
        'The customer asked, "Can your team check stock and get back to me?"',
        (
            "Current stock is unconfirmed. Our team will check the workstation "
            "dimensions and get back to you."
        ),
        (
            "Current stock is unconfirmed. Our inventory team will check the "
            "colour and get back to you."
        ),
        "Our manager will review the quotation and contact you.",
        "يمكنك زيارة معرضنا لتجربة جودة منتجاتنا.",
        "لا أستطيع تأكيد توفر كرسي محدد لتجربته في المعرض.",
        "المخزون الحالي غير مؤكد لعدم توفر نتيجة من نظام المخزون.",
        "أكد نظام المخزون توفر 7 وحدات من AX-E1 حاليًا.",
    ],
)
def test_classify_grounding_output_preserves_safe_controls(text: str) -> None:
    assert classify_grounding_output(text) == ()
    result = enforce_grounding_output(text, language="en")
    assert result.text == text
    assert result.action is GroundingOutputAction.UNCHANGED


@pytest.mark.parametrize(
    ("text", "violation"),
    [
        (
            "يمكنك زيارة معرضنا في الإمارات لتجربة كرسي Nova شخصيًا.",
            GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL,
        ),
        (
            (
                "المخزون الحالي غير مؤكد. يمكنني أن أطلب من فريقنا التحقق "
                "والرد عليك لاحقًا."
            ),
            GroundingViolation.FUTURE_STOCK_CHECK,
        ),
    ],
)
def test_classify_grounding_output_detects_arabic_violations(
    text: str,
    violation: GroundingViolation,
) -> None:
    assert classify_grounding_output(text) == (violation,)


def test_enforce_grounding_output_repairs_exact_attempt_3_answers() -> None:
    medical = enforce_grounding_output(MEDICAL_ATTEMPT_3, language="en")
    stock = enforce_grounding_output(STOCK_ATTEMPT_3, language="en")

    assert medical.action is GroundingOutputAction.REPAIRED
    assert medical.violations == (GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL,)
    assert "can't confirm that it will reduce back pain" in medical.text
    assert "experience the chair" not in medical.text.casefold()

    assert stock.action is GroundingOutputAction.REPAIRED
    assert stock.violations == (GroundingViolation.FUTURE_STOCK_CHECK,)
    assert "unable to confirm its current stock status" in stock.text
    assert "arrange for our team" not in stock.text.casefold()
    assert "get back to you" not in stock.text.casefold()


def test_enforce_grounding_output_uses_localized_fallback_for_single_unsafe_sentence() -> (
    None
):
    english = enforce_grounding_output(
        "Visit our showroom to try the Nova Task chair.",
        language="en",
    )
    arabic = enforce_grounding_output(
        "يمكنني أن أطلب من فريقنا التحقق من المخزون والرد عليك لاحقًا.",
        language="ar",
    )

    assert english.action is GroundingOutputAction.REPLACED
    assert "specific product" in english.text.casefold()
    assert classify_grounding_output(english.text) == ()
    assert arabic.action is GroundingOutputAction.REPLACED
    assert "المخزون" in arabic.text
    assert classify_grounding_output(arabic.text) == ()
