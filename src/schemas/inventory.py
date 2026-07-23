from __future__ import annotations

from pydantic import BaseModel


class StockLevel(BaseModel):
    sku: str
    name: str
    stock: int
    price: float
    currency: str = "AED"
    warehouse: str | None = None
