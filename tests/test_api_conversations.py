import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.database import get_db
from src.main import app
from src.models.conversation import Conversation
from src.models.message import Message


async def override_get_db() -> None:
    pass


@pytest.fixture
async def mock_db() -> AsyncGenerator[AsyncMock, None]:
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_conversations(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    # Pagination count
    mock_result.scalar_one_or_none.return_value = 1
    # Items
    conv = Conversation(
        id=uuid.uuid4(),
        phone="12345",
        language="en",
        status="active",
        sales_stage="greeting",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={}
    )
    mock_result.scalars.return_value.all.return_value = [conv]

    # We execute count_stmt and stmt, so side_effect is best
    mock_db.execute.side_effect = [mock_result, mock_result]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/conversations/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["phone"] == "12345"
    assert data["items"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_get_conversation_success(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock

    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        phone="123",
        sales_stage="qualifying",
        language="en",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={}
    )
    conv.metadata = {}  # type: ignore[misc, assignment]
    conv.messages = [
        Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content="Hi",
            message_type="text",
            created_at=datetime.now(UTC)
        )
    ]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/conversations/{conv_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(conv_id)
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hi"


@pytest.mark.asyncio
async def test_get_conversation_not_found(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/api/v1/conversations/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_update_conversation_success(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock

    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        phone="555",
        language="en",
        sales_stage="greeting",
        status="active",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={}
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result

    update_payload = {"status": "paused"}  # Must match ConversationStatus enum
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(f"/api/v1/conversations/{conv_id}", json=update_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(conv_id)
    assert data["status"] == "paused"
    assert conv.status == "paused"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_conversation_not_found(mock_db: AsyncMock) -> None:
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.patch(f"/api/v1/conversations/{uuid.uuid4()}", json={"status": "paused"})

    assert response.status_code == 404
