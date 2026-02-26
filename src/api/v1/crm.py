from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncGenerator
from datetime import UTC, datetime

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import get_redis
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.schemas import (
    ContactCreate,
    ContactRead,
    DealCreate,
    DealRead,
    DealUpdate,
)

logger = logging.getLogger(__name__)
router = APIRouter()


async def get_crm_client(
    redis: aioredis.Redis = Depends(get_redis),
) -> AsyncGenerator[ZohoCRMClient, None]:
    """Dependency to get an authenticated Zoho CRM client."""
    async with ZohoCRMClient(redis) as client:
        yield client


@router.get("/contacts/{phone}", response_model=ContactRead)
async def get_contact(
    phone: str,
    crm: ZohoCRMClient = Depends(get_crm_client),
) -> ContactRead:
    """Look up a CRM contact by phone number."""
    contact_data = await crm.find_contact_by_phone(phone)
    if not contact_data:
        raise HTTPException(status_code=404, detail="Contact not found")

    last_name = contact_data.get("Last_Name", "")
    first_name = contact_data.get("First_Name", "")
    name = f"{first_name} {last_name}".strip()

    try:
        created_time = datetime.fromisoformat(contact_data.get("Created_Time", ""))
    except ValueError:
        created_time = datetime.now(UTC)

    return ContactRead(
        id=uuid.uuid4(),
        phone=contact_data.get("Phone", phone),
        name=name,
        email=contact_data.get("Email"),
        company=contact_data.get("Account_Name", {}).get("name") if isinstance(contact_data.get("Account_Name"), dict) else None,
        zoho_contact_id=contact_data.get("id"),
        segment=contact_data.get("Segment"),
        created_at=created_time,
    )


@router.post("/contacts/", response_model=ContactRead)
async def create_contact(
    body: ContactCreate,
    crm: ZohoCRMClient = Depends(get_crm_client),
) -> ContactRead:
    """Create a new CRM contact."""
    payload = {
        "Phone": body.phone,
        "Last_Name": body.name or "Unknown",
        "Email": body.email or "",
        "Designation": body.position or "",
        "Lead_Source": "Chatbot",
    }
    # For company, Zoho expects Account_Name to be linked or text depending on setup
    # Usually we can pass it as a field or we leave it. We'll add text to Description if missing Account link.
    if body.company:
        payload["Description"] = f"Company: {body.company}"

    resp = await crm.create_contact(payload)
    if resp.get("code") not in ("SUCCESS", "DUPLICATE_DATA"):
        logger.error("Zoho Create Contact Error: %s", resp)
        # Even if failure, we just return what we have or raise 400
        # If it's a minor warning, it might still have created it.
        if "details" not in resp or "id" not in resp["details"]:
            raise HTTPException(status_code=400, detail="Could not create contact in CRM")

    contact_id = resp["details"]["id"]
    return ContactRead(
        id=uuid.uuid4(),
        phone=body.phone,
        name=body.name,
        email=body.email,
        company=body.company,
        zoho_contact_id=contact_id,
        created_at=datetime.now(UTC),
    )


@router.post("/deals/", response_model=DealRead)
async def create_deal(
    body: DealCreate,
    crm: ZohoCRMClient = Depends(get_crm_client),
) -> DealRead:
    """Create a new CRM deal."""
    payload = {
        "Deal_Name": body.title,
        "Contact_Name": body.contact_id,
        "Amount": body.amount,
        "Stage": body.stage,
        "Pipeline": "Standard (Standard)",
    }
    resp = await crm.create_deal(payload)
    if resp.get("code") != "SUCCESS":
        logger.error("Zoho Create Deal Error: %s", resp)
        if "details" not in resp or "id" not in resp["details"]:
            raise HTTPException(status_code=400, detail="Could not create deal in CRM")

    deal_id = resp["details"]["id"]
    return DealRead(
        id=uuid.uuid4(),
        contact_id=body.contact_id,
        title=body.title,
        amount=body.amount,
        currency=body.currency,
        stage=body.stage,
        zoho_deal_id=deal_id,
        created_at=datetime.now(UTC),
    )


@router.patch("/deals/{deal_id}", response_model=DealRead)
async def update_deal(
    deal_id: str,
    body: DealUpdate,
    crm: ZohoCRMClient = Depends(get_crm_client),
) -> DealRead:
    """Update a CRM deal stage or amount."""
    payload: dict[str, Any] = {}
    if body.stage is not None:
        payload["Stage"] = body.stage
    if body.amount is not None:
        payload["Amount"] = body.amount
    if body.notes is not None:
        payload["Description"] = body.notes

    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")

    resp = await crm.update_deal(deal_id, payload)

    if resp.get("code") != "SUCCESS":
        logger.error("Zoho Update Deal Error: %s", resp)
        raise HTTPException(status_code=400, detail="Could not update deal in CRM")

    # We don't have the full Deal so we just return a stub reflection.
    # To be fully RESTful we might want to GET the deal, but this is an internal API for the bot.
    return DealRead(
        id=uuid.uuid4(),
        contact_id="unknown",
        title="Updated Deal",
        amount=body.amount,
        currency="AED",
        stage=body.stage or "Unknown",
        zoho_deal_id=deal_id,
        created_at=datetime.now(UTC),
    )
