from __future__ import annotations

from fastapi import APIRouter

from src.schemas import ClientSelfTestSubmitRequest, ClientSelfTestSubmitResponse
from src.services.client_self_test import format_client_self_test_summary
from src.services.notifications import send_telegram_message

router = APIRouter()


@router.post("/submit", response_model=ClientSelfTestSubmitResponse)
async def submit_client_self_test(
    body: ClientSelfTestSubmitRequest,
) -> ClientSelfTestSubmitResponse:
    """Receive the public client acceptance checklist and forward it to Telegram."""
    await send_telegram_message(format_client_self_test_summary(body))
    return ClientSelfTestSubmitResponse(ok=True, submitted_count=len(body.items))
