from collections.abc import AsyncGenerator
from importlib.metadata import version as package_version
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_redis
from src.main import app


@pytest.fixture
async def health_dependencies() -> AsyncGenerator[tuple[AsyncMock, AsyncMock], None]:
    redis = AsyncMock()
    db = AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_db] = lambda: db
    yield redis, db
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_debug_redis_route_is_not_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis = AsyncMock()
    redis.llen.return_value = 1
    redis.lrange.return_value = [b"sensitive-queue-payload"]
    monkeypatch.setattr(app.state, "redis", redis, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/debug/redis")

    assert response.status_code == 404
    assert "sensitive-queue-payload" not in response.text
    redis.lrange.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("redis_fails", "db_fails", "expected_status"),
    [
        (False, False, 200),
        (True, False, 503),
        (False, True, 503),
        (True, True, 503),
    ],
    ids=["healthy", "redis-failed", "database-failed", "both-failed"],
)
async def test_health_status_reflects_required_dependencies(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    redis_fails: bool,
    db_fails: bool,
    expected_status: int,
) -> None:
    redis, db = health_dependencies
    if redis_fails:
        redis.ping.side_effect = RuntimeError("redis-secret-detail")
    if db_fails:
        db.execute.side_effect = RuntimeError("database-secret-detail")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == expected_status
    data = response.json()
    assert data["status"] == ("ok" if expected_status == 200 else "degraded")
    assert data["version"] == package_version("treejar-ai-bot")
    assert data["dependencies"]["redis"]["status"] == ("error" if redis_fails else "ok")
    assert data["dependencies"]["database"]["status"] == ("error" if db_fails else "ok")
    db.execute.assert_awaited_once()
    assert str(db.execute.await_args.args[0]) == "SELECT 1"
    assert "redis-secret-detail" not in response.text
    assert "database-secret-detail" not in response.text

    if redis_fails:
        assert data["dependencies"]["redis"]["message"] == "unavailable"
    if db_fails:
        assert data["dependencies"]["database"]["message"] == "unavailable"
