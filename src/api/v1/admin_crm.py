from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from src.api.v1.admin import require_admin_session
from src.core.database import get_db
from src.schemas.admin import (
    AdminActionAuditRead,
    AdminActionResult,
    AdminConversationDetail,
    AdminConversationListItem,
    AdminConversationUpdate,
    AdminCustomerListItem,
    AdminEscalationClose,
    AdminEscalationRead,
    AdminEscalationWrite,
    AdminResetExecuteRequest,
    AdminResetExecuteResponse,
    AdminResetPreviewRead,
)
from src.schemas.common import PaginatedResponse
from src.services.admin_crm import (
    close_admin_escalation,
    create_admin_escalation,
    execute_admin_conversation_reset,
    get_admin_conversation_detail,
    list_admin_audit,
    list_admin_conversations,
    list_admin_customers,
    preview_admin_conversation_reset,
    run_admin_bot_quality_review,
    run_admin_manager_quality_review,
    update_admin_conversation,
)

router = APIRouter(dependencies=[Depends(require_admin_session)])

DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("/customers", response_model=PaginatedResponse[AdminCustomerListItem])
async def get_customers(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    escalation: str | None = None,
    deal_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    segment: str | None = None,
) -> PaginatedResponse[AdminCustomerListItem]:
    return await list_admin_customers(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        stage=stage,
        language=language,
        escalation=escalation,
        deal_status=deal_status,
        date_from=date_from,
        date_to=date_to,
        segment=segment,
    )


@router.get(
    "/conversations",
    response_model=PaginatedResponse[AdminConversationListItem],
)
async def get_conversations(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    phone: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    escalation: str | None = None,
    deal_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    segment: str | None = None,
) -> PaginatedResponse[AdminConversationListItem]:
    return await list_admin_conversations(
        db=db,
        page=page,
        page_size=page_size,
        search=search,
        phone=phone,
        status=status,
        stage=stage,
        language=language,
        escalation=escalation,
        deal_status=deal_status,
        date_from=date_from,
        date_to=date_to,
        segment=segment,
    )


@router.get("/conversations/{conversation_id}", response_model=AdminConversationDetail)
async def get_conversation_detail(
    conversation_id: uuid.UUID,
    db: DbSession,
) -> AdminConversationDetail:
    return await get_admin_conversation_detail(
        db=db,
        conversation_id=conversation_id,
    )


@router.patch(
    "/conversations/{conversation_id}", response_model=AdminConversationDetail
)
async def patch_conversation(
    conversation_id: uuid.UUID,
    body: AdminConversationUpdate,
    db: DbSession,
    request: Request,
) -> AdminConversationDetail:
    return await update_admin_conversation(
        db=db,
        conversation_id=conversation_id,
        body=body,
        request=request,
    )


@router.post(
    "/conversations/{conversation_id}/escalations",
    response_model=AdminEscalationRead,
    status_code=201,
)
async def post_conversation_escalation(
    conversation_id: uuid.UUID,
    body: AdminEscalationWrite,
    db: DbSession,
    request: Request,
) -> AdminEscalationRead:
    return await create_admin_escalation(
        db=db,
        conversation_id=conversation_id,
        body=body,
        request=request,
    )


@router.post("/escalations/{escalation_id}/close", response_model=AdminEscalationRead)
async def post_escalation_close(
    escalation_id: uuid.UUID,
    body: Annotated[AdminEscalationClose, Body(default_factory=AdminEscalationClose)],
    db: DbSession,
    request: Request,
) -> AdminEscalationRead:
    return await close_admin_escalation(
        db=db,
        escalation_id=escalation_id,
        body=body,
        request=request,
    )


@router.post(
    "/conversations/{conversation_id}/reset/preview",
    response_model=AdminResetPreviewRead,
)
async def post_reset_preview(
    conversation_id: uuid.UUID,
    db: DbSession,
) -> AdminResetPreviewRead:
    return await preview_admin_conversation_reset(
        db=db,
        conversation_id=conversation_id,
    )


@router.post(
    "/conversations/{conversation_id}/reset/execute",
    response_model=AdminResetExecuteResponse,
)
async def post_reset_execute(
    conversation_id: uuid.UUID,
    body: AdminResetExecuteRequest,
    db: DbSession,
    request: Request,
) -> AdminResetExecuteResponse:
    return await execute_admin_conversation_reset(
        db=db,
        conversation_id=conversation_id,
        confirm=body.confirm,
        request=request,
    )


@router.post(
    "/conversations/{conversation_id}/quality/bot",
    response_model=AdminActionResult,
)
async def post_bot_quality_review(
    conversation_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminActionResult:
    return await run_admin_bot_quality_review(
        db=db,
        conversation_id=conversation_id,
        request=request,
    )


@router.post(
    "/conversations/{conversation_id}/quality/manager",
    response_model=AdminActionResult,
)
async def post_manager_quality_review(
    conversation_id: uuid.UUID,
    db: DbSession,
    request: Request,
) -> AdminActionResult:
    return await run_admin_manager_quality_review(
        db=db,
        conversation_id=conversation_id,
        request=request,
    )


@router.get(
    "/audit",
    response_model=PaginatedResponse[AdminActionAuditRead],
    response_model_by_alias=False,
)
async def get_audit(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedResponse[AdminActionAuditRead]:
    return await list_admin_audit(
        db=db,
        page=page,
        page_size=page_size,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        date_from=date_from,
        date_to=date_to,
    )
