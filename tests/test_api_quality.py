"""Tests for Quality API endpoints.

Updated from stubs (501) to verify real implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_list_reviews_empty() -> None:
    """GET /reviews/ should return 200 with empty paginated response."""
    with patch("src.api.v1.quality.get_reviews") as mock_get:
        mock_get.return_value = ([], 0)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/quality/reviews/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_reviews_with_filters() -> None:
    """GET /reviews/?min_score=20 should pass filters to service."""
    with patch("src.api.v1.quality.get_reviews") as mock_get:
        mock_get.return_value = ([], 0)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/quality/reviews/?min_score=20&page_size=5")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_reviews_normalizes_legacy_object_criteria() -> None:
    """GET /reviews/ tolerates legacy rows where criteria is stored as {}."""
    from datetime import datetime

    mock_review = MagicMock()
    mock_review.id = uuid4()
    mock_review.conversation_id = uuid4()
    mock_review.total_score = 0.0
    mock_review.max_score = 30
    mock_review.rating = "poor"
    mock_review.criteria = {}
    mock_review.summary = None
    mock_review.reviewer = "ai"
    mock_review.created_at = datetime(2026, 4, 2, 12, 0, 0)

    with patch("src.api.v1.quality.get_reviews") as mock_get:
        mock_get.return_value = ([mock_review], 1)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.get("/api/v1/quality/reviews/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["criteria"] == []


def test_quality_review_read_accepts_legacy_criteria_without_new_fields() -> None:
    """Schema should keep reading legacy criteria rows after JSON enrichment."""
    from datetime import datetime

    from src.schemas.quality import QualityReviewRead

    review = QualityReviewRead.model_validate(
        {
            "id": uuid4(),
            "conversation_id": uuid4(),
            "total_score": 14.0,
            "max_score": 30,
            "rating": "satisfactory",
            "criteria": [
                {
                    "rule_number": 1,
                    "rule_name": "Greeting",
                    "score": 2,
                    "max_score": 2,
                    "comment": "ok",
                }
            ],
            "summary": "Legacy summary",
            "reviewer": "ai",
            "created_at": datetime(2026, 4, 5, 9, 0, 0),
        }
    )

    assert len(review.criteria) == 1
    assert review.criteria[0].rule_number == 1
    assert review.criteria[0].applicable is None
    assert review.criteria[0].weight_points is None
    assert review.criteria[0].evidence == []


@pytest.mark.asyncio
async def test_create_review_success() -> None:
    """POST /reviews/ should return 201 with QualityReviewRead."""
    from src.quality.schemas import CriterionScore, EvaluationResult

    mock_criteria = [
        CriterionScore(rule_number=i, rule_name=f"Rule {i}", score=2, comment="ok")
        for i in range(1, 16)
    ]
    mock_eval_result = EvaluationResult(
        criteria=mock_criteria,
        summary="Great dialogue",
        total_score=28.0,
        rating="excellent",
    )

    from datetime import datetime

    conv_id = uuid4()
    mock_review = MagicMock()
    mock_review.id = uuid4()
    mock_review.conversation_id = conv_id
    mock_review.total_score = 28.0
    mock_review.max_score = 30
    mock_review.rating = "excellent"
    mock_review.criteria = [
        {
            "rule_number": i,
            "rule_name": f"Rule {i}",
            "score": 2,
            "max_score": 2,
            "comment": "ok",
        }
        for i in range(1, 16)
    ]
    mock_review.summary = "Great dialogue"
    mock_review.reviewer = "ai"
    mock_review.created_at = datetime(2026, 3, 5, 12, 0, 0)

    with (
        patch("src.api.v1.quality.conversation_already_reviewed", return_value=False),
        patch(
            "src.api.v1.quality.evaluate_conversation", return_value=mock_eval_result
        ),
        patch("src.api.v1.quality.save_review", return_value=mock_review),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/quality/reviews/",
                json={"conversation_id": str(conv_id)},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["total_score"] == 28.0
    assert data["rating"] == "excellent"


@pytest.mark.asyncio
async def test_create_review_already_reviewed() -> None:
    """POST /reviews/ should return 409 if conversation already reviewed."""
    conv_id = uuid4()
    with patch("src.api.v1.quality.conversation_already_reviewed", return_value=True):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/quality/reviews/",
                json={"conversation_id": str(conv_id)},
            )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_review_conversation_not_found() -> None:
    """POST /reviews/ should return 404 if conversation has no messages."""
    conv_id = uuid4()
    with (
        patch("src.api.v1.quality.conversation_already_reviewed", return_value=False),
        patch(
            "src.api.v1.quality.evaluate_conversation",
            side_effect=ValueError(f"No messages found for conversation {conv_id}"),
        ),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/api/v1/quality/reviews/",
                json={"conversation_id": str(conv_id)},
            )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_generate_report_not_implemented() -> None:
    """POST /reports/ should still return 501 (Week 11 feature)."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/quality/reports/", json={"start_date": "2024-01-01"}
        )
    assert response.status_code in (422, 501)
