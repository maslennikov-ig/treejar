"""Finish a quotation deferred by Zoho without waiting for the customer (tj-i0n0).

``defer_quotation`` keeps the request on the conversation and tells the customer
it is being prepared. Before this job, only the customer's next message or a
manager could finish it. The job retries the same quotation on a bounded
schedule, sends the PDF and a short confirmation when Zoho accepts it, and
alerts managers once when the schedule is exhausted or the request can no
longer be completed automatically.

The job holds the conversation's inbound lock while it runs, so it never races
a customer turn that is finishing the same quotation.
"""

from __future__ import annotations

import datetime
import logging
import secrets
import uuid
from collections.abc import Mapping
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pydantic_ai import RunContext

from src.llm.inventory_read import is_transient_inventory_error
from src.llm.quotation_deferral import (
    PENDING_QUOTATION_KEY,
    PENDING_QUOTATION_MAX_AGE,
    alert_managers_for_conversation,
    clear_pending_quotation,
    pending_quotation,
)

logger = logging.getLogger(__name__)

RETRY_PENDING_QUOTATION_JOB = "retry_pending_quotation"
# Delay before background attempt N (1-based). About 1 h 45 min in total.
RETRY_DELAYS_SECONDS: tuple[int, ...] = (60, 180, 600, 1800, 3600)
_LOCK_BUSY_DELAY_SECONDS = 30
_MAX_RETRY_AFTER_SECONDS = 3600
_LOCK_TTL_SECONDS = 660

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def retry_delay_seconds(attempt: int, retry_after: float | None = None) -> int | None:
    """Delay before background ``attempt``; ``None`` once the schedule is spent."""
    if attempt < 1 or attempt > len(RETRY_DELAYS_SECONDS):
        return None
    delay = RETRY_DELAYS_SECONDS[attempt - 1]
    if retry_after is not None and retry_after > 0:
        delay = max(delay, min(int(retry_after + 0.999), _MAX_RETRY_AFTER_SECONDS))
    return delay


def _update_pending(conversation: Any, **fields: Any) -> None:
    metadata = dict(getattr(conversation, "metadata_", None) or {})
    pending = metadata.get(PENDING_QUOTATION_KEY)
    if not isinstance(pending, Mapping):
        return
    metadata[PENDING_QUOTATION_KEY] = {**pending, **fields}
    conversation.metadata_ = metadata


async def _enqueue(redis: Any, conversation_id: str, attempt: int, delay: int) -> bool:
    # Inbound turns and this job both run in the ARQ worker, whose ctx["redis"]
    # is the ArqRedis pool; a plain Redis client cannot schedule jobs.
    enqueue = getattr(redis, "enqueue_job", None)
    if enqueue is None:
        return False
    job = await enqueue(
        RETRY_PENDING_QUOTATION_JOB,
        conversation_id,
        attempt,
        _job_id=f"pending-quotation:{conversation_id}:{attempt}:{secrets.token_hex(4)}",
        _defer_by=delay,
    )
    return job is not None


async def schedule_pending_quotation_retry(
    redis: Any,
    conversation: Any,
    *,
    attempt: int,
    retry_after: float | None = None,
    delay: int | None = None,
) -> bool:
    """Queue background ``attempt`` and record it on the pending quotation."""
    if delay is None:
        delay = retry_delay_seconds(attempt, retry_after)
    if delay is None or redis is None:
        return False
    try:
        scheduled = await _enqueue(redis, str(conversation.id), attempt, delay)
    except Exception:
        logger.warning(
            "Could not schedule the pending-quotation retry: conversation=%s",
            getattr(conversation, "id", None),
            exc_info=True,
        )
        return False
    if scheduled:
        at = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=delay)
        _update_pending(
            conversation,
            retry_scheduled_for=at.isoformat(),
            background_attempt=attempt,
        )
    return scheduled


def retry_is_scheduled(pending: Mapping[str, Any]) -> bool:
    raw = pending.get("retry_scheduled_for")
    if not isinstance(raw, str):
        return False
    try:
        at = datetime.datetime.fromisoformat(raw)
    except ValueError:
        return False
    # A job that should have run long ago is lost (worker restart); reschedule.
    grace = datetime.timedelta(seconds=_LOCK_TTL_SECONDS)
    return at + grace > datetime.datetime.now(datetime.UTC)


async def _acquire_chat_lock(redis: Any, phone: str) -> tuple[str, str] | None:
    from src.services.inbound_batch import inbound_chat_reference, inbound_lock_key

    lock_key = inbound_lock_key(inbound_chat_reference(phone))
    token = secrets.token_hex(16)
    claimed = await redis.set(lock_key, token, ex=_LOCK_TTL_SECONDS, nx=True)
    return (lock_key, token) if claimed else None


async def _release_chat_lock(redis: Any, lock: tuple[str, str]) -> None:
    try:
        await redis.eval(_RELEASE_LOCK_SCRIPT, 1, lock[0], lock[1])
    except Exception:
        logger.warning("Could not release the chat lock after a quotation retry")


def _pending_is_live(conversation: Any, pending: Mapping[str, Any]) -> bool:
    from src.dialogue.order_state import QuoteConsent, quote_workflow_from_metadata

    if not pending.get("items"):
        return False
    workflow = quote_workflow_from_metadata(getattr(conversation, "metadata_", None))
    if workflow.consent is not QuoteConsent.GRANTED:
        return False
    try:
        first = datetime.datetime.fromisoformat(
            str(pending.get("first_deferred_at") or pending.get("deferred_at"))
        )
    except ValueError:
        return False
    return datetime.datetime.now(datetime.UTC) - first <= PENDING_QUOTATION_MAX_AGE


def _build_deps(
    db: Any, redis: Any, conversation: Any, pending: Mapping[str, Any]
) -> Any:
    from src.integrations.crm.zoho_crm import ZohoCRMClient
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
    from src.integrations.messaging.wazzup import WazzupProvider
    from src.llm.catalog_planning import SalesDeps
    from src.rag.embeddings import EmbeddingEngine

    return SalesDeps(
        db=db,
        redis=redis,
        conversation=conversation,
        embedding_engine=EmbeddingEngine(),
        zoho_inventory=ZohoInventoryClient(redis),
        zoho_crm=ZohoCRMClient(redis),
        messaging_client=WazzupProvider(),
        pii_map={},
        crm_context=None,
        user_query="",
        recent_history=[],
        source_message_id=pending.get("source_message_id"),
    )


async def _send_confirmation(deps: Any, text: str, quote_key: str) -> None:
    from src.models.message import Message, message_created_at_now
    from src.services.outbound_audit import (
        deterministic_crm_message_id,
        send_wazzup_text_with_audit,
    )

    conversation = deps.conversation
    deps.db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=text,
            created_at=message_created_at_now(),
        )
    )
    await deps.db.commit()
    await send_wazzup_text_with_audit(
        deps.db,
        provider=deps.messaging_client,
        conversation_id=uuid.UUID(str(conversation.id)),
        chat_id=conversation.phone,
        text=text,
        source="quotation_retry",
        crm_message_id=deterministic_crm_message_id(
            "quotation_retry", conversation.id, quote_key
        ),
    )
    await deps.db.commit()


async def retry_pending_quotation(
    ctx: dict[str, Any], conversation_id: str, attempt: int = 1
) -> str:
    """ARQ job: one background attempt at a quotation Zoho refused earlier."""
    from src.core.database import async_session_factory
    from src.llm.engine import _create_quotation
    from src.llm.order_quote_routes import QuotationItem
    from src.models.conversation import Conversation

    redis = ctx["redis"]
    async with async_session_factory() as db:
        conversation = await db.get(Conversation, uuid.UUID(str(conversation_id)))
        if conversation is None:
            return "missing_conversation"
        pending = pending_quotation(conversation)
        if pending is None:
            return "nothing_pending"
        if not _pending_is_live(conversation, pending):
            logger.info(
                "Pending quotation no longer eligible for retry: conversation=%s",
                conversation_id,
            )
            return "not_eligible"

        lock = await _acquire_chat_lock(redis, conversation.phone)
        if lock is None:
            # A customer turn is running; it finishes the quotation itself.
            await schedule_pending_quotation_retry(
                redis, conversation, attempt=attempt, delay=_LOCK_BUSY_DELAY_SECONDS
            )
            await db.commit()
            return "chat_busy"

        try:
            await db.refresh(conversation)
            pending = pending_quotation(conversation)
            if pending is None:
                return "nothing_pending"
            _update_pending(conversation, retry_scheduled_for=None)
            deps = _build_deps(db, redis, conversation, pending)
            items = [
                QuotationItem(sku=str(row["sku"]), quantity=int(row["quantity"]))
                for row in pending["items"]
                if isinstance(row, Mapping)
            ]
            try:
                # The quotation path reads only ``ctx.deps``; no model run exists here.
                job_ctx = cast("RunContext[Any]", SimpleNamespace(deps=deps))
                result = await _create_quotation(job_ctx, items)
            except Exception as exc:
                if not is_transient_inventory_error(exc):
                    raise
                retry_after = getattr(exc, "retry_after_seconds", None)
                _update_pending(
                    conversation,
                    attempts=int(pending.get("attempts") or 0) + 1,
                    deferred_at=datetime.datetime.now(datetime.UTC).isoformat(),
                )
                if await schedule_pending_quotation_retry(
                    redis,
                    conversation,
                    attempt=attempt + 1,
                    retry_after=(
                        float(retry_after)
                        if isinstance(retry_after, int | float)
                        else None
                    ),
                ):
                    await db.commit()
                    return "rescheduled"
                # Keep it pending: the customer's next message can still finish it.
                await _give_up(deps, "background retries exhausted", keep_pending=True)
                await db.commit()
                return "exhausted"

            if getattr(deps, "quotation_created", False):
                clear_pending_quotation(conversation)
                await db.commit()
                await _send_confirmation(
                    deps,
                    result,
                    str(
                        (conversation.metadata_ or {}).get("zoho_sale_order_id")
                        or pending.get("first_deferred_at")
                    ),
                )
                logger.info(
                    "Deferred quotation completed in background: conversation=%s attempt=%s",
                    conversation_id,
                    attempt,
                )
                return "created"

            # Zoho answered but the quotation cannot be completed automatically
            # (catalog mismatch, missing details, uncertain side effect). The
            # tool's own path already escalated where needed; stop retrying.
            await _give_up(deps, "quotation could not be completed automatically")
            await db.commit()
            return "needs_manager"
        except Exception:
            logger.exception(
                "Background quotation retry failed: conversation=%s", conversation_id
            )
            await db.rollback()
            return "error"
        finally:
            await _release_chat_lock(redis, lock)


async def _give_up(deps: Any, reason: str, *, keep_pending: bool = False) -> None:
    conversation = deps.conversation
    pending = pending_quotation(conversation) or {}
    logger.warning(
        "Pending quotation handed to managers: conversation=%s reason=%s",
        getattr(conversation, "id", None),
        reason,
    )
    notified = await alert_managers_for_conversation(
        deps, list(pending.get("items") or []), reason, final=True
    )
    _update_pending(
        conversation,
        status="pending" if keep_pending else "needs_manager",
        retry_scheduled_for=None,
        manager_notified=bool(pending.get("manager_notified")) or notified,
    )
