from __future__ import annotations

import ipaddress
import logging
import secrets
import time
from datetime import UTC, datetime
from functools import lru_cache

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from src.core.config import settings
from src.core.database import async_session_factory
from src.schemas import WazzupWebhookPayload
from src.services.inbound_batch import inbound_chat_reference, inbound_queue_key
from src.services.outbound_audit import update_wazzup_statuses
from src.services.proposal_followup import apply_proposal_read_statuses

# Bind to uvicorn.error so info logs appear in docker logs
logger = logging.getLogger("uvicorn.error")

router = APIRouter()
_OUTBOUND_MESSAGE_STATUSES = frozenset({"sent", "delivered", "read", "error", "edited"})


def _wazzup_webhook_auth_result(request: Request) -> str:
    authorization = request.headers.get("Authorization")
    if not authorization:
        return "missing"

    scheme, separator, provided_secret = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not provided_secret
        or any(character.isspace() for character in provided_secret)
    ):
        return "mismatch"

    expected_secret = settings.wazzup_webhook_secret
    if secrets.compare_digest(
        provided_secret.encode("utf-8"),
        expected_secret.encode("utf-8"),
    ):
        return "match"
    return "mismatch"


def _verify_wazzup_webhook_auth(request: Request) -> bool:
    mode = settings.wazzup_webhook_auth_mode
    if mode == "disabled":
        return True

    result = _wazzup_webhook_auth_result(request)
    if result == "match":
        logger.info("Wazzup webhook auth: match")
    else:
        logger.warning("Wazzup webhook auth: %s", result)

    return mode == "observe" or result == "match"


@lru_cache(maxsize=1)
def _parse_allowed_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """Parse WAZZUP_ALLOWED_IPS into a list of IP networks (cached)."""
    raw = settings.wazzup_allowed_ips.strip()
    if not raw:
        return []
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for cidr in raw.split(","):
        cidr = cidr.strip()
        if cidr:
            networks.append(ipaddress.ip_network(cidr, strict=False))
    return networks


def _verify_webhook_origin(request: Request) -> bool:
    """Verify that webhook request comes from Wazzup IP ranges.

    Wazzup v3 sends webhooks from known IP ranges.  We check the
    client IP against the configured WAZZUP_ALLOWED_IPS (comma-separated
    CIDRs).  If not configured, all requests are accepted (dev mode).
    """
    networks = _parse_allowed_networks()
    if not networks:
        # No allowlist configured — accept all (dev / initial setup)
        return True

    client_host = request.client.host if request.client else None
    if not client_host:
        return False

    try:
        client_ip = ipaddress.ip_address(client_host)
    except ValueError:
        return False

    return any(client_ip in network for network in networks)


def _is_outbound_status_message(message: object) -> bool:
    if not isinstance(message, dict):
        return False
    status = message.get("status")
    return isinstance(status, str) and status in _OUTBOUND_MESSAGE_STATUSES


def _status_updates_from_messages(messages: object) -> list[dict[str, object]]:
    if not isinstance(messages, list):
        return []

    updates: list[dict[str, object]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = message.get("messageId")
        status = message.get("status")
        if (
            not isinstance(message_id, str)
            or not message_id
            or not _is_outbound_status_message(message)
        ):
            continue
        update: dict[str, object] = {
            "messageId": message_id,
            "status": status,
        }
        timestamp = message.get("dateTime") or message.get("timestamp")
        if timestamp is not None:
            update["timestamp"] = timestamp
        error = message.get("error")
        if isinstance(error, dict):
            update["error"] = error
        updates.append(update)
    return updates


def _deduplicate_status_updates(
    statuses: list[object],
) -> list[dict[str, object]]:
    unique: list[dict[str, object]] = []
    seen: set[tuple[object, object, object]] = set()
    for status in statuses:
        if not isinstance(status, dict):
            continue
        message_id = status.get("messageId")
        status_value = status.get("status")
        if (
            not isinstance(message_id, str)
            or not message_id
            or not isinstance(status_value, str)
            or status_value not in _OUTBOUND_MESSAGE_STATUSES
        ):
            continue
        timestamp = status.get("timestamp")
        normalized = dict(status)
        if timestamp is not None:
            if isinstance(timestamp, bool):
                continue
            if isinstance(timestamp, (int, float)):
                try:
                    timestamp = datetime.fromtimestamp(timestamp, UTC).isoformat()
                except (OSError, OverflowError, ValueError):
                    continue
                normalized["timestamp"] = timestamp
            elif isinstance(timestamp, str) and timestamp.strip():
                try:
                    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
            else:
                continue
        identity = (
            message_id,
            status_value,
            timestamp,
        )
        try:
            is_duplicate = identity in seen
        except TypeError:
            continue
        if is_duplicate:
            continue
        seen.add(identity)
        unique.append(normalized)
    return unique


@router.post("/wazzup")
async def handle_wazzup_webhook(request: Request) -> JSONResponse:
    """Receive incoming messages from Wazzup (WhatsApp gateway).

    Accepts raw JSON body to handle all Wazzup webhook formats:
    - Test ping: {"test": true}
    - Messages: {"messages": [...]}
    - Statuses: {"statuses": [...]}
    - Mixed: {"messages": [...], "statuses": [...]}

    Author routing (Wazzup v3):
    - authorType='client' (or absent) → save as role='user', trigger LLM
    - authorType='manager' (isEcho=true) → save as role='manager', no LLM
    - authorType='bot' → skip (echo of our own bot messages)
    """
    if not _verify_wazzup_webhook_auth(request):
        return JSONResponse(
            {"error": "unauthorized"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # CR-WA-08: Verify webhook origin (IP allowlist)
    if not _verify_webhook_origin(request):
        logger.warning(
            "Wazzup webhook: blocked request from non-allowed IP %s",
            request.client.host if request.client else "unknown",
        )
        return JSONResponse({"error": "forbidden"}, status_code=403)

    try:
        raw_body = await request.json()
    except Exception:
        logger.warning("Wazzup webhook: failed to parse JSON body")
        return JSONResponse({"ok": True}, status_code=200)

    logger.info(
        "Wazzup webhook received: messages=%d statuses=%d test=%s",
        len(raw_body.get("messages", []))
        if isinstance(raw_body.get("messages"), list)
        else 0,
        len(raw_body.get("statuses", []))
        if isinstance(raw_body.get("statuses"), list)
        else 0,
        bool(raw_body.get("test")),
    )

    # Wazzup test ping during webhook registration
    if raw_body.get("test"):
        logger.info("Wazzup test ping — responding OK")
        return JSONResponse({"ok": True}, status_code=200)

    raw_statuses = raw_body.get("statuses", [])
    status_candidates: list[object] = (
        list(raw_statuses) if isinstance(raw_statuses, list) else []
    )
    status_candidates.extend(_status_updates_from_messages(raw_body.get("messages")))
    statuses = _deduplicate_status_updates(status_candidates)
    if statuses:
        try:
            async with async_session_factory() as db:
                updated_rows = await update_wazzup_statuses(db, statuses)
                proposal_read_updates = await apply_proposal_read_statuses(
                    db,
                    statuses,
                )
                await db.commit()
            logger.info(
                "Wazzup webhook: updated %d outbound status rows and %d proposal read states",
                updated_rows,
                proposal_read_updates,
            )
        except Exception:
            logger.exception("Wazzup webhook: failed to persist status updates")

    # Parse and process messages
    raw_messages = raw_body.get("messages", [])
    messages = (
        [
            message
            for message in raw_messages
            if not _is_outbound_status_message(message)
        ]
        if isinstance(raw_messages, list)
        else []
    )
    if not messages:
        logger.info("Wazzup webhook: no messages (status update or empty payload)")
        return JSONResponse({"ok": True}, status_code=200)

    try:
        payload = WazzupWebhookPayload(**{**raw_body, "messages": messages})
    except ValidationError as exc:
        logger.error(
            "Wazzup payload validation failed: validation_errors=%d",
            exc.error_count(),
        )
        # Still return 200 so Wazzup doesn't retry
        return JSONResponse({"ok": True}, status_code=200)
    except Exception as exc:
        logger.error(
            "Wazzup payload validation failed: error_type=%s",
            type(exc).__name__,
        )
        # Still return 200 so Wazzup doesn't retry
        return JSONResponse({"ok": True}, status_code=200)

    redis = request.app.state.redis
    arq_pool = request.app.state.arq_pool

    for msg in payload.messages:
        # Filter out status-only updates
        if msg.status and msg.status != "inbound":
            logger.debug("Skipping non-inbound message: status=%s", msg.status)
            continue

        expected_channel = settings.wazzup_channel_id
        if not expected_channel:
            logger.error(
                "Skipping incoming Wazzup message because WAZZUP_CHANNEL_ID is not configured"
            )
            continue

        if msg.channelId != expected_channel:
            # tj-ppid. This used to log only `channel_present=true`, which says
            # a message was refused and nothing about why. On 2026-08-07 five
            # inbound messages had been refused since the 2026-08-06 deploy and
            # there was no way to tell from the logs whether the account had
            # grown a second channel or the configured one had gone stale.
            # Both ids are Wazzup channel identifiers, not customer data.
            logger.warning(
                "Skipping message from unexpected Wazzup channel: got=%s expected=%s",
                msg.channelId or "<absent>",
                expected_channel,
            )
            continue

        # Route by authorType
        author_type = msg.authorType or "client"

        if author_type == "bot":
            # Echo of our own bot messages — skip entirely
            logger.debug("Skipping bot echo message")
            continue

        if author_type == "manager":
            # Manager message — save but don't trigger LLM
            logger.info("Accepted manager message: message_type=%s", msg.type)
        else:
            # Client message — standard flow
            logger.info("Accepted client message: message_type=%s", msg.type)

        # Push to Redis list
        batch_ref = inbound_chat_reference(msg.chatId)
        await redis.rpush(inbound_queue_key(batch_ref), msg.model_dump_json())

        # Enqueue job with a 5-second defer to allow batching
        # Use time-windowed job ID: same window = dedup, new window = new job
        window = int(time.time()) // 10  # 10-second windows
        job_id = f"wazzup_batch_{batch_ref}_{window}"
        await arq_pool.enqueue_job(
            "process_incoming_batch",
            batch_ref=batch_ref,
            _job_id=job_id,
            _defer_by=5,
        )

    return JSONResponse({"ok": True}, status_code=200)
