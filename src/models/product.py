from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import JSON, Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class Product(UUIDMixin, TimestampMixin, Base):
    """A product from the Treejar catalog."""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String, unique=True, index=True)
    # unique=True on nullable is fine in PostgreSQL (NULLs are distinct)
    zoho_item_id: Mapped[str | None] = mapped_column(String, unique=True, default=None)
    name_en: Mapped[str] = mapped_column(String)
    name_ar: Mapped[str | None] = mapped_column(String, default=None)
    description_en: Mapped[str | None] = mapped_column(Text, default=None)
    description_ar: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str | None] = mapped_column(String, index=True, default=None)
    subcategory: Mapped[str | None] = mapped_column(String, default=None)
    price: Mapped[float] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String, default="AED")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str | None] = mapped_column(String, default=None)
    attributes: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024), nullable=True, default=None
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    synced_at: Mapped[datetime | None] = mapped_column(default=None)
