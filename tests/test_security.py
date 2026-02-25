import pytest
from fastapi import HTTPException, status
from src.core.security import compute_signature, verify_wazzup_webhook


@pytest.mark.asyncio
async def test_verify_wazzup_webhook_success() -> None:
    from unittest.mock import patch
    
    with patch("src.core.config.settings") as mock_settings:
        mock_settings.wazzup_webhook_secret = "secret-123"
        
        # Valid secret provided
        result = await verify_wazzup_webhook(x_webhook_secret="secret-123")
        assert result is None


@pytest.mark.asyncio
async def test_verify_wazzup_webhook_invalid() -> None:
    from unittest.mock import patch
    
    with patch("src.core.config.settings") as mock_settings:
        mock_settings.wazzup_webhook_secret = "secret-123"
        
        # Invalid secret provided
        with pytest.raises(HTTPException) as exc_info:
            await verify_wazzup_webhook(x_webhook_secret="wrong-secret")
            
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "Invalid webhook secret"


@pytest.mark.asyncio
async def test_verify_wazzup_webhook_no_secret() -> None:
    from unittest.mock import patch
    
    with patch("src.core.config.settings") as mock_settings:
        mock_settings.wazzup_webhook_secret = ""  # Empty secret in dev
        
        # Any secret should pass, skipping verification
        result = await verify_wazzup_webhook(x_webhook_secret="anything")
        assert result is None


def test_compute_signature() -> None:
    payload = b"test-payload"
    secret = "test-secret"
    
    expected = "5b12467d7c448555779e70d76204105c67d27d1c991f3080c19732f9ac1988ef"
    
    result = compute_signature(payload, secret)
    assert result == expected
