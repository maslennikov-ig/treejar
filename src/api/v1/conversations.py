from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.models.conversation import Conversation
from src.schemas import (
    ConversationDetail,
    ConversationRead,
    ConversationStatus,
    ConversationUpdate,
    Language,
    PaginatedResponse,
)

router = APIRouter()

DbSession = Annotated[AsyncSession, Depends(get_db)]

@router.get("/", response_model=PaginatedResponse[ConversationRead])
async def list_conversations(
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ConversationStatus | None = None,
    phone: str | None = None,
    language: Language | None = None,
) -> PaginatedResponse[ConversationRead]:
    """List conversations with optional filters."""
    # Build query
    stmt = select(Conversation)
    if status is not None:
        stmt = stmt.where(Conversation.status == status.value)
    if language is not None:
        stmt = stmt.where(Conversation.language == language.value)
    if phone is not None:
        stmt = stmt.where(Conversation.phone.ilike(f"%{phone}%"))

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one_or_none() or 0

    # Apply pagination and sorting
    stmt = stmt.order_by(Conversation.updated_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)

    # Execute query
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PaginatedResponse[ConversationRead](
        items=list(items),
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: DbSession,
) -> ConversationDetail:
    """Get conversation details including messages."""
    stmt = (
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .options(selectinload(Conversation.messages))
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Python-level sort for messages by created_at (though typically ordered by insert)
    conversation.messages.sort(key=lambda m: m.created_at)

    return ConversationDetail.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
    db: DbSession,
) -> ConversationRead:
    """Update conversation status, sales stage, or customer name."""
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()

    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if isinstance(value, (ConversationStatus, Language)):
            setattr(conversation, field, value.value)
        else:
            setattr(conversation, field, value)

    await db.commit()
    await db.refresh(conversation)

    return ConversationRead.model_validate(conversation)
