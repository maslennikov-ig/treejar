import logging
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.core.config import (
    DEFAULT_VOICE_TRANSCRIPTION_MODEL,
    Settings,
    get_system_config,
)
from src.llm.model_capabilities import (
    ModelCapabilities,
    is_known_model_id,
    resolve_model_capabilities,
    validate_openrouter_model_id,
)
from src.models.system_config import SystemConfig


@pytest.mark.asyncio
async def test_get_system_config() -> None:
    # Setup mock db
    mock_db = AsyncMock()
    mock_result = MagicMock()

    # Test 1: Config exists
    mock_config = SystemConfig(key="test_key", value="test_value")
    mock_result.scalar_one_or_none.return_value = mock_config
    mock_db.execute.return_value = mock_result

    val = await get_system_config(mock_db, "test_key", "default_val")
    assert val == "test_value"

    # Test 2: Config does not exist
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    val_missing = await get_system_config(mock_db, "missing_key", "default_val")
    assert val_missing == "default_val"


def test_model_capabilities_module_stays_dependency_light() -> None:
    code = (
        "import sys; "
        "import src.llm.model_capabilities; "
        "heavy = [m for m in ('pydantic_ai', 'openai', 'torch') if m in sys.modules]; "
        "assert not heavy, heavy"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


def test_resolve_model_capabilities_supports_exact_variants_and_anthropic_prefix() -> (
    None
):
    assert resolve_model_capabilities(
        "deepseek/deepseek-v4-flash"
    ) == ModelCapabilities(reasoning_disabled=True)
    assert resolve_model_capabilities(
        "deepseek/deepseek-v4-flash:free"
    ) == ModelCapabilities(reasoning_disabled=True)
    assert resolve_model_capabilities(
        "openai/gpt-6.1-sol-20260901"
    ) == ModelCapabilities(core_chat_only_reasoning_effort="medium")
    assert resolve_model_capabilities(
        "openai/gpt-6-luna:thinking"
    ) == ModelCapabilities(
        core_reasoning_effort="medium",
        bounded_non_core_helper=True,
    )
    assert resolve_model_capabilities("z-ai/glm-5.3-flash") == ModelCapabilities(
        core_reasoning_effort="low"
    )
    assert resolve_model_capabilities("openai/gpt-6.1-terra") == ModelCapabilities(
        bounded_non_core_helper=True
    )
    assert resolve_model_capabilities(
        "anthropic/claude-sonnet-4.6"
    ) == ModelCapabilities(supports_prompt_cache_control=True)
    assert resolve_model_capabilities("z-ai/glm-5.2") == ModelCapabilities()


@pytest.mark.parametrize(
    ("model_name", "expected"),
    [
        ("anthropic/claude-sonnet-5.5", True),
        ("anthropic/claude-haiku-5.5", True),
        ("anthropic/claude-sonnet-5.5-20260901", True),
        ("deepseek/deepseek-v4-flash:free", True),
        ("z-ai/glm-5.3-flash", True),
        ("z-ai/glm-5.2", True),
        ("openai/gpt-6-luna", True),
        ("openai/gpt-6.1-sol", True),
        ("openai/gpt-6.1-terra", True),
        ("openai/gpt-4o-mini-transcribe", True),
        ("anthropic/claude-unknown", False),
        ("custom/future-model", False),
        ("", False),
    ],
)
def test_is_known_model_id(model_name: str, expected: bool) -> None:
    assert is_known_model_id(model_name) is expected


def test_validate_openrouter_model_id_normalizes_and_rejects_invalid() -> None:
    assert validate_openrouter_model_id("  openai/gpt-6-luna  ") == "openai/gpt-6-luna"
    assert validate_openrouter_model_id("   ", allow_empty=True) == ""

    for bad in ("", "   ", "gpt-6-luna", "openai/", "/gpt-6", "openai//gpt-6", "a/b c"):
        with pytest.raises(ValueError):
            validate_openrouter_model_id(bad)


def test_settings_validates_openrouter_models_and_warns_on_unknown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="src.core.config"):
        cfg = Settings(
            _env_file=None,
            openrouter_model_main="  custom/future-chat  ",
            openrouter_model_fast="openai/gpt-6-luna",
            media_description_model="   ",
            voice_transcription_model="mistralai/voxtral-small-24b-2507",
        )

    assert cfg.openrouter_model_main == "custom/future-chat"
    assert cfg.media_description_model == ""
    assert cfg.voice_transcription_model == DEFAULT_VOICE_TRANSCRIPTION_MODEL
    assert "Unrecognized OpenRouter model ID for openrouter_model_main" in caplog.text
    assert "Unrecognized OpenRouter model ID for voice_transcription_model" not in (
        caplog.text
    )

    for field in (
        "openrouter_model_main",
        "openrouter_model_fast",
        "media_description_model",
        "voice_transcription_model",
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **{field: "missing-slash"})
