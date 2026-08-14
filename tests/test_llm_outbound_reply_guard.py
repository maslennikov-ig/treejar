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
