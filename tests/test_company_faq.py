from src.llm.company_faq import (
    APPROVED_FAQ_QUESTIONS,
    approved_faq_entries,
    with_approved_faq,
)
from src.llm.verified_answers import evaluate_verified_answer_policy


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
    assert "delivery and installation services" in contents
    assert "within a few days" in contents
    decision = evaluate_verified_answer_policy(query, faq_context)
    # "in Dubai" reads as a location detail, so support is the general fact.
    assert decision.faq_support in {"verified", "partial"}
    assert decision.policy_action == "allow"
    assert not decision.requires_manager_handoff
    assert decision.confirmed_fact is not None
    assert "delivery and installation" in decision.confirmed_fact


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
