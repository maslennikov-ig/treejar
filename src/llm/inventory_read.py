"""Contain unavailable Inventory reads without masking mutation outcomes."""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic_ai import ToolReturn

from src.integrations.zoho_oauth import ZohoOAuthError

_TRANSIENT_STATUS_CODES = frozenset({429, 502, 503, 504})


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

    def tool_result(self, sku: str, *, catalog_listed: bool = False) -> ToolReturn:
        catalog_note = (
            " The product is listed in the Treejar catalog; its catalog stock is "
            "not live-confirmed, so do not state a stock number."
            if catalog_listed
            else ""
        )
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
                "catalog_listed": catalog_listed,
                "stock_source": "catalog_unconfirmed" if catalog_listed else None,
            },
            content=(
                "The inventory lookup could not be completed. This is not a zero-stock "
                "or missing-product result. Do not invent stock, promise availability, "
                "or repeat this lookup in this turn. Answer the customer from other "
                "verified facts and explain briefly that current availability cannot "
                "yet be confirmed. No quotation or manager action was performed by "
                "this failed lookup."
                f"{catalog_note}"
            ),
        )


async def inventory_read(operation: Callable[..., Awaitable[Any]], *args: Any) -> Any:
    """Use only around idempotent Inventory reads, never notification/write code."""
    try:
        return await operation(*args)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code not in _TRANSIENT_STATUS_CODES:
            raise
        raise InventoryReadUnavailable(
            status_code=exc.response.status_code,
            retry_after=exc.response.headers.get("retry-after"),
        ) from exc
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise InventoryReadUnavailable(status_code=None) from exc


def is_transient_inventory_error(exc: BaseException) -> bool:
    """A Zoho failure that says "not now" rather than "no".

    Rate limits, gateway errors, timeouts and retryable token-refresh failures
    are worth retrying later; a 400/404 or a malformed answer is not.
    """
    if isinstance(exc, InventoryReadUnavailable):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _TRANSIENT_STATUS_CODES
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    return isinstance(exc, ZohoOAuthError) and exc.retryable
