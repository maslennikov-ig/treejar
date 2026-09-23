"""Resolve the Zoho Inventory customer a quotation is raised against.

Moved out of src.llm.engine for tj-uz6j.9. Two things changed on the way:

* A contact id already resolved for this phone (kept on the conversation and,
  across conversations, in Redis) is reused after one readback, so a returning
  customer costs no search, no create and no duplicate-name fallback.
* A transient Zoho failure (rate limit, gateway error, timeout) propagates
  instead of being folded into "no customer": the caller defers the quotation
  rather than failing it.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

import httpx

from src.integrations.inventory.zoho_inventory import (
    ZohoContactAddressPayload,
    ZohoContactPersonPayload,
    ZohoInventoryClient,
    ZohoInventoryContactPayload,
    contact_lists_only_other_phones,
)
from src.llm.inventory_read import is_transient_inventory_error
from src.models.conversation import Conversation

logger = logging.getLogger(__name__)

KNOWN_INVENTORY_CUSTOMER_KEY = "zoho_inventory_customer"
_PHONE_CUSTOMER_CACHE_PREFIX = "zoho:inventory:customer_by_phone:"
_PHONE_CUSTOMER_CACHE_TTL_SECONDS = 90 * 24 * 3600


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _phone_digits(phone: str) -> str:
    return "".join(ch for ch in phone if ch.isdigit())


def _split_contact_name(name: str) -> tuple[str, str]:
    parts = [part for part in name.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _external_inventory_phone(phone: str) -> str:
    phone_value = _string_value(phone)
    base_phone, _, suffix = phone_value.partition("#")
    if suffix and base_phone:
        return base_phone
    return phone_value


def _inventory_contact_id(contact: Mapping[str, Any] | None) -> str | None:
    if not isinstance(contact, Mapping):
        return None

    contact_id = contact.get("contact_id")
    if contact_id is None:
        return None

    contact_id_str = str(contact_id).strip()
    return contact_id_str or None


def _is_duplicate_inventory_contact_error(exc: Exception) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    if exc.response.status_code != 400:
        return False

    try:
        payload = exc.response.json()
    except ValueError:
        payload = None

    if isinstance(payload, Mapping):
        code = payload.get("code")
        message = str(payload.get("message") or "").casefold()
        if code == 3062 or "already exists" in message:
            return True

    return "already exists" in exc.response.text.casefold()


def _build_inventory_contact_payload(
    *,
    phone: str,
    customer_name: str,
    customer_email: str,
    customer_company: str,
    customer_address: str = "",
) -> ZohoInventoryContactPayload:
    fallback_suffix = "".join(ch for ch in phone if ch.isdigit())[-4:] or "customer"
    contact_name = (
        customer_company or customer_name or f"WhatsApp Customer {fallback_suffix}"
    )
    contact_person_name = customer_name or contact_name
    first_name, last_name = _split_contact_name(contact_person_name)
    if not first_name:
        first_name = contact_name

    contact_person: ZohoContactPersonPayload = {
        "first_name": first_name,
        "phone": phone,
        "mobile": phone,
        "is_primary_contact": True,
    }
    if last_name:
        contact_person["last_name"] = last_name
    if customer_email:
        contact_person["email"] = customer_email

    payload: ZohoInventoryContactPayload = {
        "contact_name": contact_name,
        "contact_type": "customer",
        "contact_persons": [contact_person],
    }
    if customer_company:
        payload["company_name"] = customer_company
    if customer_address:
        address: ZohoContactAddressPayload = {"address": customer_address[:500]}
        payload["billing_address"] = address
        payload["shipping_address"] = {"address": address["address"]}

    return payload


def _inventory_contact_matches_payload(
    contact: Mapping[str, Any] | None,
    payload: ZohoInventoryContactPayload,
    *,
    expected_status: str = "active",
) -> bool:
    if not isinstance(contact, Mapping):
        return False

    def normalized(value: Any) -> str:
        return " ".join(str(value or "").split()).casefold()

    if normalized(contact.get("status")) != normalized(expected_status):
        return False
    if normalized(contact.get("contact_type")) not in {"", "customer"}:
        return False
    for key in ("contact_name", "company_name"):
        expected = normalized(payload.get(key))
        if expected and normalized(contact.get(key)) != expected:
            return False

    expected_people = payload.get("contact_persons") or []
    expected_person: Mapping[str, Any] = (
        cast("Mapping[str, Any]", expected_people[0]) if expected_people else {}
    )
    people = contact.get("contact_persons")
    if not isinstance(people, list):
        return False
    expected_email = normalized(expected_person.get("email"))
    expected_phone = "".join(
        ch for ch in str(expected_person.get("phone") or "") if ch.isdigit()
    )
    if expected_email and not any(
        isinstance(person, Mapping)
        and normalized(person.get("email")) == expected_email
        for person in people
    ):
        return False
    if expected_phone and not any(
        isinstance(person, Mapping)
        and expected_phone
        in {
            "".join(ch for ch in str(person.get(key) or "") if ch.isdigit())
            for key in ("phone", "mobile")
        }
        for person in people
    ):
        return False

    for key in ("billing_address", "shipping_address"):
        expected_address = payload.get(key)
        if not isinstance(expected_address, Mapping):
            continue
        actual_address = contact.get(key)
        if not isinstance(actual_address, Mapping) or normalized(
            actual_address.get("address")
        ) != normalized(expected_address.get("address")):
            return False

    return True


def _raise_if_transient(exc: Exception) -> None:
    if is_transient_inventory_error(exc):
        raise exc


def _known_customer_id_from_conversation(
    conversation: Conversation | None, phone_digits: str
) -> str | None:
    metadata = getattr(conversation, "metadata_", None)
    if not isinstance(metadata, Mapping):
        return None
    known = metadata.get(KNOWN_INVENTORY_CUSTOMER_KEY)
    if not isinstance(known, Mapping):
        return None
    if _string_value(known.get("phone_digits")) != phone_digits:
        return None
    return _string_value(known.get("contact_id")) or None


async def _known_customer_id_from_redis(redis: Any, phone_digits: str) -> str | None:
    if redis is None or not phone_digits:
        return None
    try:
        raw = await redis.get(f"{_PHONE_CUSTOMER_CACHE_PREFIX}{phone_digits}")
    except Exception:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    return _string_value(raw) or None


async def remember_inventory_customer_id(
    *,
    contact_id: str,
    phone: str,
    conversation: Conversation | None,
    redis: Any,
) -> None:
    """Keep the resolved contact id on the conversation and per phone in Redis."""
    phone_digits = _phone_digits(_external_inventory_phone(phone))
    if not contact_id or not phone_digits:
        return
    if conversation is not None:
        metadata = dict(conversation.metadata_ or {})
        metadata[KNOWN_INVENTORY_CUSTOMER_KEY] = {
            "contact_id": contact_id,
            "phone_digits": phone_digits,
        }
        conversation.metadata_ = metadata
    if redis is None:
        return
    try:
        await redis.set(
            f"{_PHONE_CUSTOMER_CACHE_PREFIX}{phone_digits}",
            contact_id,
            ex=_PHONE_CUSTOMER_CACHE_TTL_SECONDS,
        )
    except Exception:
        logger.warning("Could not cache the Zoho Inventory customer id in Redis")


async def _verified_known_customer_id(
    zoho_inventory: ZohoInventoryClient,
    *,
    candidates: list[str],
    inventory_phone: str,
) -> str | None:
    """One readback per remembered id; a transient failure propagates."""
    for contact_id in dict.fromkeys(candidates):
        try:
            contact = await zoho_inventory.get_contact(contact_id)
        except Exception as exc:
            _raise_if_transient(exc)
            logger.warning(
                "Remembered Zoho Inventory customer %s unreadable", contact_id
            )
            continue
        if not isinstance(contact, Mapping):
            continue
        status = _string_value(contact.get("status")).casefold()
        contact_type = _string_value(contact.get("contact_type")).casefold()
        if status not in {"", "active"} or contact_type not in {"", "customer"}:
            continue
        if _inventory_contact_id(contact) != contact_id:
            continue
        # A contact that lists phones must list this one; a manager may have
        # repointed or merged it since it was remembered.
        if contact_lists_only_other_phones(contact, inventory_phone):
            continue
        return contact_id
    return None


async def resolve_inventory_customer_id(
    *,
    phone: str,
    customer_name: str,
    customer_email: str,
    customer_company: str,
    customer_address: str = "",
    zoho_inventory: ZohoInventoryClient,
    conversation: Conversation | None = None,
    redis: Any = None,
) -> str | None:
    """Resolve or create a valid Zoho Inventory customer contact for quotations.

    Returns None when no safe customer can be established. Raises when Zoho is
    only temporarily unavailable (see ``is_transient_inventory_error``).
    """
    inventory_phone = _external_inventory_phone(phone)
    phone_digits = _phone_digits(inventory_phone)

    remembered = [
        contact_id
        for contact_id in (
            _known_customer_id_from_conversation(conversation, phone_digits),
            await _known_customer_id_from_redis(redis, phone_digits),
        )
        if contact_id
    ]
    if remembered:
        known_id = await _verified_known_customer_id(
            zoho_inventory, candidates=remembered, inventory_phone=inventory_phone
        )
        if known_id:
            await remember_inventory_customer_id(
                contact_id=known_id,
                phone=inventory_phone,
                conversation=conversation,
                redis=redis,
            )
            return known_id

    contact_id = await _lookup_or_create_inventory_customer(
        inventory_phone=inventory_phone,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_company=customer_company,
        customer_address=customer_address,
        zoho_inventory=zoho_inventory,
    )
    if contact_id:
        await remember_inventory_customer_id(
            contact_id=contact_id,
            phone=inventory_phone,
            conversation=conversation,
            redis=redis,
        )
    return contact_id


async def _lookup_or_create_inventory_customer(
    *,
    inventory_phone: str,
    customer_name: str,
    customer_email: str,
    customer_company: str,
    customer_address: str,
    zoho_inventory: ZohoInventoryClient,
) -> str | None:
    try:
        existing_contact = await zoho_inventory.find_customer_by_phone(inventory_phone)
    except Exception as exc:
        _raise_if_transient(exc)
        logger.exception(
            "Failed to search Zoho Inventory customer by phone for %s",
            inventory_phone,
        )
        return None

    existing_contact_id = _inventory_contact_id(existing_contact)
    if existing_contact_id:
        return existing_contact_id

    if customer_email:
        try:
            existing_by_email = await zoho_inventory.find_customer_by_email(
                customer_email
            )
        except Exception as exc:
            _raise_if_transient(exc)
            logger.exception(
                "Failed to search Zoho Inventory customer by email for %s",
                customer_email,
            )
            return None

        existing_by_email_id = _inventory_contact_id(existing_by_email)
        if existing_by_email_id:
            return existing_by_email_id

    payload = _build_inventory_contact_payload(
        phone=inventory_phone,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_company=customer_company,
        customer_address=customer_address,
    )

    try:
        created_contact = await zoho_inventory.create_contact(dict(payload))
    except Exception as exc:
        _raise_if_transient(exc)
        if _is_duplicate_inventory_contact_error(exc):
            exact_duplicate: Mapping[str, Any] | None = None
            try:
                if customer_email:
                    exact_duplicate = (
                        await zoho_inventory.find_inactive_customer_by_email(
                            customer_email
                        )
                    )
                elif inventory_phone:
                    exact_duplicate = (
                        await zoho_inventory.find_inactive_customer_by_phone(
                            inventory_phone
                        )
                    )
            except Exception as lookup_exc:
                _raise_if_transient(lookup_exc)
                logger.exception("Failed exact duplicate lookup in Zoho Inventory")
                return None

            exact_duplicate_id = _inventory_contact_id(exact_duplicate)
            exact_duplicate_status = _string_value(
                (exact_duplicate or {}).get("status")
            ).casefold()
            if exact_duplicate_id and exact_duplicate_status in {"active", "inactive"}:
                if not _inventory_contact_matches_payload(
                    exact_duplicate,
                    payload,
                    expected_status=exact_duplicate_status,
                ):
                    return None
                if exact_duplicate_status == "active":
                    return exact_duplicate_id
                try:
                    await zoho_inventory.activate_contact(exact_duplicate_id)
                    reactivated = await zoho_inventory.get_contact(exact_duplicate_id)
                except Exception as reactivate_exc:
                    _raise_if_transient(reactivate_exc)
                    logger.exception(
                        "Failed to reactivate exact Zoho Inventory duplicate"
                    )
                    return None
                if _inventory_contact_id(
                    reactivated
                ) == exact_duplicate_id and _inventory_contact_matches_payload(
                    reactivated, payload
                ):
                    return exact_duplicate_id
                return None

            seen_names: set[str] = set()
            for candidate_name in (
                _string_value(payload.get("contact_name")),
                customer_company,
                customer_name,
            ):
                normalized_candidate = _string_value(candidate_name)
                if not normalized_candidate:
                    continue
                key = normalized_candidate.casefold()
                if key in seen_names:
                    continue
                seen_names.add(key)
                try:
                    existing_by_name = await zoho_inventory.find_customer_by_name(
                        normalized_candidate
                    )
                except Exception as name_exc:
                    # A rate limit here must stop the scan: every further name
                    # is another full page walk against the same quota.
                    _raise_if_transient(name_exc)
                    logger.exception(
                        "Failed duplicate-name fallback search in Zoho Inventory for %s",
                        normalized_candidate,
                    )
                    continue

                existing_by_name_id = _inventory_contact_id(existing_by_name)
                if existing_by_name_id:
                    return existing_by_name_id

        logger.exception(
            "Failed to create Zoho Inventory customer for phone %s",
            inventory_phone,
        )
        return None

    contact_id = _inventory_contact_id(created_contact)
    if contact_id is None:
        logger.error(
            "Zoho Inventory create_contact returned no contact_id for phone %s: %s",
            inventory_phone,
            created_contact,
        )
    return contact_id
