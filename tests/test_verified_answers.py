from __future__ import annotations

from src.llm.verified_answers import (
    classify_product_match,
    evaluate_verified_answer_policy,
)


def test_policy_marks_delivery_terms_as_verified_when_faq_covers_them() -> None:
    decision = evaluate_verified_answer_policy(
        query="What are your delivery times in Dubai?",
        faq_context=[
            {
                "title": "Delivery policy",
                "content": "Q: What are your delivery times?\nA: Standard delivery takes 3-5 business days in Dubai and 5-7 business days across UAE.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "verified"
    assert decision.requires_manager_handoff is False
    assert decision.confirmed_fact is not None
    assert "3-5 business days" in decision.confirmed_fact


def test_policy_marks_specific_installation_slot_as_partial_when_only_general_fact_exists() -> (
    None
):
    decision = evaluate_verified_answer_policy(
        query="Can you install in Abu Dhabi next Tuesday?",
        faq_context=[
            {
                "title": "Installation coverage",
                "content": "Q: Do you offer installation?\nA: We provide delivery and installation across UAE.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "partial"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact == "We provide delivery and installation across UAE."


def test_policy_marks_high_risk_question_as_missing_without_matching_faq() -> None:
    decision = evaluate_verified_answer_policy(
        query="What warranty do you offer on workstations?",
        faq_context=[
            {
                "title": "Showroom",
                "content": "Q: Where are you located?\nA: Our showroom is in Dubai.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "missing"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact is None


def test_policy_marks_external_delivery_request_as_partial_for_uae_only_faq() -> None:
    decision = evaluate_verified_answer_policy(
        query="Do you deliver to Saudi Arabia?",
        faq_context=[
            {
                "title": "Delivery coverage",
                "content": "Q: Where do you deliver?\nA: We provide delivery and installation across UAE.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "partial"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact == "We provide delivery and installation across UAE."


def test_policy_marks_external_installation_request_as_partial_for_uae_only_faq() -> (
    None
):
    decision = evaluate_verified_answer_policy(
        query="Can you install in Qatar?",
        faq_context=[
            {
                "title": "Installation coverage",
                "content": "Q: Do you offer installation?\nA: We provide delivery and installation across UAE.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "partial"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact == "We provide delivery and installation across UAE."


def test_policy_marks_net_30_request_as_partial_when_faq_only_lists_payment_methods() -> (
    None
):
    decision = evaluate_verified_answer_policy(
        query="Can you do net 30?",
        faq_context=[
            {
                "title": "Payment methods",
                "content": "Q: How can I pay?\nA: We accept bank transfer and card payment.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "partial"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact == "We accept bank transfer and card payment."


def test_policy_marks_deferred_payment_request_as_partial_when_faq_only_lists_payment_methods() -> (
    None
):
    decision = evaluate_verified_answer_policy(
        query="Do you offer deferred payment for this order?",
        faq_context=[
            {
                "title": "Payment methods",
                "content": "Q: How can I pay?\nA: We accept bank transfer and card payment.",
            }
        ],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.faq_support == "partial"
    assert decision.requires_manager_handoff is True
    assert decision.confirmed_fact == "We accept bank transfer and card payment."


def test_policy_marks_low_risk_missing_without_inventing_support() -> None:
    decision = evaluate_verified_answer_policy(
        query="Do you have a showroom?",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.faq_support == "missing"
    assert decision.requires_manager_handoff is True


def test_policy_keeps_product_questions_on_catalog_path() -> None:
    decision = evaluate_verified_answer_policy(
        query="Tell me about your acoustic pods",
        faq_context=[
            {
                "title": "Delivery coverage",
                "content": "Q: Delivery areas\nA: We provide delivery across UAE.",
            }
        ],
    )

    assert decision.question_class == "product"
    assert decision.faq_support == "missing"
    assert decision.requires_manager_handoff is False


def test_product_match_marks_nearby_alternatives_when_exact_term_is_missing() -> None:
    match = classify_product_match(
        query="Tell me about your acoustic pods",
        candidates=[
            "Solo Privacy Booth Compact acoustic booth for calls and focused work",
            "Meeting Booth Acoustic meeting booth for small teams",
        ],
    )

    assert match == "nearby"


def test_product_match_marks_exact_when_query_terms_are_present() -> None:
    match = classify_product_match(
        query="Tell me about your acoustic pods",
        candidates=[
            "Acoustic Pod Four-person acoustic pod for meetings and private calls",
        ],
    )

    assert match == "exact"
