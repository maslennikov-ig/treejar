from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.v1.admin import require_admin_session
from src.core.database import get_db
from src.schemas.admin import (
    AdminActionResult,
    AdminBotRulePreviewRequest,
    AdminBotRulePreviewResponse,
    AdminBotRuleRead,
    AdminBotRuleUpdate,
    AdminBotRuleWrite,
)
from src.schemas.common import PaginatedResponse
from src.services.admin_bot_rules import (
    archive_admin_bot_rule,
    create_admin_bot_rule,
    get_admin_bot_rule,
    list_admin_bot_rules,
    preview_admin_bot_rules,
    reindex_admin_bot_rule,
    reindex_admin_bot_rules,
    test_admin_bot_rule,
    update_admin_bot_rule,
)

router = APIRouter(dependencies=[Depends(require_admin_session)])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/rules", response_model=PaginatedResponse[AdminBotRuleRead])
async def get_rules(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    type: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    segment: str | None = None,
    include_archived: bool = False,
) -> PaginatedResponse[AdminBotRuleRead]:
    return await list_admin_bot_rules(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        type=type,
        stage=stage,
        language=language,
        segment=segment,
        include_archived=include_archived,
    )


@router.get("/rules/{rule_id}", response_model=AdminBotRuleRead)
async def get_rule(rule_id: uuid.UUID, db: DbSession) -> AdminBotRuleRead:
    return await get_admin_bot_rule(db=db, rule_id=rule_id)


@router.post("/rules", response_model=AdminBotRuleRead, status_code=201)
async def post_rule(
    body: AdminBotRuleWrite,
    db: DbSession,
    request: Request,
) -> AdminBotRuleRead:
    return await create_admin_bot_rule(db=db, body=body, request=request)


@router.patch("/rules/{rule_id}", response_model=AdminBotRuleRead)
async def patch_rule(
    rule_id: uuid.UUID,
    body: AdminBotRuleUpdate,
    db: DbSession,
    request: Request,
) -> AdminBotRuleRead:
    return await update_admin_bot_rule(
        db=db,
        rule_id=rule_id,
        body=body,
        request=request,
    )


@router.delete("/rules/{rule_id}", response_model=AdminBotRuleRead)
async def delete_rule(
    rule_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminBotRuleRead:
    return await archive_admin_bot_rule(db=db, rule_id=rule_id, request=request)


@router.post("/rules/{rule_id}/reindex", response_model=AdminBotRuleRead)
async def post_rule_reindex(
    rule_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminBotRuleRead:
    return await reindex_admin_bot_rule(db=db, rule_id=rule_id, request=request)


@router.post("/rules/{rule_id}/test", response_model=AdminBotRulePreviewResponse)
async def post_rule_test(
    rule_id: uuid.UUID,
    body: AdminBotRulePreviewRequest,
    db: DbSession,
) -> AdminBotRulePreviewResponse:
    return await test_admin_bot_rule(db=db, rule_id=rule_id, body=body)


@router.post("/preview", response_model=AdminBotRulePreviewResponse)
async def post_preview(
    body: AdminBotRulePreviewRequest,
    db: DbSession,
) -> AdminBotRulePreviewResponse:
    return await preview_admin_bot_rules(db=db, body=body)


@router.post("/reindex", response_model=AdminActionResult)
async def post_reindex_all(
    db: DbSession,
    request: Request,
) -> AdminActionResult:
    return await reindex_admin_bot_rules(db=db, request=request)
