from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql


@pytest.mark.asyncio
async def test_recent_assistant_candidates_avoid_grouping_by_json_metadata() -> None:
    from src.quality.service import get_recent_assistant_conversation_candidates

    mock_result = MagicMock()
    mock_result.all.return_value = []

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    since = datetime.now(tz=UTC) - timedelta(hours=4)

    await get_recent_assistant_conversation_candidates(mock_db, since=since)

    stmt = mock_db.execute.await_args.args[0]
    sql = str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "conversations.metadata" in sql
    assert "GROUP BY conversations.metadata" not in sql
    assert "GROUP BY messages.conversation_id" in sql
