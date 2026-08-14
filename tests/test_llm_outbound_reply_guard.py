import pytest

from src.llm.outbound_reply_guard import finalize_customer_reply_text


def _question_marks(text: str) -> int:
    return text.count("?") + text.count("؟")


def test_english_reply_drops_arabic_narrative_at_the_send_boundary() -> None:
    guarded = finalize_customer_reply_text(
        "I can help compare suitable office options. "
        "هل تريد كراسي أم مكاتب؟ ما نوع المساحة التي تجهزها؟ "
        "And how should I address you?",
        language="en",
    )

    assert "I can help compare suitable office options." in guarded
    assert not any("\u0600" <= character <= "\u06ff" for character in guarded)
    assert _question_marks(guarded) == 1


def test_arabic_reply_drops_english_narrative_at_the_send_boundary() -> None:
    guarded = finalize_customer_reply_text(
        "يمكنني مساعدتك في مقارنة الخيارات المناسبة. "
        "Would you prefer chairs or desks? وكيف أخاطبك؟",
        language="ar",
    )

    assert "يمكنني مساعدتك في مقارنة الخيارات المناسبة." in guarded
    assert "Would you prefer" not in guarded
    assert _question_marks(guarded) == 1


def test_wholly_wrong_language_uses_a_localized_safe_fallback() -> None:
    guarded = finalize_customer_reply_text(
        "هل تريد كراسي أم مكاتب؟",
        language="en",
    )

    assert not any("\u0600" <= character <= "\u06ff" for character in guarded)
    assert "English" in guarded
    assert _question_marks(guarded) == 1


def test_mixed_sentence_cannot_evade_the_language_ratio_gate() -> None:
    guarded = finalize_customer_reply_text(
        "English answer مرحبا بكم",
        language="en",
    )

    assert not any("\u0600" <= character <= "\u06ff" for character in guarded)
    assert "English" in guarded


def test_first_turn_name_ask_shares_the_existing_question_mark() -> None:
    guarded = finalize_customer_reply_text(
        "What kind of space are you furnishing? And how should I address you?",
        language="en",
    )

    assert "What kind of space are you furnishing" in guarded
    assert "how should I address you" in guarded
    assert _question_marks(guarded) == 1


def test_already_safe_reply_is_preserved_exactly() -> None:
    original = "The chair is available.  \n\n"

    assert finalize_customer_reply_text(original, language="en") == original


# `tj-l6pw`. The first version of this guard asked an Arabic reply to be 35%
# Arabic letters and replaced the whole reply with a fixed sentence when it was
# not. Our catalog is named in Latin script, so that test fails true Arabic
# answers and the customer loses the answer instead of receiving it.
@pytest.mark.parametrize(
    "reply",
    [
        "نعم. Ergonomic Mesh Chair و Executive Leather Chair متوفران.",
        "تفضل عرض السعر: https://noor.starec.ai/api/v1/public-media/quote-8842.pdf",
        (
            "أهلاً! إليك الخيارات: SKYLAND NOVO 1200 Executive Desk - 1,250 AED, "
            "ERGOMAX Mesh Task Chair Pro - 490 AED."
        ),
        "AED 1,250",
        "👍",
    ],
)
def test_an_arabic_reply_that_names_our_catalog_reaches_the_customer(
    reply: str,
) -> None:
    assert finalize_customer_reply_text(reply, language="ar") == reply


def test_an_english_reply_to_an_arabic_customer_still_falls_back() -> None:
    guarded = finalize_customer_reply_text(
        "Would you prefer chairs or desks? Let me know what you need today.",
        language="ar",
    )

    assert "أريد أن أجيبك بدقة بالعربية" in guarded
    assert "Would you prefer" not in guarded


def test_one_arabic_sentence_costs_only_that_sentence() -> None:
    guarded = finalize_customer_reply_text(
        "Sure, I can send the full list. مرحبا بك في تريجار اليوم",
        language="en",
    )

    assert guarded == "Sure, I can send the full list."


# `tj-yiiq`. On dialog 293 the sentence the language guard removed was the only
# place the reply asked the customer anything, and the round scored rule 5 at
# zero for it.
def test_a_first_turn_that_loses_its_only_question_gets_one_back() -> None:
    guarded = finalize_customer_reply_text(
        "Hello, I'm Noor from Treejar. We supply office furniture across the UAE. "
        "هل تريد كراسي أم مكاتب؟ And how should I address you?",
        language="en",
    )

    assert "What are you setting up" in guarded
    assert not any("؀" <= character <= "ۿ" for character in guarded)
    assert _question_marks(guarded) == 1


def test_the_arabic_first_turn_gets_its_question_back_in_arabic() -> None:
    guarded = finalize_customer_reply_text(
        "مرحبًا، أنا Noor من Treejar. Would you prefer chairs or desks? وكيف أخاطبك؟",
        language="ar",
    )

    assert "ما الذي تجهّزه" in guarded
    assert "Would you prefer" not in guarded
    assert _question_marks(guarded) == 1


def test_a_later_turn_is_never_handed_a_discovery_question() -> None:
    guarded = finalize_customer_reply_text(
        "The chair is in stock. هل تريد التوصيل؟",
        language="en",
    )

    assert guarded == "The chair is in stock."
