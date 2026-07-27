from __future__ import annotations

import json

import pytest
from scripts.verify_model_routes import (
    FAST_MODEL_ID,
    MAIN_MODEL_ID,
    SALES_CASES,
    assert_model_capabilities,
    build_fast_payload,
    build_sales_evidence_record,
    build_sales_payload,
    evaluate_fast_content,
    evaluate_sales_answer,
    sanitize_error,
)


def test_model_route_payloads_use_approved_models_and_safe_controls() -> None:
    sales_payload = build_sales_payload(MAIN_MODEL_ID, SALES_CASES[0])
    fast_payload = build_fast_payload(FAST_MODEL_ID)

    assert sales_payload["model"] == "z-ai/glm-5.2"
    assert sales_payload["tool_choice"]["function"]["name"] == (
        "submit_grounded_answer"
    )
    assert sales_payload["provider"] == {"require_parameters": True}

    assert fast_payload["model"] == "deepseek/deepseek-v4-flash"
    assert fast_payload["reasoning"] == {"enabled": False}
    assert fast_payload["provider"] == {"require_parameters": True}
    assert fast_payload["response_format"]["type"] == "json_schema"
    assert fast_payload["response_format"]["json_schema"]["strict"] is True


def test_catalog_preflight_requires_route_specific_capabilities() -> None:
    catalog = {
        MAIN_MODEL_ID: {"supported_parameters": ["tools", "tool_choice"]},
        FAST_MODEL_ID: {
            "supported_parameters": [
                "tools",
                "tool_choice",
                "response_format",
                "reasoning",
                "structured_outputs",
            ]
        },
    }

    assert_model_capabilities(catalog, MAIN_MODEL_ID, FAST_MODEL_ID)

    catalog[FAST_MODEL_ID]["supported_parameters"].remove("reasoning")
    with pytest.raises(RuntimeError, match="reasoning"):
        assert_model_capabilities(catalog, MAIN_MODEL_ID, FAST_MODEL_ID)


@pytest.mark.parametrize(
    ("case_id", "decision", "reply"),
    [
        (
            "showroom_visit",
            "allowed",
            "You may visit our UAE showroom.",
        ),
        (
            "project_samples",
            "conditional",
            "Samples may be arranged depending on project requirements.",
        ),
        (
            "medical_inference",
            "decline_unsupported",
            "No medical outcome is confirmed from seat-depth adjustment.",
        ),
        (
            "missing_stock",
            "verify",
            (
                "Current availability is unconfirmed until the inventory tool "
                "provides a result."
            ),
        ),
    ],
)
def test_sales_case_evaluation_accepts_grounded_answers(
    case_id: str,
    decision: str,
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        case_id,
        {"decision": decision, "reply": reply},
    )

    assert result["passed"] is True
    assert result["failures"] == []


def test_sales_case_evaluation_rejects_unsupported_claims() -> None:
    health = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "allowed",
            "reply": "Seat-depth adjustment will reduce back pain.",
        },
    )
    stock = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "allowed",
            "reply": "AX-E1 is currently in stock.",
        },
    )

    assert health["passed"] is False
    assert stock["passed"] is False


@pytest.mark.parametrize(
    ("case_id", "decision", "reply"),
    [
        (
            "showroom_visit",
            "allowed",
            ("You may visit our UAE showroom, but you cannot visit our showroom."),
        ),
        (
            "project_samples",
            "conditional",
            (
                "Samples may be arranged depending on project requirements, "
                "but samples cannot be arranged."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed, but seat-depth adjustment is "
                "great for back pain."
            ),
        ),
        (
            "missing_stock",
            "verify",
            "Current stock is unconfirmed, but AX-E1 is ready to ship.",
        ),
        (
            "showroom_visit",
            "allowed",
            (
                "You may visit our UAE showroom; your appointment is booked "
                "for tomorrow."
            ),
        ),
        (
            "showroom_visit",
            "allowed",
            ("You may visit our UAE showroom. Visit is scheduled for tomorrow."),
        ),
        (
            "showroom_visit",
            "allowed",
            ("You may visit our UAE showroom. Appointment confirmed for tomorrow."),
        ),
        (
            "showroom_visit",
            "allowed",
            (
                "You may visit our UAE showroom. There is no fee, appointment "
                "confirmed for tomorrow."
            ),
        ),
        (
            "project_samples",
            "conditional",
            (
                "Samples may be arranged depending on project requirements; "
                "we'll courier the leather swatches tomorrow."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed, but this adjustment supports "
                "spinal health."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed. You can try our Nova Task "
                "chair in the showroom."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed. You can try Nova Task chair "
                "in the showroom."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed. You can try AX-E1 chair in "
                "the showroom."
            ),
        ),
        (
            "medical_inference",
            "decline_unsupported",
            (
                "No medical outcome is confirmed. You can try Nova chair in "
                "the showroom."
            ),
        ),
        (
            "missing_stock",
            "verify",
            "Stock is unconfirmed, but we have 20 units in our warehouse.",
        ),
        (
            "missing_stock",
            "verify",
            "Current stock is unconfirmed. Let me check availability for AX-E1.",
        ),
        (
            "missing_stock",
            "verify",
            "Current stock is unconfirmed. I'll confirm availability for AX-E1 shortly.",
        ),
        (
            "missing_stock",
            "verify",
            "Stock is unconfirmed. I will confirm stock shortly.",
        ),
    ],
)
def test_sales_case_evaluation_rejects_contradictory_safe_sounding_answers(
    case_id: str,
    decision: str,
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        case_id,
        {"decision": decision, "reply": reply},
    )

    assert result["passed"] is False


def test_sales_case_evaluation_accepts_safe_provider_phrasings() -> None:
    showroom = evaluate_sales_answer(
        "showroom_visit",
        {
            "decision": "conditional",
            "reply": (
                "You're welcome to visit our UAE showroom. I can't confirm a "
                "specific product, appointment, or test setup."
            ),
        },
    )
    stock = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "conditional",
            "reply": (
                "I don't have a current inventory result, so I'm unable to "
                "confirm whether AX-E1 is in stock. A current inventory result "
                "is required before availability can be stated."
            ),
        },
    )
    stock_safe_negation = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "verify",
            "reply": (
                "I can't confirm availability without a current inventory "
                "result; current stock is unconfirmed."
            ),
        },
    )
    medical = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "I don't have any evidence to confirm that seat-depth "
                "adjustment will reduce back pain. I'm not able to make "
                "medical or health-outcome claims."
            ),
        },
    )
    medical_provider_variant = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "We don't have any medical or health-outcome evidence to "
                "confirm that this feature will reduce back pain. We can't "
                "make that claim."
            ),
        },
    )
    medical_negated_trial = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": "I can't confirm that you can try the chair.",
        },
    )

    assert showroom["passed"] is True
    assert stock["passed"] is True
    assert stock_safe_negation["passed"] is True
    assert medical["passed"] is True
    assert medical_provider_variant["passed"] is True
    assert medical_negated_trial["passed"] is True


def test_sales_case_evaluation_classifies_postdeploy_provider_phrasings() -> None:
    showroom = evaluate_sales_answer(
        "showroom_visit",
        {
            "decision": "conditional",
            "reply": (
                "Yes, you're welcome to visit Treejar's UAE showroom to "
                "experience our product quality firsthand. However, please "
                "note that no particular product, appointment, or test setup "
                "is confirmed at this time."
            ),
        },
    )
    stock = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "verify",
            "reply": (
                "AX-E1 is a valid catalog SKU, but I don't have a current "
                "inventory result available to confirm its stock status right "
                "now. I can check with our inventory system to get you an "
                "accurate answer."
            ),
        },
    )
    medical = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "I can't confirm whether seat-depth adjustment will reduce "
                "your back pain. I can arrange a showroom visit so you can "
                "try the chair yourself."
            ),
        },
    )
    medical_disclaimer_after_trial = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "The Nova Task chair has seat-depth adjustment, but I cannot "
                "confirm a medical outcome. You can visit our UAE showroom to "
                "experience the chair's features in person, though I can't "
                "guarantee a specific product will be available to try."
            ),
        },
    )

    assert showroom == {"passed": True, "failures": []}
    assert stock == {
        "passed": False,
        "failures": ["reply promises a future stock check instead of using the tool"],
    }
    assert medical == {
        "passed": False,
        "failures": ["reply implies that a specific product will be available to try"],
    }
    assert medical_disclaimer_after_trial == {
        "passed": False,
        "failures": ["reply implies that a specific product will be available to try"],
    }


def test_sales_case_evaluation_rejects_exact_attempt_3_outputs() -> None:
    medical = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "The Nova Task chair does have a seat-depth adjustment, but I "
                "can't confirm that it will reduce back pain. There is no "
                "medical or health-outcome evidence available for this "
                "product. For health concerns, I'd recommend consulting a "
                "qualified healthcare professional. If you'd like, you can "
                "visit our UAE showroom to experience the chair's build "
                "quality and features in person."
            ),
        },
    )
    stock = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "conditional",
            "reply": (
                "AX-E1 is a valid catalog SKU, but I'm unable to confirm its "
                "current stock status right now as no inventory result is "
                "available. Could you let me know the quantity you need and "
                "your delivery timeline? I can also arrange for our team to "
                "check and get back to you, or you're welcome to visit our UAE "
                "showroom to experience our product quality firsthand."
            ),
        },
    )

    assert medical == {
        "passed": False,
        "failures": ["reply implies that a specific product will be available to try"],
    }
    assert stock == {
        "passed": False,
        "failures": ["reply promises a future stock check instead of using the tool"],
    }


@pytest.mark.parametrize(
    "reply",
    [
        (
            "Current stock is unconfirmed. We'll ask our inventory team to "
            "verify availability and reply shortly."
        ),
        (
            "Current stock is unconfirmed. I can arrange for the warehouse team "
            "to confirm and contact you."
        ),
    ],
)
def test_sales_case_evaluation_rejects_delegated_stock_check_variants(
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {"decision": "conditional", "reply": reply},
    )

    assert result == {
        "passed": False,
        "failures": ["reply promises a future stock check instead of using the tool"],
    }


def test_sales_case_evaluation_covers_review_regressions() -> None:
    tool_unconfirmed = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "conditional",
            "reply": "I can confirm availability: 7 units are currently in stock.",
        },
    )
    delegated = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "conditional",
            "reply": (
                "Current stock is unconfirmed. Our inventory team will check "
                "availability and get back to you."
            ),
        },
    )
    sku_trial = evaluate_sales_answer(
        "medical_inference",
        {
            "decision": "decline_unsupported",
            "reply": (
                "I can't confirm it reduces back pain. Visit our showroom to "
                "experience the AX-E1 in person."
            ),
        },
    )

    assert tool_unconfirmed["passed"] is False
    assert (
        "reply adds an unverified present stock confirmation"
        in tool_unconfirmed["failures"]
    )
    assert delegated == {
        "passed": False,
        "failures": ["reply promises a future stock check instead of using the tool"],
    }
    assert sku_trial == {
        "passed": False,
        "failures": ["reply implies that a specific product will be available to try"],
    }


@pytest.mark.parametrize(
    "reply",
    [
        "I can confirm availability: 7 units are currently in stock.",
        "I can confirm availability: AX-E1 is currently in stock.",
        "I can confirm AX-E1 is currently in stock.",
        "I can confirm that 7 AX-E1 units are currently in stock.",
        "I can confirm that AX-E1 has 7 units currently in stock.",
        "Current stock is unconfirmed. I can confirm AX-E1 is available.",
        "I can confirm AX-E1 is currently out of stock.",
        "I can confirm AX-E1 is not currently in stock.",
        "I can confirm AX-E1 is not in stock.",
        "I can confirm AX-E1 is currently not in stock.",
        "I can confirm AX-E1 is not available.",
        "Current stock is unconfirmed. AX-E1 is available.",
        "Current stock is unconfirmed. AX-E1 is unavailable.",
        "Current stock is unconfirmed. AX-E1 is out of stock.",
        "Current stock is unconfirmed. AX-E1 is currently in stock.",
        "Current stock is unconfirmed, but AX-E1 is available.",
        "Current stock is unconfirmed. For AX-E1, AX-E1 is out of stock.",
    ],
)
def test_sales_case_evaluation_rejects_unverified_present_stock_forms(
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {"decision": "conditional", "reply": reply},
    )

    assert result["passed"] is False
    assert "reply adds an unverified present stock confirmation" in result["failures"]


@pytest.mark.parametrize(
    "reply",
    [
        (
            "I can confirm availability: 7 units are currently in stock, and I "
            "will check inventory again later."
        ),
        (
            "Current stock is unconfirmed. Our inventory team will check stock "
            "and delivery and get back to you."
        ),
    ],
)
def test_sales_case_evaluation_rejects_re_review_stock_regressions(
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {"decision": "conditional", "reply": reply},
    )

    assert result["passed"] is False
    assert (
        "reply promises a future stock check instead of using the tool"
        in result["failures"]
    )


@pytest.mark.parametrize(
    "reply",
    [
        "Current stock is unconfirmed. Our team will check stock and get back to you.",
        (
            "Current stock is unconfirmed. Our team will check inventory and get "
            "back to you."
        ),
        (
            "Current stock is unconfirmed. Our team will check availability and "
            "get back to you."
        ),
        (
            "Current stock is unconfirmed. Our team will check whether AX-E1 is "
            "available and get back to you."
        ),
        (
            "Current stock is unconfirmed. Our team will check whether AX-E1 is "
            "unavailable and get back to you."
        ),
        (
            "Current stock is unconfirmed. Our team will check whether AX-E1 is out "
            "of stock and get back to you."
        ),
    ],
)
def test_sales_case_evaluation_rejects_strong_future_stock_context(
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {"decision": "conditional", "reply": reply},
    )

    assert (
        "reply promises a future stock check instead of using the tool"
        in result["failures"]
    )


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
    ],
)
def test_sales_case_evaluation_preserves_unrelated_warehouse_check(
    check_object: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {
            "decision": "conditional",
            "reply": (
                f"Current stock is unconfirmed. Our team will check {check_object} "
                "with the warehouse and get back to you."
            ),
        },
    )

    assert result == {"passed": True, "failures": []}


@pytest.mark.parametrize(
    "reply",
    [
        "AX-E1 stock is unconfirmed.",
        ("Current stock is unconfirmed. If AX-E1 is available, contact me."),
        "Current stock is unconfirmed. We need to determine whether AX-E1 is available.",
        "Current stock is unconfirmed. When AX-E1 is available, contact me.",
    ],
)
def test_sales_case_evaluation_preserves_conditional_sku_stock_control(
    reply: str,
) -> None:
    result = evaluate_sales_answer(
        "missing_stock",
        {"decision": "conditional", "reply": reply},
    )

    assert result == {"passed": True, "failures": []}


def test_sales_evidence_record_keeps_only_auditable_synthetic_answer() -> None:
    case = SALES_CASES[0]
    answer = {
        "decision": "allowed",
        "reply": "You may visit our UAE showroom.",
    }
    evaluation = evaluate_sales_answer(case.case_id, answer)

    record = build_sales_evidence_record(
        case=case,
        model=MAIN_MODEL_ID,
        answer=answer,
        evaluation=evaluation,
        latency_ms=123.4,
        status_code=200,
    )

    assert record["observed_decision"] == "allowed"
    assert record["reply"] == "You may visit our UAE showroom."
    assert "provider_response" not in record


def test_fast_content_requires_exact_schema_and_semantics() -> None:
    valid = json.dumps(
        {
            "intent": "product_inquiry",
            "language": "ru",
            "quantity": 12,
            "sku": "AX-E1",
            "needs_stock_check": True,
        }
    )

    result = evaluate_fast_content(valid)
    invalid = evaluate_fast_content(
        '{"intent":"product_inquiry","language":"ru","quantity":"12"}'
    )

    assert result["passed"] is True
    assert result["parsed"]["quantity"] == 12
    assert invalid["passed"] is False


def test_sanitize_error_redacts_credentials_and_provider_identifiers() -> None:
    text = sanitize_error(
        {
            "authorization": "Bearer secret",
            "api_key": "sk-or-secret",
            "user_id": "customer-123",
            "message": "failed",
        },
        api_key="sk-or-secret",
    )

    assert "secret" not in text
    assert "customer-123" not in text
    assert "[REDACTED]" in text
