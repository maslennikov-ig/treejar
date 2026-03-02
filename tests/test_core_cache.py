import pytest
from src.core.cache import get_cached_crm_profile, set_cached_crm_profile

class MockRedis:
    def __init__(self):
        self.data = {}
        
    async def get(self, key: str):
        return self.data.get(key)
        
    async def set(self, key: str, value: str, ex: int = None):
        self.data[key] = value

@pytest.fixture
def mock_redis():
    return MockRedis()

@pytest.mark.asyncio
async def test_crm_profile_cache(mock_redis):
    phone = "+971501234567"
    profile = {"Name": "Test", "Segment": "VIP"}
    
    # Should be empty initially
    assert await get_cached_crm_profile(mock_redis, phone) is None
    
    # Should save and retrieve
    await set_cached_crm_profile(mock_redis, phone, profile, ttl=3600)
    cached = await get_cached_crm_profile(mock_redis, phone)
    assert cached == profile
