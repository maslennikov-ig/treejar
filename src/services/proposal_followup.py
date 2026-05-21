from __future__ import annotations

import datetime
import logging
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from src.core.database import async_session_factory
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.outbound_message import OutboundMessageAudit
from src.models.system_config import SystemConfig
from src.services.customer_language import normalize_customer_language
from src.services.outbound_audit import (
    deterministic_crm_message_id,
    send_wazzup_template_with_audit,
    send_wazzup_text_with_audit,
)

PROPOSAL_FOLLOWUP_METADATA_KEY = "proposal_followup"
PROPOSAL_FOLLOWUP_CONTROLS_KEY = "proposal_followup_send_controls"
PROPOSAL_FOLLOWUP_SOURCE = "proposal_followup"
DEFAULT_BUSINESS_TIMEZONE = "Asia/Dubai"
BUSINESS_START = datetime.time(hour=10)
BUSINESS_END = datetime.time(hour=20)
FOLLOWUP_OFFSETS_BY_STEP = {
    1: datetime.timedelta(hours=24),
    2: datetime.timedelta(days=3),
    3: datetime.timedelta(days=7),
}
FREEFORM_WINDOW = datetime.timedelta(hours=24)
FINAL_NO_RESPONSE_GRACE = datetime.timedelta(hours=24)
MAX_FOLLOWUPS_PER_RUN = 100
DEFAULT_FOLLOWUPS_PER_RUN = 10
MIN_FOLLOWUP_SCAN_CAP = 500
MAX_READ_STATUS_EVENTS = 100
MAX_READ_STATUS_SCAN = 500
WAZZUP_PROVIDER = "wazzup"

logger = logging.getLogger(__name__)

_AUTOREPLY_MARKERS = (
    "auto-reply",
    "autoreply",
    "automatic reply",
    "out of office",
    "out of the office",
    "away from office",
    "away from the office",
    "annual leave",
    "vacation",
    "автоответ",
    "автоматический ответ",
    "в отпуске",
    "вне офиса",
)
_REJECTION_MARKERS = (
    "not interested",
    "no longer interested",
    "do not need",
    "don't need",
    "we don't need",
    "decline",
    "reject",
    "cancel this",
    "cancel the proposal",
    "не интересно",
    "неинтересно",
    "не нужно",
    "не нужен",
    "отказыва",
    "отмена",
)


@dataclass(frozen=True)
class ProposalFollowupDueStep:
    conversation_id: uuid.UUID | None
    step: int
    scheduled_at: datetime.datetime
    kp_message_id: str | None


@dataclass(frozen=True)
class ProposalFollowupReplyDecision:
    action: Literal["ignore", "pause", "stop"]
    reason: str
    pause_until: datetime.datetime | None = None
    recommended_deal_status: str | None = None


@dataclass(frozen=True)
class ProposalFollowupSendControls:
    enabled: bool = False
    template_name: str | None = None
    template_name_by_language: Mapping[str, str] = field(default_factory=dict)
    template_name_by_step: Mapping[int, str] = field(default_factory=dict)
    template_name_by_step_language: Mapping[str, Mapping[int, str]] = field(
        default_factory=dict
    )
    template_transport_confirmed: bool = False
    freeform_text_by_language: Mapping[str, str] = field(default_factory=dict)
    freeform_text_by_step: Mapping[int, str] = field(default_factory=dict)
    freeform_text_by_step_language: Mapping[str, Mapping[int, str]] = field(
        default_factory=dict
    )
    freeform_window: datetime.timedelta = FREEFORM_WINDOW
    max_per_run: int = DEFAULT_FOLLOWUPS_PER_RUN
    scan_cap: int = MIN_FOLLOWUP_SCAN_CAP


@dataclass(frozen=True)
class ProposalFollowupSendPlan:
    can_send: bool
    reason: str | None
    mode: Literal["disabled", "blocked", "template", "freeform"]
    template_name: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class ProposalFollowupSendResult:
    sent: bool
    reason: str | None
    crm_message_id: str | None = None
    provider_message_id: str | None = None


def _as_aware_utc(value: datetime.datetime) -> datetime.datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.UTC)
    return value.astimezone(datetime.UTC)


def _iso_utc(value: datetime.datetime) -> str:
    return _as_aware_utc(value).isoformat()


def _parse_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return _as_aware_utc(value)
    if isinstance(value, str) and value.strip():
        try:
            return _as_aware_utc(
                datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            )
        except ValueError:
            return None
    return None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on", "enabled"}
    if isinstance(value, int):
        return value != 0
    return False


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(parsed, maximum))


def _optional_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _step_text_map(value: Any) -> dict[int, str]:
    if not isinstance(value, Mapping):
        return {}

    parsed: dict[int, str] = {}
    for raw_key, raw_value in value.items():
        try:
            step = int(raw_key)
        except (TypeError, ValueError):
            continue
        text = _optional_text(raw_value)
        if step in FOLLOWUP_OFFSETS_BY_STEP and text:
            parsed[step] = text
    return parsed


def _config_language_key(value: Any) -> str | None:
    language = str(value or "").strip().casefold().replace("_", "-")
    if not language:
        return None
    if language in {"en", "eng", "english"} or language.startswith("en-"):
        return "en"
    if language in {"ar", "ara", "arabic", "العربية", "عربي"} or language.startswith(
        "ar-"
    ):
        return "ar"
    return None


def _language_text_map(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    parsed: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        language = _config_language_key(raw_key)
        if language is None:
            continue
        text = _optional_text(raw_value)
        if text:
            parsed[language] = text
    return parsed


def _language_step_text_map(value: Any) -> dict[str, dict[int, str]]:
    if not isinstance(value, Mapping):
        return {}
    parsed: dict[str, dict[int, str]] = {}
    for raw_key, raw_value in value.items():
        language = _config_language_key(raw_key)
        if language is None:
            continue
        step_map = _step_text_map(raw_value)
        if step_map:
            parsed[language] = step_map
    return parsed


def _freeform_window(value: Any) -> datetime.timedelta:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return FREEFORM_WINDOW
    if hours <= 0:
        return FREEFORM_WINDOW
    return datetime.timedelta(hours=min(hours, 24))


def parse_proposal_followup_send_controls(
    raw: Any,
) -> ProposalFollowupSendControls:
    if isinstance(raw, ProposalFollowupSendControls):
        return raw
    if not isinstance(raw, Mapping):
        return ProposalFollowupSendControls()

    return ProposalFollowupSendControls(
        enabled=_parse_bool(raw.get("enabled")),
        template_name=_optional_text(raw.get("template_name")),
        template_name_by_language=_language_text_map(
            raw.get("template_name_by_language")
        ),
        template_name_by_step=_step_text_map(raw.get("template_name_by_step")),
        template_name_by_step_language=_language_step_text_map(
            raw.get("template_name_by_step_language")
        ),
        template_transport_confirmed=_parse_bool(
            raw.get("template_transport_confirmed")
        ),
        freeform_text_by_language=_language_text_map(
            raw.get("freeform_text_by_language")
        ),
        freeform_text_by_step=_step_text_map(raw.get("freeform_text_by_step")),
        freeform_text_by_step_language=_language_step_text_map(
            raw.get("freeform_text_by_step_language")
        ),
        freeform_window=_freeform_window(raw.get("freeform_window_hours")),
        max_per_run=_bounded_int(
            raw.get("max_per_run"),
            default=DEFAULT_FOLLOWUPS_PER_RUN,
            minimum=0,
            maximum=MAX_FOLLOWUPS_PER_RUN,
        ),
        scan_cap=_bounded_int(
            raw.get("scan_cap"),
            default=MIN_FOLLOWUP_SCAN_CAP,
            minimum=0,
            maximum=MAX_FOLLOWUPS_PER_RUN * 100,
        ),
    )


async def get_proposal_followup_send_controls(
    db: Any,
) -> ProposalFollowupSendControls:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == PROPOSAL_FOLLOWUP_CONTROLS_KEY)
    )
    row = result.scalar_one_or_none()
    return parse_proposal_followup_send_controls(getattr(row, "value", None))


async def _ctx_proposal_followup_send_controls(
    db: Any,
    ctx: Mapping[str, Any],
) -> ProposalFollowupSendControls:
    if PROPOSAL_FOLLOWUP_CONTROLS_KEY in ctx:
        return parse_proposal_followup_send_controls(
            ctx[PROPOSAL_FOLLOWUP_CONTROLS_KEY]
        )
    return await get_proposal_followup_send_controls(db)


def _business_timezone(name: str) -> ZoneInfo:
    return ZoneInfo(name)


def _business_day_start(
    local_date: datetime.date,
    timezone: ZoneInfo,
) -> datetime.datetime:
    return datetime.datetime.combine(
        local_date,
        BUSINESS_START,
        tzinfo=timezone,
    )


def _next_business_day_start(
    local: datetime.datetime,
    timezone: ZoneInfo,
) -> datetime.datetime:
    next_date = local.date() + datetime.timedelta(days=1)
    while next_date.weekday() >= 5:
        next_date += datetime.timedelta(days=1)
    return _business_day_start(next_date, timezone)


def _apply_business_window(
    target: datetime.datetime,
    *,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> datetime.datetime:
    timezone = _business_timezone(timezone_name)
    local = _as_aware_utc(target).astimezone(timezone)

    if local.weekday() >= 5:
        days_until_monday = 7 - local.weekday()
        shifted = _business_day_start(
            local.date() + datetime.timedelta(days=days_until_monday),
            timezone,
        )
        return shifted.astimezone(datetime.UTC)

    if local.time() < BUSINESS_START:
        return _business_day_start(local.date(), timezone).astimezone(datetime.UTC)

    if local.time() >= BUSINESS_END:
        return _next_business_day_start(local, timezone).astimezone(datetime.UTC)

    return local.astimezone(datetime.UTC)


def _step_template(step: int, scheduled_at: datetime.datetime) -> dict[str, Any]:
    return {
        "label": f"FU{step}",
        "status": "pending",
        "scheduled_at": _iso_utc(scheduled_at),
        "sent_at": None,
        "provider_message_id": None,
    }


def _build_steps(
    sent_at: datetime.datetime,
    *,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> dict[str, dict[str, Any]]:
    steps: dict[str, dict[str, Any]] = {}
    for step, offset in FOLLOWUP_OFFSETS_BY_STEP.items():
        scheduled_at = _apply_business_window(
            sent_at + offset,
            timezone_name=timezone_name,
        )
        steps[str(step)] = _step_template(step, scheduled_at)
    return steps


def _metadata(conversation: Conversation) -> dict[str, Any]:
    return dict(conversation.metadata_ or {})


def _state(conversation: Conversation) -> dict[str, Any] | None:
    metadata = (
        conversation.metadata_ if isinstance(conversation.metadata_, dict) else {}
    )
    state = metadata.get(PROPOSAL_FOLLOWUP_METADATA_KEY)
    return state if isinstance(state, dict) else None


def _set_state(conversation: Conversation, state: dict[str, Any]) -> None:
    metadata = _metadata(conversation)
    metadata[PROPOSAL_FOLLOWUP_METADATA_KEY] = state
    conversation.metadata_ = metadata


def _steps(state: Mapping[str, Any]) -> dict[str, Any]:
    steps = state.get("steps")
    return steps if isinstance(steps, dict) else {}


def _mark_no_response_rejected(
    conversation: Conversation,
    state: dict[str, Any],
    *,
    decided_at: datetime.datetime,
) -> None:
    metadata = _metadata(conversation)
    quote_number = metadata.get("zoho_sale_order_number") or metadata.get(
        "quotation_quote_number"
    )
    sale_order_id = metadata.get("zoho_sale_order_id")
    state["final_status"] = "no_response"
    state["chain_stopped"] = True
    state["stop_reason"] = "no_response_after_followups"
    state["stopped_at"] = _iso_utc(decided_at)
    metadata["quotation_decision_status"] = "rejected"
    metadata["quotation_decision_at"] = _iso_utc(decided_at)
    metadata["zoho_sale_order_active"] = False
    decision: dict[str, Any] = {
        "status": "rejected",
        "reason": "no_response_after_followups",
        "active": False,
        "decided_at": _iso_utc(decided_at),
    }
    if isinstance(quote_number, str) and quote_number.strip():
        decision["quote_number"] = quote_number.strip()
    if isinstance(sale_order_id, str) and sale_order_id.strip():
        decision["zoho_sale_order_id"] = sale_order_id.strip()
    metadata["quotation_decision"] = decision
    metadata[PROPOSAL_FOLLOWUP_METADATA_KEY] = state
    conversation.metadata_ = metadata


def _mark_explicit_rejection(
    conversation: Conversation,
    state: dict[str, Any],
    *,
    decided_at: datetime.datetime,
    customer_text: str,
) -> None:
    metadata = _metadata(conversation)
    quote_number = metadata.get("zoho_sale_order_number") or metadata.get(
        "quotation_quote_number"
    )
    sale_order_id = metadata.get("zoho_sale_order_id")
    decided_at_iso = _iso_utc(decided_at)
    metadata["quotation_decision_status"] = "rejected"
    metadata["quotation_decision_at"] = decided_at_iso
    metadata["zoho_sale_order_active"] = False
    decision: dict[str, Any] = {
        "status": "rejected",
        "reason": "explicit_rejection",
        "active": False,
        "decided_at": decided_at_iso,
        "customer_text": customer_text.strip()[:500],
    }
    if isinstance(quote_number, str) and quote_number.strip():
        decision["quote_number"] = quote_number.strip()
    if isinstance(sale_order_id, str) and sale_order_id.strip():
        decision["zoho_sale_order_id"] = sale_order_id.strip()
    metadata["quotation_decision"] = decision
    metadata[PROPOSAL_FOLLOWUP_METADATA_KEY] = state
    conversation.metadata_ = metadata


def record_proposal_sent(
    conversation: Conversation,
    *,
    sent_at: datetime.datetime,
    kp_message_id: str,
    quote_number: str | None = None,
    sale_order_id: str | None = None,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> dict[str, Any]:
    """Initialize deterministic proposal follow-up metadata without sending."""
    sent_at_utc = _as_aware_utc(sent_at)
    state: dict[str, Any] = {
        "sent_at": _iso_utc(sent_at_utc),
        "kp_message_id": kp_message_id,
        "kp_read": False,
        "kp_read_at": None,
        "chain_stopped": False,
        "pause_until": None,
        "steps": _build_steps(sent_at_utc, timezone_name=timezone_name),
    }
    metadata = _metadata(conversation)
    metadata[PROPOSAL_FOLLOWUP_METADATA_KEY] = state

    current_quote_number = (
        quote_number
        or metadata.get("zoho_sale_order_number")
        or metadata.get("quotation_quote_number")
    )
    current_sale_order_id = sale_order_id or metadata.get("zoho_sale_order_id")
    real_quote_number = (
        current_quote_number
        if isinstance(current_quote_number, str)
        and current_quote_number.strip()
        and current_quote_number.strip().casefold() != "draft"
        else None
    )
    metadata["quotation_decision_status"] = "pending"
    metadata.pop("quotation_decision_at", None)
    metadata.pop("quotation_status", None)
    metadata.pop("zoho_sale_order_number", None)
    metadata.pop("quotation_quote_number", None)
    metadata["zoho_sale_order_active"] = True
    if isinstance(current_sale_order_id, str) and current_sale_order_id.strip():
        metadata["zoho_sale_order_id"] = current_sale_order_id.strip()
    if real_quote_number:
        metadata["zoho_sale_order_number"] = real_quote_number.strip()
        metadata["quotation_quote_number"] = real_quote_number.strip()
    decision: dict[str, Any] = {
        "status": "pending",
        "active": True,
        "sent_at": _iso_utc(sent_at_utc),
    }
    if real_quote_number:
        decision["quote_number"] = real_quote_number.strip()
    if isinstance(current_sale_order_id, str) and current_sale_order_id.strip():
        decision["zoho_sale_order_id"] = current_sale_order_id.strip()
    metadata["quotation_decision"] = decision
    conversation.metadata_ = metadata
    return state


def record_proposal_read(
    conversation: Conversation,
    *,
    read_at: datetime.datetime,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> dict[str, Any] | None:
    state = _state(conversation)
    if state is None:
        return None

    read_at_utc = _as_aware_utc(read_at)
    state["kp_read"] = True
    state["kp_read_at"] = _iso_utc(read_at_utc)

    _set_state(conversation, state)
    return state


def record_followup_step_sent(
    conversation: Conversation,
    *,
    step: int,
    sent_at: datetime.datetime,
    provider_message_id: str | None = None,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> dict[str, Any] | None:
    if step not in FOLLOWUP_OFFSETS_BY_STEP:
        raise ValueError("step must be 1, 2, or 3")

    state = _state(conversation)
    if state is None:
        return None

    steps = _steps(state)
    step_state = steps.get(str(step))
    if not isinstance(step_state, dict):
        step_state = _step_template(step, _as_aware_utc(sent_at))
        steps[str(step)] = step_state

    step_state["status"] = "sent"
    sent_at_utc = _as_aware_utc(sent_at)
    step_state["sent_at"] = _iso_utc(sent_at_utc)
    step_state["provider_message_id"] = provider_message_id
    if step == max(FOLLOWUP_OFFSETS_BY_STEP):
        state["final_status"] = "awaiting_response_after_final_followup"
        state["final_followup_sent_at"] = _iso_utc(sent_at_utc)
        state["final_no_response_due_at"] = _iso_utc(
            sent_at_utc + FINAL_NO_RESPONSE_GRACE
        )
    _set_state(conversation, state)
    return state


def final_no_response_due(
    conversation: Conversation,
    *,
    now: datetime.datetime,
) -> bool:
    state = _state(conversation)
    if state is None or state.get("chain_stopped") is True:
        return False
    if state.get("final_status") != "awaiting_response_after_final_followup":
        return False

    due_at = _parse_datetime(state.get("final_no_response_due_at"))
    if due_at is None or _as_aware_utc(now) < due_at:
        return False

    final_sent_at = _parse_datetime(state.get("final_followup_sent_at"))
    last_customer_reply_at = _parse_datetime(state.get("last_customer_reply_at"))
    return not (
        final_sent_at is not None
        and last_customer_reply_at is not None
        and last_customer_reply_at >= final_sent_at
    )


def next_due_followup_step(
    conversation: Conversation,
    *,
    now: datetime.datetime,
) -> ProposalFollowupDueStep | None:
    state = _state(conversation)
    if state is None or state.get("chain_stopped") is True:
        return None

    now_utc = _as_aware_utc(now)
    pause_until = _parse_datetime(state.get("pause_until"))
    if pause_until is not None and now_utc < pause_until:
        return None

    steps = _steps(state)
    for step in FOLLOWUP_OFFSETS_BY_STEP:
        step_state = steps.get(str(step))
        if not isinstance(step_state, Mapping):
            continue
        if step_state.get("status", "pending") != "pending":
            continue
        scheduled_at = _parse_datetime(step_state.get("scheduled_at"))
        if scheduled_at is not None and scheduled_at <= now_utc:
            conversation_id = getattr(conversation, "id", None)
            return ProposalFollowupDueStep(
                conversation_id=conversation_id,
                step=step,
                scheduled_at=scheduled_at,
                kp_message_id=state.get("kp_message_id"),
            )

    return None


def _normalized_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _contains_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_autoreply(text: str) -> bool:
    return _contains_marker(text, _AUTOREPLY_MARKERS)


def _is_rejection(text: str) -> bool:
    return _contains_marker(text, _REJECTION_MARKERS)


def _return_date_from_autoreply(text: str) -> datetime.date | None:
    iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", text)
    if iso_match:
        year, month, day = (int(part) for part in iso_match.groups())
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None

    slash_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", text)
    if slash_match:
        day, month, year = (int(part) for part in slash_match.groups())
        try:
            return datetime.date(year, month, day)
        except ValueError:
            return None

    return None


def _pause_until_return_date(
    return_date: datetime.date,
    *,
    timezone_name: str,
) -> datetime.datetime:
    timezone = _business_timezone(timezone_name)
    local_midnight_next_day = datetime.datetime.combine(
        return_date + datetime.timedelta(days=1),
        datetime.time.min,
        tzinfo=timezone,
    )
    return local_midnight_next_day.astimezone(datetime.UTC)


def _stop_chain(
    state: dict[str, Any],
    *,
    reason: str,
    received_at: datetime.datetime,
) -> None:
    state["chain_stopped"] = True
    state["stop_reason"] = reason
    state["stopped_at"] = _iso_utc(received_at)
    state["last_customer_reply_at"] = _iso_utc(received_at)


def record_customer_reply(
    conversation: Conversation,
    *,
    text: str,
    received_at: datetime.datetime,
    timezone_name: str = DEFAULT_BUSINESS_TIMEZONE,
) -> ProposalFollowupReplyDecision:
    state = _state(conversation)
    if state is None:
        return ProposalFollowupReplyDecision(
            action="ignore",
            reason="proposal_followup_missing",
        )

    received_at_utc = _as_aware_utc(received_at)
    normalized = _normalized_text(text)

    if _is_rejection(normalized):
        _stop_chain(state, reason="explicit_rejection", received_at=received_at_utc)
        _mark_explicit_rejection(
            conversation,
            state,
            decided_at=received_at_utc,
            customer_text=text,
        )
        return ProposalFollowupReplyDecision(
            action="stop",
            reason="explicit_rejection",
            recommended_deal_status="rejected",
        )

    if _is_autoreply(normalized):
        return_date = _return_date_from_autoreply(normalized)
        pause_until = (
            _pause_until_return_date(return_date, timezone_name=timezone_name)
            if return_date is not None
            else received_at_utc + datetime.timedelta(days=3)
        )
        state["pause_until"] = _iso_utc(pause_until)
        state["pause_reason"] = (
            "autoreply_with_date" if return_date is not None else "autoreply"
        )
        state["last_customer_reply_at"] = _iso_utc(received_at_utc)
        _set_state(conversation, state)
        return ProposalFollowupReplyDecision(
            action="pause",
            reason=state["pause_reason"],
            pause_until=pause_until,
        )

    if normalized:
        _stop_chain(
            state,
            reason="customer_reply",
            received_at=received_at_utc,
        )
        _set_state(conversation, state)
        return ProposalFollowupReplyDecision(
            action="stop",
            reason="customer_reply",
        )

    state["last_customer_reply_at"] = _iso_utc(received_at_utc)
    _set_state(conversation, state)
    return ProposalFollowupReplyDecision(action="ignore", reason="empty_reply")


def build_followup_send_plan(
    due_step: ProposalFollowupDueStep,
    *,
    controls: ProposalFollowupSendControls | None = None,
    last_customer_inbound_at: datetime.datetime | None = None,
    now: datetime.datetime | None = None,
    language: str = "en",
) -> ProposalFollowupSendPlan:
    active_controls = controls or ProposalFollowupSendControls()
    if not active_controls.enabled:
        return ProposalFollowupSendPlan(
            can_send=False,
            reason="proposal_followup_disabled",
            mode="disabled",
        )

    current = _as_aware_utc(now or datetime.datetime.now(datetime.UTC))
    inbound_at = (
        _as_aware_utc(last_customer_inbound_at) if last_customer_inbound_at else None
    )
    within_freeform_window = (
        inbound_at is not None
        and current - inbound_at < active_controls.freeform_window
    )

    language_key = normalize_customer_language(language)

    if within_freeform_window:
        text = (
            active_controls.freeform_text_by_step_language.get(language_key, {}).get(
                due_step.step
            )
            or active_controls.freeform_text_by_step.get(due_step.step)
            or active_controls.freeform_text_by_language.get(language_key)
        )
        if not text:
            return ProposalFollowupSendPlan(
                can_send=False,
                reason="freeform_text_required_within_24h",
                mode="blocked",
            )
        return ProposalFollowupSendPlan(
            can_send=True,
            reason=None,
            mode="freeform",
            text=text,
        )

    template_name = (
        active_controls.template_name_by_step_language.get(language_key, {}).get(
            due_step.step
        )
        or active_controls.template_name_by_step.get(due_step.step)
        or active_controls.template_name_by_language.get(language_key)
        or active_controls.template_name
    )
    if not template_name:
        return ProposalFollowupSendPlan(
            can_send=False,
            reason="template_required_outside_24h",
            mode="blocked",
        )
    if not active_controls.template_transport_confirmed:
        return ProposalFollowupSendPlan(
            can_send=False,
            reason="template_transport_unconfirmed",
            mode="blocked",
        )

    return ProposalFollowupSendPlan(
        can_send=True,
        reason=None,
        mode="template",
        template_name=template_name,
    )


def proposal_followup_crm_message_id(
    conversation_id: uuid.UUID,
    due_step: ProposalFollowupDueStep,
) -> str:
    return deterministic_crm_message_id(
        PROPOSAL_FOLLOWUP_SOURCE,
        conversation_id,
        f"fu{due_step.step}",
        _iso_utc(due_step.scheduled_at),
    )


async def process_due_proposal_followup(
    db: Any,
    conversation: Conversation,
    *,
    controls: ProposalFollowupSendControls,
    last_customer_inbound_at: datetime.datetime | None,
    now: datetime.datetime,
    provider: Any,
) -> ProposalFollowupSendResult:
    if final_no_response_due(conversation, now=now):
        state = _state(conversation)
        if state is not None:
            _mark_no_response_rejected(
                conversation,
                state,
                decided_at=_as_aware_utc(now),
            )
            await db.commit()
            return ProposalFollowupSendResult(
                sent=False,
                reason="final_no_response_marked",
            )

    due_step = next_due_followup_step(conversation, now=now)
    if due_step is None:
        return ProposalFollowupSendResult(sent=False, reason="not_due")

    conversation_id = due_step.conversation_id or conversation.id
    crm_message_id = proposal_followup_crm_message_id(conversation_id, due_step)
    plan = build_followup_send_plan(
        due_step,
        controls=controls,
        last_customer_inbound_at=last_customer_inbound_at,
        now=now,
        language=str(getattr(conversation, "language", "en") or "en"),
    )
    if not plan.can_send:
        return ProposalFollowupSendResult(
            sent=False,
            reason=plan.reason,
            crm_message_id=crm_message_id,
        )

    if plan.mode == "template":
        if not plan.template_name:
            return ProposalFollowupSendResult(
                sent=False,
                reason="template_required_outside_24h",
                crm_message_id=crm_message_id,
            )
        send_result = await send_wazzup_template_with_audit(
            db,
            provider=provider,
            conversation_id=conversation_id,
            chat_id=conversation.phone,
            template_name=plan.template_name,
            params={},
            source=PROPOSAL_FOLLOWUP_SOURCE,
            crm_message_id=crm_message_id,
        )
    elif plan.mode == "freeform":
        if not plan.text:
            return ProposalFollowupSendResult(
                sent=False,
                reason="freeform_text_required_within_24h",
                crm_message_id=crm_message_id,
            )
        send_result = await send_wazzup_text_with_audit(
            db,
            provider=provider,
            conversation_id=conversation_id,
            chat_id=conversation.phone,
            text=plan.text,
            source=PROPOSAL_FOLLOWUP_SOURCE,
            crm_message_id=crm_message_id,
        )
    else:
        return ProposalFollowupSendResult(
            sent=False,
            reason=plan.reason or "send_blocked",
            crm_message_id=crm_message_id,
        )

    record_followup_step_sent(
        conversation,
        step=due_step.step,
        sent_at=now,
        provider_message_id=send_result.provider_message_id,
    )
    await db.commit()
    return ProposalFollowupSendResult(
        sent=not send_result.skipped,
        reason="duplicate" if send_result.skipped else None,
        crm_message_id=crm_message_id,
        provider_message_id=send_result.provider_message_id,
    )


async def _proposal_followup_candidate_rows(
    db: Any,
    *,
    now: datetime.datetime,
    limit: int,
    scan_cap: int,
) -> list[tuple[Conversation, datetime.datetime | None]]:
    if limit <= 0 or scan_cap <= 0:
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
    bounded_scan_cap = max(scan_cap, limit)
    offset = 0
    scanned_count = 0
    candidates: list[tuple[Conversation, datetime.datetime | None]] = []

    while len(candidates) < limit and scanned_count < bounded_scan_cap:
        current_page_size = min(page_size, bounded_scan_cap - scanned_count)
        stmt = (
            select(Conversation, last_customer_message.c.last_customer_inbound_at)
            .outerjoin(
                last_customer_message,
                last_customer_message.c.conversation_id == Conversation.id,
            )
            .where(Conversation.status == "active")
            .where(Conversation.metadata_.is_not(None))
            .order_by(Conversation.updated_at.asc(), Conversation.id.asc())
            .limit(current_page_size)
            .offset(offset)
        )
        result = await db.execute(stmt)
        rows = [(row[0], row[1]) for row in result.all()]
        if not rows:
            break

        for conversation, last_customer_inbound_at in rows:
            scanned_count += 1
            if next_due_followup_step(
                conversation,
                now=now,
            ) or final_no_response_due(conversation, now=now):
                candidates.append((conversation, last_customer_inbound_at))
                if len(candidates) >= limit:
                    break

        if len(candidates) >= limit or scanned_count >= bounded_scan_cap:
            break
        if len(rows) < current_page_size:
            break
        offset += len(rows)

    if scanned_count >= bounded_scan_cap and len(candidates) < limit:
        logger.warning(
            "Proposal follow-up scan cap reached",
            extra={
                "limit": limit,
                "scanned_count": scanned_count,
                "candidate_count": len(candidates),
                "cap": bounded_scan_cap,
            },
        )

    return candidates


async def run_due_proposal_followups(
    db: Any,
    *,
    controls: ProposalFollowupSendControls,
    now: datetime.datetime,
    provider: Any | None = None,
) -> int:
    if not controls.enabled:
        logger.info("Proposal follow-up sends disabled")
        return 0

    max_attempts = max(0, min(controls.max_per_run, MAX_FOLLOWUPS_PER_RUN))
    if max_attempts <= 0:
        logger.info("Proposal follow-up max_per_run is zero")
        return 0

    rows = await _proposal_followup_candidate_rows(
        db,
        now=now,
        limit=max_attempts,
        scan_cap=controls.scan_cap,
    )
    if not rows:
        return 0

    sent_count = 0
    created_provider = provider is None
    messaging = provider or WazzupProvider()
    try:
        for conversation, last_customer_inbound_at in rows:
            if sent_count >= max_attempts:
                break
            try:
                result = await process_due_proposal_followup(
                    db,
                    conversation,
                    controls=controls,
                    last_customer_inbound_at=last_customer_inbound_at,
                    now=now,
                    provider=messaging,
                )
            except Exception:
                logger.exception(
                    "Failed to process proposal follow-up",
                    extra={"conversation_id": str(conversation.id)},
                )
                continue
            if result.sent:
                sent_count += 1
    finally:
        if created_provider:
            await messaging.close()

    return sent_count


async def run_proposal_followups(ctx: dict[str, Any]) -> None:
    """ARQ entrypoint for disabled-by-default proposal follow-up sends."""
    async with async_session_factory() as db:
        controls = await _ctx_proposal_followup_send_controls(db, ctx)
        await run_due_proposal_followups(
            db,
            controls=controls,
            now=datetime.datetime.now(datetime.UTC),
        )


def _read_status_message_ids(
    statuses: list[dict[str, Any]],
    *,
    max_events: int = MAX_READ_STATUS_EVENTS,
) -> list[tuple[str, datetime.datetime | None]]:
    message_ids: list[tuple[str, datetime.datetime | None]] = []
    seen: set[str] = set()
    for payload in statuses[:max_events]:
        status = payload.get("status")
        if not isinstance(status, str) or status.casefold() != "read":
            continue
        message_id = payload.get("messageId")
        if not isinstance(message_id, str) or not message_id or message_id in seen:
            continue
        seen.add(message_id)
        message_ids.append((message_id, _parse_datetime(payload.get("timestamp"))))
    return message_ids


def _proposal_message_matches(
    conversation: Conversation,
    message_id: str,
) -> bool:
    state = _state(conversation)
    return bool(state and state.get("kp_message_id") == message_id)


async def _conversation_from_audit_message_id(
    db: Any,
    message_id: str,
) -> Conversation | None:
    audit_result = await db.execute(
        select(OutboundMessageAudit)
        .where(OutboundMessageAudit.provider == WAZZUP_PROVIDER)
        .where(OutboundMessageAudit.provider_message_id == message_id)
        .limit(1)
    )
    audit = audit_result.scalar_one_or_none()
    if not isinstance(audit, OutboundMessageAudit):
        return None

    conversation_result = await db.execute(
        select(Conversation).where(Conversation.id == audit.conversation_id).limit(1)
    )
    conversation = conversation_result.scalar_one_or_none()
    if isinstance(conversation, Conversation) and _proposal_message_matches(
        conversation,
        message_id,
    ):
        return conversation
    return None


async def _conversation_from_bounded_metadata_scan(
    db: Any,
    message_id: str,
    *,
    scan_limit: int,
) -> Conversation | None:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.status == "active")
        .where(Conversation.metadata_.is_not(None))
        .order_by(Conversation.updated_at.desc(), Conversation.id.asc())
        .limit(scan_limit)
    )
    for conversation in result.scalars().all():
        if isinstance(conversation, Conversation) and _proposal_message_matches(
            conversation,
            message_id,
        ):
            return conversation
    return None


async def _conversation_for_proposal_message_id(
    db: Any,
    message_id: str,
    *,
    scan_limit: int,
) -> Conversation | None:
    return await _conversation_from_audit_message_id(
        db,
        message_id,
    ) or await _conversation_from_bounded_metadata_scan(
        db,
        message_id,
        scan_limit=scan_limit,
    )


async def apply_proposal_read_statuses(
    db: Any,
    statuses: list[dict[str, Any]],
    *,
    now: datetime.datetime | None = None,
    scan_limit: int = MAX_READ_STATUS_SCAN,
) -> int:
    read_statuses = _read_status_message_ids(statuses)
    if not read_statuses:
        return 0

    current = _as_aware_utc(now or datetime.datetime.now(datetime.UTC))
    bounded_scan_limit = max(0, min(scan_limit, MAX_READ_STATUS_SCAN))
    updated = 0

    for message_id, read_at in read_statuses:
        conversation = await _conversation_for_proposal_message_id(
            db,
            message_id,
            scan_limit=bounded_scan_limit,
        )
        if conversation is None:
            continue

        state = _state(conversation)
        if state is None or state.get("kp_read") is True:
            continue

        record_proposal_read(
            conversation,
            read_at=read_at or current,
        )
        updated += 1

    if updated:
        await db.flush()
    return updated
