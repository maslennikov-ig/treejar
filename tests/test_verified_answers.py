from __future__ import annotations

from src.llm.verified_answers import (
    classify_product_match,
    evaluate_verified_answer_policy,
    is_quote_or_proposal_request,
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
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True


def test_policy_does_not_handoff_commercial_offer_request() -> None:
    decision = evaluate_verified_answer_policy(
        query="Make a commercial offer for me.",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.faq_support == "missing"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_does_not_handoff_invoice_request_without_payment_terms() -> None:
    decision = evaluate_verified_answer_policy(
        query="Please issue a proforma invoice for these items.",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.faq_support == "missing"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_sales_order_is_quotation_like_request() -> None:
    assert is_quote_or_proposal_request(
        "give me please sales order on SKYLAND NOVO 1800 - 1 pcs"
    )


def test_policy_does_not_handoff_business_proposal_request() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "What other questions do I need to answer for you to create "
            "a business proposal for me?"
        ),
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.faq_support == "missing"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


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


def test_policy_routes_office_workspace_need_to_product_path() -> None:
    decision = evaluate_verified_answer_policy(
        query="I need few work stations for my new office space in business bay dubai",
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_routes_brand_quantity_selection_to_product_path() -> None:
    for query in (
        "2 Skyland Novo and 2xten",
        "I need 2 trend mobile and 2 Skyland Novo 2400",
    ):
        decision = evaluate_verified_answer_policy(query=query, faq_context=[])

        assert decision.question_class == "product"
        assert decision.policy_action == "allow"
        assert decision.requires_manager_handoff is False


def test_policy_routes_generic_sku_quantity_selection_to_product_path() -> None:
    decision = evaluate_verified_answer_policy(
        query="I need 6 CH 616",
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_keeps_company_office_location_question_on_service_path() -> None:
    decision = evaluate_verified_answer_policy(
        query="Where is your office in Dubai?",
        faq_context=[],
    )

    assert decision.question_class != "product"
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True


def test_policy_treats_plain_greeting_as_safe_non_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="Добрый день",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "greeting"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_greeting_with_filler_tail_as_assist_opener_clarify() -> None:
    decision = evaluate_verified_answer_policy(
        query="Добрый день, подскажите",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "assist_opener"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "clarify"
    assert decision.requires_manager_handoff is False


def test_policy_treats_common_arabic_greeting_variant_as_safe_non_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="سلام عليكم",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "greeting"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_gratitude_as_social_allow() -> None:
    decision = evaluate_verified_answer_policy(
        query="Спасибо",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "gratitude"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_goodbye_as_social_allow() -> None:
    decision = evaluate_verified_answer_policy(
        query="До свидания",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "goodbye"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_assist_opener_as_social_clarify() -> None:
    decision = evaluate_verified_answer_policy(
        query="I need help",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "assist_opener"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "clarify"
    assert decision.requires_manager_handoff is False


def test_policy_treats_short_benign_no_match_as_clarify() -> None:
    decision = evaluate_verified_answer_policy(
        query="Need advice",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.social_intent is None
    assert decision.faq_support == "missing"
    assert decision.policy_action == "clarify"
    assert decision.requires_manager_handoff is False


def test_policy_routes_price_objection_to_sales_fallback() -> None:
    decision = evaluate_verified_answer_policy(
        query="This is too expensive. A competitor says they can do cheaper.",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False
    assert decision.sales_fallback_intent == "price_objection"


def test_policy_routes_product_price_objection_to_sales_fallback() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "The chairs feel too expensive, I found a cheaper option from "
            "another supplier. Why should I buy from Treejar?"
        ),
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False
    assert decision.sales_fallback_intent == "price_objection"


def test_policy_routes_retention_dropoff_to_sales_fallback() -> None:
    decision = evaluate_verified_answer_policy(
        query="Actually I don't think we need this anymore.",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False
    assert decision.sales_fallback_intent == "retention"


def test_policy_routes_product_retention_dropoff_to_sales_fallback() -> None:
    decision = evaluate_verified_answer_policy(
        query="We do not need the office furniture anymore for now. Maybe later.",
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False
    assert decision.sales_fallback_intent == "retention"


def test_policy_routes_known_off_catalog_request_to_sales_fallback() -> None:
    decision = evaluate_verified_answer_policy(
        query="Do you sell helicopter spare parts or gaming laptops?",
        faq_context=[],
    )

    assert decision.question_class == "service_low_risk"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False
    assert decision.sales_fallback_intent == "off_catalog"


def test_policy_keeps_payment_terms_on_manager_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="Can you do net 30 payment terms and a 20% discount?",
        faq_context=[],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True
    assert decision.sales_fallback_intent is None


def test_policy_keeps_payment_terms_in_proposal_on_manager_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="Please include net 30 payment terms in the business proposal.",
        faq_context=[],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True
    assert decision.sales_fallback_intent is None


def test_policy_keeps_payment_terms_in_invoice_on_manager_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="Please include net 30 payment terms in the proforma invoice.",
        faq_context=[],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True
    assert decision.sales_fallback_intent is None


def test_policy_routes_greeting_with_real_question_into_service_policy() -> None:
    decision = evaluate_verified_answer_policy(
        query="Добрый день, есть доставка в Дубай?",
        faq_context=[],
    )

    assert decision.question_class == "service_high_risk"
    assert decision.social_intent is None
    assert decision.faq_support == "missing"
    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True


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
