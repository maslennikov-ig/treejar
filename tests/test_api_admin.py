import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.api.v1.reports import ReportResponse
from src.core.config import settings
from src.main import app
from src.schemas.admin import DashboardMetricsResponse
from src.schemas.common import PaginatedResponse
from src.schemas.manager_review import ManagerReviewDetail, ManagerReviewRead
from src.services.reports import ReportData
from tests.conftest import integration


class _FakeScalars:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return list(self._rows)

    def first(self) -> object | None:
        return self._rows[0] if self._rows else None


class _FakeScalarResult:
    def __init__(self, value: object, rows: list[object] | None = None) -> None:
        self._value = value
        self._rows = rows if rows is not None else ([] if value is None else [value])

    def scalar_one_or_none(self) -> object:
        return self._value

    def scalars(self) -> _FakeScalars:
        return _FakeScalars(self._rows)


class _FakeAIQualityConfigDB:
    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self.config = None
        if value is not None:
            from src.models.system_config import SystemConfig

            self.config = SystemConfig(key="ai_quality_controls", value=value)
        self.added: list[object] = []
        self.audits: list[object] = []
        self.committed = False

    async def execute(self, _stmt: object) -> _FakeScalarResult:
        return _FakeScalarResult(self.config)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if hasattr(obj, "key"):
            self.config = obj
        else:
            self.audits.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _FakeSystemConfigDB:
    def __init__(self, values: dict[str, Any] | None = None) -> None:
        from src.models.system_config import SystemConfig

        self.rows = {
            key: SystemConfig(key=key, value=value)
            for key, value in (values or {}).items()
        }
        self.added: list[object] = []
        self.audits: list[object] = []
        self.committed = False

    async def execute(self, stmt: object) -> _FakeScalarResult:
        text = str(stmt)
        if "WHERE" not in text.upper():
            return _FakeScalarResult(None, rows=list(self.rows.values()))
        for key, row in self.rows.items():
            if key in text:
                return _FakeScalarResult(row)
        return _FakeScalarResult(None)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if hasattr(obj, "key"):
            key = obj.key  # type: ignore[attr-defined]
            self.rows[key] = obj  # type: ignore[assignment]
        else:
            self.audits.append(obj)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


async def _with_fake_db(
    admin_client: AsyncClient,
    fake_db: _FakeAIQualityConfigDB,
    method: str,
    url: str,
    **kwargs: object,
):
    from src.core.database import get_db

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        return await admin_client.request(method, url, **kwargs)
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _with_fake_system_db(
    admin_client: AsyncClient,
    fake_db: _FakeSystemConfigDB,
    method: str,
    url: str,
    **kwargs: object,
):
    from src.core.database import get_db

    async def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        return await admin_client.request(method, url, **kwargs)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_admin_requires_auth(client: AsyncClient) -> None:
    """All /api/v1/admin/ endpoints should return 401 without auth."""
    response = await client.get("/api/v1/admin/prompts/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unknown_api_routes_do_not_fall_through_to_spa(
    client: AsyncClient,
) -> None:
    """Unknown API paths must fail as API errors, not landing-page HTML."""
    response = await client.get("/api/v1/admin/bot-rules")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"] == "Not Found"


@pytest.mark.asyncio
async def test_admin_login_page_shows_telegram_admin_entrypoint(
    client: AsyncClient,
) -> None:
    response = await client.get("/admin/login")

    assert response.status_code == 200
    assert "Войти через Telegram" in response.text
    assert "Treejar_Trading_bot" in response.text
    assert "https://t.me/Treejar_Trading_bot" in response.text
    assert "/admin" in response.text
    assert "личный чат" in response.text
    assert "Личный чат с ботом не выдает CRM-ссылки" not in response.text


@pytest.mark.asyncio
async def test_admin_login_grants_dashboard_and_api_access(client: AsyncClient) -> None:
    """Real SQLAdmin login should authorize /dashboard and /api/v1/admin routes."""
    dashboard_response = await client.get("/dashboard/")
    assert dashboard_response.status_code == 302
    assert dashboard_response.headers["location"] == "/admin/login"

    api_response = await client.get("/api/v1/admin/dashboard/metrics/")
    assert api_response.status_code == 401

    login_response = await client.post(
        "/admin/login",
        data={
            "username": settings.admin_username,
            "password": settings.admin_password,
        },
    )
    assert login_response.status_code in (200, 302, 303)
    assert login_response.headers["location"].endswith("/dashboard/")

    admin_response = await client.get("/admin/")
    assert admin_response.status_code == 200

    dashboard_response = await client.get("/dashboard/")
    assert dashboard_response.status_code == 200

    with patch(
        "src.services.dashboard_metrics.calculate_dashboard_metrics",
        new_callable=AsyncMock,
    ) as mock_metrics:
        mock_metrics.return_value = DashboardMetricsResponse(period="all_time")
        api_response = await client.get("/api/v1/admin/dashboard/metrics/")

    assert api_response.status_code == 200
    assert api_response.json()["period"] == "all_time"


@integration
@pytest.mark.asyncio
async def test_admin_endpoints(admin_client: AsyncClient) -> None:
    # --- test_admin_prompts ---
    response1 = await admin_client.get("/api/v1/admin/prompts/")
    assert response1.status_code == 200
    data = response1.json()
    assert isinstance(data, list)

    some_uuid = str(uuid.uuid4())
    response2 = await admin_client.get(f"/api/v1/admin/prompts/{some_uuid}")
    assert response2.status_code == 404

    response3 = await admin_client.put(
        f"/api/v1/admin/prompts/{some_uuid}",
        json={
            "content": "new system prompt content",
            "description": "updated prompt description",
        },
    )
    assert response3.status_code == 404

    # --- test_admin_metrics ---
    response_m = await admin_client.get("/api/v1/admin/metrics/")
    assert response_m.status_code == 200
    data_m = response_m.json()
    assert "total_conversations" in data_m
    assert "messages_sent" in data_m
    assert "llm_cost_usd" in data_m
    assert "escalations" in data_m
    assert "deals_created" in data_m
    assert "quotes_generated" in data_m

    # --- test_admin_settings ---
    response_s1 = await admin_client.get("/api/v1/admin/settings/")
    assert response_s1.status_code == 200
    data1 = response_s1.json()
    assert "bot_enabled" in data1
    assert "telegram_test_mode_enabled" in data1
    assert "default_language" not in data1

    response_s2 = await admin_client.patch(
        "/api/v1/admin/settings/",
        json={
            "bot_enabled": False,
            "telegram_test_mode_enabled": False,
        },
    )
    assert response_s2.status_code == 200
    data2 = response_s2.json()
    assert data2["bot_enabled"] is False
    assert data2["telegram_test_mode_enabled"] is False

    # --- test_admin_mount_redirects_to_login ---
    response_rm = await admin_client.get("/admin/")
    assert response_rm.status_code == 200


@integration
@pytest.mark.asyncio
async def test_dashboard_metrics(admin_client: AsyncClient) -> None:
    """Test the current expanded dashboard metrics payload."""
    # Default period (all_time)
    response = await admin_client.get("/api/v1/admin/dashboard/metrics/")
    assert response.status_code == 200
    data = response.json()
    assert data["period"] == "all_time"

    # Volume
    assert "total_conversations" in data
    assert "unique_customers" in data
    assert "new_vs_returning" in data

    # Classification
    assert "by_language" in data
    assert "by_segment" in data
    assert "target_vs_nontarget" in data

    # Escalation
    assert "escalation_count" in data
    assert "escalation_reasons" in data

    # Sales
    assert "noor_sales" in data
    assert "conversion_rate" in data
    assert "average_deal_value" in data

    # Quality
    assert "avg_conversation_length" in data
    assert "avg_quality_score" in data
    assert "avg_response_time_ms" in data

    # Cost
    assert "llm_cost_usd" in data

    # Test period filtering
    for p in ("day", "week", "month"):
        resp = await admin_client.get(f"/api/v1/admin/dashboard/metrics/?period={p}")
        assert resp.status_code == 200
        assert resp.json()["period"] == p

    # Test invalid period
    resp_bad = await admin_client.get("/api/v1/admin/dashboard/metrics/?period=year")
    assert resp_bad.status_code == 422


@integration
@pytest.mark.asyncio
async def test_admin_models_list(client: AsyncClient) -> None:
    import uuid

    from src.core.config import settings
    from src.core.database import async_session_factory
    from src.models.conversation import Conversation
    from src.models.escalation import Escalation
    from src.models.knowledge_base import KnowledgeBase
    from src.models.message import Message
    from src.models.metrics_snapshot import MetricsSnapshot
    from src.models.product import Product
    from src.models.quality_review import QualityReview
    from src.models.system_config import SystemConfig
    from src.models.system_prompt import SystemPrompt

    # Create mock data to ensure SQLAdmin renders table rows (where relations might crash)
    async with async_session_factory() as session:
        conv_id = uuid.uuid4()
        conv = Conversation(
            id=conv_id, phone="1234567890", customer_name="Test User", language="en"
        )
        msg = Message(
            id=uuid.uuid4(), conversation_id=conv_id, role="user", content="Hello"
        )
        esc = Escalation(
            id=uuid.uuid4(), conversation_id=conv_id, reason="Angry", status="pending"
        )
        qr = QualityReview(
            id=uuid.uuid4(),
            conversation_id=conv_id,
            total_score=10.0,
            criteria={},
            rating="good",
        )
        prod = Product(
            id=uuid.uuid4(),
            sku=str(uuid.uuid4()),
            name_en="Test Product",
            price=10.0,
            stock=5,
        )
        kb = KnowledgeBase(
            id=uuid.uuid4(),
            source=f"test-{uuid.uuid4()}",
            title=f"Test Title {uuid.uuid4()}",
            content="test",
            language="en",
            category="faq",
        )
        sc = SystemConfig(key=str(uuid.uuid4()), value={"foo": "bar"})
        sp = SystemPrompt(
            id=uuid.uuid4(), name=str(uuid.uuid4()), content="You are an AI.", version=1
        )
        ms = MetricsSnapshot(period=f"today-{uuid.uuid4()}")
        session.add_all([conv, msg, esc, qr, prod, kb, sc, sp, ms])
        try:
            await session.commit()
            print("\n>>> MOCK DATA COMMITTED SUCCESSFULLY <<<\n")
        except Exception as e:
            print("\n>>> MOCK DATA CREATION FAILED <<<", e)
            import traceback

            traceback.print_exc()
            await session.rollback()

    # Login
    resp_login = await client.post(
        "/admin/login",
        data={"username": settings.admin_username, "password": settings.admin_password},
    )
    assert resp_login.status_code in (200, 302, 303)

    import re

    # Get the admin home page to find all list view URLs
    resp_home = await client.get("/admin/")
    assert resp_home.status_code == 200

    # Extract all links that look like list views e.g. http://test/admin/knowledge-base/list
    list_links = re.findall(r'href="(http://test/admin/[^"]+/list)"', resp_home.text)
    if not list_links:
        print(resp_home.text)
    assert len(list_links) > 0, "No list links found in admin panel!"

    for link in set(list_links):
        resp = await client.get(link)
        if resp.status_code == 500:
            print(f"500 ERROR ON {link}")
            print(resp.text)
        assert resp.status_code == 200, (
            f"Failed on {link} with status {resp.status_code}"
        )

    # Also test details and write pages for the mock items. Some SQLAdmin views are
    # intentionally read-only because the CRM dashboard owns operational actions.
    model_permissions = {
        "conversation": {"can_create": False, "can_edit": False},
        "message": {"can_create": False, "can_edit": False},
        "escalation": {"can_create": False, "can_edit": False},
        "quality-review": {"can_create": False, "can_edit": False},
        "product": {"can_create": False, "can_edit": False},
        "knowledge-base": {"can_create": False, "can_edit": False},
        "system-config": {"can_create": True, "can_edit": True},
        "system-prompt": {"can_create": False, "can_edit": True},
        "metrics-snapshot": {"can_create": False, "can_edit": False},
    }
    for model_name, item_id in [
        ("conversation", conv_id),
        ("message", msg.id),
        ("escalation", esc.id),
        ("quality-review", qr.id),
        ("product", prod.id),
        ("knowledge-base", kb.id),
        ("system-config", sc.key),
        ("system-prompt", sp.id),
        ("metrics-snapshot", ms.period),
    ]:
        # get list, find the actual detail url
        resp_list = await client.get(f"/admin/{model_name}/list")
        if str(item_id) in resp_list.text:
            match = re.search(
                r'href="([^"]+?/' + str(item_id) + r'[^"]*)"', resp_list.text
            )
            if match:
                print(f"FOUND EXACT URL FOR {model_name}: {match.group(1)}")
                det_url = match.group(1)
            else:
                det_url = f"/admin/{model_name}/details/{item_id}"
        else:
            det_url = f"/admin/{model_name}/details/{item_id}"

        resp_det = await client.get(det_url)
        if resp_det.status_code == 500:
            print(f"500 ERROR ON {det_url}")
            print(resp_det.text)
        assert resp_det.status_code == 200, f"Failed on {det_url}"

        # edit
        edit_url = f"/admin/{model_name}/edit/{item_id}"
        resp_edit = await client.get(edit_url)
        if resp_edit.status_code == 500:
            print(f"500 ERROR ON {edit_url}")
            print(resp_edit.text)
        expected_edit_status = 200 if model_permissions[model_name]["can_edit"] else 403
        assert resp_edit.status_code == expected_edit_status, f"Failed on {edit_url}"

        # create
        create_url = f"/admin/{model_name}/create"
        resp_c = await client.get(create_url)
        if resp_c.status_code == 500:
            print(f"500 ERROR ON {create_url}")
            print(resp_c.text)
        expected_create_status = (
            200 if model_permissions[model_name]["can_create"] else 403
        )
        assert resp_c.status_code == expected_create_status, f"Failed on {create_url}"


@pytest.mark.asyncio
async def test_admin_dashboard_spa_route(client: AsyncClient) -> None:
    """Unauthenticated dashboard navigations redirect cleanly to /admin/login."""
    response = await client.get("/dashboard/")
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/login"

    no_slash = await client.get("/dashboard")
    assert no_slash.status_code == 302
    assert no_slash.headers["location"] == "/admin/login"

    admin_no_slash = await client.get("/admin")
    assert admin_no_slash.status_code == 302
    assert admin_no_slash.headers["location"] == "/admin/"

    followed = await client.get("/dashboard/", follow_redirects=True)
    assert followed.status_code == 200
    assert followed.headers["content-type"].startswith("text/html")
    assert "Войти через Telegram" in followed.text
    assert "Admin authentication required" not in followed.text


@pytest.mark.asyncio
async def test_admin_login_preserves_dashboard_deep_link_next(
    client: AsyncClient,
) -> None:
    """Deep-linked dashboard URLs return to the requested view/tour after login."""
    initial = await client.get("/dashboard/?tour=1")
    assert initial.status_code == 302
    assert initial.headers["location"] == "/admin/login?next=%2Fdashboard%2F%3Ftour%3D1"

    login_page = await client.get(initial.headers["location"])
    assert login_page.status_code == 200
    assert 'name="next" value="/dashboard/?tour=1"' in login_page.text

    login_resp = await client.post(
        "/admin/login",
        data={
            "username": settings.admin_username,
            "password": settings.admin_password,
            "next": "/dashboard/?tour=1",
        },
    )
    assert login_resp.status_code == 302
    assert login_resp.headers["location"] == "/dashboard/?tour=1"

    already_logged_in = await client.get("/admin/login")
    assert already_logged_in.status_code == 302
    assert already_logged_in.headers["location"] == "/dashboard/"

    dashboard_no_slash = await client.get("/dashboard?view=guide")
    assert dashboard_no_slash.status_code == 302
    assert dashboard_no_slash.headers["location"] == "/dashboard/?view=guide"


@pytest.mark.asyncio
async def test_public_client_self_test_spa_route_without_login(
    client: AsyncClient,
) -> None:
    """Client acceptance demo should be available by direct public link."""
    root_response = await client.get("/client-self-test")
    assert root_response.status_code == 200

    response = await client.get("/client-self-test/")
    assert response.status_code == 200

    nested_response = await client.get("/client-self-test/review")
    assert nested_response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/client-self-test/..%2F..%2F..%2Fpyproject.toml",
        "/client-self-test/%2E%2E/%2E%2E/%2E%2E/pyproject.toml",
        "/..%2F..%2F..%2Fpyproject.toml",
        "/%2E%2E/%2E%2E/%2E%2E/pyproject.toml",
    ],
)
async def test_public_spa_routes_never_read_files_outside_dist(
    client: AsyncClient,
    path: str,
) -> None:
    """Public SPA catch-alls must not serve files outside their build directory."""
    response = await client.get(path)
    assert "[project]" not in response.text
    assert "dependencies" not in response.text


@pytest.mark.asyncio
async def test_admin_dashboard_spa_route_after_login(admin_client: AsyncClient) -> None:
    """Dashboard SPA route should serve the app for authenticated admins."""
    response = await admin_client.get("/dashboard/")
    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"


@pytest.mark.asyncio
async def test_spa_routes_set_no_cache_on_index_and_immutable_on_hashed_assets(
    client: AsyncClient,
) -> None:
    """SPA entry HTML must revalidate while hashed Vite assets cache immutably."""
    from pathlib import Path

    landing_resp = await client.get("/")
    assert landing_resp.status_code == 200
    assert landing_resp.headers.get("cache-control") == "no-cache"

    self_test_resp = await client.get("/client-self-test")
    assert self_test_resp.status_code == 200
    assert self_test_resp.headers.get("cache-control") == "no-cache"

    probe = Path("frontend/admin/dist/assets/_cache_probe.js")
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("export default 1;\n", encoding="utf-8")
    try:
        asset_resp = await client.get("/dashboard/assets/_cache_probe.js")
        assert asset_resp.status_code == 200
        assert (
            asset_resp.headers.get("cache-control")
            == "public, max-age=31536000, immutable"
        )
    finally:
        probe.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_admin_operator_endpoints_require_auth(client: AsyncClient) -> None:
    """Operator action endpoints under /api/v1/admin should require admin auth."""
    response = await client.get("/api/v1/admin/notifications/config")
    assert response.status_code == 401

    response = await client.post("/api/v1/admin/products/sync", json={})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_notifications_operator_endpoints(
    admin_client: AsyncClient,
) -> None:
    """Dashboard operator wrappers should expose notification config/test via admin session."""
    with (
        patch(
            "src.api.v1.notifications.get_notification_config",
            new_callable=AsyncMock,
        ) as mock_config,
        patch(
            "src.api.v1.notifications.send_test_notification",
            new_callable=AsyncMock,
        ) as mock_test,
    ):
        mock_config.return_value = {
            "telegram_configured": True,
            "telegram_bot_token": "***1234",
            "telegram_chat_id": "***9876",
        }
        mock_test.return_value = {"status": "sent"}

        config_response = await admin_client.get("/api/v1/admin/notifications/config")
        test_response = await admin_client.post("/api/v1/admin/notifications/test")

    assert config_response.status_code == 200
    assert config_response.json()["telegram_configured"] is True
    assert test_response.status_code == 200
    assert test_response.json()["status"] == "sent"
    mock_config.assert_awaited_once()
    mock_test.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_product_sync_operator_endpoint(admin_client: AsyncClient) -> None:
    """Dashboard operator wrapper should expose protected product sync via admin session."""
    mock_pool = AsyncMock()
    app.state.arq_pool = mock_pool

    response = await admin_client.post("/api/v1/admin/products/sync", json={})

    assert response.status_code == 200
    assert response.json()["errors"] == 0
    mock_pool.enqueue_job.assert_awaited_with("sync_products_from_treejar_catalog")

    del app.state.arq_pool


@pytest.mark.asyncio
async def test_admin_manager_review_operator_endpoints(
    admin_client: AsyncClient,
) -> None:
    """Dashboard operator wrappers should expose pending, recent, and evaluate flows."""
    now = datetime.now(UTC)
    recent_review = ManagerReviewRead(
        id=uuid.uuid4(),
        escalation_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        manager_name="Amina",
        total_score=17.5,
        max_score=20,
        rating="excellent",
        first_response_time_seconds=180,
        message_count=4,
        deal_converted=True,
        deal_amount=1250.0,
        reviewer="ai",
        created_at=now,
    )
    review_detail = ManagerReviewDetail(
        **recent_review.model_dump(),
        criteria=[],
        summary="Strong follow-up and clear close.",
    )
    pending_item = {
        "escalation_id": str(uuid.uuid4()),
        "conversation_id": str(uuid.uuid4()),
        "phone": "+971501234567",
        "manager_name": "Amina",
        "reason": "Customer requested human manager",
        "status": "resolved",
        "updated_at": now.isoformat(),
    }

    with (
        patch(
            "src.api.v1.admin.list_manager_reviews",
            new_callable=AsyncMock,
        ) as mock_list,
        patch(
            "src.api.v1.admin.list_pending_manager_reviews",
            new_callable=AsyncMock,
        ) as mock_pending,
        patch(
            "src.api.v1.admin.evaluate_escalation_with_settings",
            new_callable=AsyncMock,
        ) as mock_evaluate,
    ):
        mock_list.return_value = PaginatedResponse[ManagerReviewRead](
            items=[recent_review],
            total=1,
            page=1,
            page_size=5,
            pages=1,
        )
        mock_pending.return_value = [pending_item]
        mock_evaluate.return_value = review_detail

        recent_response = await admin_client.get(
            "/api/v1/admin/manager-reviews/?page_size=5"
        )
        pending_response = await admin_client.get(
            "/api/v1/admin/manager-reviews/pending"
        )
        eval_db = _FakeAIQualityConfigDB({"manager_qa": {"mode": "manual"}})
        evaluate_response = await _with_fake_db(
            admin_client,
            eval_db,
            "POST",
            f"/api/v1/admin/manager-reviews/{pending_item['escalation_id']}/evaluate",
        )

    assert recent_response.status_code == 200
    assert recent_response.json()["items"][0]["manager_name"] == "Amina"
    assert pending_response.status_code == 200
    assert pending_response.json()[0]["phone"] == "+971501234567"
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["summary"] == "Strong follow-up and clear close."
    assert len(eval_db.audits) == 1
    assert getattr(eval_db.audits[0], "action", None) == "quality.manager_review"
    assert eval_db.committed is True
    mock_list.assert_awaited_once()
    mock_pending.assert_awaited_once()
    mock_evaluate.assert_awaited_once()
    evaluator_kwargs = mock_evaluate.await_args.kwargs["evaluator_kwargs"]
    assert {"model_name", "transcript_mode", "criteria"} <= set(evaluator_kwargs)


@pytest.mark.asyncio
async def test_admin_manager_review_evaluate_respects_disabled_ai_controls(
    admin_client: AsyncClient,
) -> None:
    """Disabled Manager QA controls should block manual admin evaluation."""
    escalation_id = uuid.uuid4()

    with patch(
        "src.api.v1.admin.evaluate_escalation_with_settings",
        new_callable=AsyncMock,
    ) as mock_evaluate:
        response = await _with_fake_db(
            admin_client,
            _FakeAIQualityConfigDB(),
            "POST",
            f"/api/v1/admin/manager-reviews/{escalation_id}/evaluate",
        )

    assert response.status_code == 409
    assert "Manager QA" in response.text
    assert "disabled" in response.text
    mock_evaluate.assert_not_awaited()


@pytest.mark.asyncio
async def test_admin_report_operator_endpoint(admin_client: AsyncClient) -> None:
    """Dashboard operator wrapper should expose report generation via admin session."""
    with patch(
        "src.api.v1.admin.generate_report_endpoint",
        new_callable=AsyncMock,
    ) as mock_report:
        mock_report.return_value = ReportResponse(
            data=ReportData(
                period_start=datetime(2026, 4, 7, tzinfo=UTC),
                period_end=datetime(2026, 4, 14, tzinfo=UTC),
                total_conversations=12,
                conversion_rate=25.0,
                manager_reviews_count=2,
            ),
            text="Weekly report",
        )

        response = await admin_client.post("/api/v1/admin/reports/generate", json={})

    assert response.status_code == 200
    assert response.json()["text"] == "Weekly report"
    mock_report.assert_awaited_once()


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_default_config(
    admin_client: AsyncClient,
) -> None:
    """AI Quality Controls should default to no automated QA work and expose model options."""
    response = await _with_fake_db(
        admin_client,
        _FakeAIQualityConfigDB(),
        "GET",
        "/api/v1/admin/ai-quality-controls",
    )

    assert response.status_code == 200
    data = response.json()
    config = data["config"]
    assert config["bot_qa"]["mode"] == "disabled"
    assert config["manager_qa"]["mode"] == "disabled"
    assert config["red_flags"]["mode"] == "disabled"
    assert config["bot_qa"]["transcript_mode"] == "summary"
    assert config["manager_qa"]["model"] != "z-ai/glm-5"
    assert config["bot_qa"]["daily_budget_cents"] <= 100
    assert config["bot_qa"]["max_calls_per_run"] <= 2
    assert config["bot_qa"]["max_calls_per_day"] <= 10
    assert data["warnings"] == []
    assert data["default_model"] == "openai/gpt-6.1-terra"
    assert isinstance(data["available_models"], list)
    assert data["available_models"][0] == data["default_model"]
    assert len(data["available_models"]) == len(set(data["available_models"]))
    assert {
        "openai/gpt-6.1-terra",
        "z-ai/glm-5.2",
        "openai/gpt-6-luna",
        "deepseek/deepseek-v4-flash",
        "z-ai/glm-5",
    } <= set(data["available_models"])


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_rejects_full_transcript_without_override(
    admin_client: AsyncClient,
) -> None:
    """Full transcript mode must require explicit warning acknowledgement."""
    response = await _with_fake_db(
        admin_client,
        _FakeAIQualityConfigDB(),
        "PUT",
        "/api/v1/admin/ai-quality-controls",
        json={"bot_qa": {"transcript_mode": "full"}},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_rejects_glm5_without_override(
    admin_client: AsyncClient,
) -> None:
    """QA scopes must not accept GLM-5 unless the warning override is explicit."""
    response = await _with_fake_db(
        admin_client,
        _FakeAIQualityConfigDB(),
        "PUT",
        "/api/v1/admin/ai-quality-controls",
        json={"manager_qa": {"mode": "scheduled", "model": "z-ai/glm-5"}},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_accepts_overrides_with_warnings(
    admin_client: AsyncClient,
) -> None:
    """Risky overrides are allowed only when stored with warning metadata."""
    fake_db = _FakeAIQualityConfigDB()
    response = await _with_fake_db(
        admin_client,
        fake_db,
        "PUT",
        "/api/v1/admin/ai-quality-controls",
        json={
            "bot_qa": {
                "mode": "scheduled",
                "model": "z-ai/glm-5",
                "glm5_warning_override": True,
            },
            "red_flags": {
                "transcript_mode": "full",
                "full_transcript_warning_override": True,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    warning_codes = {warning["code"] for warning in data["warnings"]}
    assert {"glm5_qa", "full_transcript"} <= warning_codes
    assert data["default_model"] == "openai/gpt-6.1-terra"
    assert "z-ai/glm-5" in data["available_models"]
    assert fake_db.committed is True
    assert fake_db.config is not None
    assert fake_db.config.value["bot_qa"]["model"] == "z-ai/glm-5"
    assert fake_db.config.value["red_flags"]["transcript_mode"] == "full"


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_patch_preserves_unspecified_scopes(
    admin_client: AsyncClient,
) -> None:
    """PATCH should merge updates and include custom configured models in available_models."""
    fake_db = _FakeAIQualityConfigDB(
        {
            "bot_qa": {
                "mode": "scheduled",
                "max_calls_per_run": 2,
                "model": "custom/qa-judge-v1",
            },
            "manager_qa": {"mode": "disabled"},
            "red_flags": {"mode": "manual"},
        }
    )
    response = await _with_fake_db(
        admin_client,
        fake_db,
        "PATCH",
        "/api/v1/admin/ai-quality-controls",
        json={"manager_qa": {"mode": "manual", "max_calls_per_run": 3}},
    )

    assert response.status_code == 200
    payload = response.json()
    config = payload["config"]
    assert config["bot_qa"]["mode"] == "scheduled"
    assert config["bot_qa"]["max_calls_per_run"] == 2
    assert config["manager_qa"]["mode"] == "manual"
    assert config["manager_qa"]["max_calls_per_run"] == 3
    assert config["red_flags"]["mode"] == "manual"
    assert payload["default_model"] == "openai/gpt-6.1-terra"
    assert "custom/qa-judge-v1" in payload["available_models"]
    assert len(payload["available_models"]) == len(set(payload["available_models"]))


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_validates_budget_calls_and_retry_bounds(
    admin_client: AsyncClient,
) -> None:
    """Budget, max-call, and retry policy limits should fail before persistence."""
    response = await _with_fake_db(
        admin_client,
        _FakeAIQualityConfigDB(),
        "PUT",
        "/api/v1/admin/ai-quality-controls",
        json={
            "bot_qa": {
                "daily_budget_cents": -1,
                "max_calls_per_run": 1000,
                "retry": {"max_attempts": 5},
            }
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_payment_reminder_controls_default_disabled(
    admin_client: AsyncClient,
) -> None:
    response = await _with_fake_system_db(
        admin_client,
        _FakeSystemConfigDB(),
        "GET",
        "/api/v1/admin/payment-reminder-controls",
    )

    assert response.status_code == 200
    config = response.json()["config"]
    assert config["mode"] == "disabled"
    assert config["within_24h_text_enabled"] is False
    assert config["template_name"] is None


@pytest.mark.asyncio
async def test_admin_payment_reminder_controls_update_persists_system_config(
    admin_client: AsyncClient,
) -> None:
    fake_db = _FakeSystemConfigDB()

    response = await _with_fake_system_db(
        admin_client,
        fake_db,
        "PUT",
        "/api/v1/admin/payment-reminder-controls",
        json={
            "mode": "scheduled",
            "max_per_run": 3,
            "daily_limit": 10,
            "min_hours_after_approval": 24,
            "template_name": "payment_reminder_approved_order_v1",
            "within_24h_text_enabled": False,
        },
    )

    assert response.status_code == 200
    assert fake_db.committed is True
    row = fake_db.rows["payment_reminder_controls"]
    assert row.value["mode"] == "scheduled"
    assert row.value["template_name"] == "payment_reminder_approved_order_v1"


@pytest.mark.asyncio
async def test_admin_payment_reminder_controls_rejects_enabled_text_without_copy(
    admin_client: AsyncClient,
) -> None:
    response = await _with_fake_system_db(
        admin_client,
        _FakeSystemConfigDB(),
        "PUT",
        "/api/v1/admin/payment-reminder-controls",
        json={
            "mode": "scheduled",
            "within_24h_text_enabled": True,
            "within_24h_text": "",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_admin_session_endpoint_reports_auth_identity(
    client: AsyncClient,
    admin_client: AsyncClient,
) -> None:
    """GET /api/v1/admin/session requires auth and reflects login metadata."""
    from types import SimpleNamespace

    from src.api.v1.admin import get_admin_session_info

    unauth = await client.get("/api/v1/admin/session")
    assert unauth.status_code == 401

    fallback = await get_admin_session_info(
        SimpleNamespace(session={"token": "authenticated"})  # type: ignore[arg-type]
    )
    assert fallback.authenticated is True
    assert fallback.auth_method == "session"
    assert fallback.logout_url == "/admin/logout"
    assert fallback.sqladmin_url == "/admin/"

    pw_session = await admin_client.get("/api/v1/admin/session")
    assert pw_session.status_code == 200
    pw_data = pw_session.json()
    assert pw_data["authenticated"] is True
    assert pw_data["auth_method"] == "password"
    assert pw_data["display_name"] == settings.admin_username
    assert pw_data["username"] == settings.admin_username
    assert pw_data["actor"] == settings.admin_username
    assert pw_data["logout_url"] == "/admin/logout"
    assert pw_data["sqladmin_url"] == "/admin/"

    logout_resp = await admin_client.get("/admin/logout")
    assert logout_resp.status_code in (302, 303)
    after_logout = await admin_client.get("/api/v1/admin/session")
    assert after_logout.status_code == 401
    dash_after_logout = await admin_client.get("/dashboard/")
    assert dash_after_logout.status_code in (302, 303)
    assert "/admin/login" in dash_after_logout.headers["location"]


def test_parse_config_bool_handles_jsonb_scalars_strings_and_dicts() -> None:
    """parse_config_bool handles string falsy/truthy values instead of Python bool('false') (AD-10)."""
    from src.core.config_bool import parse_config_bool

    for falsy in (False, 0, "false", "FALSE", "0", "no", "off", ""):
        assert parse_config_bool(falsy, default=True) is False
    for truthy in (True, 1, "true", "TRUE", "1", "yes", "on"):
        assert parse_config_bool(truthy, default=False) is True
    assert parse_config_bool(None, default=False) is False
    assert parse_config_bool(None, default=True) is True
    assert parse_config_bool({"enabled": "false"}, default=True) is False
    assert parse_config_bool({"value": "yes"}, default=False) is True


@pytest.mark.asyncio
async def test_admin_settings_parses_string_booleans_removes_dead_fields_and_audits(
    admin_client: AsyncClient,
) -> None:
    """GET/PATCH /api/v1/admin/settings/ honours string booleans, omits dead fields, and audits (AD-10, AD-11, AD-14)."""
    from src.models.admin_action_audit import AdminActionAudit

    fake_db = _FakeSystemConfigDB(
        {
            "bot_enabled": "false",
            "telegram_test_mode_enabled": "0",
            "default_language": "ar",
        }
    )

    get_resp = await _with_fake_system_db(
        admin_client, fake_db, "GET", "/api/v1/admin/settings/"
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data == {
        "bot_enabled": False,
        "telegram_test_mode_enabled": False,
    }
    assert "default_language" not in get_data
    assert "follow_up_enabled" not in get_data
    assert "max_messages_per_conversation" not in get_data

    patch_resp = await _with_fake_system_db(
        admin_client,
        fake_db,
        "PATCH",
        "/api/v1/admin/settings/",
        json={"bot_enabled": True},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json() == {
        "bot_enabled": True,
        "telegram_test_mode_enabled": False,
    }
    assert len(fake_db.audits) == 1
    audit = fake_db.audits[0]
    assert isinstance(audit, AdminActionAudit)
    assert audit.action == "settings.update"
    assert audit.entity_id == "settings"
    assert audit.before == {
        "bot_enabled": False,
        "telegram_test_mode_enabled": False,
    }
    assert audit.after == {
        "bot_enabled": True,
        "telegram_test_mode_enabled": False,
    }


@pytest.mark.asyncio
async def test_admin_system_health_isolates_contour_errors_and_parses_bot_enabled(
    admin_client: AsyncClient,
) -> None:
    """System health reports status='error' on failing DB/Redis contours instead of masking them (AD-15, AD-10)."""
    from src.core.database import get_db

    class BrokenDB:
        async def scalar(self, _stmt: object) -> object:
            raise RuntimeError("db unavailable")

    async def override_broken_db():
        yield BrokenDB()

    app.dependency_overrides[get_db] = override_broken_db
    try:
        with patch(
            "src.api.v1.admin._read_zoho_snapshot_status",
            new=AsyncMock(side_effect=RuntimeError("redis unavailable")),
        ):
            err_resp = await admin_client.get("/api/v1/admin/system/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert err_resp.status_code == 200
    err_data = err_resp.json()
    assert err_data["overall_status"] == "error"
    by_id = {c["id"]: c for c in err_data["contours"]}
    assert by_id["whatsapp"]["status"] == "error"
    assert by_id["zoho_inventory"]["status"] == "error"
    assert by_id["knowledge_rag"]["status"] == "error"
    assert by_id["knowledge_rag"]["summary"] == "error"

    class HealthyPausedDB:
        async def scalar(self, stmt: object) -> object:
            sql = str(stmt).lower()
            if "system_configs" in sql:
                return "false"  # bot_enabled stored as string "false"
            if "messages" in sql:
                return datetime(2026, 4, 14, tzinfo=UTC)
            return 5

    async def override_paused_db():
        yield HealthyPausedDB()

    from src.schemas.admin import AdminZohoSnapshotStatus

    app.dependency_overrides[get_db] = override_paused_db
    try:
        with patch(
            "src.api.v1.admin._read_zoho_snapshot_status",
            new=AsyncMock(
                return_value=AdminZohoSnapshotStatus(status="fresh", item_count=120)
            ),
        ):
            paused_resp = await admin_client.get("/api/v1/admin/system/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert paused_resp.status_code == 200
    paused_by_id = {c["id"]: c for c in paused_resp.json()["contours"]}
    assert paused_by_id["whatsapp"]["status"] == "warning"
    assert paused_by_id["whatsapp"]["summary"] == "paused"


@pytest.mark.asyncio
async def test_update_prompt_preserves_description_when_omitted_and_audits(
    admin_client: AsyncClient,
) -> None:
    """PUT /api/v1/admin/prompts/{id} keeps old_prompt.description when omitted and writes audit (AD-33, AD-14)."""
    from src.api.deps import get_redis
    from src.core.database import get_db
    from src.models.admin_action_audit import AdminActionAudit
    from src.models.system_config import SystemConfig
    from src.models.system_prompt import SystemPrompt

    prompt_id = uuid.uuid4()
    now = datetime(2026, 4, 14, tzinfo=UTC)
    old_prompt = SystemPrompt(
        id=prompt_id,
        name="base_prompt",
        content="Old prompt content",
        version=2,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    desc_config = SystemConfig(
        key="prompt_descriptions",
        value={"base_prompt": "Canonical operator description"},
    )

    class FakePromptDB:
        def __init__(self) -> None:
            self.added: list[object] = []

        async def get(self, model: object, key: object) -> object | None:
            if model is SystemPrompt and key == prompt_id:
                return old_prompt
            if model is SystemConfig and key == "prompt_descriptions":
                return desc_config
            return None

        def add(self, obj: object) -> None:
            self.added.append(obj)

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, obj: SystemPrompt) -> None:
            if obj.id is None:
                obj.id = uuid.uuid4()
            if obj.created_at is None:
                obj.created_at = now
            if obj.updated_at is None:
                obj.updated_at = now

    fake_db = FakePromptDB()
    fake_redis = AsyncMock()

    async def override_db():
        yield fake_db

    async def override_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = override_redis
    try:
        resp = await admin_client.put(
            f"/api/v1/admin/prompts/{prompt_id}",
            json={"content": "Updated prompt content"},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis, None)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["description"] == "Canonical operator description"
    assert payload["version"] == 3
    fake_redis.delete.assert_awaited_once_with("prompt:base_prompt")
    audits = [obj for obj in fake_db.added if isinstance(obj, AdminActionAudit)]
    assert len(audits) == 1
    assert audits[0].action == "prompt.update"


@pytest.mark.asyncio
async def test_admin_catalog_sync_persists_redis_status_and_audits(
    admin_client: AsyncClient,
) -> None:
    """POST /api/v1/admin/products/sync returns status='queued', stores state in Redis, and audits (AD-16, AD-14)."""
    from src.api.v1 import admin as admin_module
    from src.core.database import get_db
    from src.models.admin_action_audit import AdminActionAudit

    redis_store: dict[str, str] = {}

    class FakeRedis:
        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            redis_store[key] = value

        async def get(self, key: str) -> str | None:
            return redis_store.get(key)

    class FakeCatalogDB:
        def __init__(self) -> None:
            self.audits: list[object] = []

        def add(self, obj: object) -> None:
            self.audits.append(obj)

        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def scalar(self, _stmt: object) -> int:
            return 10

    fake_db = FakeCatalogDB()
    fake_redis = FakeRedis()
    mock_pool = AsyncMock()
    app.state.arq_pool = mock_pool

    async def override_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_db
    try:
        with patch("src.api.v1.admin.get_redis_client", return_value=fake_redis):
            sync_resp = await admin_client.post(
                "/api/v1/admin/products/sync",
                json={"source": "treejar"},
            )
            assert sync_resp.status_code == 200
            sync_data = sync_resp.json()
            assert sync_data["status"] == "queued"
            assert sync_data["synced"] == 0

            # Clear process-local cache to prove GET /catalog/status reads from Redis
            admin_module._LAST_CATALOG_SYNC_SOURCES.clear()
            status_resp = await admin_client.get("/api/v1/admin/catalog/status")
    finally:
        app.dependency_overrides.pop(get_db, None)
        del app.state.arq_pool

    assert status_resp.status_code == 200
    treejar_status = status_resp.json()["sources"]["treejar"]
    assert treejar_status["last_status"] == "queued"
    assert treejar_status["last_triggered_at"] is not None
    assert len(fake_db.audits) == 1
    assert isinstance(fake_db.audits[0], AdminActionAudit)
    assert fake_db.audits[0].action == "catalog.sync"


@pytest.mark.asyncio
async def test_admin_controls_and_notifications_write_audit_entries(
    admin_client: AsyncClient,
) -> None:
    """Controls PUT/PATCH and test notification endpoints record AdminActionAudit entries (AD-14)."""
    from src.models.admin_action_audit import AdminActionAudit

    ai_db = _FakeAIQualityConfigDB()
    ai_resp = await _with_fake_db(
        admin_client,
        ai_db,
        "PATCH",
        "/api/v1/admin/ai-quality-controls",
        json={"bot_qa": {"mode": "manual"}},
    )
    assert ai_resp.status_code == 200
    assert len(ai_db.audits) == 1
    assert isinstance(ai_db.audits[0], AdminActionAudit)
    assert ai_db.audits[0].action == "ai_quality_controls.update"

    pr_db = _FakeSystemConfigDB()
    pr_resp = await _with_fake_system_db(
        admin_client,
        pr_db,
        "PATCH",
        "/api/v1/admin/payment-reminder-controls",
        json={"daily_limit": 12},
    )
    assert pr_resp.status_code == 200
    assert len(pr_db.audits) == 1
    assert isinstance(pr_db.audits[0], AdminActionAudit)
    assert pr_db.audits[0].action == "payment_reminder_controls.update"

    notif_db = _FakeSystemConfigDB()
    with patch(
        "src.api.v1.admin.notifications_api.send_test_notification",
        new=AsyncMock(
            return_value={"status": "ok", "detail": "Test notification sent"}
        ),
    ):
        notif_resp = await _with_fake_system_db(
            admin_client,
            notif_db,
            "POST",
            "/api/v1/admin/notifications/test",
        )
    assert notif_resp.status_code == 200
    assert len(notif_db.audits) == 1
    assert isinstance(notif_db.audits[0], AdminActionAudit)
    assert notif_db.audits[0].action == "notification.test"


@pytest.mark.asyncio
async def test_dashboard_metrics_and_timeseries_redis_cache_and_refresh(
    admin_client: AsyncClient,
) -> None:
    """Dashboard metrics and timeseries cache per period for 60s, support refresh=true, and fail open (P3-5)."""
    from src.core.database import get_db
    from src.schemas.admin import TimeseriesPoint, TimeseriesResponse

    cache_store: dict[str, tuple[str, int | None]] = {}

    class FakeRedis:
        async def get(self, key: str) -> str | None:
            item = cache_store.get(key)
            return item[0] if item else None

        async def set(self, key: str, value: str, ex: int | None = None) -> None:
            cache_store[key] = (value, ex)

    class DummyDB:
        pass

    async def override_db():
        yield DummyDB()

    metrics_calls = 0
    ts_calls = 0

    async def fake_calc_metrics(_db: object, period: str) -> DashboardMetricsResponse:
        nonlocal metrics_calls
        metrics_calls += 1
        return DashboardMetricsResponse(
            period=period,
            total_conversations=10 + metrics_calls,
        )

    async def fake_calc_ts(_db: object, period: str) -> TimeseriesResponse:
        nonlocal ts_calls
        ts_calls += 1
        return TimeseriesResponse(
            period=period,
            points=[TimeseriesPoint(date="2026-05-01", new=ts_calls, returning=1)],
        )

    fake_redis = FakeRedis()
    app.dependency_overrides[get_db] = override_db
    try:
        with (
            patch("src.api.v1.admin.get_redis_client", return_value=fake_redis),
            patch(
                "src.services.dashboard_metrics.calculate_dashboard_metrics",
                side_effect=fake_calc_metrics,
            ),
            patch(
                "src.services.dashboard_metrics.calculate_timeseries",
                side_effect=fake_calc_ts,
            ),
        ):
            # 1. Cold miss populates 60s cache
            m1 = await admin_client.get("/api/v1/admin/dashboard/metrics/?period=month")
            assert m1.status_code == 200
            assert m1.json()["total_conversations"] == 11
            assert metrics_calls == 1
            assert cache_store["admin:dashboard:metrics:v1:month"][1] == 60

            # 2. Second request hits cache without recomputing
            m2 = await admin_client.get("/api/v1/admin/dashboard/metrics/?period=month")
            assert m2.status_code == 200
            assert m2.json()["total_conversations"] == 11
            assert metrics_calls == 1

            # 3. Different period uses a distinct cache key
            mw = await admin_client.get("/api/v1/admin/dashboard/metrics/?period=week")
            assert mw.status_code == 200
            assert mw.json()["period"] == "week"
            assert metrics_calls == 2

            # 4. refresh=true bypasses cache read and updates cached value
            m3 = await admin_client.get(
                "/api/v1/admin/dashboard/metrics/?period=month&refresh=true"
            )
            assert m3.status_code == 200
            assert m3.json()["total_conversations"] == 13
            assert metrics_calls == 3

            # 5. Timeseries caches with 60s TTL and honours refresh=true
            t1 = await admin_client.get(
                "/api/v1/admin/dashboard/timeseries/?period=month"
            )
            t2 = await admin_client.get(
                "/api/v1/admin/dashboard/timeseries/?period=month"
            )
            assert t1.status_code == 200 and t2.status_code == 200
            assert t1.json()["points"][0]["new"] == 1
            assert t2.json()["points"][0]["new"] == 1
            assert ts_calls == 1
            assert cache_store["admin:dashboard:timeseries:v1:month"][1] == 60

            t3 = await admin_client.get(
                "/api/v1/admin/dashboard/timeseries/?period=month&refresh=true"
            )
            assert t3.status_code == 200
            assert t3.json()["points"][0]["new"] == 2
            assert ts_calls == 2

        # 6. Redis connection failure fails open cleanly
        class BrokenRedis:
            async def get(self, _key: str) -> str | None:
                raise ConnectionError("redis down")

            async def set(self, _key: str, _val: str, ex: int | None = None) -> None:
                raise ConnectionError("redis down")

        with (
            patch("src.api.v1.admin.get_redis_client", return_value=BrokenRedis()),
            patch(
                "src.services.dashboard_metrics.calculate_dashboard_metrics",
                side_effect=fake_calc_metrics,
            ),
        ):
            m_err = await admin_client.get(
                "/api/v1/admin/dashboard/metrics/?period=day"
            )
            assert m_err.status_code == 200
            assert m_err.json()["period"] == "day"
    finally:
        app.dependency_overrides.pop(get_db, None)
