"""Tests for dashboard manager KPIs (Component 9).

Verifies DashboardMetricsResponse includes manager performance fields.
"""

from __future__ import annotations


def test_dashboard_response_has_manager_fields() -> None:
    """DashboardMetricsResponse includes manager and feedback KPIs."""
    from src.schemas.admin import DashboardMetricsResponse

    response = DashboardMetricsResponse(period="week")

    assert hasattr(response, "avg_manager_score")
    assert hasattr(response, "avg_manager_response_time_seconds")
    assert hasattr(response, "manager_deal_conversion_rate")
    assert hasattr(response, "manager_leaderboard")
    assert hasattr(response, "feedback_count")
    assert hasattr(response, "avg_rating_overall")
    assert hasattr(response, "avg_rating_delivery")
    assert hasattr(response, "nps_score")
    assert hasattr(response, "recommend_rate")

    # Defaults
    assert response.avg_manager_score == 0.0
    assert response.avg_manager_response_time_seconds == 0.0
    assert response.manager_deal_conversion_rate == 0.0
    assert response.manager_leaderboard == []
    assert response.feedback_count == 0
    assert response.avg_rating_overall == 0.0
    assert response.avg_rating_delivery == 0.0
    assert response.nps_score == 0.0
    assert response.recommend_rate == 0.0


def test_dashboard_response_with_manager_and_feedback_data() -> None:
    """DashboardMetricsResponse accepts manager and feedback KPI data."""
    from src.schemas.admin import DashboardMetricsResponse
    from src.schemas.manager_review import ManagerLeaderboardEntry

    response = DashboardMetricsResponse(
        period="week",
        avg_manager_score=16.2,
        avg_manager_response_time_seconds=480.0,
        manager_deal_conversion_rate=65.0,
        manager_leaderboard=[
            ManagerLeaderboardEntry(name="Israullah", avg_score=17.5, reviews_count=10),
            ManagerLeaderboardEntry(name="Annabelle", avg_score=16.8, reviews_count=8),
        ],
        feedback_count=24,
        avg_rating_overall=4.6,
        avg_rating_delivery=4.3,
        nps_score=58.3,
        recommend_rate=79.2,
    )

    assert response.avg_manager_score == 16.2
    assert len(response.manager_leaderboard) == 2
    assert response.manager_leaderboard[0].name == "Israullah"
    assert response.feedback_count == 24
    assert response.avg_rating_overall == 4.6
    assert response.avg_rating_delivery == 4.3
    assert response.nps_score == 58.3
    assert response.recommend_rate == 79.2
