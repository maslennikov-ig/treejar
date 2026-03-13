from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.schemas import WazzupWebhookPayload, WazzupWebhookResponse

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
        logger.warning("Wazzup webhook: failed to parse JSON body")
        return JSONResponse({"ok": True}, status_code=200)

    logger.info("Wazzup webhook received: %s", raw_body)

    # Wazzup test ping during webhook registration
    if raw_body.get("test"):
        logger.info("Wazzup test ping — responding OK")
        return JSONResponse({"ok": True}, status_code=200)

    # Parse and process messages
    messages = raw_body.get("messages", [])
    if not messages:
        # Could be a status-only update — acknowledge it
        logger.info("Wazzup webhook: no messages (status update or empty payload)")
        return JSONResponse({"ok": True}, status_code=200)

    redis = request.app.state.redis
    arq_pool = request.app.state.arq_pool

    payload = WazzupWebhookPayload(**raw_body)

    for msg in payload.messages:
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
