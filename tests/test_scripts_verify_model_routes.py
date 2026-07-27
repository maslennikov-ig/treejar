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
            "Current stock is unconfirmed; I can check availability for AX-E1.",
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
                "confirm whether AX-E1 is in stock. Let me check availability."
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

    assert showroom["passed"] is True
    assert stock["passed"] is True
    assert medical["passed"] is True
    assert medical_provider_variant["passed"] is True


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
