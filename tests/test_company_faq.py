from src.llm.company_faq import (
    APPROVED_FAQ_QUESTIONS,
    approved_faq_entries,
    grounded_faq_amounts,
    with_approved_faq,
)


def test_approved_faq_entries_load_only_the_owner_approved_questions() -> None:
    entries = approved_faq_entries()

    assert len(entries) == len(APPROVED_FAQ_QUESTIONS)
    titles = {entry["title"] for entry in entries}
    assert titles == {
        "What is your delivery timeline?",
        "Do you provide installation services?",
    }
    assert all("warranty" not in entry["content"].lower() for entry in entries)


def test_delivery_and_assembly_question_gets_the_faq_answer_without_rag() -> None:
    query = "Do you provide delivery and assembly in Dubai?"

    faq_context = with_approved_faq(query, [])

    contents = " ".join(item["content"] for item in faq_context)
    assert "2–3 business days" in contents
    assert "2–5 business days" in contents
    assert "Express delivery is not available" in contents
    assert "free delivery is not available" in contents
    assert "AED 50" in contents
    assert "AED 200" in contents
    assert "Sharjah" in contents
    assert "AED 130" in contents
    assert "AED 30 per item" in contents
    assert "Saudi Arabia, Oman and Qatar" in contents


def test_assemble_verb_and_followup_emirate_receive_approved_faq() -> None:
    assemble_ctx = with_approved_faq("How much to assemble 4 chairs?", [])
    assert any("AED 30 per item" in item["content"] for item in assemble_ctx)

    followup_ctx = with_approved_faq(
        "And what about Sharjah?",
        [],
        recent_history=["User: How much is delivery to Dubai?"],
    )
    assert any("Sharjah" in item["content"] for item in followup_ctx)

    # First-turn greeting mentioning Dubai without a delivery/assembly question stays empty.
    assert with_approved_faq("Good afternoon from Dubai", []) == []


def test_grounded_faq_amounts_covers_tariffs_and_item_assembly_math() -> None:
    query = "How much is delivery and assembly for 4 chairs in Dubai (order AED 1,500)?"
    faq_context = with_approved_faq(query, [])
    amounts = set(grounded_faq_amounts(query, faq_context, customer_amounts=("1,500",)))

    assert {30.0, 50.0, 100.0, 120.0, 220.0, 1600.0, 1720.0} <= amounts
    # Unrelated greeting with an unrequested KB row must not ground tariff numbers.
    assert grounded_faq_amounts("Good Afternoon", faq_context) == ()


def test_approved_faq_is_not_added_to_unrelated_or_duplicate_context() -> None:
    assert with_approved_faq("I need four office chairs", []) == []

    existing = [
        {
            "title": "Do you provide installation services?",
            "content": "Q: Do you provide installation services?\nA: Yes.",
        }
    ]
    merged = with_approved_faq("Can you install the desks?", existing)
    titles = [item["title"] for item in merged]
    assert titles.count("Do you provide installation services?") == 1
