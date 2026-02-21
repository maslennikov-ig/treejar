from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query

from src.schemas import (
    ConversationDetail,
    ConversationRead,
    ConversationStatus,
    ConversationUpdate,
    Language,
    PaginatedResponse,
)

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[ConversationRead])
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ConversationStatus | None = None,
    phone: str | None = None,
    language: Language | None = None,
) -> PaginatedResponse[ConversationRead]:
    """List conversations with optional filters."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
) -> ConversationDetail:
    """Get conversation details including messages."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: uuid.UUID,
    body: ConversationUpdate,
) -> ConversationRead:
    """Update conversation status or sales stage."""
    raise HTTPException(status_code=501, detail="Not implemented")
