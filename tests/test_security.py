import pytest

from src.core.config import Settings
from src.core.security import compute_signature


def test_compute_signature() -> None:
    payload = b"test-payload"
    secret = "test-secret"

    expected = "5b12467d7c448555779e70d76204105c67d27d1c991f3080c19732f9ac1988ef"

    result = compute_signature(payload, secret)
    assert result == expected


def test_wazzup_webhook_auth_defaults_to_disabled() -> None:
    configured = Settings(_env_file=None)

    assert configured.wazzup_webhook_auth_mode == "disabled"


def test_wazzup_webhook_auth_enforce_requires_non_empty_secret() -> None:
    with pytest.raises(
        ValueError,
        match="wazzup_webhook_secret must be set when webhook auth is enforced",
    ):
        Settings(
            _env_file=None,
            wazzup_webhook_auth_mode="enforce",
            wazzup_webhook_secret="   ",
        )
