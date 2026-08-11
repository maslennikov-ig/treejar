from __future__ import annotations

import pytest

from src.llm import grounding_output
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


def test_visible_grounding_text_masks_quotes_but_preserves_word_apostrophes() -> None:
    text = (
        "Treejar's note says 'AX-E1 is currently in stock', "
        "but AX-E1 isn't otherwise asserted."
    )

    visible = grounding_output.visible_grounding_text(text)

    assert len(visible) == len(text)
    assert "AX-E1 is currently in stock" not in visible
    assert "Treejar's" in visible
    assert "isn't" in visible


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
        "We can buy your used office desks.",
        "We can help you resell customer-owned chairs.",
        "We can assess and value the conference table you already own.",
        (
            "Do you want to sell your own desk? I can help clarify the resale "
            "options—please share its condition and location."
        ),
    ],
)
def test_customer_owned_furniture_service_promises_require_confirmation(
    text: str,
) -> None:
    assert [item.value for item in classify_grounding_output(text)] == [
        "unverified_customer_owned_furniture_service"
    ]


@pytest.mark.parametrize(
    "text",
    [
        (
            "We don't have confirmed information that we buy or resell "
            "customer-owned furniture."
        ),
        "I can't confirm a customer-owned furniture buying or resale service.",
        "Do you mean you'd like to sell a desk you already own?",
        "We can sell furniture for your office.",
        "The note says 'We can buy your used desk', but that service is unconfirmed.",
    ],
)
def test_customer_owned_furniture_service_controls_stay_safe(text: str) -> None:
    assert classify_grounding_output(text) == ()


def test_customer_owned_furniture_service_repair_keeps_the_safe_question() -> None:
    result = enforce_grounding_output(
        "We can help you sell your existing desk. Are you looking for a replacement?",
        language="en",
    )

    assert result.action is GroundingOutputAction.REPAIRED
    assert [item.value for item in result.violations] == [
        "unverified_customer_owned_furniture_service"
    ]
    assert result.text == "Are you looking for a replacement?"


def test_customer_owned_furniture_service_repair_drops_unsupported_intake() -> None:
    result = enforce_grounding_output(
        (
            "Do you want to sell your own desk? Please share photos, dimensions, "
            "condition, location, and your asking price."
        ),
        language="en",
    )

    assert result.action is GroundingOutputAction.REPAIRED
    assert [item.value for item in result.violations] == [
        "unverified_customer_owned_furniture_service"
    ]
    assert result.text == "Do you want to sell your own desk?"


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


# --- the invented price, tj-vz7o.10.1 -------------------------------------
#
# Measured on 2026-08-10 over 20 real customer openings: a bare "Good
# Afternoon" retrieved nothing from the catalog, and the reply came back with
# "Our ergonomic office chairs start from AED 500 in our catalog" -- in the
# same message as our own promise to quote only confirmed prices. The three
# older violations are text-only patterns, so none of them could see that no
# row existed behind the figure.

UNGROUNDED_OPENING = (
    "Hello, I'm Noor from Treejar. We supply office furniture across the UAE, "
    "and I quote from our own catalog with confirmed prices and stock.\n\n"
    "Good afternoon! Welcome to Treejar.\n\n"
    "Our ergonomic office chairs start from AED 500 in our catalog. Are you "
    "furnishing a new office or upgrading an existing workspace?"
)


def test_a_price_with_no_verified_row_behind_it_is_removed() -> None:
    result = enforce_grounding_output(
        UNGROUNDED_OPENING,
        language="en",
        grounded_amounts=[],
    )

    assert result.action is GroundingOutputAction.REPAIRED
    assert result.violations == (GroundingViolation.UNVERIFIED_PRICE,)
    assert "AED 500" not in result.text
    assert "Are you furnishing a new office" in result.text


def test_removing_a_sentence_does_not_flatten_the_paragraphs() -> None:
    """The repair used to re-join the whole reply with single spaces.

    That was invisible while the repair path almost never fired on an opening.
    The price violation fires there by design, and a three-paragraph WhatsApp
    greeting arriving as one wall of text is a defect of its own.
    """

    result = enforce_grounding_output(
        UNGROUNDED_OPENING,
        language="en",
        grounded_amounts=[],
    )

    assert result.text.count("\n\n") == 2
    assert "  " not in result.text


def test_a_price_that_is_on_a_verified_row_survives() -> None:
    text = "The XTEN-S workstation is AED 566.87 in the catalog."

    assert (
        enforce_grounding_output(text, language="en", grounded_amounts=[566.87]).action
        is GroundingOutputAction.UNCHANGED
    )


@pytest.mark.parametrize(
    ("grounded", "written"),
    [
        # One sum, four spellings. A guard that cannot see these are equal
        # reports defects that are not there, which is how the first automatic
        # pass of the 2026-08-10 round produced five false flags.
        (5000, "AED 5,000"),
        (5000.0, "AED 5000.00"),
        ("5000.000", "AED 5,000.0"),
        (566.87, "566.87 AED"),
    ],
)
def test_one_sum_spelled_four_ways_is_one_sum(grounded: object, written: str) -> None:
    result = enforce_grounding_output(
        f"That comes to {written}.",
        language="en",
        grounded_amounts=[grounded],
    )

    assert result.action is GroundingOutputAction.UNCHANGED


def test_the_customers_own_figure_read_back_is_not_our_invention() -> None:
    result = enforce_grounding_output(
        "Understood, a budget of AED 12,000 for the fit-out.",
        language="en",
        grounded_amounts=["12000"],
    )

    assert result.action is GroundingOutputAction.UNCHANGED


def test_only_money_counts_as_a_price() -> None:
    """Dimensions, quantities and lead times are not prices.

    Stripping a sentence for saying "2-3 days" would be a worse defect than
    the one this violation catches.
    """

    result = enforce_grounding_output(
        "The desk is 1200x600 mm and delivery takes 2-3 days for 7 units.",
        language="en",
        grounded_amounts=[],
    )

    assert result.action is GroundingOutputAction.UNCHANGED


def test_the_check_stays_off_when_nobody_offered_evidence() -> None:
    """`None` and an empty list mean opposite things, on purpose.

    `None` is "no caller looked", which is every non-selling call site and must
    not change their behaviour. `[]` is "we looked and found nothing", which is
    the case this violation exists for.
    """

    text = "Our chairs start from AED 500."

    assert (
        enforce_grounding_output(text, language="en").action
        is GroundingOutputAction.UNCHANGED
    )
    assert (
        enforce_grounding_output(text, language="en", grounded_amounts=[]).action
        is GroundingOutputAction.REPLACED
    )


def test_a_reply_that_is_only_an_invented_price_falls_back_in_both_languages() -> None:
    english = enforce_grounding_output(
        "Our chairs start from AED 500.", language="en", grounded_amounts=[]
    )
    arabic = enforce_grounding_output(
        "تبدأ كراسينا من 500 درهم.", language="ar", grounded_amounts=[]
    )

    assert english.action is GroundingOutputAction.REPLACED
    assert "only from our own catalog" in english.text
    assert classify_grounding_output(english.text, grounded_amounts=[]) == ()
    assert arabic.action is GroundingOutputAction.REPLACED
    assert "الكتالوج" in arabic.text
    assert classify_grounding_output(arabic.text, grounded_amounts=[]) == ()
