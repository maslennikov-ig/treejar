from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .common import UUIDModel


class ContactCreate(BaseModel):
    phone: str
    name: str | None = None
    email: str | None = None
    company: str | None = None
    position: str | None = None


class ContactRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    phone: str
    name: str | None = None
    email: str | None = None
    company: str | None = None
    zoho_contact_id: str | None = None
    segment: str | None = None
    created_at: datetime


class DealCreate(BaseModel):
    contact_id: str
    title: str
    amount: float | None = None
    currency: str = "AED"
    stage: str = "Qualification"


class DealRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id: str
    title: str
    amount: float | None = None
    currency: str
    stage: str
    zoho_deal_id: str | None = None
    created_at: datetime


class DealUpdate(BaseModel):
    stage: str | None = None
    amount: float | None = None
    notes: str | None = None
