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
        "I can confirm availability: AX-E1 is currently in stock.",
        "I can confirm AX-E1 is currently in stock.",
        "I can confirm that 7 AX-E1 units are currently in stock.",
        "I can confirm that AX-E1 has 7 units currently in stock.",
        "I can confirm AX-E1 is available.",
        "I can confirm AX-E1 is currently out of stock.",
        "I can confirm AX-E1 is not currently in stock.",
        "I can confirm AX-E1 is not in stock.",
        "I can confirm AX-E1 is currently not in stock.",
        "I can confirm AX-E1 is not available.",
        "I can confirm AX-E1 isn't in stock.",
        "I can confirm AX-E1 isn’t available.",
        "I can confirm that 7 AX-E1 units aren't available.",
    ],
)
def test_present_stock_confirmation_requires_current_turn_inventory_evidence(
    text: str,
) -> None:
    assert classify_grounding_output(text) == (
        GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION,
    )
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


@pytest.mark.parametrize(
    "text",
    [
        "Current stock is unconfirmed. AX-E1 is available.",
        "Current stock is unconfirmed. AX-E1 is unavailable.",
        "Current stock is unconfirmed. AX-E1 is out of stock.",
        "Current stock is unconfirmed. AX-E1 is currently in stock.",
        "Current stock is unconfirmed, but AX-E1 is available.",
        "For AX-E1, AX-E1 is out of stock.",
        "Current stock is unconfirmed. AX-E1 isn't available.",
        "Current stock is unconfirmed. AX-E1 isn’t in stock.",
        "Current stock is unconfirmed — AX-E1 is available.",
        "Current stock is unconfirmed – AX-E1 is available.",
        "Current stock is unconfirmed\nAX-E1 is available.",
        "Current stock is unconfirmed:\n- AX-E1 is available.",
        "Current stock is unconfirmed:\n• AX-E1 is available.",
        "Treejar's note: AX-E1 is available.",
    ],
)
def test_direct_sku_stock_assertion_requires_current_turn_inventory_evidence(
    text: str,
) -> None:
    assert classify_grounding_output(text) == (
        GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION,
    )
    assert classify_grounding_output(text, inventory_confirmed=True) == ()

    rejected = enforce_grounding_output(text, language="en")
    confirmed = enforce_grounding_output(
        text,
        language="en",
        inventory_confirmed=True,
    )
    assert rejected.action in {
        GroundingOutputAction.REPAIRED,
        GroundingOutputAction.REPLACED,
    }
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


def test_unverified_present_stock_and_future_check_remain_distinct() -> None:
    text = (
        "I can confirm AX-E1 is currently in stock, and I will check inventory "
        "again later."
    )

    assert classify_grounding_output(text) == (
        GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION,
        GroundingViolation.FUTURE_STOCK_CHECK,
    )
    assert classify_grounding_output(text, inventory_confirmed=True) == (
        GroundingViolation.FUTURE_STOCK_CHECK,
    )


@pytest.mark.parametrize(
    "text",
    [
        "Our team will check stock and get back to you.",
        "Our team will check inventory and get back to you.",
        "Our team will check availability and get back to you.",
        "Our team will check whether AX-E1 is available and get back to you.",
        "Our team will check whether AX-E1 is unavailable and get back to you.",
        "Our team will check whether AX-E1 is out of stock and get back to you.",
        "Our inventory team will check stock and delivery and get back to you.",
    ],
)
def test_future_check_with_strong_stock_context_is_unsafe(text: str) -> None:
    assert classify_grounding_output(text) == (GroundingViolation.FUTURE_STOCK_CHECK,)


@pytest.mark.parametrize(
    "check_object",
    [
        "dimension",
        "dimensions",
        "measurement",
        "measurements",
        "size",
        "sizes",
        "colour",
        "colours",
        "color",
        "colors",
        "delivery timing",
    ],
)
def test_delivery_only_check_is_safe_even_with_weak_warehouse_context(
    check_object: str,
) -> None:
    text = f"Our team will check {check_object} with the warehouse and get back to you."
    assert classify_grounding_output(text) == ()


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
        "The product is available.",
        "AXE1 is available.",
        "We discussed whether AX-E1 is available.",
        "If AX-E1 is available, a current inventory result is still required.",
        "When AX-E1 is available, contact me.",
        "AX-E1 stock is unconfirmed.",
        "Treejar's AX-E1 catalog entry is documented.",
        "Current stock is unconfirmed. The note says 'AX-E1 is available.'",
        "Current stock is unconfirmed. The note says ‘AX-E1 is available.’",
        "Current stock is unconfirmed. The note says 'AX-E1 is currently in stock.'",
        "Current stock is unconfirmed. Determine whether:\n- AX-E1 is available.",
        "Current stock is unconfirmed. Check if:\n• AX-E1 is available.",
        "Current stock is unconfirmed. Tell me when:\n- AX-E1 is available.",
        (
            "Current stock is unconfirmed. The note says, 'Our team will check "
            "stock and get back to you.'"
        ),
        (
            "Current stock is unconfirmed. The note says, ‘Our team will check "
            "stock and get back to you.’"
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
