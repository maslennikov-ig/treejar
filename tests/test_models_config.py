import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.config import get_system_config
from src.models.system_config import SystemConfig

@pytest.mark.asyncio
async def test_get_system_config():
    # Setup mock db
    mock_db = AsyncMock()
    mock_result = MagicMock()
    
    # Test 1: Config exists
    mock_config = SystemConfig(key="test_key", value="test_value")
    mock_result.scalar_one_or_none.return_value = mock_config
    mock_db.execute.return_value = mock_result
    
    val = await get_system_config(mock_db, "test_key", "default_val")
    assert val == "test_value"
    
    # Test 2: Config does not exist
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    val_missing = await get_system_config(mock_db, "missing_key", "default_val")
    assert val_missing == "default_val"
