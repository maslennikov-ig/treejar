from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.config import settings
from src.integrations.messaging.wazzup import WazzupProvider


@pytest.fixture
def wazzup_provider() -> WazzupProvider:
    settings.wazzup_api_key = "fake-key"
    settings.wazzup_api_url = "http://fake-url"
    return WazzupProvider()


@pytest.mark.asyncio
@patch("src.integrations.messaging.wazzup.httpx.AsyncClient.request", new_callable=AsyncMock)
async def test_send_text_success(mock_request: AsyncMock, wazzup_provider: WazzupProvider) -> None:
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_123"}
    mock_resp.raise_for_status.return_value = None
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_text("79998881122", "Hello World")

    assert msg_id == "msg_123"
    mock_request.assert_awaited_once()
    args, kwargs = mock_request.call_args
    assert "/message" in kwargs["url"]

    payload = kwargs["json"]
    assert payload["chatId"] == "79998881122"
    assert payload["chatType"] == "whatsapp"
    assert payload["text"] == "Hello World"


@pytest.mark.asyncio
@patch("src.integrations.messaging.wazzup.httpx.AsyncClient.request", new_callable=AsyncMock)
async def test_send_text_http_error(mock_request: AsyncMock, wazzup_provider: WazzupProvider) -> None:
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.text = '{"error": "bad request"}'

    # We set raise_for_status to raise an exception like httpx does
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Bad Request", request=AsyncMock(), response=mock_resp
    )
    mock_request.return_value = mock_resp

    with pytest.raises(httpx.HTTPStatusError):
        await wazzup_provider.send_text("79998881122", "Fail")


@pytest.mark.asyncio
@patch("src.integrations.messaging.wazzup.httpx.AsyncClient.request", new_callable=AsyncMock)
async def test_send_media_success(mock_request: AsyncMock, wazzup_provider: WazzupProvider) -> None:
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_media"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_media("123", "http://image.jpg", "Look!")

    assert msg_id == "msg_media"

    payload = mock_request.call_args.kwargs["json"]
    assert payload["contentUri"] == "http://image.jpg"
    assert payload["text"] == "Look!"


@pytest.mark.asyncio
@patch("src.integrations.messaging.wazzup.httpx.AsyncClient.request", new_callable=AsyncMock)
async def test_send_template_success(mock_request: AsyncMock, wazzup_provider: WazzupProvider) -> None:
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_tmpl"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_template("123", "tmpl_1", {})
    assert msg_id == "msg_tmpl"
