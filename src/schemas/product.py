from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .common import TimestampModel, UUIDModel


class ProductRead(UUIDModel, TimestampModel):
    model_config = ConfigDict(from_attributes=True)

    sku: str
    name_en: str
    name_ar: str | None = None
    description_en: str | None = None
    category: str | None = None
    subcategory: str | None = None
    price: float
    currency: str
    stock: int
    image_url: str | None = None
    attributes: dict[str, Any] | None = None
    is_active: bool


class ProductSearchQuery(BaseModel):
    query: str
    category: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    colors: list[str] | None = None
    in_stock_only: bool = True
    limit: int = Field(default=5, ge=1, le=50)


class ProductSearchResult(BaseModel):
    products: list[ProductRead]
    query_interpreted: str | None = None
    total_found: int


class ProductSyncRequest(BaseModel):
    source: str  # "zoho" | "website_treejar" | "website_bazara"


class ProductSyncResponse(BaseModel):
    synced: int
    created: int
    updated: int
    errors: int
