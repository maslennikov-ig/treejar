"""Tests for quality background jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_evaluation_result(score: float = 30.0):
    from src.quality.schemas import BlockScore, CriterionScore, EvaluationResult

    criteria = [
        CriterionScore(
            rule_number=i,
            rule_name=f"Rule {i}",
            score=2,
            comment="ok",
            applicable=True,
        )
        for i in range(1, 16)
    ]
    return EvaluationResult(
        criteria=criteria,
        summary="Что сделано хорошо:\n- Сильное начало\n\nЧто ухудшило диалог:\n- н/д",
        total_score=score,
        rating="excellent",
        strengths=["Strong opening"],
        weaknesses=["No major issues"],
        recommendations=["Keep the same structure"],
        next_best_action="Send the requested quotation.",
        block_scores=[
            BlockScore(
                block_name="Opening & Trust", weight=6.0, points=6.0, applicable_rules=4
            ),
            BlockScore(
                block_name="Relationship & Discovery",
                weight=9.0,
                points=9.0,
                applicable_rules=5,
            ),
            BlockScore(
                block_name="Consultative Solution",
                weight=9.0,
                points=9.0,
                applicable_rules=3,
            ),
            BlockScore(
                block_name="Conversion & Next Step",
                weight=6.0,
                points=6.0,
                applicable_rules=3,
            ),
        ],
    )


def _make_red_flag_result(flag_codes: list[str]):
    from src.quality.schemas import RedFlagEvaluationResult, RedFlagItem

    flags = [
        RedFlagItem(
            code=code,
            title=code.replace("_", " ").title(),
            explanation=f"{code} explanation",
            evidence=[f"{code} evidence 1", f"{code} evidence 2"],
        )
        for code in flag_codes
    ]
    return RedFlagEvaluationResult(
        flags=flags,
        recommended_action="Review the conversation before the customer disengages.",
    )


def _make_candidate(
    *,
    status: str = "active",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
    sales_stage: str = "greeting",
    phone: str = "+971501234567",
    customer_name: str | None = "Acme",
    metadata_: dict[str, str] | None = None,
):
    return SimpleNamespace(
        conversation_id=uuid4(),
        status=status,
        created_at=created_at or datetime.now(tz=UTC) - timedelta(hours=1),
        updated_at=updated_at or datetime.now(tz=UTC),
        sales_stage=sales_stage,
        phone=phone,
        customer_name=customer_name,
        metadata_=(
            {"inbound_channel_phone": "+971551220665"}
            if metadata_ is None
            else metadata_
        ),
    )


def _make_session_ctx(mock_db: AsyncMock) -> AsyncMock:
    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_db
    mock_session_ctx.__aexit__.return_value = False
    return mock_session_ctx


@pytest.mark.asyncio
async def test_red_flag_warning_fires_only_when_flags_exist() -> None:
    """Realtime warning job should notify only for actual red flags."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate_a = _make_candidate()
    candidate_b = _make_candidate(sales_stage="qualifying")
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
            ],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate_a, candidate_b]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(
                side_effect=[
                    _make_red_flag_result([]),
                    _make_red_flag_result(["missing_identity"]),
                ]
            ),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis})

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_warning_passes_identity_context_without_crm_lookup() -> None:
    """Realtime warning should thread identity fields and prefer conversation name."""
    from src.quality.job import evaluate_realtime_red_flags

    created_at = datetime(2026, 4, 9, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 9, 10, 0, tzinfo=UTC)
    candidate = _make_candidate(
        created_at=created_at,
        updated_at=updated_at,
        customer_name="Acme",
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_crm = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis, "crm_client": mock_crm})

    mock_notify.assert_awaited_once()
    kwargs = mock_notify.await_args.kwargs
    assert kwargs["customer_name"] == "Acme"
    assert kwargs["inbound_channel_phone"] == "+971551220665"
    assert kwargs["conversation_created_at"] == created_at
    assert kwargs["last_activity_at"] == updated_at
    mock_crm.find_contact_by_phone.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_red_flag_signature_does_not_repeat() -> None:
    """Realtime warning job should suppress duplicate signatures."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    marker = {
        "signature": "same-signature",
        "updated_at": candidate.updated_at.isoformat(),
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(marker))
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch(
            "src.quality.job._build_red_flag_signature",
            return_value="same-signature",
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis})

    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_red_flag_signature_realerts() -> None:
    """Realtime warning job should re-alert when the flag signature changes."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate()
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    marker = {
        "signature": "old-signature",
        "updated_at": candidate.updated_at.isoformat(),
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(marker))
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(
                return_value=_make_red_flag_result(
                    ["missing_identity", "ignored_question"]
                )
            ),
        ),
        patch(
            "src.quality.job._build_red_flag_signature",
            return_value="new-signature",
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis})

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_warning_skips_telegram_for_blocked_inbound_phone() -> None:
    """Realtime warning job should stay fail-closed outside the allowed inbound."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate = _make_candidate(metadata_={"inbound_channel_phone": "+971509999999"})
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
        patch(
            "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
            "+971551220665",
        ),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis})

    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_red_flag_warning_paginates_full_candidate_set() -> None:
    """Realtime warning job should keep reading candidate pages beyond the first batch."""
    from src.quality.job import evaluate_realtime_red_flags

    candidate_a = _make_candidate()
    candidate_b = _make_candidate()
    candidate_c = _make_candidate()
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    worker_db_c = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    fetch_mock = AsyncMock(return_value=[candidate_a, candidate_b])
    fetch_mock.side_effect = [[candidate_a, candidate_b], [candidate_c]]

    with (
        patch("src.quality.job._QUERY_BATCH_SIZE", 2),
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
                _make_session_ctx(worker_db_c),
            ],
        ),
        patch(
            "src.quality.job.get_recent_assistant_conversation_candidates",
            new=fetch_mock,
        ),
        patch(
            "src.quality.job.evaluate_red_flags",
            new=AsyncMock(return_value=_make_red_flag_result(["missing_identity"])),
        ),
        patch("src.services.notifications.notify_red_flag_warning", new=mock_notify),
    ):
        await evaluate_realtime_red_flags({"redis": mock_redis})

    assert fetch_mock.await_count == 2
    assert fetch_mock.await_args_list[0].kwargs["offset"] == 0
    assert fetch_mock.await_args_list[1].kwargs["offset"] == 2
    assert mock_notify.await_count == 3


@pytest.mark.asyncio
async def test_final_review_triggers_on_closed() -> None:
    """Final review job should send a review for closed conversations."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(status="closed", updated_at=datetime.now(tz=UTC))
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_save = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=mock_save),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    mock_save.assert_awaited_once()
    mock_notify.assert_awaited_once()
    assert mock_notify.await_args.kwargs["trigger"] == "closed"
    worker_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_fetches_customer_name_from_crm_and_caches_it() -> None:
    """Final review should enrich customer name from Zoho when conversation/cache miss."""
    from src.quality.job import evaluate_mature_conversations_quality

    created_at = datetime(2026, 4, 9, 9, 0, tzinfo=UTC)
    updated_at = datetime(2026, 4, 9, 13, 5, tzinfo=UTC)
    candidate = _make_candidate(
        status="closed",
        created_at=created_at,
        updated_at=updated_at,
        customer_name=None,
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.set = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_crm = AsyncMock()
    mock_crm.find_contact_by_phone = AsyncMock(
        return_value={
            "First_Name": "Aisha",
            "Last_Name": "Khan",
            "Segment": "B2B",
        }
    )

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality(
            {"redis": mock_redis, "crm_client": mock_crm}
        )

    mock_notify.assert_awaited_once()
    kwargs = mock_notify.await_args.kwargs
    assert kwargs["customer_name"] == "Aisha Khan"
    assert kwargs["inbound_channel_phone"] == "+971551220665"
    assert kwargs["conversation_created_at"] == created_at
    assert kwargs["last_activity_at"] == updated_at
    mock_crm.find_contact_by_phone.assert_awaited_once_with("+971501234567")
    mock_redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_triggers_on_idle_threshold() -> None:
    """Final review job should send a review after 3 hours of inactivity."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        updated_at=datetime.now(tz=UTC) - timedelta(hours=3, minutes=5),
        sales_stage="solution",
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=21.0)),
        ),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    mock_notify.assert_awaited_once()
    assert mock_notify.await_args.kwargs["trigger"] == "idle 3h"


@pytest.mark.asyncio
async def test_final_review_does_not_trigger_before_idle_threshold() -> None:
    """Final review job should skip active conversations before 3 hours of inactivity."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        updated_at=datetime.now(tz=UTC) - timedelta(hours=2, minutes=59)
    )
    query_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_notify = AsyncMock()
    mock_evaluate = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            return_value=_make_session_ctx(query_db),
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch("src.quality.job.evaluate_conversation", new=mock_evaluate),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    mock_evaluate.assert_not_awaited()
    mock_notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_final_review_paginates_full_candidate_set() -> None:
    """Final review job should keep evaluating pages beyond the first candidate batch."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate_a = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=4)
    )
    candidate_b = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=5)
    )
    candidate_c = _make_candidate(
        status="closed", updated_at=datetime.now(tz=UTC) - timedelta(hours=6)
    )
    query_db = AsyncMock()
    worker_db_a = AsyncMock()
    worker_db_b = AsyncMock()
    worker_db_c = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None, None])
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    fetch_mock = AsyncMock(side_effect=[[candidate_a, candidate_b], [candidate_c]])

    with (
        patch("src.quality.job._QUERY_BATCH_SIZE", 2),
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[
                _make_session_ctx(query_db),
                _make_session_ctx(worker_db_a),
                _make_session_ctx(worker_db_b),
                _make_session_ctx(worker_db_c),
            ],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=fetch_mock,
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    assert fetch_mock.await_count == 2
    assert fetch_mock.await_args_list[0].kwargs["offset"] == 0
    assert fetch_mock.await_args_list[1].kwargs["offset"] == 2
    assert mock_notify.await_count == 3


@pytest.mark.asyncio
async def test_final_review_retriggers_after_new_activity() -> None:
    """Final review job should send a new review when updated_at changed since last review."""
    from src.quality.job import evaluate_mature_conversations_quality

    old_updated_at = datetime.now(tz=UTC) - timedelta(hours=6)
    new_updated_at = datetime.now(tz=UTC) - timedelta(hours=4)
    candidate = _make_candidate(updated_at=new_updated_at, sales_stage="quoting")
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=old_updated_at.isoformat())
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=24.0)),
        ),
        patch("src.quality.job.save_review", new=AsyncMock()),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    mock_notify.assert_awaited_once()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_final_review_skips_telegram_for_missing_inbound_phone() -> None:
    """Final review should persist marker but skip Telegram when inbound is unknown."""
    from src.quality.job import evaluate_mature_conversations_quality

    candidate = _make_candidate(
        status="closed",
        updated_at=datetime.now(tz=UTC) - timedelta(hours=4),
        metadata_={},
    )
    query_db = AsyncMock()
    worker_db = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.setex = AsyncMock()
    mock_notify = AsyncMock()
    mock_save = AsyncMock()

    with (
        patch(
            "src.quality.job.async_session_factory",
            side_effect=[_make_session_ctx(query_db), _make_session_ctx(worker_db)],
        ),
        patch(
            "src.quality.job.get_recent_updated_conversation_candidates",
            new=AsyncMock(return_value=[candidate]),
        ),
        patch(
            "src.quality.job.evaluate_conversation",
            new=AsyncMock(return_value=_make_evaluation_result(score=18.0)),
        ),
        patch("src.quality.job.save_review", new=mock_save),
        patch(
            "src.services.notifications.notify_final_quality_review", new=mock_notify
        ),
        patch(
            "src.services.inbound_channels.settings.telegram_allowed_inbound_phone",
            "+971551220665",
        ),
    ):
        await evaluate_mature_conversations_quality({"redis": mock_redis})

    mock_save.assert_awaited_once()
    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_review_updates_existing_review_when_present() -> None:
    """save_review should update an existing quality review instead of inserting."""
    from src.quality.service import save_review

    conv_id = uuid4()
    existing_review = MagicMock()
    existing_review.conversation_id = conv_id
    existing_review.total_score = 12.0
    existing_review.max_score = 30
    existing_review.criteria = []
    existing_review.rating = "poor"
    existing_review.summary = "Old summary"
    existing_review.reviewer = "ai"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_review

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()

    result = await save_review(mock_db, conv_id, _make_evaluation_result())

    assert result is existing_review
    assert existing_review.total_score == 30.0
    assert existing_review.rating == "excellent"
    assert "Что сделано хорошо" in existing_review.summary
    mock_db.add.assert_not_called()
    mock_db.flush.assert_awaited_once()
