import datetime
import logging
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Self

from logfire import Logfire
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select

from src.core.database import async_session_factory
from src.core.redis import get_redis_client
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.conversation import Conversation
from src.models.feedback import Feedback
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit
from src.models.system_config import SystemConfig
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import DealStatus, SalesStage
from src.services.escalation_state import allows_automatic_followup
from src.services.outbound_audit import (
    deterministic_crm_message_id,
    send_wazzup_template_with_audit,
    send_wazzup_text_with_audit,
)

logfire = Logfire()
logger = logging.getLogger(__name__)

PAYMENT_REMINDER_CONTROLS_KEY = "payment_reminder_controls"
PAYMENT_REMINDER_SOURCE = "payment_reminder"
LEGACY_AUTOMATIC_FOLLOWUP_KEY = "legacy_automatic_followup_enabled"
WHATSAPP_FREEFORM_WINDOW_HOURS = 24
MAX_PAYMENT_REMINDERS_PER_RUN = 100
MAX_PAYMENT_REMINDERS_PER_DAY = 500
MAX_APPROVAL_DELAY_HOURS = 24 * 90


def _naive_utc_now() -> datetime.datetime:
    """Return naive UTC for timestamp-without-time-zone conversation timestamps."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class PaymentReminderMode(StrEnum):
    DISABLED = "disabled"
    MANUAL = "manual"
    SCHEDULED = "scheduled"


class PaymentReminderRetryPolicy(BaseModel):
    """Minimal deterministic retry policy for reminder sends."""

    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(default=1, ge=1, le=1)


class PaymentReminderRetryPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int | None = Field(default=None, ge=1, le=1)


class PaymentReminderDuplicatePolicy(BaseModel):
    """Duplicate suppression for one approved order and reminder window."""

    model_config = ConfigDict(extra="forbid")

    suppress_same_order_window: bool = True
    window_prefix: str = Field(default="initial", min_length=1, max_length=40)


class PaymentReminderDuplicatePolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suppress_same_order_window: bool | None = None
    window_prefix: str | None = Field(default=None, min_length=1, max_length=40)


class PaymentReminderControlsConfig(BaseModel):
    """SystemConfig JSON payload for payment reminder controls."""

    model_config = ConfigDict(extra="forbid")

    mode: PaymentReminderMode = PaymentReminderMode.DISABLED
    max_per_run: int = Field(default=10, ge=0, le=MAX_PAYMENT_REMINDERS_PER_RUN)
    daily_limit: int = Field(default=25, ge=0, le=MAX_PAYMENT_REMINDERS_PER_DAY)
    min_hours_after_approval: int = Field(default=24, ge=0, le=MAX_APPROVAL_DELAY_HOURS)
    template_name: str | None = Field(default=None, min_length=1, max_length=200)
    within_24h_text_enabled: bool = False
    within_24h_text: str | None = Field(default=None, min_length=1, max_length=1000)
    retry: PaymentReminderRetryPolicy = Field(
        default_factory=PaymentReminderRetryPolicy
    )
    duplicate_policy: PaymentReminderDuplicatePolicy = Field(
        default_factory=PaymentReminderDuplicatePolicy
    )

    @model_validator(mode="after")
    def validate_controls(self) -> Self:
        if (
            self.max_per_run > 0
            and self.daily_limit > 0
            and self.max_per_run > self.daily_limit
        ):
            raise ValueError("max_per_run cannot exceed daily_limit")
        if self.within_24h_text_enabled and not self.within_24h_text:
            raise ValueError("within_24h_text is required when enabled")
        return self


class PaymentReminderControlsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: PaymentReminderMode | None = None
    max_per_run: int | None = Field(
        default=None, ge=0, le=MAX_PAYMENT_REMINDERS_PER_RUN
    )
    daily_limit: int | None = Field(
        default=None, ge=0, le=MAX_PAYMENT_REMINDERS_PER_DAY
    )
    min_hours_after_approval: int | None = Field(
        default=None, ge=0, le=MAX_APPROVAL_DELAY_HOURS
    )
    template_name: str | None = Field(default=None, min_length=1, max_length=200)
    within_24h_text_enabled: bool | None = None
    within_24h_text: str | None = Field(default=None, min_length=1, max_length=1000)
    retry: PaymentReminderRetryPolicyUpdate | None = None
    duplicate_policy: PaymentReminderDuplicatePolicyUpdate | None = None


class PaymentReminderControlsResponse(BaseModel):
    config: PaymentReminderControlsConfig


@dataclass(frozen=True)
class PaymentReminderCandidate:
    conversation_id: uuid.UUID
    order_key: str
    window_key: str
    crm_message_id: str
    approval_at: datetime.datetime
    last_customer_inbound_at: datetime.datetime | None


@dataclass(frozen=True)
class PaymentReminderSendResult:
    sent: bool
    reason: str | None
    crm_message_id: str | None = None
    provider_message_id: str | None = None


def _deep_merge(base: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def parse_payment_reminder_controls(raw: Any) -> PaymentReminderControlsConfig:
    if isinstance(raw, PaymentReminderControlsConfig):
        return raw
    if isinstance(raw, Mapping):
        return PaymentReminderControlsConfig.model_validate(raw)
    return PaymentReminderControlsConfig()


def merge_payment_reminder_controls_update(
    current: PaymentReminderControlsConfig,
    update: PaymentReminderControlsUpdate,
) -> PaymentReminderControlsConfig:
    merged = _deep_merge(
        current.model_dump(mode="json"),
        update.model_dump(mode="json", exclude_unset=True),
    )
    return PaymentReminderControlsConfig.model_validate(merged)


async def get_payment_reminder_controls_config(
    db: Any,
) -> PaymentReminderControlsConfig:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == PAYMENT_REMINDER_CONTROLS_KEY)
    )
    row = result.scalar_one_or_none()
    value = getattr(row, "value", None)
    if value is None:
        return PaymentReminderControlsConfig()
    try:
        return parse_payment_reminder_controls(value)
    except ValidationError:
        logger.warning(
            "Invalid SystemConfig %s; using disabled defaults",
            PAYMENT_REMINDER_CONTROLS_KEY,
            exc_info=True,
        )
        return PaymentReminderControlsConfig()


async def save_payment_reminder_controls_config(
    db: Any,
    config: PaymentReminderControlsConfig,
) -> PaymentReminderControlsConfig:
    value = config.model_dump(mode="json")
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == PAYMENT_REMINDER_CONTROLS_KEY)
    )
    row = result.scalar_one_or_none()
    if row is None:
        db.add(
            SystemConfig(
                key=PAYMENT_REMINDER_CONTROLS_KEY,
                value=value,
                description="Payment reminder controls JSON configuration",
            )
        )
    else:
        row.value = value
    await db.commit()
    return config


def build_payment_reminder_response(
    config: PaymentReminderControlsConfig,
) -> PaymentReminderControlsResponse:
    return PaymentReminderControlsResponse(config=config)


def _text_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _lower_text(value: Any) -> str:
    return _text_value(value).lower()


def _parse_metadata_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        if value.tzinfo is not None:
            return value.astimezone(datetime.UTC).replace(tzinfo=None)
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(datetime.UTC).replace(tzinfo=None)
        return parsed
    return None


def _conversation_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        if value.tzinfo is not None:
            return value.astimezone(datetime.UTC).replace(tzinfo=None)
        return value
    return None


def _decision(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    value = metadata.get("quotation_decision")
    return value if isinstance(value, Mapping) else {}


def _quotation_status(metadata: Mapping[str, Any]) -> str:
    decision = _decision(metadata)
    return _lower_text(
        metadata.get("quotation_decision_status")
        or metadata.get("quotation_status")
        or decision.get("status")
    )


def _order_key(metadata: Mapping[str, Any]) -> str:
    decision = _decision(metadata)
    return _text_value(
        metadata.get("zoho_sale_order_id")
        or decision.get("zoho_sale_order_id")
        or decision.get("salesorder_id")
        or metadata.get("zoho_sale_order_number")
        or decision.get("zoho_sale_order_number")
        or decision.get("salesorder_number")
        or decision.get("quote_number")
        or metadata.get("quote_number")
    )


def _approval_at(
    conversation: Conversation,
    metadata: Mapping[str, Any],
) -> datetime.datetime | None:
    decision = _decision(metadata)
    return (
        _parse_metadata_datetime(decision.get("decided_at"))
        or _parse_metadata_datetime(metadata.get("quotation_decision_at"))
        or _conversation_datetime(getattr(conversation, "updated_at", None))
    )


def _is_false(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"false", "0", "no", "inactive"}
    return False


def _has_stop_metadata(metadata: Mapping[str, Any]) -> bool:
    decision = _decision(metadata)
    if _is_false(metadata.get("zoho_sale_order_active")):
        return True
    if _is_false(metadata.get("order_active")):
        return True
    if _is_false(decision.get("active")):
        return True

    stop_values = {"paid", "delivered", "cancelled", "canceled", "rejected", "inactive"}
    for key in (
        "payment_status",
        "order_status",
        "deal_status",
        "quotation_status",
        "quotation_decision_status",
    ):
        if _lower_text(metadata.get(key)) in stop_values:
            return True
    return _lower_text(decision.get("status")) in stop_values


def _window_key(controls: PaymentReminderControlsConfig) -> str:
    prefix = controls.duplicate_policy.window_prefix
    return f"{prefix}-{controls.min_hours_after_approval}h"


def _metadata_payment_state(
    metadata: Mapping[str, Any],
    order_key: str,
    window_key: str,
) -> Mapping[str, Any]:
    reminders = metadata.get("payment_reminders")
    if not isinstance(reminders, Mapping):
        return {}
    order_state = reminders.get(order_key)
    if not isinstance(order_state, Mapping):
        return {}
    window_state = order_state.get(window_key)
    return window_state if isinstance(window_state, Mapping) else {}


def _record_payment_state(
    conv: Conversation,
    *,
    order_key: str,
    window_key: str,
    status: Literal["blocked", "sent", "skipped"],
    reason: str | None,
    crm_message_id: str,
    now: datetime.datetime,
    provider_message_id: str | None = None,
) -> None:
    metadata = dict(conv.metadata_ or {})
    reminders = dict(metadata.get("payment_reminders") or {})
    order_state = dict(reminders.get(order_key) or {})
    state: dict[str, Any] = {
        "status": status,
        "crm_message_id": crm_message_id,
        "updated_at": now.isoformat(),
    }
    if reason:
        state["reason"] = reason
    if provider_message_id:
        state["provider_message_id"] = provider_message_id
    order_state[window_key] = state
    reminders[order_key] = order_state
    metadata["payment_reminders"] = reminders
    conv.metadata_ = metadata


def build_payment_reminder_candidate(
    conversation: Conversation,
    *,
    controls: PaymentReminderControlsConfig,
    last_customer_inbound_at: datetime.datetime | None,
    now: datetime.datetime | None = None,
) -> PaymentReminderCandidate | None:
    if controls.mode == PaymentReminderMode.DISABLED:
        return None

    current = now or _naive_utc_now()
    metadata = (
        conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
    )

    if _lower_text(getattr(conversation, "status", None)) not in {"", "active"}:
        return None
    if _lower_text(getattr(conversation, "escalation_status", None)) not in {
        "",
        "none",
        "resolved",
    }:
        return None
    if _lower_text(getattr(conversation, "deal_status", None)) in {
        "delivered",
        "paid",
        "cancelled",
        "canceled",
    }:
        return None
    if _has_stop_metadata(metadata):
        return None
    if _quotation_status(metadata) != "approved":
        return None

    order_key = _order_key(metadata)
    if not order_key:
        return None

    approved_at = _approval_at(conversation, metadata)
    if approved_at is None:
        return None
    if approved_at > current:
        return None
    hours_after_approval = (current - approved_at).total_seconds() / 3600
    if hours_after_approval < controls.min_hours_after_approval:
        return None

    window = _window_key(controls)
    return PaymentReminderCandidate(
        conversation_id=conversation.id,
        order_key=order_key,
        window_key=window,
        crm_message_id=deterministic_crm_message_id(
            "payment_reminder",
            conversation.id,
            order_key,
            window,
        ),
        approval_at=approved_at,
        last_customer_inbound_at=last_customer_inbound_at,
    )


def _hours_since(value: datetime.datetime | None, now: datetime.datetime) -> float:
    if value is None:
        return float("inf")
    if value.tzinfo is not None:
        value = value.astimezone(datetime.UTC).replace(tzinfo=None)
    return (now - value).total_seconds() / 3600


async def _ctx_payment_reminder_controls(
    db: Any,
    ctx: Mapping[str, Any],
) -> PaymentReminderControlsConfig:
    raw = ctx.get(PAYMENT_REMINDER_CONTROLS_KEY)
    if raw is not None:
        try:
            return parse_payment_reminder_controls(raw)
        except ValidationError:
            logger.warning("Invalid ctx payment reminder controls; using disabled")
            return PaymentReminderControlsConfig()
    return await get_payment_reminder_controls_config(db)


async def _legacy_followups_enabled(db: Any, ctx: Mapping[str, Any]) -> bool:
    if "legacy_automatic_followup_enabled" in ctx:
        return bool(ctx["legacy_automatic_followup_enabled"])
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == LEGACY_AUTOMATIC_FOLLOWUP_KEY)
    )
    row = result.scalar_one_or_none()
    return bool(getattr(row, "value", False))


async def _run_legacy_inactive_followups(db: Any, now: datetime.datetime) -> None:
    intervals = [
        (24, 25),  # 1 day
        (72, 73),  # 3 days
        (168, 169),  # 7 days
    ]

    for min_hrs, max_hrs in intervals:
        min_time = now - datetime.timedelta(hours=max_hrs)
        max_time = now - datetime.timedelta(hours=min_hrs)

        eligible_statuses = [
            status
            for status in ("none", "resolved")
            if allows_automatic_followup(status)
        ]

        stmt = select(Conversation).where(
            Conversation.updated_at >= min_time,
            Conversation.updated_at < max_time,
            Conversation.escalation_status.in_(eligible_statuses),
        )

        result = await db.execute(stmt)
        conversations: list[Conversation] = list(result.scalars().all())

        logfire.info(
            "Found {count} conversations for {hours}h legacy follow-up",
            count=len(conversations),
            hours=min_hrs,
        )

        for conv in conversations:
            try:
                await _process_followup_for_conversation(db, conv)
            except Exception as e:
                logfire.error(
                    "Failed to process legacy followup for {conv_id}: {error}",
                    conv_id=conv.id,
                    error=str(e),
                )


async def _count_payment_reminders_sent_today(
    db: Any,
    now: datetime.datetime,
) -> int:
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(OutboundMessageAudit.id)).where(
            OutboundMessageAudit.source == PAYMENT_REMINDER_SOURCE,
            OutboundMessageAudit.status.in_(
                ("pending", "sent", "delivered", "read", "provider_duplicate")
            ),
            OutboundMessageAudit.created_at >= day_start,
        )
    )
    return int(result.scalar() or 0)


async def _payment_reminder_candidate_rows(
    db: Any,
    *,
    controls: PaymentReminderControlsConfig,
    now: datetime.datetime,
    limit: int,
) -> list[tuple[Conversation, datetime.datetime | None]]:
    if limit <= 0:
        return []

    last_customer_message = (
        select(
            Message.conversation_id.label("conversation_id"),
            func.max(Message.created_at).label("last_customer_inbound_at"),
        )
        .where(Message.role == "user")
        .group_by(Message.conversation_id)
        .subquery()
    )
    page_size = max(limit * 5, 50)
    offset = 0
    candidates: list[tuple[Conversation, datetime.datetime | None]] = []

    while len(candidates) < limit:
        stmt = (
            select(Conversation, last_customer_message.c.last_customer_inbound_at)
            .outerjoin(
                last_customer_message,
                last_customer_message.c.conversation_id == Conversation.id,
            )
            .where(Conversation.status == "active")
            .where(Conversation.escalation_status.in_(("none", "resolved")))
            .order_by(Conversation.updated_at.asc(), Conversation.id.asc())
            .limit(page_size)
            .offset(offset)
        )
        result = await db.execute(stmt)
        rows = [(row[0], row[1]) for row in result.all()]
        if not rows:
            break

        for conv, last_customer_inbound_at in rows:
            if build_payment_reminder_candidate(
                conv,
                controls=controls,
                last_customer_inbound_at=last_customer_inbound_at,
                now=now,
            ):
                candidates.append((conv, last_customer_inbound_at))
                if len(candidates) >= limit:
                    break

        if len(rows) < page_size:
            break
        offset += len(rows)

    return candidates


async def _process_payment_reminder_for_conversation(
    db: Any,
    conv: Conversation,
    *,
    controls: PaymentReminderControlsConfig,
    last_customer_inbound_at: datetime.datetime | None,
    now: datetime.datetime | None = None,
    provider: Any | None = None,
) -> PaymentReminderSendResult:
    current = now or _naive_utc_now()
    candidate = build_payment_reminder_candidate(
        conv,
        controls=controls,
        last_customer_inbound_at=last_customer_inbound_at,
        now=current,
    )
    if candidate is None:
        return PaymentReminderSendResult(sent=False, reason="not_candidate")

    metadata = conv.metadata_ if isinstance(conv.metadata_, dict) else {}
    state = _metadata_payment_state(
        metadata,
        candidate.order_key,
        candidate.window_key,
    )
    if (
        controls.duplicate_policy.suppress_same_order_window
        and state.get("status") == "sent"
    ):
        return PaymentReminderSendResult(
            sent=False,
            reason="duplicate",
            crm_message_id=candidate.crm_message_id,
        )

    created_provider = provider is None
    messaging = provider or WazzupProvider()
    try:
        last_customer_activity = last_customer_inbound_at or _conversation_datetime(
            conv.updated_at
        )
        outside_freeform_window = (
            _hours_since(last_customer_activity, current)
            >= WHATSAPP_FREEFORM_WINDOW_HOURS
        )

        if outside_freeform_window:
            if not controls.template_name:
                _record_payment_state(
                    conv,
                    order_key=candidate.order_key,
                    window_key=candidate.window_key,
                    status="blocked",
                    reason="template_missing",
                    crm_message_id=candidate.crm_message_id,
                    now=current,
                )
                logger.info(
                    "Blocked payment reminder without template",
                    extra={
                        "conversation_id": str(conv.id),
                        "order_key": candidate.order_key,
                    },
                )
                await db.commit()
                return PaymentReminderSendResult(
                    sent=False,
                    reason="template_missing",
                    crm_message_id=candidate.crm_message_id,
                )

            send_result = await send_wazzup_template_with_audit(
                db,
                provider=messaging,
                conversation_id=conv.id,
                chat_id=conv.phone,
                template_name=controls.template_name,
                params={},
                source=PAYMENT_REMINDER_SOURCE,
                crm_message_id=candidate.crm_message_id,
            )
        else:
            if not controls.within_24h_text_enabled:
                return PaymentReminderSendResult(
                    sent=False,
                    reason="within_24h_text_disabled",
                    crm_message_id=candidate.crm_message_id,
                )
            if not controls.within_24h_text:
                return PaymentReminderSendResult(
                    sent=False,
                    reason="within_24h_text_missing",
                    crm_message_id=candidate.crm_message_id,
                )
            send_result = await send_wazzup_text_with_audit(
                db,
                provider=messaging,
                conversation_id=conv.id,
                chat_id=conv.phone,
                text=controls.within_24h_text,
                source=PAYMENT_REMINDER_SOURCE,
                crm_message_id=candidate.crm_message_id,
            )
    finally:
        if created_provider:
            await messaging.close()

    reason = "duplicate" if send_result.skipped else None
    _record_payment_state(
        conv,
        order_key=candidate.order_key,
        window_key=candidate.window_key,
        status="sent",
        reason=reason,
        crm_message_id=candidate.crm_message_id,
        now=current,
        provider_message_id=send_result.provider_message_id,
    )
    await db.commit()
    return PaymentReminderSendResult(
        sent=not send_result.skipped,
        reason=reason,
        crm_message_id=candidate.crm_message_id,
        provider_message_id=send_result.provider_message_id,
    )


async def _run_payment_reminders_with_db(
    db: Any,
    *,
    controls: PaymentReminderControlsConfig,
    now: datetime.datetime,
    trigger: Literal["manual", "scheduled"],
) -> None:
    if controls.mode == PaymentReminderMode.DISABLED:
        logfire.info("Payment reminders disabled")
        return
    if trigger == "scheduled" and controls.mode == PaymentReminderMode.MANUAL:
        logfire.info("Payment reminders in manual mode; scheduled run skipped")
        return

    sent_today = await _count_payment_reminders_sent_today(db, now)
    remaining_daily = max(controls.daily_limit - sent_today, 0)
    max_attempts = min(controls.max_per_run, remaining_daily)
    if max_attempts <= 0:
        logfire.info("Payment reminders capped for this run")
        return

    rows = await _payment_reminder_candidate_rows(
        db,
        controls=controls,
        now=now,
        limit=max_attempts,
    )
    sent_count = 0
    for conv, last_customer_inbound_at in rows:
        if sent_count >= max_attempts:
            break
        try:
            result = await _process_payment_reminder_for_conversation(
                db,
                conv,
                controls=controls,
                last_customer_inbound_at=last_customer_inbound_at,
                now=now,
            )
            if result.sent:
                sent_count += 1
        except Exception as e:
            logfire.error(
                "Failed to process payment reminder for {conv_id}: {error}",
                conv_id=conv.id,
                error=str(e),
            )


async def run_payment_reminders(ctx: dict[str, Any]) -> None:
    """Cron/manual entrypoint for accepted payment reminder sends."""
    async with async_session_factory() as db:
        now = _naive_utc_now()
        controls = await _ctx_payment_reminder_controls(db, ctx)
        trigger: Literal["manual", "scheduled"] = (
            "scheduled" if ctx.get("trigger") == "scheduled" else "manual"
        )
        await _run_payment_reminders_with_db(
            db,
            controls=controls,
            now=now,
            trigger=trigger,
        )


async def run_automatic_followups(ctx: dict[str, Any]) -> None:
    """Cron job for safe reminder follow-ups.

    Payment reminders are disabled by default. The legacy LLM-generated inactive
    follow-up path is retained only behind an explicit opt-in flag.
    """
    logfire.info("Starting automatic follow-ups cron job")

    async with async_session_factory() as db:
        now = _naive_utc_now()
        controls = await _ctx_payment_reminder_controls(db, ctx)
        await _run_payment_reminders_with_db(
            db,
            controls=controls,
            now=now,
            trigger="scheduled",
        )

        if not await _legacy_followups_enabled(db, ctx):
            logfire.info("Legacy automatic LLM follow-ups disabled")
            return

        await _run_legacy_inactive_followups(db, now)


async def _process_followup_for_conversation(db: Any, conv: Conversation) -> None:
    """Generates and sends a follow-up for a specific conversation."""
    logfire.info(f"Processing follow-up for conversation {conv.id}")

    # We simulate a "system" ping to the agent, asking it to draft a follow-up.
    system_instruction = "SYSTEM: The user has been inactive. Draft a polite, short follow-up acknowledging the previous quotes/discussion. Make it a single short paragraph. Do not push, just offer help."

    redis = get_redis_client()
    engine = EmbeddingEngine()
    zoho_crm = ZohoCRMClient(redis)
    messaging = WazzupProvider()
    zoho = None

    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

    zoho = ZohoInventoryClient(redis)

    # Normally, process_message saves user message, calls LLM, saves AIMessage, sends message.
    # Because this is a system-initiated message, we will call the LLM directly
    # and then use messaging_client to send it, and save the AI message manually to DB.

    from src.llm.context import build_message_history
    from src.llm.engine import SalesDeps, sales_agent
    from src.llm.pii import unmask_pii
    from src.llm.safety import (
        PATH_CORE_FOLLOWUP,
        model_name_for_path,
        run_agent_with_safety,
    )
    from src.models.message import Message, message_created_at_now

    # 1. Provide context
    pii_map: dict[str, str] = {}
    history = await build_message_history(db, conv.id, pii_map)

    # Fetch CRM Context
    crm_context = None
    if conv.phone:
        from src.core.cache import get_cached_crm_profile

        crm_context = await get_cached_crm_profile(redis, conv.phone)

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=engine,
        zoho_inventory=zoho,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map=pii_map,
        crm_context=crm_context,
    )

    # 2. Call LLM with the instruction appended to history as a faux System requirement
    # Or simply run the agent with the internal message
    result = await run_agent_with_safety(
        sales_agent,
        PATH_CORE_FOLLOWUP,
        system_instruction,
        model_name=model_name_for_path(PATH_CORE_FOLLOWUP),
        deps=deps,
        message_history=history,
    )

    final_text = unmask_pii(result.output, pii_map)

    # 3. Save AI message to DB
    ai_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=final_text,
        tokens_in=result.usage().input_tokens if result.usage() else None,
        tokens_out=result.usage().output_tokens if result.usage() else None,
        created_at=message_created_at_now(),
    )
    db.add(ai_msg)
    await db.commit()

    # 4. Send message
    await send_wazzup_text_with_audit(
        db,
        provider=messaging,
        conversation_id=conv.id,
        chat_id=conv.phone,
        text=final_text,
        source="automatic_followup",
        crm_message_id=deterministic_crm_message_id(
            "followup",
            conv.id,
            "inactive",
        ),
    )
    await db.commit()
    logfire.info(f"Follow-up sent successfully to {conv.phone}")


async def run_feedback_requests(ctx: dict[str, Any]) -> None:
    """Cron job to send feedback requests to customers with delivered orders.

    Targets conversations where:
    - deal_status = 'delivered'
    - No existing Feedback record
    - Updated 24-48h ago (after delivery)
    """
    logfire.info("Starting feedback requests cron job")

    async with async_session_factory() as db:
        now = datetime.datetime.now(datetime.UTC)
        min_time = now - datetime.timedelta(hours=48)
        max_time = now - datetime.timedelta(hours=24)

        stmt = (
            select(Conversation)
            .outerjoin(Feedback, Feedback.conversation_id == Conversation.id)
            .where(
                Conversation.deal_status == DealStatus.DELIVERED.value,
                Conversation.deal_delivered_at >= min_time,
                Conversation.deal_delivered_at < max_time,
                Feedback.id.is_(None),  # No feedback yet
            )
        )

        result = await db.execute(stmt)
        conversations: list[Conversation] = list(result.scalars().all())

        logfire.info(
            "Found {count} delivered deals awaiting feedback",
            count=len(conversations),
        )

        for conv in conversations:
            try:
                await _send_feedback_request(db, conv)
            except Exception as e:
                logfire.error(
                    "Failed to send feedback request for {conv_id}: {error}",
                    conv_id=conv.id,
                    error=str(e),
                )


async def _send_feedback_request(db: Any, conv: Conversation) -> None:
    """Send a feedback request message and set stage to feedback."""
    logfire.info(f"Sending feedback request for conversation {conv.id}")

    messaging = WazzupProvider()

    # Send initial feedback request FIRST (before committing stage change)
    if conv.language == "ar":
        text = (
            "مرحبًا! 🎉 نأمل أنك تستمتع بأثاثك الجديد من Treejar. "
            "نود سماع رأيك حول تجربتك معنا. "
            "هل يمكنك مشاركة بعض الملاحظات؟"
        )
    else:
        text = (
            "Hello! 🎉 We hope you're enjoying your new furniture from Treejar. "
            "We'd love to hear about your experience. "
            "Could you share some feedback with us?"
        )

    await send_wazzup_text_with_audit(
        db,
        provider=messaging,
        conversation_id=conv.id,
        chat_id=conv.phone,
        text=text,
        source="feedback_request",
        crm_message_id=deterministic_crm_message_id(
            "feedback",
            conv.id,
            "request",
        ),
    )

    # Only commit stage change AFTER successful message send
    conv.sales_stage = SalesStage.FEEDBACK.value
    await db.commit()

    logfire.info(f"Feedback request sent to {conv.phone}")
