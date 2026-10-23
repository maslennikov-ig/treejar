from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.models.bot_behavior_rule import BotBehaviorRule
from src.rag.embeddings import EmbeddingEngine
from src.schemas.admin import (
    AdminActionResult,
    AdminBotRulePreviewRequest,
    AdminBotRulePreviewResponse,
    AdminBotRuleRead,
    AdminBotRuleUpdate,
    AdminBotRuleWrite,
    AdminCanonicalSyncPreview,
    AdminCanonicalSyncResult,
    AdminCanonicalSyncStatus,
)
from src.schemas.common import PaginatedResponse
from src.services.admin_audit import log_admin_action
from src.services.bot_behavior_rules import (
    BehaviorRuleSearchContext,
    format_behavior_rules_prompt,
    rule_embedding_text,
    rule_to_applied,
    search_behavior_rules,
)
from src.services.canonical_admin_seed import (
    CANONICAL_BOT_RULES,
    CANONICAL_RULE_SOURCE_TYPE,
    is_canonical_bot_rule_customized,
    preview_canonical_bot_behavior_rules,
    qa_synthetic_title_clause,
    search_mentions_qa,
    sync_canonical_bot_behavior_rules,
)

_LAST_RULES_SYNC_STATE: dict[str, Any] = {
    "running": False,
    "last_mode": None,
    "last_synced_at": None,
    "last_result": None,
}


def _pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 1


def _now() -> datetime:
    return datetime.now(UTC)


def _enum_value(value: object | None) -> object | None:
    if isinstance(value, Enum):
        return str(value.value)
    return value


def _optional_str(value: object | None) -> str | None:
    raw_value = _enum_value(value)
    return str(raw_value) if raw_value is not None else None


def _read(rule: BotBehaviorRule) -> AdminBotRuleRead:
    metadata = rule.metadata_ if isinstance(rule.metadata_, dict) else {}
    raw_source = metadata.get("source_type")
    source_type = (
        "canonical_treejar"
        if raw_source == CANONICAL_RULE_SOURCE_TYPE
        else str(raw_source)
        if isinstance(raw_source, str) and raw_source
        else "manual"
    )
    canonical_key = metadata.get("canonical_key")
    return AdminBotRuleRead(
        id=rule.id,
        title=rule.title,
        type=rule.type,
        status=rule.status,
        priority=rule.priority,
        scope=rule.scope,
        stage=rule.stage,
        language=rule.language,
        segment=rule.segment,
        instruction=rule.instruction,
        trigger_examples=list(rule.trigger_examples or []),
        has_embedding=rule.embedding is not None,
        source_type=source_type,
        canonical_key=canonical_key if isinstance(canonical_key, str) else None,
        is_canonical_customized=is_canonical_bot_rule_customized(rule),
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
        archived_at=rule.archived_at,
    )


def _snapshot(rule: BotBehaviorRule) -> dict[str, Any]:
    return {
        "title": rule.title,
        "type": rule.type,
        "status": rule.status,
        "priority": rule.priority,
        "scope": rule.scope,
        "stage": rule.stage,
        "language": rule.language,
        "segment": rule.segment,
        "instruction": rule.instruction,
        "trigger_examples": list(rule.trigger_examples or []),
        "has_embedding": rule.embedding is not None,
        "created_by": rule.created_by,
        "updated_by": rule.updated_by,
        "archived_at": rule.archived_at.isoformat() if rule.archived_at else None,
    }


async def list_admin_bot_rules(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status: str | None = None,
    type: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    segment: str | None = None,
    include_archived: bool = False,
) -> PaginatedResponse[AdminBotRuleRead]:
    filters: list[ColumnElement[bool]] = []
    normalized_status = status.strip().lower() if status and status.strip() else None
    if normalized_status == "archived":
        # Archived rules carry both status="archived" and archived_at; the
        # include_archived default must not hide exactly what was asked for.
        filters.append(BotBehaviorRule.status == "archived")
    else:
        if not include_archived:
            filters.append(BotBehaviorRule.archived_at.is_(None))
        if normalized_status is not None:
            filters.append(BotBehaviorRule.status == normalized_status)
    if not search_mentions_qa(search):
        filters.append(not_(qa_synthetic_title_clause(BotBehaviorRule.title)))
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                BotBehaviorRule.title.ilike(like),
                BotBehaviorRule.instruction.ilike(like),
            )
        )
    if type:
        filters.append(BotBehaviorRule.type == type)
    if stage:
        filters.append(BotBehaviorRule.stage == stage)
    if language:
        filters.append(BotBehaviorRule.language == language)
    if segment:
        filters.append(BotBehaviorRule.segment.ilike(segment))

    count_stmt = select(func.count()).select_from(BotBehaviorRule)
    item_stmt = select(BotBehaviorRule).order_by(
        BotBehaviorRule.priority.asc(),
        BotBehaviorRule.created_at.desc(),
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
        item_stmt = item_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())
    item_result = await db.execute(
        item_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    return PaginatedResponse(
        items=[_read(rule) for rule in item_result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


async def get_admin_bot_rule(
    db: AsyncSession,
    rule_id: uuid.UUID,
) -> AdminBotRuleRead:
    rule = await db.get(BotBehaviorRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Bot behavior rule not found")
    return _read(rule)


async def create_admin_bot_rule(
    db: AsyncSession,
    *,
    body: AdminBotRuleWrite,
    request: object | None,
) -> AdminBotRuleRead:
    now = _now()
    rule = BotBehaviorRule(
        id=uuid.uuid4(),
        title=body.title,
        type=body.type,
        status=body.status,
        priority=body.priority,
        scope=body.scope,
        stage=_optional_str(body.stage),
        language=_optional_str(body.language),
        segment=body.segment,
        instruction=body.instruction,
        trigger_examples=body.trigger_examples,
        created_by="admin",
        updated_by="admin",
        updated_at=now,
        archived_at=now if body.status == "archived" else None,
    )
    rule.embedding = await EmbeddingEngine().embed_async(rule_embedding_text(rule))
    db.add(rule)
    await log_admin_action(
        db,
        action="bot_rule.create",
        entity_type="bot_behavior_rule",
        entity_id=rule.id,
        before=None,
        after=_snapshot(rule),
        request=request,
    )
    await db.commit()
    await db.refresh(rule)
    return _read(rule)


async def update_admin_bot_rule(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID,
    body: AdminBotRuleUpdate,
    request: object | None,
) -> AdminBotRuleRead:
    rule = await db.get(BotBehaviorRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Bot behavior rule not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return _read(rule)

    before = _snapshot(rule)
    for key, value in update_data.items():
        setattr(rule, key, _enum_value(value))
    if update_data.get("status") == "archived":
        rule.archived_at = _now()
    elif update_data.get("status") in {"draft", "active"}:
        rule.archived_at = None
    if {"title", "instruction", "trigger_examples"} & set(update_data):
        rule.embedding = await EmbeddingEngine().embed_async(rule_embedding_text(rule))
    rule.updated_by = "admin"
    rule.updated_at = _now()

    await log_admin_action(
        db,
        action="bot_rule.update",
        entity_type="bot_behavior_rule",
        entity_id=rule_id,
        before=before,
        after=_snapshot(rule),
        request=request,
        metadata={"updated_fields": sorted(update_data)},
    )
    await db.commit()
    await db.refresh(rule)
    return _read(rule)


async def archive_admin_bot_rule(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID,
    request: object | None,
) -> AdminBotRuleRead:
    rule = await db.get(BotBehaviorRule, rule_id)
    if rule is None or rule.archived_at is not None:
        raise HTTPException(status_code=404, detail="Bot behavior rule not found")

    before = _snapshot(rule)
    rule.status = "archived"
    rule.archived_at = _now()
    rule.updated_by = "admin"
    rule.updated_at = rule.archived_at
    await log_admin_action(
        db,
        action="bot_rule.archive",
        entity_type="bot_behavior_rule",
        entity_id=rule_id,
        before=before,
        after=_snapshot(rule),
        request=request,
    )
    await db.commit()
    await db.refresh(rule)
    return _read(rule)


async def reindex_admin_bot_rule(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID,
    request: object | None,
) -> AdminBotRuleRead:
    rule = await db.get(BotBehaviorRule, rule_id)
    if rule is None or rule.archived_at is not None:
        raise HTTPException(status_code=404, detail="Bot behavior rule not found")

    before = _snapshot(rule)
    rule.embedding = await EmbeddingEngine().embed_async(rule_embedding_text(rule))
    rule.updated_by = "admin"
    rule.updated_at = _now()
    await log_admin_action(
        db,
        action="bot_rule.reindex",
        entity_type="bot_behavior_rule",
        entity_id=rule_id,
        before=before,
        after=_snapshot(rule),
        request=request,
    )
    await db.commit()
    await db.refresh(rule)
    return _read(rule)


async def reindex_admin_bot_rules(
    db: AsyncSession,
    *,
    request: object | None,
) -> AdminActionResult:
    result = await db.execute(
        select(BotBehaviorRule).where(BotBehaviorRule.archived_at.is_(None))
    )
    rules = list(result.scalars().all())
    engine = EmbeddingEngine()
    for rule in rules:
        rule.embedding = await engine.embed_async(rule_embedding_text(rule))
        rule.updated_by = "admin"
        rule.updated_at = _now()
    await log_admin_action(
        db,
        action="bot_rule.reindex_all",
        entity_type="bot_behavior_rule",
        before=None,
        after={"count": len(rules)},
        request=request,
    )
    await db.commit()
    return AdminActionResult(
        ok=True,
        status="reindexed",
        detail=f"Reindexed {len(rules)} bot behavior rules",
    )


async def preview_admin_bot_rules(
    db: AsyncSession,
    *,
    body: AdminBotRulePreviewRequest,
) -> AdminBotRulePreviewResponse:
    rules = await search_behavior_rules(
        db,
        context=BehaviorRuleSearchContext(
            message=body.message,
            stage=_optional_str(body.stage),
            language=_optional_str(body.language),
            segment=body.segment,
        ),
    )
    applied = [rule_to_applied(rule) for rule in rules]
    return AdminBotRulePreviewResponse(
        applied_rules=applied,
        prompt_block=format_behavior_rules_prompt(applied),
        rule_count=len(applied),
    )


async def test_admin_bot_rule(
    db: AsyncSession,
    *,
    rule_id: uuid.UUID,
    body: AdminBotRulePreviewRequest,
) -> AdminBotRulePreviewResponse:
    rule = await db.get(BotBehaviorRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Bot behavior rule not found")

    preview = await preview_admin_bot_rules(db=db, body=body)
    if all(applied.id != rule_id for applied in preview.applied_rules):
        preview.applied_rules.insert(0, rule_to_applied(rule))
        preview.rule_count = len(preview.applied_rules)
        preview.prompt_block = format_behavior_rules_prompt(preview.applied_rules)
    return preview


async def preview_canonical_admin_bot_rules(
    db: AsyncSession,
) -> AdminCanonicalSyncPreview:
    """Preview diff between current DB bot rules and canonical Noor templates."""
    return await preview_canonical_bot_behavior_rules(db)


async def get_canonical_admin_bot_rules_sync_status(
    db: AsyncSession,
) -> AdminCanonicalSyncStatus:
    """Return canonical bot rules sync status and template coverage."""
    preview = await preview_canonical_bot_behavior_rules(db)
    active_count = (
        preview.total_templates - preview.will_create - preview.deleted_or_archived
    )
    return AdminCanonicalSyncStatus(
        kind="bot_rules",
        running=bool(_LAST_RULES_SYNC_STATE.get("running", False)),
        last_mode=_LAST_RULES_SYNC_STATE.get("last_mode"),
        last_synced_at=_LAST_RULES_SYNC_STATE.get("last_synced_at"),
        last_result=_LAST_RULES_SYNC_STATE.get("last_result"),
        total_templates=preview.total_templates,
        active_canonical_count=max(0, active_count),
        customized_count=preview.customized,
        unindexed_count=preview.unindexed,
    )


async def sync_canonical_admin_bot_rules(
    db: AsyncSession,
    *,
    request: object | None,
    mode: Literal["safe", "full_reset"] = "safe",
) -> AdminCanonicalSyncResult:
    """Load the canonical Noor operating rules (idempotent) and audit it."""
    _LAST_RULES_SYNC_STATE["running"] = True
    try:
        counts = await sync_canonical_bot_behavior_rules(db, actor="admin", mode=mode)
        await log_admin_action(
            db,
            action="bot_rule.sync_canonical",
            entity_type="bot_behavior_rule",
            before=None,
            after={**counts, "mode": mode},
            request=request,
            metadata={"canonical_rules": len(CANONICAL_BOT_RULES), "mode": mode},
        )
        await db.commit()
        result = AdminCanonicalSyncResult(
            ok=True,
            status="synced",
            mode=mode,
            detail=(
                f"Canonical bot rules synced ({mode}): {counts['created']} created, "
                f"{counts['updated']} updated, {counts['restored']} restored, "
                f"{counts['unchanged']} unchanged"
            ),
            **counts,
        )
        _LAST_RULES_SYNC_STATE["last_mode"] = mode
        _LAST_RULES_SYNC_STATE["last_synced_at"] = _now()
        _LAST_RULES_SYNC_STATE["last_result"] = result.model_dump(mode="json")
        return result
    finally:
        _LAST_RULES_SYNC_STATE["running"] = False
