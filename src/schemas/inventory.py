from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .common import UUIDModel


class StockLevel(BaseModel):
    sku: str
    name: str
    stock: int
    price: float
    currency: str = "AED"
    warehouse: str | None = None


class SaleOrderItem(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_price: float


class SaleOrderCreate(BaseModel):
    contact_name: str
    contact_email: str | None = None
    company: str | None = None
    items: list[SaleOrderItem]
    notes: str | None = None
    discount_percent: float | None = None


class SaleOrderRead(UUIDModel):
    model_config = ConfigDict(from_attributes=True)

    zoho_order_id: str | None = None
    status: str
    total: float
    currency: str
    pdf_url: str | None = None
    items: list[SaleOrderItem]
    created_at: datetime
