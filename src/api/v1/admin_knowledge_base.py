from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.v1.admin import require_admin_session
from src.core.database import get_db
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
from src.services.admin_knowledge_base import (
    approve_admin_kb_candidate,
    create_admin_kb_candidate,
    create_admin_kb_entry,
    get_admin_kb_entry,
    list_admin_kb_candidates,
    list_admin_kb_entries,
    preview_admin_kb_entry,
    reindex_admin_kb_entries,
    reindex_admin_kb_entry,
    reject_admin_kb_candidate,
    soft_delete_admin_kb_entry,
    update_admin_kb_entry,
)

router = APIRouter(dependencies=[Depends(require_admin_session)])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/entries", response_model=PaginatedResponse[AdminKnowledgeBaseRead])
async def get_entries(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    source: str | None = None,
    category: str | None = None,
    language: str | None = None,
    include_deleted: bool = False,
) -> PaginatedResponse[AdminKnowledgeBaseRead]:
    return await list_admin_kb_entries(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        source=source,
        category=category,
        language=language,
        include_deleted=include_deleted,
    )


@router.get("/entries/{entry_id}", response_model=AdminKnowledgeBaseRead)
async def get_entry(
    entry_id: uuid.UUID,
    db: DbSession,
) -> AdminKnowledgeBaseRead:
    return await get_admin_kb_entry(db=db, entry_id=entry_id)


@router.post("/entries/preview", response_model=AdminKnowledgeBasePreview)
async def post_entry_preview(
    body: AdminKnowledgeBaseWrite,
    db: DbSession,
) -> AdminKnowledgeBasePreview:
    return await preview_admin_kb_entry(db=db, body=body)


@router.post("/entries", response_model=AdminKnowledgeBaseRead, status_code=201)
async def post_entry(
    body: AdminKnowledgeBaseWrite,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseRead:
    return await create_admin_kb_entry(db=db, body=body, request=request)


@router.patch("/entries/{entry_id}", response_model=AdminKnowledgeBaseRead)
async def patch_entry(
    entry_id: uuid.UUID,
    body: AdminKnowledgeBaseUpdate,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseRead:
    return await update_admin_kb_entry(
        db=db,
        entry_id=entry_id,
        body=body,
        request=request,
    )


@router.delete("/entries/{entry_id}", response_model=AdminKnowledgeBaseRead)
async def delete_entry(
    entry_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseRead:
    return await soft_delete_admin_kb_entry(
        db=db,
        entry_id=entry_id,
        request=request,
    )


@router.post("/entries/{entry_id}/reindex", response_model=AdminKnowledgeBaseRead)
async def post_entry_reindex(
    entry_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseRead:
    return await reindex_admin_kb_entry(
        db=db,
        entry_id=entry_id,
        request=request,
    )


@router.post("/reindex", response_model=AdminActionResult)
async def post_reindex_all(
    db: DbSession,
    request: Request,
) -> AdminActionResult:
    return await reindex_admin_kb_entries(db=db, request=request)


@router.get(
    "/candidates",
    response_model=PaginatedResponse[AdminKnowledgeBaseCandidate],
    response_model_by_alias=False,
)
async def get_candidates(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = "needs_confirmation",
) -> PaginatedResponse[AdminKnowledgeBaseCandidate]:
    return await list_admin_kb_candidates(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
    )


@router.post(
    "/candidates",
    response_model=AdminKnowledgeBaseCandidate,
    response_model_by_alias=False,
    status_code=201,
)
async def post_candidate(
    body: AdminKnowledgeBaseCandidateCreate,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseCandidate:
    return await create_admin_kb_candidate(db=db, body=body, request=request)


@router.post(
    "/candidates/{candidate_id}/approve",
    response_model=AdminKnowledgeBaseRead,
)
async def post_candidate_approve(
    candidate_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseRead:
    return await approve_admin_kb_candidate(
        db=db,
        candidate_id=candidate_id,
        request=request,
    )


@router.post(
    "/candidates/{candidate_id}/reject",
    response_model=AdminKnowledgeBaseCandidate,
    response_model_by_alias=False,
)
async def post_candidate_reject(
    candidate_id: uuid.UUID,
    body: Annotated[
        AdminKnowledgeBaseCandidateReject,
        Body(default_factory=AdminKnowledgeBaseCandidateReject),
    ],
    db: DbSession,
    request: Request,
) -> AdminKnowledgeBaseCandidate:
    return await reject_admin_kb_candidate(
        db=db,
        candidate_id=candidate_id,
        body=body,
        request=request,
    )
