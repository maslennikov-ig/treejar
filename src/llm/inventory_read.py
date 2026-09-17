"""Contain unavailable Inventory reads without masking mutation outcomes."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic_ai import ToolReturn


class InventoryReadUnavailable(Exception):
    def __init__(self, *, status_code: int | None, retry_after: str | None = None):
        self.status_code = status_code
        # Only carry a bounded numeric Retry-After, never raw provider content.
        self.retry_after_seconds = (
            min(int(retry_after), 86400)
            if retry_after
            and retry_after.isascii()
            and retry_after.isdigit()
            and len(retry_after) <= 8
            else None
        )
        super().__init__("Inventory read temporarily unavailable")

    def tool_result(self, sku: str) -> ToolReturn:
        return ToolReturn(
            return_value={
                "status": "temporarily_unavailable",
                "reason": "rate_limited"
                if self.status_code == 429
                else "inventory_unavailable",
                "sku": sku,
                "stock_confirmed": False,
                "http_status": self.status_code,
                "retry_after_seconds": self.retry_after_seconds,
            },
            content=(
                "The inventory lookup could not be completed. This is not a zero-stock "
                "or missing-product result. Do not invent stock, promise availability, "
                "or repeat this lookup in this turn. Answer the customer from other "
                "verified facts and explain briefly that current availability cannot "
                "yet be confirmed. No quotation or manager action was performed by "
                "this failed lookup."
            ),
        )


async def inventory_read(operation: Callable[..., Awaitable[Any]], *args: Any) -> Any:
    """Use only around idempotent Inventory reads, never notification/write code."""
    try:
        return await operation(*args)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in {429, 502, 503, 504}:
            raise
        raise InventoryReadUnavailable(
            status_code=exc.response.status_code,
            retry_after=exc.response.headers.get("retry-after"),
        ) from exc
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise InventoryReadUnavailable(status_code=None) from exc
