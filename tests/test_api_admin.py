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


class _FakeScalarResult:
    def __init__(self, value: object) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object:
        return self._value


class _FakeAIQualityConfigDB:
    def __init__(self, value: dict[str, Any] | None = None) -> None:
        self.config = None
        if value is not None:
            from src.models.system_config import SystemConfig

            self.config = SystemConfig(key="ai_quality_controls", value=value)
        self.added: list[object] = []
        self.committed = False

    async def execute(self, _stmt: object) -> _FakeScalarResult:
        return _FakeScalarResult(self.config)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        self.config = obj

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
        self.committed = False

    async def execute(self, stmt: object) -> _FakeScalarResult:
        text = str(stmt)
        for key, row in self.rows.items():
            if key in text:
                return _FakeScalarResult(row)
        return _FakeScalarResult(None)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        key = obj.key
        self.rows[key] = obj

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
async def test_admin_login_grants_dashboard_and_api_access(client: AsyncClient) -> None:
    """Real SQLAdmin login should authorize /dashboard and /api/v1/admin routes."""
    dashboard_response = await client.get("/dashboard/")
    assert dashboard_response.status_code == 401

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
    assert "default_language" in data1
    assert "telegram_test_mode_enabled" in data1

    response_s2 = await admin_client.patch(
        "/api/v1/admin/settings/",
        json={
            "bot_enabled": False,
            "default_language": "ar",
            "telegram_test_mode_enabled": False,
        },
    )
    assert response_s2.status_code == 200
    data2 = response_s2.json()
    assert data2["bot_enabled"] is False
    assert data2["default_language"] == "ar"
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

    # Also test details and edit pages for the mock items
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
        assert resp_edit.status_code == 200, f"Failed on {edit_url}"

        # create
        create_url = f"/admin/{model_name}/create"
        resp_c = await client.get(create_url)
        if resp_c.status_code == 500:
            print(f"500 ERROR ON {create_url}")
            print(resp_c.text)
        assert resp_c.status_code == 200, f"Failed on {create_url}"


@pytest.mark.asyncio
async def test_admin_dashboard_spa_route(client: AsyncClient) -> None:
    """Dashboard SPA route should require an authenticated admin session."""
    response = await client.get("/dashboard/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_dashboard_spa_route_after_login(admin_client: AsyncClient) -> None:
    """Dashboard SPA route should serve the app for authenticated admins."""
    response = await admin_client.get("/dashboard/")
    assert response.status_code == 200


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
            "src.api.v1.admin.evaluate_escalation",
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
        evaluate_response = await admin_client.post(
            f"/api/v1/admin/manager-reviews/{pending_item['escalation_id']}/evaluate"
        )

    assert recent_response.status_code == 200
    assert recent_response.json()["items"][0]["manager_name"] == "Amina"
    assert pending_response.status_code == 200
    assert pending_response.json()[0]["phone"] == "+971501234567"
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["summary"] == "Strong follow-up and clear close."
    mock_list.assert_awaited_once()
    mock_pending.assert_awaited_once()
    mock_evaluate.assert_awaited_once()


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
    """AI Quality Controls should default to no automated QA work."""
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
    assert fake_db.committed is True
    assert fake_db.config is not None
    assert fake_db.config.value["bot_qa"]["model"] == "z-ai/glm-5"
    assert fake_db.config.value["red_flags"]["transcript_mode"] == "full"


@pytest.mark.asyncio
async def test_admin_ai_quality_controls_patch_preserves_unspecified_scopes(
    admin_client: AsyncClient,
) -> None:
    """PATCH should merge updates instead of resetting other scopes to defaults."""
    fake_db = _FakeAIQualityConfigDB(
        {
            "bot_qa": {"mode": "scheduled", "max_calls_per_run": 2},
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
    config = response.json()["config"]
    assert config["bot_qa"]["mode"] == "scheduled"
    assert config["bot_qa"]["max_calls_per_run"] == 2
    assert config["manager_qa"]["mode"] == "manual"
    assert config["manager_qa"]["max_calls_per_run"] == 3
    assert config["red_flags"]["mode"] == "manual"


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
