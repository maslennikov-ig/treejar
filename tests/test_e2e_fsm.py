"""E2E tests for SalesStage FSM traversal (advance_stage tool).

Covers:
  - Valid transitions through ALLOWED_TRANSITIONS.
  - Invalid/disallowed transitions return error strings.
  - Multi-turn traversal from GREETING through to CLOSING.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import (
    ALLOWED_TRANSITIONS,
    SalesDeps,
    advance_stage,
)
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_deps(
    conv: Conversation,
    *,
    db: AsyncSession | None = None,
    redis: Redis | None = None,
) -> SalesDeps:
    """Build a minimal SalesDeps with the given conversation."""
    return SalesDeps(
        db=db or AsyncMock(spec=AsyncSession),
        redis=redis or AsyncMock(spec=Redis),
        conversation=conv,
        embedding_engine=AsyncMock(spec=EmbeddingEngine),
        zoho_inventory=AsyncMock(spec=ZohoInventoryClient),
        zoho_crm=AsyncMock(spec=ZohoCRMClient),
        messaging_client=AsyncMock(spec=MessagingProvider),
        pii_map={},
    )


def _make_conversation(stage: SalesStage) -> Any:
    """Create a lightweight in-memory Conversation stub via MagicMock."""
    conv = MagicMock(spec=Conversation)
    conv.phone = "+971500000001"
    conv.sales_stage = stage.value
    conv.language = "en"
    conv.customer_name = None
    conv.escalation_status = "none"
    return conv


# ---------------------------------------------------------------------------
# advance_stage tool is decorated with @sales_agent.tool which wraps it in
# a ToolDefinition. We invoke the *raw* inner function directly by importing
# it (the module-level function, not the registered wrapper). Pydantic-AI
# tool functions expect a RunContext[SalesDeps] as first arg.
# ---------------------------------------------------------------------------

@dataclass
class _FakeRunContext:
    """Minimal RunContext-like object carrying deps."""
    deps: SalesDeps


# ---------------------------------------------------------------------------
# Tests: valid transitions
# ---------------------------------------------------------------------------


class TestAdvanceStageValid:
    """Every transition listed in ALLOWED_TRANSITIONS should succeed."""

    @pytest.mark.asyncio
    async def test_greeting_to_qualifying(self) -> None:
        conv = _make_conversation(SalesStage.GREETING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.QUALIFYING)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.QUALIFYING.value

    @pytest.mark.asyncio
    async def test_qualifying_to_needs_analysis(self) -> None:
        conv = _make_conversation(SalesStage.QUALIFYING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.NEEDS_ANALYSIS)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.NEEDS_ANALYSIS.value

    @pytest.mark.asyncio
    async def test_needs_analysis_to_solution(self) -> None:
        conv = _make_conversation(SalesStage.NEEDS_ANALYSIS)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.SOLUTION)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.SOLUTION.value

    @pytest.mark.asyncio
    async def test_solution_to_company_details(self) -> None:
        conv = _make_conversation(SalesStage.SOLUTION)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.COMPANY_DETAILS)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.COMPANY_DETAILS.value

    @pytest.mark.asyncio
    async def test_company_details_to_quoting(self) -> None:
        conv = _make_conversation(SalesStage.COMPANY_DETAILS)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.QUOTING)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.QUOTING.value

    @pytest.mark.asyncio
    async def test_quoting_to_closing(self) -> None:
        conv = _make_conversation(SalesStage.QUOTING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.CLOSING)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.CLOSING.value


# ---------------------------------------------------------------------------
# Tests: invalid / disallowed transitions
# ---------------------------------------------------------------------------


class TestAdvanceStageInvalid:
    """Transitions NOT listed in ALLOWED_TRANSITIONS must return an error."""

    @pytest.mark.asyncio
    async def test_greeting_to_closing_rejected(self) -> None:
        conv = _make_conversation(SalesStage.GREETING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.CLOSING)  # type: ignore[arg-type]
        assert "Cannot transition" in result
        # Stage must remain unchanged
        assert conv.sales_stage == SalesStage.GREETING.value

    @pytest.mark.asyncio
    async def test_closing_to_greeting_rejected(self) -> None:
        conv = _make_conversation(SalesStage.CLOSING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.GREETING)  # type: ignore[arg-type]
        assert "Cannot transition" in result
        assert conv.sales_stage == SalesStage.CLOSING.value

    @pytest.mark.asyncio
    async def test_greeting_to_solution_rejected(self) -> None:
        conv = _make_conversation(SalesStage.GREETING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.SOLUTION)  # type: ignore[arg-type]
        assert "Cannot transition" in result

    @pytest.mark.asyncio
    async def test_closing_has_no_exits(self) -> None:
        """CLOSING is a terminal state, no transitions allowed."""
        conv = _make_conversation(SalesStage.CLOSING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        for stage in SalesStage:
            result = await advance_stage(ctx, stage)  # type: ignore[arg-type]
            assert "Cannot transition" in result


# ---------------------------------------------------------------------------
# Tests: backward transitions
# ---------------------------------------------------------------------------


class TestAdvanceStageBackward:
    """Some backward transitions are allowed (e.g. SOLUTION -> NEEDS_ANALYSIS)."""

    @pytest.mark.asyncio
    async def test_solution_back_to_needs_analysis(self) -> None:
        conv = _make_conversation(SalesStage.SOLUTION)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.NEEDS_ANALYSIS)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.NEEDS_ANALYSIS.value

    @pytest.mark.asyncio
    async def test_quoting_back_to_solution(self) -> None:
        conv = _make_conversation(SalesStage.QUOTING)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.SOLUTION)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.SOLUTION.value

    @pytest.mark.asyncio
    async def test_needs_analysis_back_to_qualifying(self) -> None:
        conv = _make_conversation(SalesStage.NEEDS_ANALYSIS)
        ctx = _FakeRunContext(deps=_make_deps(conv))
        result = await advance_stage(ctx, SalesStage.QUALIFYING)  # type: ignore[arg-type]
        assert "Successfully advanced" in result
        assert conv.sales_stage == SalesStage.QUALIFYING.value


# ---------------------------------------------------------------------------
# Tests: multi-turn full funnel traversal
# ---------------------------------------------------------------------------


class TestFullFunnelTraversal:
    """Simulate a complete walk through the funnel."""

    @pytest.mark.asyncio
    async def test_full_happy_path(self) -> None:
        """GREETING → QUALIFYING → NEEDS → SOLUTION → COMPANY → QUOTING → CLOSING."""
        happy_path = [
            SalesStage.QUALIFYING,
            SalesStage.NEEDS_ANALYSIS,
            SalesStage.SOLUTION,
            SalesStage.COMPANY_DETAILS,
            SalesStage.QUOTING,
            SalesStage.CLOSING,
        ]
        conv = _make_conversation(SalesStage.GREETING)
        ctx = _FakeRunContext(deps=_make_deps(conv))

        for target in happy_path:
            result = await advance_stage(ctx, target)  # type: ignore[arg-type]
            assert "Successfully advanced" in result, f"Failed at {target}: {result}"
            assert conv.sales_stage == target.value


# ---------------------------------------------------------------------------
# Tests: ALLOWED_TRANSITIONS completeness sanity check
# ---------------------------------------------------------------------------


class TestAllowedTransitionsMap:
    """Ensure the transition map covers every stage."""

    def test_every_stage_has_an_entry(self) -> None:
        for stage in SalesStage:
            assert stage in ALLOWED_TRANSITIONS, f"{stage} missing from ALLOWED_TRANSITIONS"
