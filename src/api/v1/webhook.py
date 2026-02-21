from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.schemas import WazzupWebhookPayload, WazzupWebhookResponse

router = APIRouter()


@router.post("/wazzup", response_model=WazzupWebhookResponse)
async def handle_wazzup_webhook(
    payload: WazzupWebhookPayload,
) -> WazzupWebhookResponse:
    """Receive incoming messages from Wazzup (WhatsApp gateway).

    TODO: Add Depends(verify_wazzup_webhook) when webhook secret is configured.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
