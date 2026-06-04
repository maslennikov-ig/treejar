from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select

from src.models.conversation import Conversation
from src.models.customer_memory import (
    CustomerFact,
    CustomerOrderMemory,
    CustomerProfile,
)
from src.models.message import Message

FactValue = dict[str, Any] | list[Any] | str | int | float | bool | None

ACTIVE_ORDER_STATUSES = ("active", "quoted_snapshot")
TERMINAL_ORDER_STATUSES = (
    "accepted",
    "closed_refused",
    "closed_no_response",
    "superseded",
)


@dataclass(slots=True)
class FactMergeResult:
    accepted: list[CustomerFact] = field(default_factory=list)
    proposed: list[CustomerFact] = field(default_factory=list)
    conflicts: list[CustomerFact] = field(default_factory=list)
    confirmation_required: list[CustomerFact] = field(default_factory=list)


@dataclass(slots=True)
class CustomerFactsContext:
    profile_lines: list[str]
    current_order_lines: list[str]
    past_order_lines: list[str]
    missing_quote_fields: list[str]
    confirmation_required: list[str] = field(default_factory=list)

    def render(self) -> str:
        sections = [
            ("Known customer profile:", self.profile_lines),
            ("Current order:", self.current_order_lines),
            ("Past orders:", self.past_order_lines),
            ("Missing for quotation:", self.missing_quote_fields),
        ]
        if self.confirmation_required:
            sections.append(("Needs confirmation:", self.confirmation_required))

        rendered: list[str] = []
        for heading, lines in sections:
            rendered.append(heading)
            rendered.extend(lines or ["- none"])
        return "\n".join(rendered)


async def get_or_create_customer_profile(
    db: Any,
    *,
    phone: str,
    conversation: Conversation | None = None,
) -> CustomerProfile:
    canonical_phone = phone.strip()
    if not canonical_phone:
        raise ValueError("phone is required to create a customer profile")

    profile = await _fetch_profile_by_phone(db, canonical_phone)
    if profile is not None:
        return profile

    profile = CustomerProfile(
        canonical_phone=canonical_phone,
        display_name=conversation.customer_name if conversation else None,
        preferred_language=conversation.language if conversation else None,
        zoho_contact_id=conversation.zoho_contact_id if conversation else None,
    )
    db.add(profile)
    await db.flush()
    return profile


async def get_or_create_active_order(
    db: Any,
    *,
    profile: CustomerProfile,
    conversation: Conversation,
) -> CustomerOrderMemory:
    order = await _fetch_active_order(db, profile=profile, conversation=conversation)
    if order is not None:
        return order

    order = CustomerOrderMemory(
        profile=profile,
        customer_profile_id=profile.id,
        conversation=conversation,
        conversation_id=conversation.id,
        status="active",
    )
    db.add(order)
    await db.flush()
    return order


async def apply_extracted_facts(
    db: Any,
    *,
    profile: CustomerProfile,
    order: CustomerOrderMemory,
    message: Message | None,
    facts: list[Any],
) -> FactMergeResult:
    result = FactMergeResult()

    for raw_fact in facts:
        fact_data = _normalize_fact_input(raw_fact, message=message)
        scope = str(fact_data["scope"])
        key = str(fact_data["key"])
        value = fact_data["value"]
        confidence = str(fact_data["confidence"])
        needs_confirmation = bool(fact_data["needs_confirmation"])

        scoped_order = order if scope == "current_order" else None
        existing = await _fetch_accepted_fact(
            db,
            profile=profile,
            order=scoped_order,
            scope=scope,
            key=key,
        )
        status = _merge_status(
            existing=existing,
            value=value,
            confidence=confidence,
            scope=scope,
            needs_confirmation=needs_confirmation,
        )

        saved = CustomerFact(
            profile=profile,
            customer_profile_id=profile.id,
            order_memory=scoped_order,
            order_memory_id=scoped_order.id if scoped_order else None,
            conversation_id=fact_data["conversation_id"] or order.conversation_id,
            scope=scope,
            key=key,
            value=value,
            confidence=confidence,
            status=status,
            source=str(fact_data["source"]),
            source_message_id=fact_data["source_message_id"],
            source_excerpt=fact_data["source_excerpt"],
        )
        db.add(saved)

        if status == "accepted":
            result.accepted.append(saved)
            _apply_profile_projection(profile, saved)
        elif status == "conflict":
            result.conflicts.append(saved)
        else:
            result.proposed.append(saved)

        if scope == "past_order_reference" or needs_confirmation:
            result.confirmation_required.append(saved)

    if facts:
        await db.flush()
    return result


async def mark_order_quoted(
    db: Any,
    *,
    order: CustomerOrderMemory,
    snapshot: dict[str, Any],
) -> CustomerOrderMemory:
    order.status = "quoted_snapshot"
    order.snapshot = snapshot
    order.quoted_at = _now()
    await db.flush()
    return order


async def close_order(
    db: Any,
    *,
    order: CustomerOrderMemory,
    status: str,
    snapshot: dict[str, Any] | None = None,
) -> CustomerOrderMemory:
    if status not in TERMINAL_ORDER_STATUSES:
        raise ValueError(f"Unsupported terminal customer order status: {status}")

    order.status = status
    order.closed_at = _now()
    if snapshot is not None:
        order.snapshot = snapshot
    await db.flush()
    return order


async def build_customer_facts_context(
    db: Any,
    *,
    profile: CustomerProfile,
    active_order: CustomerOrderMemory,
    max_past_orders: int,
) -> CustomerFactsContext:
    profile_facts = await _fetch_context_profile_facts(db, profile=profile)
    order_facts = await _fetch_context_order_facts(db, order=active_order)
    past_orders = await _fetch_past_orders(
        db,
        profile=profile,
        limit=max_past_orders,
    )

    profile_lines = _profile_lines(profile, profile_facts)
    order_lines = _order_lines(active_order, order_facts)
    past_order_lines = [_past_order_line(order) for order in past_orders]
    missing = _missing_quote_fields(profile, profile_facts, order_facts)

    return CustomerFactsContext(
        profile_lines=profile_lines,
        current_order_lines=order_lines,
        past_order_lines=past_order_lines,
        missing_quote_fields=missing,
    )


async def _fetch_profile_by_phone(db: Any, phone: str) -> CustomerProfile | None:
    result = await db.execute(
        select(CustomerProfile).where(CustomerProfile.canonical_phone == phone).limit(1)
    )
    return cast("CustomerProfile | None", result.scalars().first())


async def _fetch_active_order(
    db: Any,
    *,
    profile: CustomerProfile,
    conversation: Conversation,
) -> CustomerOrderMemory | None:
    result = await db.execute(
        select(CustomerOrderMemory)
        .where(CustomerOrderMemory.customer_profile_id == profile.id)
        .where(CustomerOrderMemory.conversation_id == conversation.id)
        .where(CustomerOrderMemory.status.in_(ACTIVE_ORDER_STATUSES))
        .order_by(CustomerOrderMemory.started_at.desc())
        .limit(1)
    )
    return cast("CustomerOrderMemory | None", result.scalars().first())


async def _fetch_accepted_fact(
    db: Any,
    *,
    profile: CustomerProfile,
    order: CustomerOrderMemory | None,
    scope: str,
    key: str,
) -> CustomerFact | None:
    statement = (
        select(CustomerFact)
        .where(CustomerFact.customer_profile_id == profile.id)
        .where(CustomerFact.scope == scope)
        .where(CustomerFact.key == key)
        .where(CustomerFact.status == "accepted")
    )
    if order is None:
        statement = statement.where(CustomerFact.order_memory_id.is_(None))
    else:
        statement = statement.where(CustomerFact.order_memory_id == order.id)

    result = await db.execute(
        statement.order_by(CustomerFact.created_at.desc()).limit(1)
    )
    return cast("CustomerFact | None", result.scalars().first())


async def _fetch_context_profile_facts(
    db: Any,
    *,
    profile: CustomerProfile,
) -> list[CustomerFact]:
    result = await db.execute(
        select(CustomerFact)
        .where(CustomerFact.customer_profile_id == profile.id)
        .where(CustomerFact.scope == "persistent_profile")
        .where(CustomerFact.status == "accepted")
        .where(CustomerFact.order_memory_id.is_(None))
        .order_by(CustomerFact.created_at.desc())
    )
    return list(result.scalars().all())


async def _fetch_context_order_facts(
    db: Any,
    *,
    order: CustomerOrderMemory,
) -> list[CustomerFact]:
    result = await db.execute(
        select(CustomerFact)
        .where(CustomerFact.order_memory_id == order.id)
        .where(CustomerFact.scope == "current_order")
        .where(CustomerFact.status == "accepted")
        .order_by(CustomerFact.created_at.desc())
    )
    return list(result.scalars().all())


async def _fetch_past_orders(
    db: Any,
    *,
    profile: CustomerProfile,
    limit: int,
) -> list[CustomerOrderMemory]:
    result = await db.execute(
        select(CustomerOrderMemory)
        .where(CustomerOrderMemory.customer_profile_id == profile.id)
        .where(CustomerOrderMemory.status.in_(TERMINAL_ORDER_STATUSES))
        .order_by(CustomerOrderMemory.closed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


def _normalize_fact_input(raw_fact: Any, *, message: Message | None) -> dict[str, Any]:
    def get(name: str, default: Any = None) -> Any:
        if isinstance(raw_fact, dict):
            return raw_fact.get(name, default)
        return getattr(raw_fact, name, default)

    source_message_id = get("source_message_id")
    if source_message_id is None and message is not None:
        source_message_id = str(message.id)

    return {
        "scope": get("scope"),
        "key": get("key"),
        "value": get("value"),
        "confidence": get("confidence", "low"),
        "source": get("source", "unknown"),
        "source_message_id": source_message_id,
        "source_excerpt": get("source_excerpt", get("evidence")),
        "conversation_id": get(
            "conversation_id",
            getattr(message, "conversation_id", None) if message is not None else None,
        ),
        "needs_confirmation": get("needs_confirmation", False),
    }


def _merge_status(
    *,
    existing: CustomerFact | None,
    value: FactValue,
    confidence: str,
    scope: str,
    needs_confirmation: bool,
) -> str:
    if scope == "past_order_reference" or needs_confirmation:
        return "proposed"
    if existing is not None and existing.value != value:
        return "conflict"
    if confidence == "high":
        return "accepted"
    if confidence == "medium" and existing is None:
        return "accepted"
    return "proposed"


def _apply_profile_projection(profile: CustomerProfile, fact: CustomerFact) -> None:
    if fact.scope != "persistent_profile":
        return
    if fact.key in {"customer.name", "customer.display_name"} and isinstance(
        fact.value,
        str,
    ):
        profile.display_name = fact.value
    elif fact.key in {"customer.email", "customer.primary_email"} and isinstance(
        fact.value,
        str,
    ):
        profile.primary_email = fact.value
    elif fact.key in {
        "customer.language",
        "customer.preferred_language",
    } and isinstance(
        fact.value,
        str,
    ):
        profile.preferred_language = fact.value


def _profile_lines(
    profile: CustomerProfile,
    facts: list[CustomerFact],
) -> list[str]:
    lines: list[str] = []
    if profile.display_name:
        lines.append(f"- Name: {profile.display_name}")
    if profile.preferred_language:
        lines.append(f"- Preferred language: {profile.preferred_language}")
    if profile.primary_email:
        lines.append(f"- Email: {profile.primary_email}")

    for fact in facts:
        if fact.key == "customer.company":
            lines.append(f"- Known company: {_format_value(fact.value)}")
        elif fact.key not in {
            "customer.name",
            "customer.display_name",
            "customer.email",
            "customer.primary_email",
            "customer.language",
            "customer.preferred_language",
        }:
            lines.append(f"- {_label_from_key(fact.key)}: {_format_value(fact.value)}")
    return lines


def _order_lines(
    order: CustomerOrderMemory,
    facts: list[CustomerFact],
) -> list[str]:
    lines: list[str] = []
    for fact in facts:
        if fact.key == "delivery.address":
            lines.append(f"- Delivery address: {_format_value(fact.value)}")
        elif fact.key == "order.items":
            lines.append(f"- Items: {_format_items(fact.value)}")
        elif fact.key == "assembly.requirements":
            lines.append(f"- Assembly: {_format_value(fact.value)}")
        else:
            lines.append(f"- {_label_from_key(fact.key)}: {_format_value(fact.value)}")
    lines.append(f"- Quote status: {order.status}")
    return lines


def _missing_quote_fields(
    profile: CustomerProfile,
    profile_facts: list[CustomerFact],
    order_facts: list[CustomerFact],
) -> list[str]:
    profile_keys = {fact.key for fact in profile_facts}
    missing: list[str] = []
    if not profile.primary_email and "customer.email" not in profile_keys:
        missing.append("- customer email")
    order_customer_type = _latest_fact_value(order_facts, "customer.type")
    has_customer_type = isinstance(
        order_customer_type, str
    ) and order_customer_type.casefold() in {"individual", "company"}
    profile_company = getattr(profile, "company", None)
    if (
        not profile_company
        and not {"customer.company", "quote.customer_type"} & profile_keys
        and not has_customer_type
    ):
        missing.append("- company name or explicit individual status")
    delivery_address = _latest_fact_value(order_facts, "delivery.address")
    if not _is_specific_delivery_address(delivery_address):
        missing.append("- specific delivery address")
    return missing


def _latest_fact_value(facts: list[CustomerFact], key: str) -> FactValue:
    for fact in facts:
        if fact.key == key:
            return fact.value
    return None


def _is_specific_delivery_address(value: FactValue) -> bool:
    if not isinstance(value, str):
        return False
    normalized = re.sub(r"[\W_]+", " ", value.casefold()).strip()
    if normalized in {
        "uae",
        "u a e",
        "united arab emirates",
        "emirates",
        "dubai",
        "abu dhabi",
        "sharjah",
        "ajman",
    }:
        return False
    tokens = [token for token in normalized.split() if token]
    return len(tokens) >= 2 or bool(re.search(r"\d", value))


def _past_order_line(order: CustomerOrderMemory) -> str:
    snapshot = order.snapshot or {}
    closed_at = order.closed_at or order.started_at
    date = closed_at.date().isoformat() if closed_at is not None else "unknown date"
    return (
        f"- Last closed order: {date}, "
        f"{_format_items(snapshot.get('items'))}, status {order.status}"
    )


def _format_items(value: FactValue) -> str:
    if isinstance(value, list):
        rendered: list[str] = []
        for item in value:
            if isinstance(item, dict):
                quantity = item.get("quantity", "?")
                sku = item.get("sku") or item.get("name") or "item"
                rendered.append(f"{quantity} x {sku}")
            else:
                rendered.append(str(item))
        return ", ".join(rendered)
    return _format_value(value)


def _format_value(value: FactValue) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return ", ".join(f"{key}: {val}" for key, val in value.items())
    return str(value)


def _label_from_key(key: str) -> str:
    return key.replace("_", " ").replace(".", " ").title()


def _now() -> datetime:
    return datetime.now(tz=UTC)
