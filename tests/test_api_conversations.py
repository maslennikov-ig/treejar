import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.core.config import settings
from src.core.database import get_db
from src.main import app
from src.models.conversation import Conversation
from src.models.message import Message

API_KEY = "expected-key"
AUTH_HEADERS = {"X-API-Key": API_KEY}


async def override_get_db() -> None:
    pass


@pytest.fixture(autouse=True)
def require_conversation_api_key() -> Generator[None, None, None]:
    original_env = settings.app_env
    original_api_key = settings.api_key
    settings.app_env = "production"
    settings.api_key = API_KEY
    yield
    settings.app_env = original_env
    settings.api_key = original_api_key


@pytest.fixture
async def mock_db() -> AsyncGenerator[AsyncMock, None]:
    db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


def _executed_sql(mock_db: AsyncMock, call_index: int) -> str:
    statement = mock_db.execute.await_args_list[call_index].args[0]
    return str(statement)


@pytest.mark.asyncio
async def test_conversation_routes_reject_anonymous_requests(
    mock_db: AsyncMock,
) -> None:
    conv_id = uuid.uuid4()

    cases: list[tuple[str, str, dict[str, str] | None]] = [
        ("GET", "/api/v1/conversations/", None),
        ("GET", f"/api/v1/conversations/{conv_id}", None),
        ("PATCH", f"/api/v1/conversations/{conv_id}", {"status": "paused"}),
        ("POST", f"/api/v1/conversations/{conv_id}/escalate", None),
    ]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        for method, path, payload in cases:
            kwargs = {} if payload is None else {"json": payload}
            response = await ac.request(method, path, **kwargs)

            assert response.status_code == 403
            assert response.json()["detail"] == "Invalid or missing API key"

    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_conversations(mock_db: AsyncMock) -> None:
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
        escalation_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={},
    )
    mock_result.scalars.return_value.all.return_value = [conv]

    # We execute count_stmt and stmt, so side_effect is best
    mock_db.execute.side_effect = [mock_result, mock_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/conversations/", headers=AUTH_HEADERS)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["phone"] == "12345"
    assert data["items"][0]["status"] == "active"


@pytest.mark.asyncio
async def test_list_conversations_filters_phone_exact_by_default(
    mock_db: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 0
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [mock_result, mock_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/api/v1/conversations/",
            params={"phone": "+79262810921"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    count_sql = _executed_sql(mock_db, 0)
    list_sql = _executed_sql(mock_db, 1)
    assert "conversations.phone =" in count_sql
    assert "conversations.phone =" in list_sql
    assert "LIKE" not in count_sql.upper()
    assert "LIKE" not in list_sql.upper()


@pytest.mark.asyncio
async def test_list_conversations_can_filter_phone_fuzzy_explicitly(
    mock_db: AsyncMock,
) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 0
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.side_effect = [mock_result, mock_result]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            "/api/v1/conversations/",
            params={"phone": "2810921", "phone_match": "fuzzy"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    count_sql = _executed_sql(mock_db, 0)
    list_sql = _executed_sql(mock_db, 1)
    assert "LIKE" in count_sql.upper()
    assert "LIKE" in list_sql.upper()


@pytest.mark.asyncio
async def test_get_conversation_success(mock_db: AsyncMock) -> None:
    conv_id = uuid.uuid4()
    conv = Conversation(
        id=conv_id,
        phone="123",
        sales_stage="qualifying",
        language="en",
        status="active",
        escalation_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={},
    )
    conv.metadata = {}  # type: ignore[misc, assignment]
    conv.messages = [
        Message(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            role="user",
            content="Hi",
            message_type="text",
            created_at=datetime.now(UTC),
        )
    ]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv
    mock_db.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            f"/api/v1/conversations/{conv_id}", headers=AUTH_HEADERS
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(conv_id)
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hi"


@pytest.mark.asyncio
async def test_get_conversation_not_found(mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get(
            f"/api/v1/conversations/{uuid.uuid4()}", headers=AUTH_HEADERS
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_update_conversation_success(mock_db: AsyncMock) -> None:
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

    update_payload = {"status": "paused"}  # Must match ConversationStatus enum
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.patch(
            f"/api/v1/conversations/{conv_id}",
            json=update_payload,
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(conv_id)
    assert data["status"] == "paused"
    assert conv.status == "paused"
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_conversation_not_found(mock_db: AsyncMock) -> None:
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.patch(
            f"/api/v1/conversations/{uuid.uuid4()}",
            json={"status": "paused"},
            headers=AUTH_HEADERS,
        )

    assert response.status_code == 404
