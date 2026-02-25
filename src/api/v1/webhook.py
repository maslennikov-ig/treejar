from __future__ import annotations

from fastapi import APIRouter, Request

from src.schemas import WazzupWebhookPayload, WazzupWebhookResponse

router = APIRouter()


@router.post("/wazzup", response_model=WazzupWebhookResponse)
async def handle_wazzup_webhook(
    payload: WazzupWebhookPayload,
    request: Request,
) -> WazzupWebhookResponse:
    """Receive incoming messages from Wazzup (WhatsApp gateway)."""
    redis = request.app.state.redis
    arq_pool = request.app.state.arq_pool

    for msg in payload.messages:
        # Ignore non-user messages if the webhook echoes our own sends
        # Depending on Wazzup, inbound might have status=None or chatType="whatsapp"
        # We push it to Redis list
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

    return WazzupWebhookResponse(ok=True)

