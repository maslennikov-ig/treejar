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
        # Filter out echo/operator messages — only process client inbound
        if msg.status and msg.status != "inbound":
            print(f"[WEBHOOK] Skipping non-inbound message: status={msg.status}")
            continue
        if msg.authorType and msg.authorType != "client":
            print(f"[WEBHOOK] Skipping non-client message: authorType={msg.authorType}")
            continue

        print(f"[WEBHOOK] Processing message from chatId={msg.chatId}: {msg.text[:100] if msg.text else '(no text)'}")

        # Push to Redis list
        await redis.rpush(f"wazzup_msgs:{msg.chatId}", msg.model_dump_json())

        # Enqueue job with a 5-second defer to allow batching
        # Use time-windowed job ID: same window = dedup, new window = new job
        import time
        window = int(time.time()) // 10  # 10-second windows
        job_id = f"wazzup_batch_{msg.chatId}_{window}"
        await arq_pool.enqueue_job(
            "process_incoming_batch",
            chat_id=msg.chatId,
            _job_id=job_id,
            _defer_by=5,
        )

    return JSONResponse({"ok": True}, status_code=200)
