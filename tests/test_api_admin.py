import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import requires_db


@pytest.mark.asyncio
async def test_admin_requires_auth(client: AsyncClient) -> None:
    """All /api/v1/admin/ endpoints should return 401 without auth."""
    response = await client.get("/api/v1/admin/prompts/")
    assert response.status_code == 401


@requires_db
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

    response_s2 = await admin_client.patch(
        "/api/v1/admin/settings/", json={"bot_enabled": False, "default_language": "ar"}
    )
    assert response_s2.status_code == 200
    data2 = response_s2.json()
    assert data2["bot_enabled"] is False
    assert data2["default_language"] == "ar"

    # --- test_admin_mount_redirects_to_login ---
    response_rm = await admin_client.get("/admin/")
    assert response_rm.status_code in (302, 303)
    assert "/admin/login" in response_rm.headers["location"]


@requires_db
@pytest.mark.asyncio
async def test_dashboard_metrics(admin_client: AsyncClient) -> None:
    """Test the expanded dashboard metrics endpoint (17 KPIs, 6 categories)."""
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


@requires_db
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
    """Test dashboard SPA route serves index.html."""
    response = await client.get("/dashboard/")
    assert response.status_code == 200
