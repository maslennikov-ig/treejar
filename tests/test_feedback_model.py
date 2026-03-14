"""Tests for the Feedback model and save_feedback LLM tool."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm.engine import SalesDeps
from src.models.conversation import Conversation
from src.models.feedback import Feedback
from src.schemas.common import SalesStage

# ── Model Tests ──


class TestFeedbackModel:
    """Tests for Feedback model instantiation and fields."""

    def test_create_feedback_all_fields(self) -> None:
        """Test that a Feedback object is created with all fields."""
        conv_id = uuid.uuid4()
        fb = Feedback(
            conversation_id=conv_id,
            deal_id="DEAL123",
            rating_overall=5,
            rating_delivery=4,
            recommend=True,
            comment="Great service!",
        )
        assert fb.conversation_id == conv_id
        assert fb.deal_id == "DEAL123"
        assert fb.rating_overall == 5
        assert fb.rating_delivery == 4
        assert fb.recommend is True
        assert fb.comment == "Great service!"

    def test_create_feedback_minimal(self) -> None:
        """Test feedback with only required fields."""
        conv_id = uuid.uuid4()
        fb = Feedback(
            conversation_id=conv_id,
            rating_overall=3,
            rating_delivery=3,
            recommend=False,
        )
        assert fb.conversation_id == conv_id
        assert fb.deal_id is None
        assert fb.comment is None
        assert fb.recommend is False

    def test_feedback_has_correct_tablename(self) -> None:
        assert Feedback.__tablename__ == "feedbacks"


# ── SalesStage Tests ──


class TestFeedbackStage:
    """Tests for FEEDBACK stage integration."""

    def test_feedback_stage_exists(self) -> None:
        assert SalesStage.FEEDBACK.value == "feedback"
        assert "feedback" in [s.value for s in SalesStage]

    def test_feedback_in_allowed_transitions(self) -> None:
        from src.llm.engine import ALLOWED_TRANSITIONS

        assert SalesStage.FEEDBACK in ALLOWED_TRANSITIONS.get(
            SalesStage.CLOSING, []
        ), "CLOSING should be able to transition to FEEDBACK"

    def test_feedback_prompt_exists(self) -> None:
        from src.llm.prompts import STAGE_RULES

        assert "feedback" in STAGE_RULES, "STAGE_RULES should have feedback key"
        assert "save_feedback" in STAGE_RULES["feedback"]


# ── LLM Tool Tests ──


@pytest.fixture
def feedback_deps() -> tuple[
    AsyncMock, Conversation, AsyncMock, AsyncMock, AsyncMock, AsyncMock, AsyncMock
]:
    """Mock deps for feedback tool testing."""
    db = AsyncMock()
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        sales_stage=SalesStage.FEEDBACK.value,
        language="en",
        escalation_status="none",
        zoho_deal_id="DEAL-999",
    )
    db.get.return_value = conv

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_config_result = MagicMock()
    mock_config_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one_or_none.return_value = None  # No existing feedback
    db.execute.return_value = mock_result

    engine = AsyncMock()
    zoho = AsyncMock()
    zoho_crm = AsyncMock()
    redis = AsyncMock()
    redis.get.return_value = None
    messaging = AsyncMock()

    return db, conv, engine, zoho, zoho_crm, redis, messaging


class TestSaveFeedbackTool:
    """Tests for the save_feedback LLM tool."""

    @pytest.mark.asyncio
    async def test_save_feedback_success(
        self,
        feedback_deps: tuple[
            AsyncMock,
            Conversation,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test that save_feedback creates a Feedback record."""
        db, conv, engine, zoho, zoho_crm, redis, messaging = feedback_deps
        deps = SalesDeps(
            db=db,
            conversation=conv,
            embedding_engine=engine,
            zoho_inventory=zoho,
            zoho_crm=zoho_crm,
            messaging_client=messaging,
            pii_map={},
            redis=redis,
        )
        from pydantic_ai import RunContext

        from src.llm.engine import save_feedback

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="",
            model=TestModel(),
            usage=RunUsage(),
        )

        result = await save_feedback(
            ctx,
            rating_overall=5,
            rating_delivery=4,
            recommend=True,
            comment="Excellent!",
        )

        assert "saved" in result.lower() or "thank" in result.lower()
        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, Feedback)
        assert added_obj.rating_overall == 5
        assert added_obj.rating_delivery == 4
        assert added_obj.recommend is True
        assert added_obj.comment == "Excellent!"
        assert added_obj.conversation_id == conv.id

    @pytest.mark.asyncio
    async def test_save_feedback_without_comment(
        self,
        feedback_deps: tuple[
            AsyncMock,
            Conversation,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test save_feedback with optional comment omitted."""
        db, conv, engine, zoho, zoho_crm, redis, messaging = feedback_deps
        deps = SalesDeps(
            db=db,
            conversation=conv,
            embedding_engine=engine,
            zoho_inventory=zoho,
            zoho_crm=zoho_crm,
            messaging_client=messaging,
            pii_map={},
            redis=redis,
        )
        from pydantic_ai import RunContext

        from src.llm.engine import save_feedback

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="",
            model=TestModel(),
            usage=RunUsage(),
        )

        result = await save_feedback(
            ctx,
            rating_overall=3,
            rating_delivery=2,
            recommend=False,
        )

        assert "saved" in result.lower() or "thank" in result.lower()
        added_obj = db.add.call_args[0][0]
        assert added_obj.comment is None
        assert added_obj.recommend is False

    @pytest.mark.asyncio
    async def test_save_feedback_invalid_rating(
        self,
        feedback_deps: tuple[
            AsyncMock,
            Conversation,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test save_feedback rejects invalid ratings."""
        db, conv, engine, zoho, zoho_crm, redis, messaging = feedback_deps
        deps = SalesDeps(
            db=db,
            conversation=conv,
            embedding_engine=engine,
            zoho_inventory=zoho,
            zoho_crm=zoho_crm,
            messaging_client=messaging,
            pii_map={},
            redis=redis,
        )
        from pydantic_ai import RunContext

        from src.llm.engine import save_feedback

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="",
            model=TestModel(),
            usage=RunUsage(),
        )

        from pydantic_ai import ModelRetry

        with pytest.raises(ModelRetry, match="(?i)invalid|between"):
            await save_feedback(
                ctx,
                rating_overall=0,
                rating_delivery=6,
                recommend=True,
            )

    @pytest.mark.asyncio
    async def test_save_feedback_duplicate(
        self,
        feedback_deps: tuple[
            AsyncMock,
            Conversation,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
    ) -> None:
        """Test save_feedback returns message if feedback already exists."""
        db, conv, engine, zoho, zoho_crm, redis, messaging = feedback_deps

        # Mock existing feedback found
        mock_existing = MagicMock()
        mock_existing.scalar_one_or_none.return_value = uuid.uuid4()
        db.execute.return_value = mock_existing

        deps = SalesDeps(
            db=db,
            conversation=conv,
            embedding_engine=engine,
            zoho_inventory=zoho,
            zoho_crm=zoho_crm,
            messaging_client=messaging,
            pii_map={},
            redis=redis,
        )
        from pydantic_ai import RunContext

        from src.llm.engine import save_feedback

        ctx = RunContext(
            deps=deps,
            retry=0,
            messages=[],
            prompt="",
            model=TestModel(),
            usage=RunUsage(),
        )

        result = await save_feedback(
            ctx,
            rating_overall=5,
            rating_delivery=4,
            recommend=True,
        )

        assert "already" in result.lower()
        db.add.assert_not_called()
