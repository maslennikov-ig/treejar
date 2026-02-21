from __future__ import annotations

from typing import Any, Protocol


class InventoryProvider(Protocol):
    """Abstract inventory provider interface.

    Implement this protocol to add new inventory integrations
    (Zoho Inventory, custom ERP, etc.)
    """

    async def get_stock(self, sku: str) -> dict[str, Any] | None:
        """Get stock level for a specific SKU."""
        ...

    async def get_stock_bulk(self, skus: list[str]) -> list[dict[str, Any]]:
        """Get stock levels for multiple SKUs."""
        ...

    async def create_sale_order(self, data: dict[str, Any]) -> dict[str, Any]:
        """Create a sale order / quotation."""
        ...

    async def get_sale_order(self, order_id: str) -> dict[str, Any] | None:
        """Get sale order details including PDF URL."""
        ...
