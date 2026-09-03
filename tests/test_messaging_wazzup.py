from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.core.config import settings
from src.integrations.messaging.wazzup import (
    WazzupProvider,
    _resolve_tmpfiles_download_url,
)


@pytest.fixture(autouse=True)
def authorized_transport_unit_fixture():
    """Payload/retry unit tests isolate permission from their HTTP doubles.

    Real audited scope + transport enforcement lives in test_wazzup_outbound_safety.
    """
    with patch(
        "src.integrations.messaging.wazzup.require_wazzup_send", new_callable=AsyncMock
    ):
        yield


@pytest.fixture
def wazzup_provider() -> WazzupProvider:
    settings.wazzup_api_key = "fake-key"
    settings.wazzup_api_url = "http://fake-url"
    return WazzupProvider()


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_text_success(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
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
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_text_strips_smoke_profile_suffix_from_chat_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_123"}
    mock_resp.raise_for_status.return_value = None
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_text(
        "+15550001111#smoke-tool-final-20260411T1552",
        "Hello World",
    )

    assert msg_id == "msg_123"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["chatId"] == "+15550001111"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_text_includes_optional_crm_message_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"messageId": "msg_123"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_text(
        "79998881122",
        "Hello World",
        crm_message_id="bot:conv-1:msg-1",
    )

    assert msg_id == "msg_123"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["crmMessageId"] == "bot:conv-1:msg-1"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_text_http_error(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
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
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_media_success(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    """send_media with URL sends contentUri, caption as separate text message."""
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_media"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_media("123", "http://image.jpg", "Look!")

    assert msg_id == "msg_media"

    # First call: file (contentUri only, no text)
    first_call_payload = mock_request.call_args_list[0].kwargs["json"]
    assert first_call_payload["contentUri"] == "http://image.jpg"
    assert "text" not in first_call_payload

    # Second call: caption text
    second_call_payload = mock_request.call_args_list[1].kwargs["json"]
    assert second_call_payload["text"] == "Look!"
    assert "contentUri" not in second_call_payload


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_media_detailed_returns_media_and_caption_ids_with_crm_ids(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    media_resp = MagicMock()
    media_resp.status_code = 200
    media_resp.raise_for_status.return_value = None
    media_resp.json.return_value = {"messageId": "msg_media"}
    caption_resp = MagicMock()
    caption_resp.status_code = 200
    caption_resp.raise_for_status.return_value = None
    caption_resp.json.return_value = {"messageId": "msg_caption"}
    mock_request.side_effect = [media_resp, caption_resp]

    result = await wazzup_provider.send_media_detailed(
        chat_id="123",
        url="http://image.jpg",
        caption="Look!",
        crm_message_id="product:conv-1:media",
        caption_crm_message_id="product:conv-1:caption",
    )

    assert result.message_id == "msg_media"
    assert result.caption_message_id == "msg_caption"
    assert result.content_uri == "http://image.jpg"
    assert result.outbound_chat_id == "123"

    first_call_payload = mock_request.call_args_list[0].kwargs["json"]
    assert first_call_payload["crmMessageId"] == "product:conv-1:media"
    assert "text" not in first_call_payload

    second_call_payload = mock_request.call_args_list[1].kwargs["json"]
    assert second_call_payload["crmMessageId"] == "product:conv-1:caption"
    assert second_call_payload["text"] == "Look!"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_media_url_only(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    """send_media with URL and no caption sends a single message."""
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_url"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_media("123", url="http://image.jpg")

    assert msg_id == "msg_url"
    mock_request.assert_awaited_once()  # Only one call, no caption


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_media_strips_smoke_profile_suffix_from_chat_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"messageId": "msg_url"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_media(
        "+15550001111#smoke-tool-final-20260411T1552",
        url="http://image.jpg",
        caption="Look!",
    )

    assert msg_id == "msg_url"
    first_payload = mock_request.call_args_list[0].kwargs["json"]
    second_payload = mock_request.call_args_list[1].kwargs["json"]
    assert first_payload["chatId"] == "+15550001111"
    assert second_payload["chatId"] == "+15550001111"


@pytest.mark.asyncio
@patch("src.integrations.messaging.wazzup.WazzupProvider._upload_to_tmpfiles")
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_media_with_bytes_uploads_to_tmpfiles(
    mock_request: AsyncMock,
    mock_upload: AsyncMock,
    wazzup_provider: WazzupProvider,
) -> None:
    """send_media with content=bytes uploads to tmpfiles and sends contentUri."""
    from unittest.mock import MagicMock

    mock_upload.return_value = "https://tmpfiles.org/dl/12345/file.pdf"

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {"messageId": "msg_pdf"}
    mock_request.return_value = mock_resp

    pdf_bytes = b"%PDF-1.4 fake pdf content"
    msg_id = await wazzup_provider.send_media(
        chat_id="79998881122",
        content=pdf_bytes,
        content_type="application/pdf",
        caption="Your quotation",
    )

    assert msg_id == "msg_pdf"
    mock_upload.assert_awaited_once_with(pdf_bytes, "application/pdf")

    # First call: file
    file_payload = mock_request.call_args_list[0].kwargs["json"]
    assert file_payload["contentUri"] == "https://tmpfiles.org/dl/12345/file.pdf"
    assert "text" not in file_payload

    # Second call: caption
    caption_payload = mock_request.call_args_list[1].kwargs["json"]
    assert caption_payload["text"] == "Your quotation"


@pytest.mark.asyncio
async def test_send_media_no_url_no_content_raises(
    wazzup_provider: WazzupProvider,
) -> None:
    """send_media without url or content raises ValueError."""
    with pytest.raises(ValueError, match="requires either url or content"):
        await wazzup_provider.send_media("123")


@pytest.mark.asyncio
async def test_tmpfiles_upload_resolves_and_verifies_direct_binary_url() -> None:
    content = b"%PDF-1.7 exact quotation"

    class FakeClient:
        def __init__(self) -> None:
            self.responses = [
                httpx.Response(
                    200,
                    text='<a href="/dl/123/file.pdf">Download</a>',
                    request=httpx.Request("GET", "https://tmpfiles.org/123/file.pdf"),
                ),
                httpx.Response(
                    200,
                    text='<a href="/download/123/file.pdf">Download file</a>',
                    request=httpx.Request(
                        "GET", "https://tmpfiles.org/dl/123/file.pdf"
                    ),
                ),
                httpx.Response(
                    200,
                    content=content,
                    headers={"content-type": "application/pdf"},
                    request=httpx.Request(
                        "GET", "https://tmpfiles.org/download/123/file.pdf"
                    ),
                ),
            ]

        async def get(self, url: str) -> httpx.Response:
            response = self.responses.pop(0)
            assert str(response.request.url) == url
            return response

    resolved = await _resolve_tmpfiles_download_url(
        FakeClient(),
        "https://tmpfiles.org/123/file.pdf",
        content,
    )

    assert resolved == "https://tmpfiles.org/download/123/file.pdf"


@pytest.mark.asyncio
async def test_tmpfiles_upload_keeps_client_open_through_download_resolution() -> None:
    content = b"%PDF-1.7 quotation"

    class FakeClient:
        def __init__(self, **_: object) -> None:
            self.closed = False
            self.downloads = [
                httpx.Response(
                    200,
                    text='<a href="/download/123/file.pdf">Download</a>',
                    request=httpx.Request("GET", "https://tmpfiles.org/123/file.pdf"),
                ),
                httpx.Response(
                    200,
                    content=content,
                    request=httpx.Request(
                        "GET", "https://tmpfiles.org/download/123/file.pdf"
                    ),
                ),
            ]

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *_: object) -> None:
            self.closed = True

        async def post(self, *_: object, **__: object) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {"url": "https://tmpfiles.org/123/file.pdf"},
                },
                request=httpx.Request("POST", "https://tmpfiles.org/api/v1/upload"),
            )

        async def get(self, _: str) -> httpx.Response:
            if self.closed:
                raise RuntimeError("fake client closed")
            return self.downloads.pop(0)

    with patch(
        "src.integrations.messaging.wazzup.httpx.AsyncClient",
        FakeClient,
    ):
        resolved = await WazzupProvider._upload_to_tmpfiles(
            content,
            "application/pdf",
        )

    assert resolved == "https://tmpfiles.org/download/123/file.pdf"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_template_success(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"messageId": "msg_tmpl"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_template(
        "123",
        "6201005a-9a6f-486f-bdd5-e6cb86c76ddb",
        {"customer_name": "Lilia"},
    )
    assert msg_id == "msg_tmpl"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["templateId"] == "6201005a-9a6f-486f-bdd5-e6cb86c76ddb"
    assert payload["templateValues"] == ["Lilia"]
    assert "template" not in payload
    assert "text" not in payload


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_template_supports_wazzup_template_code_in_text(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"messageId": "msg_tmpl"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_template(
        "123",
        "@template: 6201005a-9a6f-486f-bdd5-e6cb86c76ddb { [[Lilia]] }",
        {},
    )

    assert msg_id == "msg_tmpl"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["text"] == (
        "@template: 6201005a-9a6f-486f-bdd5-e6cb86c76ddb { [[Lilia]] }"
    )
    assert "templateId" not in payload
    assert "templateValues" not in payload


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_template_includes_optional_crm_message_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"messageId": "msg_tmpl"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_template(
        "123",
        "tmpl_1",
        {},
        crm_message_id="followup:conv-1:feedback",
    )

    assert msg_id == "msg_tmpl"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["crmMessageId"] == "followup:conv-1:feedback"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_template_strips_smoke_profile_suffix_from_chat_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"messageId": "msg_tmpl"}
    mock_request.return_value = mock_resp

    msg_id = await wazzup_provider.send_template(
        "+15550001111#smoke-tool-final-20260411T1552",
        "tmpl_1",
        {},
    )

    assert msg_id == "msg_tmpl"
    payload = mock_request.call_args.kwargs["json"]
    assert payload["chatId"] == "+15550001111"


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_send_typing_is_best_effort_noop_without_api_request(
    mock_request: AsyncMock,
    wazzup_provider: WazzupProvider,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level("INFO", logger="src.integrations.messaging.wazzup")

    result = await wazzup_provider.send_typing("79998881122")

    assert result is False
    mock_request.assert_not_awaited()
    assert "typing indicator is not supported" in caplog.text


@pytest.mark.asyncio
@patch(
    "src.integrations.messaging.wazzup.httpx.AsyncClient.request",
    new_callable=AsyncMock,
)
async def test_resolve_channel_phone_returns_normalized_plain_id(
    mock_request: AsyncMock, wazzup_provider: WazzupProvider
) -> None:
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = [
        {
            "channelId": "chan-1",
            "transport": "whatsapp",
            "plainId": "971551220665",
            "state": "active",
        }
    ]
    mock_request.return_value = mock_resp

    phone = await wazzup_provider.resolve_channel_phone("chan-1")

    assert phone == "+971551220665"
    _, kwargs = mock_request.call_args
    assert kwargs["method"] == "GET"
    assert kwargs["url"] == "/channels"
