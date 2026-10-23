"""tj-ierv.1: canonical KB / bot-rule seed, archived filter and QA hiding."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import AsyncClient
from sqlalchemy.dialects import postgresql

from src.models.bot_behavior_rule import BotBehaviorRule
from src.models.knowledge_base import KnowledgeBase
from src.services import canonical_admin_seed as seed


class FakeEmbeddingEngine:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        return [[0.1] * 4 for _ in texts]


def _fake_db(existing: list[Any]) -> MagicMock:
    db = MagicMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = existing
    db.execute = AsyncMock(return_value=result)
    db.added = []
    db.add.side_effect = db.added.append
    return db


def _compiled(statement: Any) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()


# --------------------------------------------------------------------------
# Catalogue content
# --------------------------------------------------------------------------


def test_canonical_kb_covers_policies_and_faq_without_manager_terms() -> None:
    articles = seed.canonical_kb_articles()
    titles = [article.title for article in articles]
    categories = {article.category for article in articles}

    assert len(titles) == len(set(titles))
    assert {"delivery", "warranty", "payment", "showroom", "b2b", "products"} <= (
        categories
    )
    faq_titles = [title for title in titles if title.startswith("FAQ: ")]
    # docs/faq.md has 20 questions; 12, 13 and 17 are manager-controlled.
    assert len(faq_titles) == 17
    assert not any("competitor" in title.lower() for title in faq_titles)
    assert not any("warranty" in title.lower() for title in faq_titles)
    assert not any("payment terms" in title.lower() for title in faq_titles)


def test_canonical_kb_makes_no_unapproved_promises() -> None:
    text = " ".join(article.content.lower() for article in seed.canonical_kb_articles())

    for forbidden in ("7-day", "7 day", "9:00", "free assembly is", "1-5 year"):
        assert forbidden not in text
    vat = next(a for a in seed.canonical_kb_articles() if a.category == "payment")
    assert "excl. 5% vat" in vat.content.lower()
    assert "incl. 5% vat" in vat.content.lower()


def test_canonical_bot_rules_cover_the_eight_operating_rules() -> None:
    rules = seed.CANONICAL_BOT_RULES
    assert len(rules) == 8
    assert len({rule.key for rule in rules}) == 8
    keys = {rule.key for rule in rules}
    assert keys == {
        "vat_dual_pricing",
        "package_math_budget",
        "canonical_product_links",
        "no_hallucinated_facts",
        "wholesale_handoff",
        "custom_furniture_handoff",
        "out_of_catalog_sourcing",
        "concise_consultative_tone",
    }
    links = next(rule for rule in rules if rule.key == "canonical_product_links")
    assert "treejartrading.ae/product/" in links.instruction
    assert "r2.dev" in links.instruction
    wholesale = next(rule for rule in rules if rule.key == "wholesale_handoff")
    assert "20 or more" in wholesale.instruction
    assert wholesale.type == "escalation_rule"
    tone = next(rule for rule in rules if rule.key == "concise_consultative_tone")
    assert tone.type == "style_rule"


# --------------------------------------------------------------------------
# Knowledge base sync
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_canonical_kb_creates_all_rows_with_embeddings() -> None:
    db = _fake_db([])
    engine = FakeEmbeddingEngine()
    articles = seed.canonical_kb_articles()

    counts = await seed.sync_canonical_knowledge_base(db, engine)

    assert counts["created"] == len(articles)
    assert counts["updated"] == counts["restored"] == counts["unchanged"] == 0
    assert counts["total_active"] == len(articles)
    assert all(row.source == seed.CANONICAL_KB_SOURCE for row in db.added)
    assert all(row.embedding is not None for row in db.added)
    assert len(engine.calls) == 1


@pytest.mark.asyncio
async def test_sync_canonical_kb_is_idempotent_and_restores_soft_deleted() -> None:
    article = seed.canonical_kb_articles()[0]
    other = seed.canonical_kb_articles()[1]
    unchanged = KnowledgeBase(
        id=uuid.uuid4(),
        source=seed.CANONICAL_KB_SOURCE,
        title=article.title,
        content=article.content,
        language=article.language,
        category=article.category,
        embedding=[0.2] * 4,
    )
    deleted = KnowledgeBase(
        id=uuid.uuid4(),
        source=seed.CANONICAL_KB_SOURCE,
        title=other.title,
        content="stale content",
        language=other.language,
        category=other.category,
        embedding=[0.2] * 4,
        deleted_at=datetime.now(UTC),
        deleted_by="admin",
    )
    db = _fake_db([unchanged, deleted])
    engine = FakeEmbeddingEngine()

    counts = await seed.sync_canonical_knowledge_base(
        db, engine, articles=[article, other]
    )

    assert counts == {
        "created": 0,
        "updated": 0,
        "restored": 1,
        "unchanged": 1,
        "total_active": 2,
    }
    assert deleted.deleted_at is None and deleted.deleted_by is None
    assert deleted.content == other.content
    assert engine.calls == [[other.content]]
    assert db.added == []


# --------------------------------------------------------------------------
# Bot rules sync
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_canonical_bot_rules_creates_active_rules() -> None:
    db = _fake_db([])
    engine = FakeEmbeddingEngine()

    counts = await seed.sync_canonical_bot_behavior_rules(db, engine, actor="admin")

    assert counts["created"] == 8
    assert counts["total_active"] == 8
    assert {row.status for row in db.added} == {"active"}
    assert all(row.archived_at is None for row in db.added)
    assert all(
        row.metadata_["source_type"] == seed.CANONICAL_RULE_SOURCE_TYPE
        for row in db.added
    )
    assert all(row.embedding is not None for row in db.added)


@pytest.mark.asyncio
async def test_sync_canonical_bot_rules_restores_archived_and_skips_unchanged() -> None:
    first, second = seed.CANONICAL_BOT_RULES[:2]

    def row_for(rule: seed.CanonicalBotRule, **overrides: Any) -> BotBehaviorRule:
        values: dict[str, Any] = {
            "id": uuid.uuid4(),
            "title": rule.title,
            "type": rule.type,
            "status": "active",
            "priority": rule.priority,
            "scope": rule.scope,
            "stage": rule.stage,
            "language": None,
            "segment": None,
            "instruction": rule.instruction,
            "trigger_examples": list(rule.trigger_examples),
            "embedding": [0.3] * 4,
            "archived_at": None,
            "metadata_": {
                "source_type": seed.CANONICAL_RULE_SOURCE_TYPE,
                "canonical_key": rule.key,
            },
        }
        values.update(overrides)
        return BotBehaviorRule(**values)

    unchanged = row_for(first)
    archived = row_for(second, status="archived", archived_at=datetime.now(UTC))
    unrelated = row_for(second, metadata_=None, title="Admin custom rule")
    db = _fake_db([unchanged, archived, unrelated])
    engine = FakeEmbeddingEngine()

    counts = await seed.sync_canonical_bot_behavior_rules(
        db, engine, rules=[first, second]
    )

    assert counts["unchanged"] == 1
    assert counts["restored"] == 1
    assert counts["created"] == 0
    assert archived.status == "active" and archived.archived_at is None
    assert unrelated.title == "Admin custom rule"
    assert engine.calls == []


# --------------------------------------------------------------------------
# List filters
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_admin_bot_rules_archived_status_returns_archived_rows() -> None:
    from src.services.admin_bot_rules import list_admin_bot_rules

    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, item_result])

    await list_admin_bot_rules(db, status="archived", include_archived=False)

    count_sql = _compiled(db.execute.call_args_list[0].args[0])
    assert "bot_behavior_rules.status = 'archived'" in count_sql
    assert "archived_at is null" not in count_sql
    assert "qa disposable" in count_sql


@pytest.mark.asyncio
async def test_list_admin_bot_rules_default_hides_archived_and_qa_rows() -> None:
    from src.services.admin_bot_rules import list_admin_bot_rules

    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, item_result])

    await list_admin_bot_rules(db)
    default_sql = _compiled(db.execute.call_args_list[0].args[0])
    assert "archived_at is null" in default_sql
    assert "not (" in default_sql and "qa disposable" in default_sql

    db.execute = AsyncMock(side_effect=[count_result, item_result])
    await list_admin_bot_rules(db, search="QA disposable")
    search_sql = _compiled(db.execute.call_args_list[0].args[0])
    assert "not (" not in search_sql


@pytest.mark.asyncio
async def test_list_admin_kb_entries_hides_qa_rows_unless_searched() -> None:
    from src.services.admin_knowledge_base import list_admin_kb_entries

    db = MagicMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    item_result = MagicMock()
    item_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, item_result])

    await list_admin_kb_entries(db)
    default_sql = _compiled(db.execute.call_args_list[0].args[0])
    assert "qa disposable" in default_sql
    assert "qa sentinel" in default_sql

    db.execute = AsyncMock(side_effect=[count_result, item_result])
    await list_admin_kb_entries(db, search="qa smoke")
    assert "qa disposable" not in _compiled(db.execute.call_args_list[0].args[0])


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "module_name", "attr"),
    [
        (
            "/api/v1/admin/knowledge-base/sync-canonical",
            "admin_knowledge_base",
            "sync_canonical_admin_kb_entries",
        ),
        (
            "/api/v1/admin/knowledge-base/seed-defaults",
            "admin_knowledge_base",
            "sync_canonical_admin_kb_entries",
        ),
        (
            "/api/v1/admin/bot-rules/sync-canonical",
            "admin_bot_rules",
            "sync_canonical_admin_bot_rules",
        ),
        (
            "/api/v1/admin/bot-rules/seed-defaults",
            "admin_bot_rules",
            "sync_canonical_admin_bot_rules",
        ),
    ],
)
async def test_sync_canonical_endpoints(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    module_name: str,
    attr: str,
) -> None:
    import importlib

    from src.schemas.admin import AdminCanonicalSyncResult

    module = importlib.import_module(f"src.api.v1.{module_name}")

    async def fake_sync(**kwargs: Any) -> AdminCanonicalSyncResult:
        assert "db" in kwargs and "request" in kwargs
        return AdminCanonicalSyncResult(
            ok=True, status="synced", created=3, total_active=3
        )

    monkeypatch.setattr(module, attr, fake_sync)

    response = await admin_client.post(path)

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] == 3
    assert payload["total_active"] == 3


@pytest.mark.asyncio
async def test_sync_canonical_endpoint_requires_admin_session(
    client: AsyncClient,
) -> None:
    response = await client.post("/api/v1/admin/bot-rules/sync-canonical")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_canonical_admin_kb_entries_audits_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import admin_knowledge_base

    async def fake_sync(db: Any, **kwargs: Any) -> dict[str, int]:
        return {
            "created": 2,
            "updated": 1,
            "restored": 0,
            "unchanged": 4,
            "total_active": 7,
        }

    audit = AsyncMock()
    monkeypatch.setattr(
        admin_knowledge_base, "sync_canonical_knowledge_base", fake_sync
    )
    monkeypatch.setattr(admin_knowledge_base, "log_admin_action", audit)
    db = MagicMock()
    db.commit = AsyncMock()

    result = await admin_knowledge_base.sync_canonical_admin_kb_entries(
        db, request=None
    )

    assert result.created == 2 and result.total_active == 7
    assert audit.await_args.kwargs["action"] == "knowledge_base.sync_canonical"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_safe_sync_preserves_admin_edits_and_deleted_rows() -> None:
    article = seed.canonical_kb_articles()[0]
    second = seed.canonical_kb_articles()[1]
    third = seed.canonical_kb_articles()[2]

    customized = KnowledgeBase(
        id=uuid.uuid4(),
        source=seed.CANONICAL_KB_SOURCE,
        title=article.title,
        content="Admin custom policy wording",
        language=article.language,
        category=article.category,
        embedding=[0.2] * 4,
    )
    deleted = KnowledgeBase(
        id=uuid.uuid4(),
        source=seed.CANONICAL_KB_SOURCE,
        title=second.title,
        content=second.content,
        language=second.language,
        category=second.category,
        embedding=[0.2] * 4,
        deleted_at=datetime.now(UTC),
        deleted_by="admin",
    )
    db = _fake_db([customized, deleted])
    engine = FakeEmbeddingEngine()

    preview = await seed.preview_canonical_knowledge_base(
        db, articles=[article, second, third]
    )
    assert preview.will_create == 1
    assert preview.customized == 1
    assert preview.deleted_or_archived == 1

    counts = await seed.sync_canonical_knowledge_base(
        db,
        engine,
        articles=[article, second, third],
        mode="safe",
    )
    assert counts["created"] == 1
    assert counts["restored"] == 0
    assert customized.content == "Admin custom policy wording"
    assert deleted.deleted_at is not None


@pytest.mark.asyncio
async def test_catalog_status_and_system_health_endpoints(
    admin_client: AsyncClient,
) -> None:
    cat_resp = await admin_client.get("/api/v1/admin/catalog/status")
    assert cat_resp.status_code == 200
    cat_data = cat_resp.json()
    assert "sources" in cat_data
    assert "treejar" in cat_data["sources"]
    assert "zoho" in cat_data["sources"]
    assert "zoho_snapshot" in cat_data

    health_resp = await admin_client.get("/api/v1/admin/system/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert "contours" in health_data
    contour_ids = {c["id"] for c in health_data["contours"]}
    assert {
        "whatsapp",
        "telegram",
        "zoho_inventory",
        "knowledge_rag",
        "llm_engine",
    } <= contour_ids
