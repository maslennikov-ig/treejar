import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.database import get_db
from src.main import app
from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus


@pytest.fixture
async def mock_db() -> AsyncGenerator[AsyncMock, None]:
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_escalate_conversation(mock_db: AsyncMock):
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        phone="555",
        language="en",
        sales_stage="greeting",
        status="active",
        escalation_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={},
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(f"/api/v1/conversations/{conv_id}/escalate")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["escalation_status"] == EscalationStatus.PENDING.value
    assert conv.escalation_status == EscalationStatus.PENDING.value
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_escalate_conversation_not_found(mock_db: AsyncMock):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    random_id = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.post(f"/api/v1/conversations/{random_id}/escalate")

    assert resp.status_code == 404
