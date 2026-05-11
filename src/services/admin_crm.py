from __future__ import annotations

import asyncio
import logging
import math
import uuid
from collections import OrderedDict
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from pydantic_ai import UnexpectedModelBehavior
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.models.admin_action_audit import AdminActionAudit
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.models.feedback import Feedback
from src.models.manager_review import ManagerReview
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit
from src.models.quality_review import QualityReview
from src.quality.config import (
    AIQualityScope,
    evaluate_ai_quality_run_gate,
    get_ai_quality_controls_config,
)
from src.quality.evaluator import evaluate_conversation
from src.quality.service import conversation_already_reviewed, save_review
from src.schemas.admin import (
    AdminActionAuditRead,
    AdminActionResult,
    AdminBotRuleApplied,
    AdminConversationDetail,
    AdminConversationListItem,
    AdminConversationUpdate,
    AdminCustomerListItem,
    AdminEscalationClose,
    AdminEscalationRead,
    AdminEscalationWrite,
    AdminFeedbackRead,
    AdminManagerReviewSummary,
    AdminOutboundAuditRead,
    AdminQualityReviewSummary,
    AdminResetExecuteResponse,
    AdminResetPreviewRead,
    AdminTimelineMessage,
)
from src.schemas.common import EscalationStatus, PaginatedResponse
from src.services.admin_audit import log_admin_action
from src.services.conversation_reset import (
    build_reset_preview,
    execute_conversation_reset,
)

logger = logging.getLogger(__name__)


def _pages(total: int, page_size: int) -> int:
    return math.ceil(total / page_size) if total > 0 else 1


def _money(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def _metadata(conversation: Conversation) -> dict[str, Any]:
    return dict(conversation.metadata_ or {})


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return str(value) if value is not None else None


def _metadata_dict(metadata: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = metadata.get(key)
    return dict(value) if isinstance(value, dict) else None


def _ai_quality_scope_label(scope: AIQualityScope) -> str:
    return "Bot QA" if scope == AIQualityScope.BOT_QA else "Manager QA"


async def require_admin_ai_quality_manual_gate(
    db: AsyncSession,
    scope: AIQualityScope,
) -> None:
    try:
        config = await get_ai_quality_controls_config(db)
    except Exception as exc:
        logger.warning("Failed to read Admin AI Quality Controls", exc_info=True)
        raise HTTPException(
            status_code=409,
            detail=(
                f"{_ai_quality_scope_label(scope)} cannot run because Admin AI "
                "Quality Controls are unavailable"
            ),
        ) from exc

    gate = evaluate_ai_quality_run_gate(config, scope=scope, trigger="manual")
    if gate.allowed:
        return

    raise HTTPException(
        status_code=409,
        detail=(
            f"{_ai_quality_scope_label(scope)} is disabled by Admin AI Quality "
            f"Controls ({gate.reason}). Enable manual mode in Settings before "
            "running this action."
        ),
    )


def _order_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("order", "order_metadata", "sale_order", "sale_order_metadata"):
        value = metadata.get(key)
        if isinstance(value, dict):
            return dict(value)
    return None


def _applied_bot_rules(metadata: dict[str, Any]) -> list[AdminBotRuleApplied]:
    raw_rules = metadata.get("last_applied_bot_rules")
    if not isinstance(raw_rules, list):
        return []
    rules: list[AdminBotRuleApplied] = []
    for raw_rule in raw_rules:
        if not isinstance(raw_rule, dict):
            continue
        try:
            rules.append(AdminBotRuleApplied.model_validate(raw_rule))
        except Exception:
            continue
    return rules


def _preview(content: str | None, *, limit: int = 180) -> str | None:
    if not content:
        return None
    clean = " ".join(content.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 1]}..."


def _date_start(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.min)


def _date_end(value: date | None) -> datetime | None:
    if value is None:
        return None
    return datetime.combine(value, time.max)


def _conversation_filters(
    *,
    search: str | None = None,
    status: str | None = None,
    stage: str | None = None,
    language: str | None = None,
    escalation: str | None = None,
    deal_status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    segment: str | None = None,
) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if status:
        filters.append(Conversation.status == status)
    if stage:
        filters.append(Conversation.sales_stage == stage)
    if language:
        filters.append(Conversation.language == language)
    if escalation:
        filters.append(Conversation.escalation_status == escalation)
    if deal_status:
        filters.append(Conversation.deal_status == deal_status)
    start = _date_start(date_from)
    if start is not None:
        filters.append(Conversation.created_at >= start)
    end = _date_end(date_to)
    if end is not None:
        filters.append(Conversation.created_at <= end)
    if segment:
        filters.append(cast(Conversation.metadata_, String).ilike(f"%{segment}%"))
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                Conversation.phone.ilike(like),
                Conversation.customer_name.ilike(like),
                Conversation.zoho_contact_id.ilike(like),
                Conversation.zoho_deal_id.ilike(like),
                cast(Conversation.metadata_, String).ilike(like),
            )
        )
    return filters


async def _message_summary(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> tuple[int, datetime | None, str | None]:
    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    )
    last_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    last_message = last_result.scalars().first()
    return (
        int(count_result.scalar_one()),
        last_message.created_at if last_message else None,
        _preview(last_message.content if last_message else None),
    )


async def _conversation_list_item(
    db: AsyncSession,
    conversation: Conversation,
) -> AdminConversationListItem:
    metadata = _metadata(conversation)
    message_count, last_message_at, last_message_preview = await _message_summary(
        db,
        conversation.id,
    )
    return AdminConversationListItem(
        id=conversation.id,
        phone=conversation.phone,
        customer_name=conversation.customer_name,
        language=conversation.language,
        sales_stage=conversation.sales_stage,
        status=conversation.status,
        escalation_status=conversation.escalation_status,
        deal_status=conversation.deal_status,
        deal_amount=_money(conversation.deal_amount),
        zoho_contact_id=conversation.zoho_contact_id,
        zoho_deal_id=conversation.zoho_deal_id,
        message_count=message_count,
        last_message_at=last_message_at,
        last_message_preview=last_message_preview,
        source=_metadata_text(metadata, "source"),
        segment=_metadata_text(metadata, "segment"),
        utm=_metadata_dict(metadata, "utm"),
        order_metadata=_order_metadata(metadata),
        metadata=metadata,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


async def list_admin_customers(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
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
    filters = _conversation_filters(
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
    stmt = select(Conversation).order_by(
        Conversation.updated_at.desc(),
        Conversation.created_at.desc(),
    )
    if filters:
        stmt = stmt.where(*filters)

    result = await db.execute(stmt)
    conversations = list(result.scalars().all())
    latest_by_phone: OrderedDict[str, Conversation] = OrderedDict()
    counts_by_phone: dict[str, int] = {}
    for conversation in conversations:
        counts_by_phone[conversation.phone] = (
            counts_by_phone.get(conversation.phone, 0) + 1
        )
        latest_by_phone.setdefault(conversation.phone, conversation)

    all_latest = list(latest_by_phone.values())
    total = len(all_latest)
    start = (page - 1) * page_size
    paged = all_latest[start : start + page_size]
    items: list[AdminCustomerListItem] = []
    for conversation in paged:
        metadata = _metadata(conversation)
        _, last_message_at, last_message_preview = await _message_summary(
            db,
            conversation.id,
        )
        items.append(
            AdminCustomerListItem(
                phone=conversation.phone,
                customer_name=conversation.customer_name,
                latest_conversation_id=conversation.id,
                latest_message_at=last_message_at,
                latest_message_preview=last_message_preview,
                conversation_count=counts_by_phone[conversation.phone],
                status=conversation.status,
                sales_stage=conversation.sales_stage,
                language=conversation.language,
                escalation_status=conversation.escalation_status,
                deal_status=conversation.deal_status,
                zoho_contact_id=conversation.zoho_contact_id,
                zoho_deal_id=conversation.zoho_deal_id,
                segment=_metadata_text(metadata, "segment"),
                updated_at=conversation.updated_at,
            )
        )

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


async def list_admin_conversations(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
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
    filters = _conversation_filters(
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
    if phone:
        filters.append(Conversation.phone == phone)

    count_stmt = select(func.count()).select_from(Conversation)
    item_stmt = select(Conversation).order_by(
        Conversation.updated_at.desc(),
        Conversation.created_at.desc(),
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
        item_stmt = item_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())
    item_result = await db.execute(
        item_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    conversations = list(item_result.scalars().all())

    return PaginatedResponse(
        items=[
            await _conversation_list_item(db, conversation)
            for conversation in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


async def get_admin_conversation_detail(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> AdminConversationDetail:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = list(messages_result.scalars().all())

    escalation_result = await db.execute(
        select(Escalation)
        .where(Escalation.conversation_id == conversation_id)
        .order_by(Escalation.updated_at.desc(), Escalation.created_at.desc())
    )
    quality_result = await db.execute(
        select(QualityReview)
        .where(QualityReview.conversation_id == conversation_id)
        .order_by(QualityReview.created_at.desc())
    )
    manager_result = await db.execute(
        select(ManagerReview)
        .where(ManagerReview.conversation_id == conversation_id)
        .order_by(ManagerReview.created_at.desc())
    )
    feedback_result = await db.execute(
        select(Feedback)
        .where(Feedback.conversation_id == conversation_id)
        .order_by(Feedback.created_at.desc())
    )
    outbound_result = await db.execute(
        select(OutboundMessageAudit)
        .where(OutboundMessageAudit.conversation_id == conversation_id)
        .order_by(OutboundMessageAudit.created_at.desc())
    )

    list_item = await _conversation_list_item(db, conversation)
    metadata = _metadata(conversation)
    detail_data = list_item.model_dump()
    detail_data.update(
        {
            "timeline": [
                AdminTimelineMessage.model_validate(message) for message in messages
            ],
            "escalations": [
                AdminEscalationRead.model_validate(row)
                for row in escalation_result.scalars().all()
            ],
            "quality_reviews": [
                AdminQualityReviewSummary.model_validate(row)
                for row in quality_result.scalars().all()
            ],
            "manager_reviews": [
                AdminManagerReviewSummary.model_validate(row)
                for row in manager_result.scalars().all()
            ],
            "feedback": [
                AdminFeedbackRead.model_validate(row)
                for row in feedback_result.scalars().all()
            ],
            "outbound_audits": [
                AdminOutboundAuditRead.model_validate(row)
                for row in outbound_result.scalars().all()
            ],
            "applied_bot_rules": _applied_bot_rules(metadata),
        }
    )
    return AdminConversationDetail.model_validate(detail_data)


def _conversation_snapshot(conversation: Conversation) -> dict[str, Any]:
    return {
        "customer_name": conversation.customer_name,
        "status": conversation.status,
        "sales_stage": conversation.sales_stage,
        "escalation_status": conversation.escalation_status,
        "deal_status": conversation.deal_status,
        "language": conversation.language,
    }


async def update_admin_conversation(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    body: AdminConversationUpdate,
    request: object | None,
) -> AdminConversationDetail:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        return await get_admin_conversation_detail(db, conversation_id)

    before = _conversation_snapshot(conversation)
    for key, value in update_data.items():
        setattr(conversation, key, value)
    after = _conversation_snapshot(conversation)

    await log_admin_action(
        db,
        action="conversation.update",
        entity_type="conversation",
        entity_id=conversation_id,
        before=before,
        after=after,
        request=request,
        metadata={"updated_fields": sorted(update_data)},
    )
    await db.commit()
    await db.refresh(conversation)
    return await get_admin_conversation_detail(db, conversation_id)


async def create_admin_escalation(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    body: AdminEscalationWrite,
    request: object | None,
) -> AdminEscalationRead:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    before = {
        "conversation": _conversation_snapshot(conversation),
        "escalation": None,
    }
    escalation = Escalation(
        conversation_id=conversation_id,
        reason=body.reason,
        assigned_to=body.assigned_to,
        status=body.status,
        notes=body.notes,
    )
    db.add(escalation)
    conversation.escalation_status = body.status
    await log_admin_action(
        db,
        action="escalation.create",
        entity_type="conversation",
        entity_id=conversation_id,
        before=before,
        after={
            "conversation": _conversation_snapshot(conversation),
            "escalation": body.model_dump(),
        },
        request=request,
    )
    await db.commit()
    await db.refresh(escalation)
    return AdminEscalationRead.model_validate(escalation)


async def close_admin_escalation(
    db: AsyncSession,
    *,
    escalation_id: uuid.UUID,
    body: AdminEscalationClose,
    request: object | None,
) -> AdminEscalationRead:
    escalation = await db.get(Escalation, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")

    before = {
        "status": escalation.status,
        "notes": escalation.notes,
    }
    escalation.status = EscalationStatus.RESOLVED.value
    if body.notes is not None:
        escalation.notes = body.notes
    await log_admin_action(
        db,
        action="escalation.close",
        entity_type="escalation",
        entity_id=escalation_id,
        before=before,
        after={"status": escalation.status, "notes": escalation.notes},
        request=request,
    )
    await db.commit()
    await db.refresh(escalation)
    return AdminEscalationRead.model_validate(escalation)


async def preview_admin_conversation_reset(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
) -> AdminResetPreviewRead:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    preview = await build_reset_preview(db, conversation.phone)
    return AdminResetPreviewRead(
        phone=preview.phone,
        phone_variants=list(preview.phone_variants),
        conversation_count=preview.conversation_count,
        latest_conversation_id=preview.latest_conversation_id,
        message_count=preview.message_count,
        pending_escalation_count=preview.pending_escalation_count,
    )


async def execute_admin_conversation_reset(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    confirm: bool,
    request: object | None,
) -> AdminResetExecuteResponse:
    if not confirm:
        raise HTTPException(status_code=400, detail="Confirmation is required")

    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    preview = await build_reset_preview(db, conversation.phone)
    result = await execute_conversation_reset(
        db,
        conversation.phone,
        requested_by_telegram_user_id=None,
        source="admin_crm",
    )
    await log_admin_action(
        db,
        action="conversation.reset",
        entity_type="conversation",
        entity_id=conversation_id,
        before=preview.__dict__,
        after={
            "phone": result.phone,
            "archived_count": result.archived_count,
            "new_conversation_id": result.new_conversation.id
            if result.new_conversation
            else None,
        },
        request=request,
    )
    await db.commit()
    return AdminResetExecuteResponse(
        phone=result.phone,
        archived_count=result.archived_count,
        new_conversation_id=result.new_conversation.id
        if result.new_conversation
        else None,
    )


async def run_admin_bot_quality_review(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    request: object | None,
) -> AdminActionResult:
    await require_admin_ai_quality_manual_gate(db, AIQualityScope.BOT_QA)
    if await conversation_already_reviewed(db, conversation_id):
        raise HTTPException(status_code=409, detail="Conversation already reviewed")

    try:
        result = await asyncio.wait_for(
            evaluate_conversation(conversation_id, db),
            timeout=60.0,
        )
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail="LLM evaluation timed out") from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UnexpectedModelBehavior as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM evaluation failed after retries",
        ) from exc

    review = await save_review(db, conversation_id, result)
    await log_admin_action(
        db,
        action="quality.bot_review",
        entity_type="conversation",
        entity_id=conversation_id,
        before=None,
        after={"review_id": review.id, "rating": review.rating},
        request=request,
    )
    await db.commit()
    return AdminActionResult(
        ok=True,
        status="created",
        entity_id=review.id,
        detail="Bot QA review created",
    )


async def run_admin_manager_quality_review(
    db: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    request: object | None,
) -> AdminActionResult:
    from src.quality.manager_evaluator import (
        escalation_already_reviewed,
        evaluate_manager_conversation,
        save_manager_review,
    )

    await require_admin_ai_quality_manual_gate(db, AIQualityScope.MANAGER_QA)
    escalation_result = await db.execute(
        select(Escalation)
        .where(Escalation.conversation_id == conversation_id)
        .order_by(Escalation.updated_at.desc(), Escalation.created_at.desc())
        .limit(1)
    )
    escalation = escalation_result.scalars().first()
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if await escalation_already_reviewed(db, escalation.id):
        raise HTTPException(status_code=409, detail="Escalation already reviewed")

    try:
        evaluation, metrics = await evaluate_manager_conversation(escalation.id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    review = await save_manager_review(
        db=db,
        escalation_id=escalation.id,
        conversation_id=conversation_id,
        evaluation=evaluation,
        metrics=metrics,
        manager_name=escalation.assigned_to,
    )
    await log_admin_action(
        db,
        action="quality.manager_review",
        entity_type="conversation",
        entity_id=conversation_id,
        before=None,
        after={"review_id": review.id, "rating": review.rating},
        request=request,
    )
    await db.commit()
    return AdminActionResult(
        ok=True,
        status="created",
        entity_id=review.id,
        detail="Manager QA review created",
    )


async def list_admin_audit(
    db: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> PaginatedResponse[AdminActionAuditRead]:
    filters: list[ColumnElement[bool]] = []
    if action:
        filters.append(AdminActionAudit.action == action)
    if entity_type:
        filters.append(AdminActionAudit.entity_type == entity_type)
    if entity_id:
        filters.append(AdminActionAudit.entity_id == entity_id)
    start = _date_start(date_from)
    if start is not None:
        filters.append(AdminActionAudit.created_at >= start.replace(tzinfo=UTC))
    end = _date_end(date_to)
    if end is not None:
        filters.append(AdminActionAudit.created_at <= end.replace(tzinfo=UTC))

    count_stmt = select(func.count()).select_from(AdminActionAudit)
    item_stmt = select(AdminActionAudit).order_by(AdminActionAudit.created_at.desc())
    if filters:
        count_stmt = count_stmt.where(*filters)
        item_stmt = item_stmt.where(*filters)

    total_result = await db.execute(count_stmt)
    total = int(total_result.scalar_one())
    item_result = await db.execute(
        item_stmt.offset((page - 1) * page_size).limit(page_size)
    )
    items = [
        AdminActionAuditRead.model_validate(row) for row in item_result.scalars().all()
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )
