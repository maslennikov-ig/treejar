from collections.abc import AsyncGenerator, Generator
from importlib.metadata import version as package_version
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, get_redis
from src.api.v1 import health
from src.main import app
from src.schemas import HealthCheckResponse


@pytest.fixture(autouse=True)
def forget_the_resolved_release_sha() -> Generator[None, None, None]:
    """`tj-hls5` made the resolver per-process, so each case starts from disk.

    Cleared on the way out as well as on the way in: the cache is a process
    global, and a value read from this module's `tmp_path` must not survive
    into a test file that does not patch the path at all.
    """

    health.resolve_release_sha.cache_clear()
    yield
    health.resolve_release_sha.cache_clear()


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


class _CountingReleaseShaPath:
    """A `_RELEASE_SHA_PATH` that says how often it was actually read."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self.reads = 0

    def read_text(self, encoding: str = "utf-8") -> str:
        self.reads += 1
        return self._path.read_text(encoding=encoding)


@pytest.mark.asyncio
async def test_the_release_sha_is_read_from_disk_once_per_process(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`tj-hls5`. Every health poll did blocking file I/O in an async handler.

    The value cannot change without a container rebuild, and the deploy loop in
    `scripts/vps-deploy.sh` polls up to twenty times every three seconds while
    monitoring polls continuously. `resolve_app_version`, the function the
    design said to copy, is an in-memory metadata lookup.
    """

    release_sha_path = tmp_path / ".release-sha"
    release_sha_path.write_text("278c46c8\n", encoding="utf-8")
    counting = _CountingReleaseShaPath(release_sha_path)
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", counting, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        first = await ac.get("/api/v1/health")
        second = await ac.get("/api/v1/health")
        third = await ac.get("/api/v1/health")

    assert first.json()["release_sha"] == "278c46c8"
    assert second.json()["release_sha"] == "278c46c8"
    assert third.json()["release_sha"] == "278c46c8"
    assert counting.reads == 1


@pytest.mark.asyncio
async def test_a_missing_release_sha_is_not_retried_on_every_poll(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The fallback is an answer, not a retry: an absent file stays absent."""

    counting = _CountingReleaseShaPath(tmp_path / ".release-sha")
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", counting, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        first = await ac.get("/api/v1/health")
        second = await ac.get("/api/v1/health")

    assert first.json()["release_sha"] == "unknown"
    assert second.json()["release_sha"] == "unknown"
    assert counting.reads == 1


@pytest.mark.asyncio
async def test_health_reports_deployed_release_sha(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    release_sha_path = tmp_path / ".release-sha"
    release_sha_path.write_text("278c46c8\n", encoding="utf-8")
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", release_sha_path, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["release_sha"] == "278c46c8"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path_kind", ["missing", "unreadable", "empty", "blank", "undecodable"]
)
async def test_health_reports_unknown_when_release_sha_is_unavailable(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    path_kind: str,
) -> None:
    release_sha_path = tmp_path / ".release-sha"
    if path_kind == "unreadable":
        release_sha_path.mkdir()
    elif path_kind == "empty":
        release_sha_path.write_bytes(b"")
    elif path_kind == "blank":
        release_sha_path.write_text("   \n\t ", encoding="utf-8")
    elif path_kind == "undecodable":
        # A truncated or half-written file is not UTF-8. This raised
        # UnicodeDecodeError -- a ValueError, not an OSError -- and returned
        # 500, which the deploy health loop reads as a failed release.
        release_sha_path.write_bytes(b"\xff\xfe\x00sha")
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", release_sha_path, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["release_sha"] == "unknown"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content",
    [
        # `tj-izkn`, both probed on 2026-08-13. The file is returned whole on a
        # public unauthenticated endpoint, and `.strip()` only takes the outer
        # whitespace, so a second line travels inside the value.
        pytest.param(b"a" * 200_000, id="over-long"),
        pytest.param(b"abc123\nSECOND-LINE\n", id="multi-line"),
        pytest.param(b"not a sha at all\n", id="prose"),
        pytest.param(b"278C46C8\n", id="upper-case"),
        pytest.param(b"278c46\n", id="too-short"),
    ],
)
async def test_health_reports_unknown_for_anything_that_is_not_a_release_sha(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    content: bytes,
) -> None:
    release_sha_path = tmp_path / ".release-sha"
    release_sha_path.write_bytes(content)
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", release_sha_path, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["release_sha"] == "unknown"


@pytest.mark.asyncio
async def test_health_reports_the_full_sha_ci_writes(
    health_dependencies: tuple[AsyncMock, AsyncMock],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The deploy job writes `$GITHUB_SHA`, which is forty characters."""

    full_sha = "0123456789abcdef0123456789abcdef01234567"
    release_sha_path = tmp_path / ".release-sha"
    release_sha_path.write_text(f"{full_sha}\n", encoding="utf-8")
    monkeypatch.setattr(health, "_RELEASE_SHA_PATH", release_sha_path, raising=False)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.get("/api/v1/health")

    assert response.json()["release_sha"] == full_sha


def test_the_response_schema_bounds_the_release_sha() -> None:
    """The endpoint is public. Nothing reaches it that the schema would refuse.

    Belt and braces on purpose: the resolver is the gate, and the schema is
    what stops a future caller routing around it.
    """

    ok = HealthCheckResponse(
        status="ok",
        version="1.0.0",
        release_sha="278c46c8",
        dependencies={},
    )

    assert ok.release_sha == "278c46c8"

    for rejected in ("a" * 41, "abc123\nSECOND-LINE", "not a sha", ""):
        with pytest.raises(ValidationError):
            HealthCheckResponse(
                status="ok",
                version="1.0.0",
                release_sha=rejected,
                dependencies={},
            )


# --- the shipped location, not a patched one ------------------------------
#
# Every test above patches `_RELEASE_SHA_PATH`, so none of them can see where
# the file actually has to be. That is how the endpoint reached production
# reporting "unknown" for every release: CI wrote `.release-sha` into the
# release archive, the archive landed on the VPS, and the Dockerfile never
# copied it into the image. The two tests below hold the packaging contract.

_REPO_ROOT = Path(__file__).resolve().parents[1]


def test_release_sha_is_read_from_the_application_root() -> None:
    """The resolved path is the directory the image's WORKDIR holds."""

    assert health._RELEASE_SHA_PATH.name == ".release-sha"
    assert health._RELEASE_SHA_PATH.parent == _REPO_ROOT
    assert (health._RELEASE_SHA_PATH.parent / "pyproject.toml").is_file()


def test_the_runtime_image_copies_the_release_sha_it_reports() -> None:
    """A build that does not ship the file can only ever answer 'unknown'."""

    dockerfile = (_REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    runtime_stage = dockerfile.split("FROM uv AS runtime", 1)[1].split("FROM ", 1)[0]

    copies = [
        line
        for line in runtime_stage.splitlines()
        if line.startswith("COPY ") and ".release-sha" in line
    ]

    assert copies, "the runtime stage must COPY .release-sha into the image"
    # A wildcard matching nothing fails the build, and .release-sha is absent
    # from every local checkout, so it has to travel with a file that is not.
    assert any("*" in line for line in copies)
    assert any(
        other.strip() and not other.startswith(".release-sha")
        for line in copies
        for other in line.removeprefix("COPY ").split()[:-1]
    )
