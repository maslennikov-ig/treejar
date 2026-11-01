import pytest

from src.core.cache import (
    CRM_NEGATIVE_CACHE_KEY_PREFIX,
    CRM_NEGATIVE_CACHE_TTL_SECONDS,
    CRM_NOT_FOUND_SENTINEL,
    get_cached_crm_profile,
    invalidate_crm_contact_cache,
    is_crm_contact_negatively_cached,
    set_cached_crm_profile,
    set_crm_contact_negative_cache,
)


class MockRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value
        self.ttls[key] = ex

    async def delete(self, key: str) -> None:
        self.data.pop(key, None)
        self.ttls.pop(key, None)


@pytest.fixture
def mock_redis() -> MockRedis:
    return MockRedis()


@pytest.mark.asyncio
async def test_crm_profile_cache(mock_redis: MockRedis) -> None:
    phone = "+971501234567"
    profile = {"Name": "Test", "Segment": "VIP"}

    # Should be empty initially
    assert await get_cached_crm_profile(mock_redis, phone) is None

    # Should save and retrieve
    await set_cached_crm_profile(mock_redis, phone, profile, ttl=3600)
    cached = await get_cached_crm_profile(mock_redis, phone)
    assert cached == profile


@pytest.mark.asyncio
async def test_crm_negative_cache_and_invalidation(mock_redis: MockRedis) -> None:
    phone = "+971509998877"
    assert await is_crm_contact_negatively_cached(mock_redis, phone) is False

    await set_crm_contact_negative_cache(mock_redis, phone)
    assert await is_crm_contact_negatively_cached(mock_redis, phone) is True
    assert (
        mock_redis.ttls[f"{CRM_NEGATIVE_CACHE_KEY_PREFIX}{phone}"]
        == CRM_NEGATIVE_CACHE_TTL_SECONDS
    )

    # Sentinel written directly to crm_profile must never leak as a valid profile dict
    await set_cached_crm_profile(mock_redis, phone, CRM_NOT_FOUND_SENTINEL)
    assert await get_cached_crm_profile(mock_redis, phone) is None

    # Invalidation clears both formatted and bare digit variants
    await invalidate_crm_contact_cache(mock_redis, "971509998877")
    assert await is_crm_contact_negatively_cached(mock_redis, phone) is False
    assert f"crm_profile:{phone}" not in mock_redis.data
