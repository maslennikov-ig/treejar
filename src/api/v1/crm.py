from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from src.schemas import (
    ContactCreate,
    ContactRead,
    DealCreate,
    DealRead,
    DealUpdate,
)

router = APIRouter()


@router.get("/contacts/{phone}", response_model=ContactRead)
async def get_contact(
    phone: str,
) -> ContactRead:
    """Look up a CRM contact by phone number."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/contacts/", response_model=ContactRead)
async def create_contact(
    body: ContactCreate,
) -> ContactRead:
    """Create a new CRM contact."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/deals/", response_model=DealRead)
async def create_deal(
    body: DealCreate,
) -> DealRead:
    """Create a new CRM deal."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.patch("/deals/{deal_id}", response_model=DealRead)
async def update_deal(
    deal_id: uuid.UUID,
    body: DealUpdate,
) -> DealRead:
    """Update a CRM deal stage or amount."""
    raise HTTPException(status_code=501, detail="Not implemented")
