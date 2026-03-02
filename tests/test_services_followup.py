import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus
from src.services.followup import run_automatic_followups


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Mock the async DB session."""
    session = AsyncMock(spec=AsyncSession)

    # We mock the return value for db.execute().scalars().all()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    session.execute.return_value = mock_result
    return session

@pytest.mark.asyncio
async def test_run_automatic_followups_queries_db(mock_db_session: AsyncMock) -> None:
    # We patch the database session context manager
    with patch("src.services.followup.async_session_factory") as mock_session_maker:
        mock_session_maker.return_value.__aenter__.return_value = mock_db_session

        # Also mock _process_followup_for_conversation to ensure it's called
        with patch("src.services.followup._process_followup_for_conversation") as mock_process:
            # Provide some mock conversations to return
            now = datetime.datetime.now(datetime.UTC)
            conv_24h = Conversation(
                id=uuid.uuid4(),
                phone="1",
                updated_at=now - datetime.timedelta(hours=24, minutes=30),
                escalation_status=EscalationStatus.NONE.value
            )

            # Setup db execute to return different conversations for different queries
            # For simplicity, we just return one conv on the first query and [] for others
            mock_result = MagicMock()
            mock_scalars = MagicMock()

            # The order of execution: 24h, 72h, 168h
            mock_scalars.all.side_effect = [
                [conv_24h], # 24h
                [],         # 72h
                []          # 168h
            ]
            mock_result.scalars.return_value = mock_scalars
            mock_db_session.execute.return_value = mock_result

            await run_automatic_followups({})

            assert mock_db_session.execute.call_count == 3
            mock_process.assert_called_once_with(mock_db_session, conv_24h)
