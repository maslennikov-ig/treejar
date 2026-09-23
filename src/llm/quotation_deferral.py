"""Keep a quotation request alive while Zoho Inventory is temporarily unavailable.

tj-uz6j.9. On 2026-09-23 a Zoho 429 during create_quotation escaped the tool,
the LLM loop failed, and the customer who had just given every detail got the
generic "temporary issue" reply while the request was lost. A rate limit is not
a refusal: the request is persisted on the conversation, managers get one
operational alert (the bot is not paused), the customer is told honestly that
the quotation is being prepared and has not been sent, and the next customer
turn is told to finish it.
"""

from __future__ import annotations

import datetime
import html
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol

import httpx

from src.dialogue.order_state import QuoteConsent, quote_workflow_from_metadata
from src.llm.inventory_read import (
    InventoryReadUnavailable,
    is_transient_inventory_error,
)
from src.services.customer_language import is_arabic_customer_language

logger = logging.getLogger(__name__)

PENDING_QUOTATION_KEY = "pending_quotation"
_PENDING_QUOTATION_VERSION = 1
_PENDING_QUOTATION_MAX_AGE = datetime.timedelta(days=7)


class _QuoteItem(Protocol):
    sku: str
    quantity: int


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _item_rows(items: Sequence[_QuoteItem]) -> list[dict[str, Any]]:
    return [
        {"sku": str(item.sku).strip(), "quantity": int(item.quantity)} for item in items
    ]


def _source_message_id(deps: Any) -> str | None:
    return _string_value(getattr(deps, "source_message_id", None)) or None


def pending_quotation(conversation: Any) -> dict[str, Any] | None:
    metadata = getattr(conversation, "metadata_", None)
    if not isinstance(metadata, Mapping):
        return None
    pending = metadata.get(PENDING_QUOTATION_KEY)
    if not isinstance(pending, Mapping) or pending.get("status") != "pending":
        return None
    return dict(pending)


def clear_pending_quotation(conversation: Any) -> None:
    metadata = getattr(conversation, "metadata_", None)
    if isinstance(metadata, Mapping) and PENDING_QUOTATION_KEY in metadata:
        updated = dict(metadata)
        updated.pop(PENDING_QUOTATION_KEY, None)
        conversation.metadata_ = updated


def deferred_quotation_message(conversation: Any, *, manager_notified: bool) -> str:
    """Customer-facing status: saved, being prepared, explicitly not yet sent."""
    arabic = is_arabic_customer_language(getattr(conversation, "language", "en"))
    if manager_notified:
        if arabic:
            return (
                "تم حفظ طلب عرض السعر وبياناتك، ونحن نجهّز العرض الآن. لم يتم "
                "إرساله بعد؛ تم إبلاغ مديرنا وسيصلك العرض قريباً. لا حاجة "
                "لإعادة إرسال أي بيانات."
            )
        return (
            "Your quotation request and details are saved, and the quotation is "
            "being prepared now. It has not been sent yet; our manager has been "
            "notified and it will be sent to you shortly. You don't need to "
            "resend any details."
        )
    if arabic:
        return (
            "تم حفظ طلب عرض السعر وبياناتك، لكن لم أتمكن من إكمال تجهيز العرض "
            "الآن، لذلك لم يتم إرساله بعد. سأكمله في أقرب وقت ممكن، ولا حاجة "
            "لإعادة إرسال أي بيانات."
        )
    return (
        "Your quotation request and details are saved, but I couldn't finish "
        "preparing the quotation just now, so it has not been sent yet. I'll "
        "complete it as soon as possible; you don't need to resend any details."
    )


def _failure_reason(exc: BaseException) -> tuple[str, float | None]:
    retry_after = getattr(exc, "retry_after_seconds", None)
    status_code: int | None = None
    if isinstance(exc, InventoryReadUnavailable):
        status_code = exc.status_code
    elif isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
    reason = "inventory_rate_limited" if status_code == 429 else "inventory_unavailable"
    return reason, float(retry_after) if isinstance(retry_after, int | float) else None


def _manager_alert_text(
    conversation: Any, items: list[dict[str, Any]], reason: str
) -> str:
    metadata = getattr(conversation, "metadata_", None)
    details = (
        metadata.get("quote_customer_details")
        if isinstance(metadata, Mapping)
        else None
    )
    details = details if isinstance(details, Mapping) else {}
    customer = ", ".join(
        html.escape(_string_value(details.get(key)))
        for key in ("name", "company", "email")
        if _string_value(details.get(key))
    )
    item_lines = "\n".join(
        f"• {html.escape(row['sku'])} × {row['quantity']}" for row in items
    )
    phone = html.escape(_string_value(getattr(conversation, "phone", "")))
    return (
        "⏳ <b>Quotation pending: Zoho Inventory temporarily unavailable</b>\n"
        f"Reason: {html.escape(reason)}\n"
        f"Conversation: <code>{html.escape(str(getattr(conversation, 'id', '')))}</code>\n"
        f"Phone: {phone}\n"
        f"Customer: {customer or 'details in conversation'}\n"
        f"Items:\n{item_lines}\n"
        "The customer was told the quotation is being prepared and has not been "
        "sent. The bot retries on the customer's next message; send it manually "
        "if it is urgent."
    )


async def _alert_managers(deps: Any, items: list[dict[str, Any]], reason: str) -> bool:
    """Operational Telegram alert that does not pause the bot."""
    from src.services.inbound_channels import (
        should_send_manager_alert_for_conversation_with_db,
    )
    from src.services.notifications import send_telegram_message

    conversation = deps.conversation
    try:
        if not await should_send_manager_alert_for_conversation_with_db(
            conversation, deps.db
        ):
            return False
        return await send_telegram_message(
            _manager_alert_text(conversation, items, reason)
        )
    except Exception:
        logger.exception("Pending-quotation manager alert failed")
        return False


async def defer_quotation(
    deps: Any, items: Sequence[_QuoteItem], exc: BaseException
) -> str:
    conversation = deps.conversation
    rows = _item_rows(items)
    reason, retry_after = _failure_reason(exc)
    logger.warning(
        "Quotation deferred, Zoho Inventory temporarily unavailable: "
        "conversation=%s reason=%s error=%s",
        getattr(conversation, "id", None),
        reason,
        type(exc).__name__,
    )
    previous = pending_quotation(conversation) or {}
    same_request = previous.get("items") == rows
    manager_notified = bool(previous.get("manager_notified")) and same_request
    if not manager_notified:
        manager_notified = await _alert_managers(deps, rows, reason)
    now = datetime.datetime.now(datetime.UTC).isoformat()
    metadata = dict(getattr(conversation, "metadata_", None) or {})
    metadata[PENDING_QUOTATION_KEY] = {
        "version": _PENDING_QUOTATION_VERSION,
        "status": "pending",
        "items": rows,
        "reason": reason,
        "retry_after_seconds": retry_after,
        "first_deferred_at": (
            (previous.get("first_deferred_at") or now) if same_request else now
        ),
        "deferred_at": now,
        "source_message_id": _source_message_id(deps),
        "attempts": (int(previous.get("attempts") or 0) + 1) if same_request else 1,
        "manager_notified": manager_notified,
    }
    conversation.metadata_ = metadata
    try:
        await deps.db.flush()
    except Exception:
        logger.warning("Could not flush the pending quotation", exc_info=True)
    return deferred_quotation_message(conversation, manager_notified=manager_notified)


async def run_quotation_with_inventory_deferral(
    ctx: Any,
    items: Sequence[_QuoteItem],
    create: Callable[[Any, Any], Awaitable[str]],
) -> str:
    """Run create_quotation; a transient Zoho failure defers instead of raising."""
    deps = ctx.deps
    pending = pending_quotation(deps.conversation)
    source_message_id = _source_message_id(deps)
    if (
        pending
        and source_message_id
        and pending.get("source_message_id") == source_message_id
        and pending.get("items") == _item_rows(items)
    ):
        # Already deferred on this inbound message: answer again without
        # another round of Zoho calls against a quota that just refused us.
        return deferred_quotation_message(
            deps.conversation,
            manager_notified=bool(pending.get("manager_notified")),
        )
    try:
        result = await create(ctx, items)
    except Exception as exc:
        if not is_transient_inventory_error(exc):
            raise
        return await defer_quotation(deps, items, exc)
    if getattr(deps, "quotation_created", False):
        clear_pending_quotation(deps.conversation)
    return result


def pending_quotation_directive(deps: Any) -> str | None:
    """Tell a later customer turn to finish a quotation deferred by Zoho."""
    conversation = deps.conversation
    pending = pending_quotation(conversation)
    if not pending or not pending.get("items"):
        return None
    if pending.get("source_message_id") and pending.get(
        "source_message_id"
    ) == _source_message_id(deps):
        return None
    workflow = quote_workflow_from_metadata(getattr(conversation, "metadata_", None))
    if workflow.consent is not QuoteConsent.GRANTED:
        return None
    try:
        deferred_at = datetime.datetime.fromisoformat(str(pending.get("deferred_at")))
    except ValueError:
        return None
    if datetime.datetime.now(datetime.UTC) - deferred_at > _PENDING_QUOTATION_MAX_AGE:
        return None
    item_text = ", ".join(
        f"{row.get('sku')} x {row.get('quantity')}"
        for row in pending["items"]
        if isinstance(row, Mapping)
    )
    return (
        "A quotation the customer already requested was saved but not created, "
        f"because the inventory system was temporarily unavailable: {item_text}. "
        "The customer's details are already recorded. If create_quotation is "
        "available, call it with exactly these items before replying, and do not "
        "ask the customer to repeat details. Until create_quotation confirms it, "
        "never say the quotation was created or sent."
    )
