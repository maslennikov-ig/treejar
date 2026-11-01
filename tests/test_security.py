import pytest
from pydantic import SecretStr

from src.core.config import Settings


def test_wazzup_webhook_auth_defaults_to_disabled() -> None:
    configured = Settings(_env_file=None)

    assert configured.wazzup_webhook_auth_mode == "disabled"


@pytest.mark.parametrize("mode", ["observe", "enforce"])
@pytest.mark.parametrize(
    "secret",
    ["", "   ", "x" * 31],
    ids=["empty", "blank", "weak"],
)
def test_wazzup_webhook_rollout_auth_requires_strong_secret(
    mode: str,
    secret: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="wazzup_webhook_secret must be at least 32 UTF-8 bytes",
    ):
        Settings(
            _env_file=None,
            wazzup_webhook_auth_mode=mode,
            wazzup_webhook_secret=secret,
        )


def test_wazzup_webhook_secret_is_masked_in_settings_output() -> None:
    raw_secret = "strong-webhook-secret-value-32-bytes"

    configured = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="observe",
        wazzup_webhook_secret=raw_secret,
    )

    assert isinstance(configured.wazzup_webhook_secret, SecretStr)
    assert configured.wazzup_webhook_secret.get_secret_value() == raw_secret
    assert raw_secret not in repr(configured)
    assert raw_secret not in configured.model_dump_json()


def test_wazzup_webhook_secret_minimum_uses_utf8_bytes() -> None:
    raw_secret = "é" * 16

    configured = Settings(
        _env_file=None,
        wazzup_webhook_auth_mode="observe",
        wazzup_webhook_secret=raw_secret,
    )

    assert isinstance(configured.wazzup_webhook_secret, SecretStr)
    assert configured.wazzup_webhook_secret.get_secret_value() == raw_secret
