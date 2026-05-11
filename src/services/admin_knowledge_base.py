from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_base_candidate import KnowledgeBaseCandidate
from src.rag.embeddings import EmbeddingEngine
from src.schemas.admin import (
    AdminActionResult,
    AdminKnowledgeBaseCandidate,
    AdminKnowledgeBaseCandidateCreate,
    AdminKnowledgeBaseCandidateReject,
    AdminKnowledgeBasePreview,
    AdminKnowledgeBaseRead,
    AdminKnowledgeBaseUpdate,
    AdminKnowledgeBaseWrite,
)
from src.schemas.common import PaginatedResponse
from src.services.admin_audit import log_admin_action
from src.services.auto_faq import (
    DUPLICATE_THRESHOLD,
    _detect_context_specific_reasons,
    _detect_unsafe_reasons,
    _nearest_duplicate_similarity,
)


def _pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 1


def _now() -> datetime:
    return datetime.now(UTC)


def _now_naive_utc() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def _kb_snapshot(entry: KnowledgeBase) -> dict[str, Any]:
    return {
        "source": entry.source,
        "title": entry.title,
        "content": entry.content,
        "language": entry.language,
        "category": entry.category,
        "has_embedding": entry.embedding is not None,
        "deleted_at": entry.deleted_at.isoformat() if entry.deleted_at else None,
        "deleted_by": entry.deleted_by,
    }


def _kb_read(entry: KnowledgeBase) -> AdminKnowledgeBaseRead:
    return AdminKnowledgeBaseRead(
        id=entry.id,
        source=entry.source,
        title=entry.title,
        content=entry.content,
        language=entry.language,
        category=entry.category,
        has_embedding=entry.embedding is not None,
        is_auto_generated=bool(entry.is_auto_generated),
        original_question=entry.original_question,
        manager_draft=entry.manager_draft,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        deleted_at=entry.deleted_at,
        deleted_by=entry.deleted_by,
    )


def _candidate_read(candidate: KnowledgeBaseCandidate) -> AdminKnowledgeBaseCandidate:
    return AdminKnowledgeBaseCandidate(
        id=candidate.id,
        question=candidate.question,
        answer=candidate.answer,
        language=candidate.language,
        confidence=_float(candidate.confidence),
        status=candidate.status,
        guard_reasons=list(candidate.guard_reasons or []),
        duplicate_similarity=_float(candidate.duplicate_similarity),
        original_question=candidate.original_question,
        manager_draft=candidate.manager_draft,
        customer_message=candidate.customer_message,
        metadata=candidate.metadata_,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


async def _auto_faq_title_exists(db: AsyncSession, title: str) -> bool:
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.source == "auto_faq", KnowledgeBase.title == title)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _candidate_kb_title(
    db: AsyncSession,
    candidate: KnowledgeBaseCandidate,
) -> str:
    base_title = candidate.question[:200]
    if not await _auto_faq_title_exists(db, base_title):
        return base_title

    suffix = f" [{str(candidate.id)[:8]}]"
    candidate_title = f"{candidate.question[: 200 - len(suffix)]}{suffix}"
    if not await _auto_faq_title_exists(db, candidate_title):
        return candidate_title

    raise HTTPException(
        status_code=409,
        detail="Knowledge-base entry already exists for this Auto-FAQ candidate",
    )


async def _rollback_if_available(db: AsyncSession) -> None:
    rollback = getattr(db, "rollback", None)
    if rollback is not None:
        await rollback()


async def list_admin_kb_entries(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    source: str | None = None,
    category: str | None = None,
    language: str | None = None,
    include_deleted: bool = False,
) -> PaginatedResponse[AdminKnowledgeBaseRead]:
    filters: list[ColumnElement[bool]] = []
    if not include_deleted:
        filters.append(KnowledgeBase.deleted_at.is_(None))
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                KnowledgeBase.title.ilike(like),
                KnowledgeBase.content.ilike(like),
                KnowledgeBase.source.ilike(like),
            )
        )
    if source:
        filters.append(KnowledgeBase.source == source)
    if category:
        filters.append(KnowledgeBase.category == category)
    if language:
        filters.append(KnowledgeBase.language == language)

    count_stmt = select(func.count()).select_from(KnowledgeBase)
    item_stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        item_stmt = item_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())
    item_result = await db.execute(
        item_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    return PaginatedResponse(
        items=[_kb_read(entry) for entry in item_result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


async def get_admin_kb_entry(
    db: AsyncSession,
    entry_id: uuid.UUID,
) -> AdminKnowledgeBaseRead:
    entry = await db.get(KnowledgeBase, entry_id)
    if entry is None or entry.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Knowledge-base entry not found")
    return _kb_read(entry)


async def preview_admin_kb_entry(
    db: AsyncSession,
    body: AdminKnowledgeBaseWrite | AdminKnowledgeBaseUpdate,
) -> AdminKnowledgeBasePreview:
    content = body.content or ""
    unsafe_reasons = list(_detect_unsafe_reasons(body.title or "", content))
    context_reasons = list(_detect_context_specific_reasons(body.title or "", content))
    embedding = await EmbeddingEngine().embed_async(content)
    duplicate_similarity = await _nearest_duplicate_similarity(db, embedding)
    duplicate = (
        duplicate_similarity is not None and duplicate_similarity >= DUPLICATE_THRESHOLD
    )
    return AdminKnowledgeBasePreview(
        embedding_ready=True,
        duplicate=duplicate,
        duplicate_similarity=duplicate_similarity,
        unsafe_reasons=unsafe_reasons,
        context_reasons=context_reasons,
    )


async def create_admin_kb_entry(
    db: AsyncSession,
    *,
    body: AdminKnowledgeBaseWrite,
    request: object | None,
) -> AdminKnowledgeBaseRead:
    now = _now()
    entry = KnowledgeBase(
        id=uuid.uuid4(),
        source=body.source,
        title=body.title,
        content=body.content,
        language=body.language.value,
        category=body.category,
        embedding=await EmbeddingEngine().embed_async(body.content),
        is_auto_generated=False,
        updated_at=now,
    )
    db.add(entry)
    await log_admin_action(
        db,
        action="knowledge_base.create",
        entity_type="knowledge_base",
        entity_id=entry.id,
        before=None,
        after=_kb_snapshot(entry),
        request=request,
    )
    await db.commit()
    await db.refresh(entry)
    return _kb_read(entry)


async def update_admin_kb_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    body: AdminKnowledgeBaseUpdate,
    request: object | None,
) -> AdminKnowledgeBaseRead:
    entry = await db.get(KnowledgeBase, entry_id)
    if entry is None or entry.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Knowledge-base entry not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return _kb_read(entry)

    before = _kb_snapshot(entry)
    for key, value in update_data.items():
        if key == "language" and value is not None:
            value = value.value
        setattr(entry, key, value)
    if "content" in update_data:
        entry.embedding = await EmbeddingEngine().embed_async(entry.content)
    entry.updated_at = _now()

    await log_admin_action(
        db,
        action="knowledge_base.update",
        entity_type="knowledge_base",
        entity_id=entry_id,
        before=before,
        after=_kb_snapshot(entry),
        request=request,
        metadata={"updated_fields": sorted(update_data)},
    )
    await db.commit()
    await db.refresh(entry)
    return _kb_read(entry)


async def soft_delete_admin_kb_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    request: object | None,
) -> AdminKnowledgeBaseRead:
    entry = await db.get(KnowledgeBase, entry_id)
    if entry is None or entry.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Knowledge-base entry not found")

    before = _kb_snapshot(entry)
    entry.deleted_at = _now()
    entry.deleted_by = "admin"
    entry.updated_at = entry.deleted_at
    await log_admin_action(
        db,
        action="knowledge_base.soft_delete",
        entity_type="knowledge_base",
        entity_id=entry_id,
        before=before,
        after=_kb_snapshot(entry),
        request=request,
    )
    await db.commit()
    await db.refresh(entry)
    return _kb_read(entry)


async def reindex_admin_kb_entry(
    db: AsyncSession,
    *,
    entry_id: uuid.UUID,
    request: object | None,
) -> AdminKnowledgeBaseRead:
    entry = await db.get(KnowledgeBase, entry_id)
    if entry is None or entry.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Knowledge-base entry not found")

    before = _kb_snapshot(entry)
    entry.embedding = await EmbeddingEngine().embed_async(entry.content)
    entry.updated_at = _now()
    await log_admin_action(
        db,
        action="knowledge_base.reindex_entry",
        entity_type="knowledge_base",
        entity_id=entry_id,
        before=before,
        after=_kb_snapshot(entry),
        request=request,
    )
    await db.commit()
    await db.refresh(entry)
    return _kb_read(entry)


async def reindex_admin_kb_entries(
    db: AsyncSession,
    *,
    request: object | None,
) -> AdminActionResult:
    result = await db.execute(
        select(KnowledgeBase)
        .where(KnowledgeBase.deleted_at.is_(None))
        .order_by(KnowledgeBase.created_at.asc())
    )
    entries = list(result.scalars().all())
    if not entries:
        return AdminActionResult(ok=True, status="noop", detail="No entries to reindex")

    embeddings = await EmbeddingEngine().embed_batch_async(
        [entry.content for entry in entries]
    )
    now = _now()
    for entry, embedding in zip(entries, embeddings, strict=False):
        entry.embedding = embedding
        entry.updated_at = now

    await log_admin_action(
        db,
        action="knowledge_base.reindex_all",
        entity_type="knowledge_base",
        before=None,
        after={"processed_count": len(entries)},
        request=request,
    )
    await db.commit()
    return AdminActionResult(
        ok=True,
        status="processed",
        detail=f"Reindexed {len(entries)} entries",
    )


async def list_admin_kb_candidates(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = "needs_confirmation",
) -> PaginatedResponse[AdminKnowledgeBaseCandidate]:
    filters: list[ColumnElement[bool]] = []
    if status:
        filters.append(KnowledgeBaseCandidate.status == status)

    count_stmt = select(func.count()).select_from(KnowledgeBaseCandidate)
    item_stmt = select(KnowledgeBaseCandidate).order_by(
        KnowledgeBaseCandidate.created_at.desc()
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
        items=[_candidate_read(row) for row in item_result.scalars().all()],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


async def create_admin_kb_candidate(
    db: AsyncSession,
    *,
    body: AdminKnowledgeBaseCandidateCreate,
    request: object | None,
) -> AdminKnowledgeBaseCandidate:
    preview = await preview_admin_kb_entry(
        db,
        AdminKnowledgeBaseWrite(
            source="auto_faq",
            title=body.question,
            content=f"Q: {body.question}\nA: {body.answer}",
            language=body.language,
            category="faq",
        ),
    )
    if preview.unsafe_reasons:
        status = "blocked_unsafe"
    elif preview.context_reasons:
        status = "blocked_context_specific"
    elif preview.duplicate:
        status = "duplicate"
    else:
        status = "needs_confirmation"

    candidate = KnowledgeBaseCandidate(
        id=uuid.uuid4(),
        question=body.question,
        answer=body.answer,
        language=body.language.value,
        confidence=body.confidence,
        status=status,
        guard_reasons=preview.unsafe_reasons + preview.context_reasons,
        duplicate_similarity=preview.duplicate_similarity,
        original_question=body.original_question,
        manager_draft=body.manager_draft,
        customer_message=body.customer_message,
        metadata_=body.metadata,
    )
    db.add(candidate)
    await log_admin_action(
        db,
        action="knowledge_base.candidate_create",
        entity_type="knowledge_base_candidate",
        entity_id=candidate.id,
        before=None,
        after={
            "question": candidate.question,
            "status": candidate.status,
            "guard_reasons": candidate.guard_reasons,
        },
        request=request,
    )
    await db.commit()
    await db.refresh(candidate)
    return _candidate_read(candidate)


async def approve_admin_kb_candidate(
    db: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    request: object | None,
) -> AdminKnowledgeBaseRead:
    candidate = await db.get(KnowledgeBaseCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "needs_confirmation":
        raise HTTPException(status_code=409, detail="Candidate is not approvable")

    content = f"Q: {candidate.question}\nA: {candidate.answer}"
    title = await _candidate_kb_title(db, candidate)
    entry = KnowledgeBase(
        id=uuid.uuid4(),
        source="auto_faq",
        title=title,
        content=content,
        language=candidate.language,
        category="faq",
        embedding=await EmbeddingEngine().embed_async(content),
        is_auto_generated=True,
        original_question=candidate.original_question or candidate.question,
        manager_draft=candidate.manager_draft,
        updated_at=_now(),
    )
    db.add(entry)
    before = {"candidate_status": candidate.status}
    candidate.status = "approved"
    candidate.updated_at = _now_naive_utc()
    await log_admin_action(
        db,
        action="knowledge_base.candidate_approve",
        entity_type="knowledge_base_candidate",
        entity_id=candidate_id,
        before=before,
        after={"candidate_status": candidate.status, "entry_id": entry.id},
        request=request,
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await _rollback_if_available(db)
        raise HTTPException(
            status_code=409,
            detail="Knowledge-base entry already exists for this Auto-FAQ candidate",
        ) from exc
    await db.refresh(entry)
    return _kb_read(entry)


async def reject_admin_kb_candidate(
    db: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    body: AdminKnowledgeBaseCandidateReject,
    request: object | None,
) -> AdminKnowledgeBaseCandidate:
    candidate = await db.get(KnowledgeBaseCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    before = {"status": candidate.status, "metadata": candidate.metadata_}
    metadata = dict(candidate.metadata_ or {})
    if body.reason:
        metadata["rejection_reason"] = body.reason
    candidate.metadata_ = metadata
    candidate.status = "rejected"
    candidate.updated_at = _now_naive_utc()
    await log_admin_action(
        db,
        action="knowledge_base.candidate_reject",
        entity_type="knowledge_base_candidate",
        entity_id=candidate_id,
        before=before,
        after={"status": candidate.status, "metadata": candidate.metadata_},
        request=request,
    )
    await db.commit()
    await db.refresh(candidate)
    return _candidate_read(candidate)
