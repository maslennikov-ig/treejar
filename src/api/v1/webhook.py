from __future__ import annotations

import ipaddress
import json
import logging
import time
import traceback
from functools import lru_cache

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.schemas import WazzupWebhookPayload

# Bind to uvicorn.error so info logs appear in docker logs
logger = logging.getLogger("uvicorn.error")

router = APIRouter()


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

    # Log raw payload for debugging (truncate to 2000 chars)
    logger.info(
        "Wazzup webhook received: %s",
        json.dumps(raw_body, ensure_ascii=False, default=str)[:2000],
    )

    # Wazzup test ping during webhook registration
    if raw_body.get("test"):
        logger.info("Wazzup test ping — responding OK")
        return JSONResponse({"ok": True}, status_code=200)

    # Parse and process messages
    messages = raw_body.get("messages", [])
    if not messages:
        logger.info("Wazzup webhook: no messages (status update or empty payload)")
        return JSONResponse({"ok": True}, status_code=200)

    try:
        payload = WazzupWebhookPayload(**raw_body)
    except Exception as e:
        logger.error("Wazzup payload validation error: %s", e)
        traceback.print_exc()
        # Still return 200 so Wazzup doesn't retry
        return JSONResponse({"ok": True}, status_code=200)

    redis = request.app.state.redis
    arq_pool = request.app.state.arq_pool

    for msg in payload.messages:
        # Filter out status-only updates
        if msg.status and msg.status != "inbound":
            logger.debug("Skipping non-inbound message: status=%s", msg.status)
            continue

        # Accept only the configured Wazzup channel when explicitly set.
        expected_channel = settings.wazzup_channel_id
        if expected_channel and msg.channelId and msg.channelId != expected_channel:
            logger.warning(
                "Skipping message from unexpected Wazzup channel: expected=%s got=%s chatId=%s",
                expected_channel,
                msg.channelId,
                msg.chatId,
            )
            continue

        # Route by authorType
        author_type = msg.authorType or "client"

        if author_type == "bot":
            # Echo of our own bot messages — skip entirely
            logger.debug("Skipping bot echo message: chatId=%s", msg.chatId)
            continue

        if author_type == "manager":
            # Manager message — save but don't trigger LLM
            logger.info(
                "Manager message from %s (chatId=%s): %s",
                msg.authorName or "unknown",
                msg.chatId,
                msg.text[:100] if msg.text else "(no text)",
            )
        else:
            # Client message — standard flow
            logger.info(
                "Client message from chatId=%s: %s",
                msg.chatId,
                msg.text[:100] if msg.text else "(no text)",
            )

        # Push to Redis list
        await redis.rpush(f"wazzup_msgs:{msg.chatId}", msg.model_dump_json())

        # Enqueue job with a 5-second defer to allow batching
        # Use time-windowed job ID: same window = dedup, new window = new job
        window = int(time.time()) // 10  # 10-second windows
        job_id = f"wazzup_batch_{msg.chatId}_{window}"
        await arq_pool.enqueue_job(
            "process_incoming_batch",
            chat_id=msg.chatId,
            _job_id=job_id,
            _defer_by=5,
        )

    return JSONResponse({"ok": True}, status_code=200)
