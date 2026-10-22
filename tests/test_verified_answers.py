from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.llm import verified_answers as verified_answers_module
from src.llm.verified_answers import (
    build_clarification_response,
    build_sales_fallback_response,
    build_service_handoff_response,
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


def test_customer_facing_verified_answer_builders_normalize_legacy_arabic_markers() -> (
    None
):
    decision = evaluate_verified_answer_policy(
        query="Can you deliver tomorrow?",
        faq_context=[],
    )

    handoff = build_service_handoff_response(decision, "العربية")
    fallback = build_sales_fallback_response("retention", "Arabic")
    clarification = build_clarification_response("arabic")

    assert "مديرنا" in handoff
    assert "لا مشكلة" in fallback
    assert "يمكنني المساعدة" in clarification


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

    # Missing FAQ support is still reported, so the runtime directives keep the
    # model inside the knowledge-base facts. What it no longer does is escalate:
    # asking a manager to confirm that Treejar has a showroom is the over-eager
    # handoff tj-rily removes.
    assert decision.question_class == "service_low_risk"
    assert decision.faq_support == "missing"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


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


def test_policy_routes_common_furniture_categories_to_product_path() -> None:
    for query in (
        "Hi, I need two wardrobes for my living room.",
        "I want two beds for kids.",
    ):
        decision = evaluate_verified_answer_policy(query=query, faq_context=[])

        assert decision.question_class == "product"
        assert decision.policy_action == "allow"
        assert decision.requires_manager_handoff is False


def test_policy_treats_furniture_use_case_context_as_clarify_without_handoff() -> None:
    for query in ("This is for my restaurant.", "This is for my restaurant?"):
        decision = evaluate_verified_answer_policy(query=query, faq_context=[])

        assert decision.question_class == "service_low_risk"
        assert decision.policy_action == "clarify"
        assert decision.requires_manager_handoff is False


def test_policy_routes_contextual_catalog_discovery_question_to_product_path() -> None:
    decision = evaluate_verified_answer_policy(
        query="Do you have options for my restaurant?",
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
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
    assert "showroom" in decision.matched_topics
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_plain_greeting_as_safe_non_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="Good afternoon",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "greeting"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_greeting_with_filler_tail_as_assist_opener_clarify() -> None:
    decision = evaluate_verified_answer_policy(
        query="Good afternoon, help please",
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
        query="Thank you",
        faq_context=[],
    )

    assert decision.question_class == "social"
    assert decision.social_intent == "gratitude"
    assert decision.faq_support == "verified"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_treats_goodbye_as_social_allow() -> None:
    decision = evaluate_verified_answer_policy(
        query="Goodbye",
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


def test_policy_treats_preference_statement_as_clarify_without_handoff() -> None:
    decision = evaluate_verified_answer_policy(
        query="I prefer more open for team",
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


def test_policy_keeps_internal_cheaper_configuration_on_product_path() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "That configuration is too expensive. Give me a cheaper option and "
            "one relevant cross-sell while keeping the total under AED 7,000. "
            "Do not prepare a quotation."
        ),
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.sales_fallback_intent is None
    assert not is_quote_or_proposal_request(
        "Give me a cheaper option, but do not prepare a quotation."
    )


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "Show a private LUMA four-person workstation.",
            "NOVO four-person workstation with privacy panels.",
        ),
        (
            "Show a private NOVO four-person workstation in black.",
            "NOVO four-person workstation with privacy panels in white.",
        ),
        (
            "Show a private COMP four-person workstation.",
            "NOVO four-person workstation with privacy panels.",
        ),
        (
            "Show a private four-person workstation in sonoma finish.",
            "Four-person workstation with privacy panels in walnut finish.",
        ),
        (
            "Show a private COMP-4 four-person workstation.",
            "COMP-5 four-person workstation with privacy panels.",
        ),
        (
            "Show a private COMP-4 four-person workstation.",
            "COMP four-person workstation with privacy panels.",
        ),
        (
            "Show a private COMP-4 four-person workstation.",
            "COMP-40 four-person workstation with privacy panels.",
        ),
        (
            "Show a private Comp-4 four-person workstation.",
            "NOVO four-person workstation with privacy panels.",
        ),
    ],
)
def test_structured_workstation_match_requires_explicit_discriminators(
    query: str,
    candidate: str,
) -> None:
    assert classify_product_match(query, [candidate]) != "exact"


def test_dedicated_alone_is_not_a_structured_privacy_constraint() -> None:
    assert not verified_answers_module._matches_structured_workstation_constraints(
        "dedicated four-person workstation",
        "dedicated four-person workstation",
    )


def test_structured_workstation_match_accepts_matching_brand_and_finish() -> None:
    assert (
        classify_product_match(
            "Show a private LUMA four-person workstation in black.",
            ["LUMA black four-person workstation with privacy panels."],
        )
        == "exact"
    )


def test_structured_unknown_discriminators_match_when_candidate_confirms_them() -> None:
    assert verified_answers_module._matches_structured_workstation_constraints(
        "Show a private COMP-4 four-person workstation in sonoma finish.",
        "COMP-4 four-person workstation with privacy panels in sonoma finish.",
    )


def test_individual_privacy_word_is_not_a_product_discriminator() -> None:
    assert (
        classify_product_match(
            "Show a private four-person workstation with individual privacy panels.",
            ["Four-person workstation with privacy panels."],
        )
        == "exact"
    )


def test_product_match_binds_generic_accessory_to_storage_family() -> None:
    candidate = "Mobile Storage Pedestal. Compact office storage cabinet."

    assert classify_product_match("office accessories", [candidate]) == "nearby"
    assert classify_product_match("office lighting add-on", [candidate]) == "missing"


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
        query="Good afternoon, is there delivery to Dubai?",
        faq_context=[],
    )

    # The point of this one is the routing: a greeting carrying a real question
    # is not social. The question behind it reaches the model rather than a
    # manager.
    assert decision.question_class == "service_high_risk"
    assert decision.social_intent is None
    assert decision.faq_support == "missing"
    assert decision.policy_action == "allow"
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


def test_product_match_accepts_verified_capacity_and_privacy_constraints() -> None:
    match = classify_product_match(
        query=(
            "We need a private desk arrangement for four people with individual "
            "privacy panels rather than an open bench."
        ),
        candidates=[
            (
                "SKYLAND LUMA Four Person Workstation. Screen dividers for each "
                "user and a dedicated personal workspace."
            ),
        ],
    )

    assert match == "exact"


def test_policy_routes_arabic_workstation_discovery_to_catalog() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "نحتاج إلى محطات عمل خاصة وكراسي مريحة لستة موظفين في دبي، "
            "والميزانية ١٠٬٠٠٠ درهم. ماذا تقترحين؟"
        ),
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_policy_routes_furniture_no_match_request_to_catalog() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "Do you sell laboratory fume hoods and chemical-resistant lab "
            "benches for a research facility?"
        ),
        faq_context=[],
    )

    assert decision.question_class == "product"
    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


# tj-rily: the handoff decision used to fire on any service question the FAQ did
# not already answer. These pin the narrowed rule — escalate only what needs
# authority the assistant does not have.


def test_capability_question_inside_the_service_area_reaches_the_model() -> None:
    decision = evaluate_verified_answer_policy(
        query="Before we continue, do you provide delivery and assembly in Dubai?",
        faq_context=[],
    )

    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_saved_context_summary_request_reaches_the_model() -> None:
    decision = evaluate_verified_answer_policy(
        query="Summarize the updated requirement and tell me the best next step.",
        faq_context=[],
    )

    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_saved_detail_recall_question_reaches_the_model() -> None:
    decision = evaluate_verified_answer_policy(
        query=(
            "What details have you saved about my company, delivery address, "
            "products, quantities, delivery timing, and assembly?"
        ),
        faq_context=[],
    )

    assert decision.policy_action == "allow"
    assert decision.requires_manager_handoff is False


def test_a_bare_next_is_not_a_scheduling_commitment() -> None:
    assert not verified_answers_module.requires_manager_commitment(
        "Tell me the best next step."
    )
    assert verified_answers_module.requires_manager_commitment(
        "Can you install it next Tuesday?"
    )


@pytest.mark.parametrize(
    "query",
    [
        "Can I get a 20% discount on this order?",
        "Do you offer net 30 payment terms?",
        "We need deferred payment for this project, is that possible?",
    ],
)
def test_manager_required_capabilities_still_escalate(query: str) -> None:
    decision = evaluate_verified_answer_policy(query=query, faq_context=[])

    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True


@pytest.mark.parametrize(
    "query",
    [
        "Can you deliver and install everything next Thursday morning?",
        "Do you deliver to Saudi Arabia?",
        "I need the exact installation slot confirmed for our office.",
    ],
)
def test_commitments_the_assistant_cannot_confirm_still_escalate(query: str) -> None:
    decision = evaluate_verified_answer_policy(query=query, faq_context=[])

    assert decision.policy_action == "handoff"
    assert decision.requires_manager_handoff is True


def test_partial_faq_support_escalates_only_for_a_real_commitment() -> None:
    coverage = [
        {
            "title": "Installation coverage",
            "content": (
                "Q: Do you offer installation?\n"
                "A: We provide delivery and installation for office projects."
            ),
        }
    ]

    scheduled = evaluate_verified_answer_policy(
        query="Can you install in Abu Dhabi next Tuesday?",
        faq_context=coverage,
    )
    capability = evaluate_verified_answer_policy(
        query="Do you provide delivery and assembly in Dubai?",
        faq_context=coverage,
    )

    assert scheduled.faq_support == "partial"
    assert scheduled.policy_action == "handoff"
    assert capability.policy_action == "allow"
    assert capability.requires_manager_handoff is False


# tj-uz6j.2: production 2026-09-23. Every reply about the LUMA workstation the
# bot had just shown said "the exact requested item isn't confirmed", because a
# verbose model-written query needed every one of its words on one catalog row.
_LUMA_ROW = (
    "Four person workstation SKYLAND LUMA 9719-4\n"
    "Four-person workstation with a shared frame.\n"
    "Workstations"
)
_NOVO_ROW = (
    "4 Person Face to Face Table SKYLAND NOVO 2400\nFace to face desk.\nWorkstations"
)
_LUMA_SKU = "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut"
_LUMA_AGGREGATE_REQUEST = (
    "We’re considering two LUMA 9719-4 workstations in walnut for eight people. "
    "Our furniture budget is AED 6,000. Don’t prepare a quotation yet."
)


def test_verbose_compare_query_naming_two_models_is_exact() -> None:
    query = (
        "Compare SKYLAND LUMA 9719-4 and SKYLAND NOVO 2400 four-person "
        "workstation setups for privacy, collaboration, and current price"
    )

    assert classify_product_match(query, [_LUMA_ROW, _NOVO_ROW]) == "exact"
    assert classify_product_match(query, [_NOVO_ROW]) == "exact"


def test_named_model_with_appended_seat_count_is_exact() -> None:
    assert (
        classify_product_match(
            "LUMA 9719-4 four-person workstation setup 4 person", [_LUMA_ROW]
        )
        == "exact"
    )


@pytest.mark.parametrize(
    ("query", "row", "sku"),
    [
        (
            _LUMA_AGGREGATE_REQUEST,
            _LUMA_ROW,
            _LUMA_SKU,
        ),
        (
            "Three LUMA 9719-4 workstations in walnut for twelve people",
            _LUMA_ROW,
            _LUMA_SKU,
        ),
        (
            "2 SKYLAND NOVO 2400 workstations for a team of eight",
            _NOVO_ROW,
            None,
        ),
        (
            "Twenty-five NOVO 2400 workstations for 100 people",
            _NOVO_ROW,
            None,
        ),
        (
            "Two AERO 5500 workstations for twelve people",
            "Six person workstation SKYLAND AERO 5500\nWorkstations",
            None,
        ),
    ],
)
def test_named_model_quantity_accounts_for_aggregate_team_capacity(
    query: str, row: str, sku: str | None
) -> None:
    assert classify_product_match(query, [row], candidate_skus=[sku]) == "exact"


@pytest.mark.parametrize(
    "query",
    [
        "Exact walnut LUMA 9719-4 workstation for 12 people, three units, "
        "budget AED 6000",
        "LUMA 9719-4 workstation, walnut finish, for 12 people using 3 units",
    ],
)
def test_live_named_model_suffix_quantity_confirms_the_exact_catalog_row(
    query: str,
) -> None:

    assert (
        classify_product_match(
            query,
            [
                "Four person workstation SKYLAND LUMA 9719-4",
                "Two person workstation SKYLAND LUMA 9719-2",
            ],
            candidate_skus=[
                _LUMA_SKU,
                "OF-HAI-Luma-Workstation-RJ 9719-2-Walnut",
            ],
        )
        == "exact"
    )
    assert (
        classify_product_match(
            query,
            ["Two person workstation SKYLAND LUMA 9719-2"],
            candidate_skus=["OF-HAI-Luma-Workstation-RJ 9719-2-Walnut"],
        )
        == "nearby"
    )


@pytest.mark.parametrize(
    ("query", "row", "sku"),
    [
        (
            "LUMA 9719-4 workstation in walnut for twelve people, 3 units",
            _LUMA_ROW,
            _LUMA_SKU,
        ),
        (
            "LUMA9719-4 walnut workstation for twelve people, three workstations",
            _LUMA_ROW,
            _LUMA_SKU,
        ),
        (
            "SKYLAND NOVO 2400 workstation for a team of eight, two units",
            _NOVO_ROW,
            None,
        ),
        (
            "AERO 5500 workstation for twelve people, two units",
            "Six person workstation SKYLAND AERO 5500\nWorkstations",
            None,
        ),
        (
            "NOVO 2400 table for eight people, two tables",
            _NOVO_ROW,
            None,
        ),
        (
            "AERO 5500 bench for twelve people, two benches",
            "Six person bench SKYLAND AERO 5500\nWorkstations",
            None,
        ),
        (
            "NOVO 240 workstation for twelve people, three units",
            "Four person workstation SKYLAND NOVO 240\nWorkstations",
            None,
        ),
        (
            "LUMA 9719-4 workstation in walnut for twelve people, three units. Budget AED 6000",
            _LUMA_ROW,
            _LUMA_SKU,
        ),
        (
            "LUMA 9719-4 workstation in walnut for twelve people, three units; budget AED 6000",
            _LUMA_ROW,
            _LUMA_SKU,
        ),
    ],
)
def test_named_model_suffix_quantity_accounts_for_aggregate_capacity(
    query: str, row: str, sku: str | None
) -> None:
    assert classify_product_match(query, [row], candidate_skus=[sku]) == "exact"


@pytest.mark.parametrize(
    "query",
    [
        "LUMA 9719-4 workstation in oak for twelve people, three units",
        "LUMA 9719-4 eight-person workstation in walnut for twelve people, three units",
        "LUMA 9719-4 workstation in walnut for twelve people each, three units",
        "LUMA 9719-4 workstation in walnut for twelve people and eight people, three units",
        "LUMA 9719-4 workstation in walnut for twelve people, three units per workstation",
        "LUMA 9719-4 workstation in walnut for twelve people, two units",
        "LUMA 9719-4 and NOVO 2400 workstations in walnut for twelve people, three units",
        "LUMA 9719-4 NOVO 2400 workstations in walnut for twelve people, three units",
        "LUMA 9719-4 workstation in walnut for twelve people; three units",
        "LUMA 9719-4 workstation in walnut for twelve people, three chairs",
        "LUMA 9719-4 workstation in walnut for twelve people, three tables",
        "LUMA 9719-4 workstation in walnut for twelve people, three units for CT 1065",
        "LUMA 9719-4 workstation in walnut for twelve people, two or three units",
        "LUMA 9719-4 workstation in walnut for twelve people, three units, two units",
        "Two LUMA 9719-4 workstations in walnut for twelve people, three units",
        "Three LUMA 9719-4 workstations in walnut for twelve people, two units",
        "LUMA 9719-4 workstation in walnut for twelve people, three units or six units",
        "LUMA 9719-4 workstation in walnut for twelve people, maybe three units",
        "LUMA 9719-4 workstation, oak finish, for twelve people using three units",
        "LUMA 9719-4 eight-person workstation, walnut finish, for twelve people using three units",
        "LUMA 9719-4 workstation, walnut finish, for twelve people each using three units",
        "LUMA 9719-4 workstation, walnut finish, for twelve people using three units per workstation",
        "LUMA 9719-4 workstation, walnut finish, for twelve people using two units",
        "LUMA 9719-4 workstation, walnut finish, NOVO 2400 workstation, for twelve people using three units",
        "LUMA 9719-4 workstation, walnut finish, chairs, for twelve people using three units",
        "LUMA 9719-4 workstation, walnut finish, for twelve people using three chairs",
        "LUMA 9719-4 workstation, walnut finish, for twelve people using two or three units",
        "LUMA 9719-4 workstation, walnut finish, for twelve people using three units. Actually two units",
    ],
)
def test_named_model_suffix_quantity_keeps_product_and_quantity_constraints(
    query: str,
) -> None:
    assert (
        classify_product_match(query, [_LUMA_ROW], candidate_skus=[_LUMA_SKU])
        == "nearby"
    )


@pytest.mark.parametrize(
    "later_request",
    [
        "; actually two units",
        ". Two units instead",
        "; switch to NOVO 2400",
        ". Use NOVO 2400 instead",
    ],
)
@pytest.mark.parametrize("with_customer_fallback", [False, True])
def test_named_model_suffix_quantity_rejects_later_conflicting_requests(
    later_request: str, with_customer_fallback: bool
) -> None:
    query = (
        "LUMA 9719-4 workstation in walnut for twelve people, three units"
        + later_request
    )

    assert (
        classify_product_match(
            query,
            [_LUMA_ROW],
            candidate_skus=[_LUMA_SKU],
            customer_request=(
                "Three LUMA 9719-4 workstations in walnut for twelve people"
                if with_customer_fallback
                else None
            ),
        )
        == "nearby"
    )


def test_short_named_model_code_does_not_block_literal_quantity_fallback() -> None:
    assert (
        classify_product_match(
            "NOVO 240 workstation for twelve people",
            ["Four person workstation SKYLAND NOVO 240\nWorkstations"],
            customer_request="Three NOVO 240 workstations for twelve people",
        )
        == "exact"
    )


def test_short_named_model_code_keeps_explicit_quantity_constraints() -> None:
    assert (
        classify_product_match(
            "NOVO 240 workstation for twelve people, two units",
            ["Four person workstation SKYLAND NOVO 240\nWorkstations"],
            customer_request="Three NOVO 240 workstations for twelve people",
        )
        == "nearby"
    )


def test_shortened_named_query_reuses_literal_customer_suffix_quantity() -> None:
    assert (
        classify_product_match(
            "LUMA9719-4 walnut for twelve people",
            [_LUMA_ROW],
            candidate_skus=[_LUMA_SKU],
            customer_request=(
                "LUMA 9719-4 workstation in walnut for twelve people, three units"
            ),
        )
        == "exact"
    )


@pytest.mark.parametrize(
    "query",
    [
        "LUMA9719-4 walnut for twelve people, two units",
        "LUMA9719-4 walnut for twelve people, one unit",
        "LUMA9719-4 walnut for twelve people, two or three units",
        "LUMA9719-4 walnut for twelve people, three units, two units",
        "LUMA9719-4 workstation, walnut finish, for twelve people using two units",
        "LUMA9719-4 workstation, walnut finish, for twelve people using two or three units",
    ],
)
def test_literal_customer_quantity_cannot_override_explicit_query_suffix(
    query: str,
) -> None:
    assert classify_product_match(
        query,
        [_LUMA_ROW],
        candidate_skus=[_LUMA_SKU],
        customer_request="Three LUMA 9719-4 workstations in walnut for twelve people",
    ) in {"nearby", "missing"}


@pytest.mark.parametrize(
    "query",
    [
        "Two LUMA 9719-4 workstations in oak for eight people",
        "LUMA 9719-4 eight-person workstation in walnut",
        "Two eight-person LUMA 9719-4 workstations in walnut for eight people",
        "Two LUMA 9719-4 workstations in walnut for eight people each",
        "Two LUMA 9719-4 workstations in walnut for eight people per workstation",
        "Three LUMA 9719-4 workstations in walnut for eight people",
        "Two NOVO 2400 workstations; LUMA 9719-4 in walnut for eight people",
        "Two LUMA 9719-4 workstations and chairs in walnut for eight people",
    ],
)
def test_named_model_aggregate_capacity_keeps_product_constraints(query: str) -> None:
    assert (
        classify_product_match(query, [_LUMA_ROW], candidate_skus=[_LUMA_SKU])
        == "nearby"
    )


def test_shortened_named_query_reuses_customer_request_quantity() -> None:
    assert (
        classify_product_match(
            "LUMA9719-4 walnut for eight people",
            [_LUMA_ROW],
            candidate_skus=[_LUMA_SKU],
            customer_request=_LUMA_AGGREGATE_REQUEST,
        )
        == "exact"
    )


@pytest.mark.parametrize(
    ("query", "customer_request"),
    [
        ("LUMA9719-4 oak for eight people", _LUMA_AGGREGATE_REQUEST),
        (
            "LUMA9719-4 walnut for eight people",
            "Two LUMA 9719-4 workstations in oak for eight people",
        ),
        (
            "LUMA9719-4 walnut for eight people",
            "Two NOVO 2400 workstations in walnut for eight people",
        ),
        (
            "LUMA9719-4 walnut for eight people",
            "Three LUMA 9719-4 workstations in walnut for eight people",
        ),
        (
            "LUMA9719-4 walnut for eight people",
            "Three LUMA 9719-4 workstations in walnut for twelve people",
        ),
        (
            "LUMA9719-4 walnut for eight people",
            "Two eight-person LUMA 9719-4 workstations in walnut for eight people",
        ),
        (
            "LUMA9719-4 walnut for eight people",
            "Two LUMA 9719-4 workstations in walnut for eight people each",
        ),
        ("LUMA9719-4 eight-person workstation in walnut", _LUMA_AGGREGATE_REQUEST),
        ("LUMA9719-4 eight-person in walnut", _LUMA_AGGREGATE_REQUEST),
        (
            "LUMA9719-4 eight-person workstation in walnut for eight people",
            _LUMA_AGGREGATE_REQUEST,
        ),
        ("LUMA9719-4 walnut for eight people each", _LUMA_AGGREGATE_REQUEST),
        ("LUMA9719-4 walnut for eight people per unit", _LUMA_AGGREGATE_REQUEST),
        (
            "Three LUMA 9719-4 workstations in walnut for eight people",
            _LUMA_AGGREGATE_REQUEST,
        ),
        ("NOVO 2400 walnut for eight people", _LUMA_AGGREGATE_REQUEST),
    ],
)
def test_customer_quantity_cannot_override_named_query_constraints(
    query: str, customer_request: str
) -> None:
    assert classify_product_match(
        query,
        [_LUMA_ROW],
        candidate_skus=[_LUMA_SKU],
        customer_request=customer_request,
    ) in {"nearby", "missing"}


def test_customer_quantity_does_not_promote_generic_or_missing_query() -> None:
    assert (
        classify_product_match(
            "workstations for eight people",
            [_LUMA_ROW],
            customer_request=_LUMA_AGGREGATE_REQUEST,
        )
        == "generic"
    )
    assert (
        classify_product_match(
            "LUMA9719-4 walnut for eight people",
            [],
            customer_request=_LUMA_AGGREGATE_REQUEST,
        )
        == "missing"
    )


def test_finish_carried_only_by_the_sku_still_confirms_the_named_model() -> None:
    query = "LUMA workstation SKYLAND 9719-4 walnut"

    assert (
        classify_product_match(query, [_LUMA_ROW], candidate_skus=[_LUMA_SKU])
        == "exact"
    )
    assert classify_product_match(query, [_LUMA_ROW]) != "exact"


def test_named_model_in_an_absent_finish_is_not_exact() -> None:
    assert (
        classify_product_match(
            "LUMA 9719-4 in oak finish", [_LUMA_ROW], candidate_skus=[_LUMA_SKU]
        )
        == "nearby"
    )


_CT_1065_WENGE = "Coffee table, COFFEE, CT 1065, 1000х650х400, Wenge magic"
_CT_1065_OAK = "Coffee table, COFFEE, CT 1065, 1000х650х400, Oak Devon"
_CT_1065_WALNUT = "Coffee table, COFFEE, CT 1065, 1000х650х400, Walnut Dallas"
_CT_1065_MULTI_FINISH_QUERY = (
    "CT 1065 coffee table in Oak Devon and Wenge Magic; show product photos"
)


@pytest.mark.parametrize(
    "query",
    [
        _CT_1065_MULTI_FINISH_QUERY,
        "CT 1065 coffee table, Oak Devon finish and Wenge Magic finish; show product photos",
    ],
)
def test_actual_named_model_multiple_finishes_are_exact_catalog_variants(
    query: str,
) -> None:
    assert (
        classify_product_match(
            query,
            [_CT_1065_WENGE, _CT_1065_OAK, _CT_1065_WALNUT],
            candidate_skus=["00-07015316", "00-07015317", "00-07052840"],
        )
        == "exact"
    )


@pytest.mark.parametrize(
    ("query", "rows"),
    [
        (_CT_1065_MULTI_FINISH_QUERY, [_CT_1065_OAK, _CT_1065_WALNUT]),
        (_CT_1065_MULTI_FINISH_QUERY, [_CT_1065_WENGE]),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [_CT_1065_OAK, _CT_1065_WENGE.replace("CT 1065", "CT 1075")],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [_CT_1065_OAK, _CT_1065_WENGE.replace("1000х650х400", "1200х650х400")],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [_CT_1065_OAK, _CT_1065_WENGE.replace("Coffee table", "Meeting table")],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [
                _CT_1065_OAK.replace("Coffee table", "Meeting table"),
                _CT_1065_WENGE.replace("Coffee table", "Meeting table"),
            ],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [
                _CT_1065_OAK,
                _CT_1065_WENGE.replace("Coffee table", "Round coffee table"),
            ],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY,
            [_CT_1065_OAK.replace("Oak Devon", "Oak Loft"), _CT_1065_WENGE],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY.replace("coffee table", "meeting table"),
            [_CT_1065_OAK, _CT_1065_WENGE],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY.replace("coffee table", "round coffee table"),
            [_CT_1065_OAK, _CT_1065_WENGE],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY.replace(
                "coffee table", "1200x650x400 coffee table"
            ),
            [_CT_1065_OAK, _CT_1065_WENGE],
        ),
        (
            _CT_1065_MULTI_FINISH_QUERY.replace("CT 1065", "CT 1065 and CT 1075"),
            [_CT_1065_OAK, _CT_1065_WENGE.replace("CT 1065", "CT 1075")],
        ),
        (
            "LUMA 9719-4 eight-person workstation in Oak Devon and Wenge Magic",
            [
                "Four person workstation SKYLAND LUMA 9719-4, Oak Devon",
                "Four person workstation SKYLAND LUMA 9719-4, Wenge Magic",
            ],
        ),
        (
            "LUMA 9719-4 four-person workstation in Oak Devon and Wenge Magic",
            [
                "Four person workstation SKYLAND LUMA 9719-4, Oak Devon",
                "Eight person workstation SKYLAND LUMA 9719-4, Wenge Magic",
            ],
        ),
    ],
)
def test_named_model_multiple_finishes_keep_each_catalog_variant_constraint(
    query: str, rows: list[str]
) -> None:
    assert classify_product_match(query, rows) == "nearby"


def test_named_model_multiple_finishes_keep_explicit_matching_dimensions() -> None:
    assert (
        classify_product_match(
            _CT_1065_MULTI_FINISH_QUERY.replace(
                "coffee table", "1000x650x400 coffee table"
            ),
            [_CT_1065_OAK, _CT_1065_WENGE],
        )
        == "exact"
    )


def test_named_model_one_bicolor_finish_preserves_single_row_matching() -> None:
    assert (
        classify_product_match(
            "CT 1065 coffee table in black and white",
            ["Coffee table, CT 1065, black and white"],
        )
        == "exact"
    )


_ACTUAL_MIXED_PRODUCT_QUERY = (
    "walnut LUMA 9719-4 workstation for 4 people, and CT 1065 coffee tables "
    "Oak Devon and Wenge Magic with photos"
)
_ACTUAL_MIXED_CUSTOMER_REQUEST = (
    "I need two walnut LUMA 9719-4 workstations for eight people in Dubai. "
    "My budget is AED 6000. Do not prepare a quotation. "
    "Please show CT 1065 coffee tables in Oak Devon and Wenge Magic with photos."
)


@pytest.fixture(scope="module")
def actual_mixed_product_catalog() -> tuple[list[str], list[str]]:
    rows = json.loads(
        (
            Path(__file__).parent
            / "fixtures/catalog_snapshot_2026-10-14_tester_subset.json"
        ).read_text()
    )
    return (
        [
            f"{row['name_en']}\n{row['description_en'] or ''}\n{row['category'] or ''}"
            for row in rows
        ],
        [row["sku"] for row in rows],
    )


def test_actual_mixed_named_products_are_exact_when_every_clause_is_supported(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY,
            texts,
            candidate_skus=skus,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
        == "exact"
    )


def test_mixed_named_products_keep_literal_customer_quantity_in_its_own_clause(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY.replace("for 4 people", "for eight people"),
            texts,
            candidate_skus=skus,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
        == "exact"
    )


@pytest.mark.parametrize("location", ["Atlantis", "Abu Custom"])
def test_mixed_named_products_keep_unknown_locality_discriminators_conservative(
    actual_mixed_product_catalog: tuple[list[str], list[str]], location: str
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY.replace("for 4 people", "for eight people"),
            texts,
            candidate_skus=skus,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST.replace(
                "in Dubai", f"in {location}"
            ),
        )
        == "nearby"
    )


@pytest.mark.parametrize("attribute", ["brand Dubai", "Dubai finish"])
def test_mixed_named_products_keep_explicit_location_named_brand_or_finish(
    actual_mixed_product_catalog: tuple[list[str], list[str]], attribute: str
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY.replace(
                "walnut LUMA", f"{attribute} walnut LUMA"
            ),
            texts,
            candidate_skus=skus,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
        == "nearby"
    )


@pytest.mark.parametrize(
    "attribute",
    [
        "in Dubai finish",
        "in Dubai color",
        "in Dubai colour",
        "in Dubai brand",
        "in Abu Dhabi finish",
        "in Dubai Marina color",
    ],
)
def test_mixed_named_products_do_not_erase_explicit_qualified_city_attributes(
    actual_mixed_product_catalog: tuple[list[str], list[str]], attribute: str
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY.replace("for 4 people", "for eight people"),
            texts,
            candidate_skus=skus,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST.replace(
                "in Dubai", attribute
            ),
        )
        == "nearby"
    )


@pytest.mark.parametrize(
    ("category", "sku"),
    [
        ("Workstations", "NOVO-2400-Walnut"),
        ("", "OF-HAI-Novo-Workstation-RJ 2400-Walnut"),
    ],
)
def test_mixed_named_products_keep_grounded_workspace_category_and_sku_aliases(
    category: str, sku: str
) -> None:
    row = (
        f"4 Person Face to Face Table SKYLAND NOVO 2400\nFace to face desk.\n{category}"
    )
    query = (
        "NOVO2400 workstation for 4 people, and CT1065 coffee tables "
        "Oak Devon and Wenge Magic"
    )

    assert (
        classify_product_match(
            query,
            [row, _CT_1065_OAK, _CT_1065_WENGE],
            candidate_skus=[sku, "00-07015317", "00-07015316"],
        )
        == "exact"
    )
    assert verified_answers_module.is_requested_product_candidate(
        query, row, candidate_sku=sku
    )


@pytest.mark.parametrize(
    "row",
    [
        "4 Person Face to Face Table SKYLAND NOVO 2400\nA useful workstation.\nCoffee Table",
        "4 Person Chair SKYLAND NOVO 2400\nFace to face chair.\nWorkstations",
        "4 Person Coffee Table SKYLAND NOVO 2400\nCoffee table.\nWorkstations",
    ],
)
def test_mixed_workspace_alias_keeps_wrong_family_and_specialized_type_uncertain(
    row: str,
) -> None:
    query = (
        "NOVO2400 workstation for 4 people, and CT1065 coffee tables "
        "Oak Devon and Wenge Magic"
    )

    assert (
        classify_product_match(
            query,
            [row, _CT_1065_OAK, _CT_1065_WENGE],
            candidate_skus=["NOVO-2400-Walnut", "00-07015317", "00-07015316"],
        )
        == "nearby"
    )
    assert not verified_answers_module.is_requested_product_candidate(
        query, row, candidate_sku="NOVO-2400-Walnut"
    )


@pytest.mark.parametrize(
    "missing_sku",
    [_LUMA_SKU, "00-07015316", "00-07015317"],
)
def test_mixed_named_products_require_each_model_and_each_finish(
    actual_mixed_product_catalog: tuple[list[str], list[str]], missing_sku: str
) -> None:
    texts, skus = actual_mixed_product_catalog
    rows = [
        (text, sku) for text, sku in zip(texts, skus, strict=True) if sku != missing_sku
    ]

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY,
            [text for text, _ in rows],
            candidate_skus=[sku for _, sku in rows],
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
        == "nearby"
    )


@pytest.mark.parametrize(
    "query",
    [
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("walnut LUMA", "oak LUMA"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("for 4 people", "for eight people each"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace(
            "walnut LUMA 9719-4 workstation for 4 people",
            "Three walnut LUMA 9719-4 workstations for eight people",
        ),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("CT 1065", "CT 1075"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("CT 1065", "CT 1065 and CT 1075"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("coffee tables", "meeting tables"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("coffee tables", "round coffee tables"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace(
            "coffee tables", "1200x650x400 coffee tables"
        ),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("Oak Devon", "Oak Loft"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("Wenge Magic", "Walnut Dallas"),
    ],
)
def test_mixed_named_products_keep_each_clauses_literal_constraints(
    actual_mixed_product_catalog: tuple[list[str], list[str]], query: str
) -> None:
    texts, skus = actual_mixed_product_catalog
    # Exclude the unrequested Walnut Dallas sibling so a missing finish cannot
    # be borrowed from the walnut workstation in the other clause.
    rows = [
        (text, sku)
        for text, sku in zip(texts, skus, strict=True)
        if sku != "00-07052840"
    ]

    assert (
        classify_product_match(
            query,
            [text for text, _ in rows],
            candidate_skus=[sku for _, sku in rows],
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
        == "nearby"
    )


def test_mixed_query_singleton_does_not_claim_complete_search_coverage(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog

    for text, sku in zip(texts, skus, strict=True):
        assert (
            classify_product_match(
                _ACTUAL_MIXED_PRODUCT_QUERY, [text], candidate_skus=[sku]
            )
            != "exact"
        )


def test_mixed_named_products_keep_repeated_separators_and_finish_conjunctions(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert (
        classify_product_match(
            _ACTUAL_MIXED_PRODUCT_QUERY.replace(", and CT", ", and, CT"),
            texts,
            candidate_skus=skus,
        )
        == "exact"
    )


def test_mixed_named_products_expose_per_candidate_membership_separately(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog

    assert {
        sku
        for text, sku in zip(texts, skus, strict=True)
        if verified_answers_module.is_requested_product_candidate(
            _ACTUAL_MIXED_PRODUCT_QUERY,
            text,
            candidate_sku=sku,
            customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
        )
    } == {_LUMA_SKU, "00-07015316", "00-07015317"}


@pytest.mark.parametrize(
    "query",
    [
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("for 4 people", "for eight people each"),
        _ACTUAL_MIXED_PRODUCT_QUERY.replace("walnut LUMA", "oak LUMA"),
    ],
)
def test_mixed_query_candidate_membership_keeps_its_own_capacity_and_finish(
    actual_mixed_product_catalog: tuple[list[str], list[str]], query: str
) -> None:
    texts, skus = actual_mixed_product_catalog
    index = skus.index(_LUMA_SKU)

    assert not verified_answers_module.is_requested_product_candidate(
        query,
        texts[index],
        candidate_sku=_LUMA_SKU,
        customer_request=_ACTUAL_MIXED_CUSTOMER_REQUEST,
    )


def test_mixed_query_candidate_membership_keeps_its_own_dimensions(
    actual_mixed_product_catalog: tuple[list[str], list[str]],
) -> None:
    texts, skus = actual_mixed_product_catalog
    index = skus.index("00-07015316")

    assert not verified_answers_module.is_requested_product_candidate(
        _ACTUAL_MIXED_PRODUCT_QUERY.replace(
            "coffee tables", "1200x650x400 coffee tables"
        ),
        texts[index],
        candidate_sku=skus[index],
    )


def test_bare_number_does_not_name_a_model() -> None:
    assert classify_product_match("novo 2400", [_NOVO_ROW]) == "exact"
    assert classify_product_match("novo 1600 table", [_NOVO_ROW]) == "nearby"


@pytest.mark.parametrize(
    "query",
    [
        "office furniture for a new Dubai office for four people; seating and "
        "workspace options",
        "four-person workstation with privacy dividers",
        "office furniture for 4 people under AED 5000",
    ],
)
def test_needs_only_request_is_generic(query: str) -> None:
    assert classify_product_match(query, [_LUMA_ROW, _NOVO_ROW]) == "generic"


def test_spelled_out_head_count_keeps_a_need_request_generic() -> None:
    # Live check 2026-09-24: "six" read as an unmet product discriminator.
    chairs = [
        "Executive Office Chair CH 430 Black",
        "SkyLand Executive Chair CH 950 BLACK",
        "Visitor Office Chair CH 490 V brown",
    ]
    query = "comfortable ergonomic office chairs for a team of six in Abu Dhabi"
    assert classify_product_match(query, chairs) == "generic"


@pytest.mark.parametrize(
    "query",
    [
        "comfortable chairs for a team of fifteen",
        "comfortable office chairs for a team of six",
        "office chairs for twenty people",
        "office chairs for a team of 15",
        "office chairs for twenty-five staff",
    ],
)
def test_any_head_count_keeps_a_need_request_generic(query: str) -> None:
    # tj-aq4t: head counts past ten or twelve, or phrased as "a team of N",
    # used to read as unmet product words or as a model number.
    chairs = [
        "Executive Office Chair CH 430 Black",
        "SkyLand Executive Chair CH 950 BLACK",
        "Visitor Office Chair CH 490 V brown",
    ]
    assert classify_product_match(query, chairs) == "generic"


@pytest.mark.parametrize(
    "query",
    ["HERMAN desk for four people", "luma workstation", "Show a LUMA workstation"],
)
def test_named_but_absent_brand_stays_nearby(query: str) -> None:
    assert classify_product_match(query, [_NOVO_ROW]) == "nearby"


def test_search_filler_words_do_not_block_an_exact_match() -> None:
    assert (
        classify_product_match(
            "compare current price and stock options for acoustic pods",
            ["Acoustic Pod Four-person acoustic pod for meetings"],
        )
        == "exact"
    )


@pytest.mark.parametrize(
    ("query", "candidates"),
    [
        ("2 workstations for 8 people", [_LUMA_ROW, _NOVO_ROW]),
        ("two workstations for 8 people", [_LUMA_ROW, _NOVO_ROW]),
        ("3 desks", [_LUMA_ROW, _NOVO_ROW]),
        ("three desks", [_LUMA_ROW, _NOVO_ROW]),
        (
            "10 ergonomic mesh chairs",
            [
                "Executive Office Chair CH 430 Black",
                "SkyLand Executive Chair CH 950 BLACK",
            ],
        ),
        (
            "ten ergonomic mesh chairs",
            [
                "Executive Office Chair CH 430 Black",
                "SkyLand Executive Chair CH 950 BLACK",
            ],
        ),
    ],
)
def test_digit_and_word_quantities_preserve_generic_product_match_parity(
    query: str,
    candidates: list[str],
) -> None:
    assert not verified_answers_module.query_names_specific_item(query)
    assert classify_product_match(query, candidates) == "generic"


@pytest.mark.parametrize(
    "query",
    [
        "CH 160",
        "CT1065",
        "LUMA 9719-4",
        "1200x600",
        "chair 205",
    ],
)
def test_query_names_specific_item_retains_model_codes_and_dimensions(
    query: str,
) -> None:
    assert verified_answers_module.query_names_specific_item(query)
