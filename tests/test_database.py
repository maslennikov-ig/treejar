from unittest.mock import AsyncMock, patch

import pytest

from src.core.database import get_db


@pytest.mark.asyncio
async def test_get_db_success() -> None:
    # Test normal lifecycle with commit
    mock_session = AsyncMock()

    with patch("src.core.database.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session

        gen = get_db()
        session = await anext(gen)

        assert session == mock_session

        import contextlib
        # Generator closing simulates successful yielded context exit
        with contextlib.suppress(StopAsyncIteration):
            await anext(gen)

        mock_session.commit.assert_awaited_once()
        mock_session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_get_db_exception() -> None:
    # Test error lifecycle with rollback
    mock_session = AsyncMock()

    with patch("src.core.database.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session

        gen = get_db()
        session = await anext(gen)

        assert session == mock_session

        # Inject an exception into the generator to simulate error in route
        with pytest.raises(ValueError):
            await gen.athrow(ValueError("Test exception"))

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_called()
