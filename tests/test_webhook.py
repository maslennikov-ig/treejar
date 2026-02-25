from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

def test_wazzup_webhook_endpoint() -> None:
    # Mock redis and arq_pool
    app.state.redis = AsyncMock()
    app.state.arq_pool = AsyncMock()

    payload = {
        "messages": [
            {
                "messageId": "123",
                "chatId": "79991234567",
                "chatType": "whatsapp",
                "text": "Hello bot!",
                "type": "text",
                "channelId": "ch1",
                "timestamp": 1234567890
            }
        ]
    }

    response = client.post("/api/v1/webhook/wazzup", json=payload)

    assert response.status_code == 200
    assert response.json() == {"ok": True}

    app.state.redis.rpush.assert_called_once()
    app.state.arq_pool.enqueue_job.assert_called_once_with(
        "process_incoming_batch",
        chat_id="79991234567",
        _job_id="wazzup_batch_79991234567",
        _defer_by=5,
    )
