from __future__ import annotations

import json
import logging
import traceback

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.schemas import WazzupWebhookPayload

logger = logging.getLogger(__name__)

router = APIRouter()


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
    try:
        raw_body = await request.json()
    except Exception:
        print("[WEBHOOK] Failed to parse JSON body")
        return JSONResponse({"ok": True}, status_code=200)

    # Always log the raw payload to stdout for debugging
    print(f"[WEBHOOK] Received: {json.dumps(raw_body, ensure_ascii=False, default=str)[:2000]}")

    # Wazzup test ping during webhook registration
    if raw_body.get("test"):
        print("[WEBHOOK] Test ping — responding OK")
        return JSONResponse({"ok": True}, status_code=200)

    # Parse and process messages
    messages = raw_body.get("messages", [])
    if not messages:
        print("[WEBHOOK] No messages in payload (status update or empty)")
        return JSONResponse({"ok": True}, status_code=200)

    try:
        payload = WazzupWebhookPayload(**raw_body)
    except Exception as e:
        print(f"[WEBHOOK] Payload validation error: {e}")
        traceback.print_exc()
        # Still return 200 so Wazzup doesn't retry
        return JSONResponse({"ok": True}, status_code=200)

    redis = request.app.state.redis
    arq_pool = request.app.state.arq_pool

    for msg in payload.messages:
        # Filter out status-only updates
        if msg.status and msg.status != "inbound":
            print(f"[WEBHOOK] Skipping non-inbound message: status={msg.status}")
            continue

        # Route by authorType
        author_type = msg.authorType or "client"

        if author_type == "bot":
            # Echo of our own bot messages — skip entirely
            print(f"[WEBHOOK] Skipping bot echo message: chatId={msg.chatId}")
            continue

        if author_type == "manager":
            # Manager message — save but don't trigger LLM
            print(
                f"[WEBHOOK] Manager message from {msg.authorName or 'unknown'}"
                f" (chatId={msg.chatId}): {msg.text[:100] if msg.text else '(no text)'}"
            )
        else:
            # Client message — standard flow
            print(
                f"[WEBHOOK] Client message from chatId={msg.chatId}:"
                f" {msg.text[:100] if msg.text else '(no text)'}"
            )

        # Push to Redis list
        await redis.rpush(f"wazzup_msgs:{msg.chatId}", msg.model_dump_json())

        # Enqueue job with a 5-second defer to allow batching
        # ARQ unique job ID prevents duplicate schedules
        job_id = f"wazzup_batch_{msg.chatId}"
        await arq_pool.enqueue_job(
            "process_incoming_batch",
            chat_id=msg.chatId,
            _job_id=job_id,
            _defer_by=5,
        )

    return JSONResponse({"ok": True}, status_code=200)
